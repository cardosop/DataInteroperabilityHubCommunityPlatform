"""
Phase 250.5.B (closes Gap 14) — canonical SSRF validator.

This module ships ``SSRFGuard`` — a class facade over the existing
:mod:`hub.apps.webhooks.ssrf_guard` IP/scheme/network checks that
adds:

1. An **optional ``allowlist``** parameter — exact-match hostname
   bypass for tenant-configured trusted partner endpoints (e.g. a
   corporate-VPC RFC1918 host that's explicitly intended to be
   reachable). Allowlist short-circuits the blocked-network check
   ONLY — disallowed schemes (``file:``, ``gopher:``, ``ftp:``)
   stay rejected even for allowlisted hosts.

2. A **dnspython-based worker-time re-resolution path** (
   :meth:`SSRFGuard.revalidate_resolved_ip`) — the registration-
   time validate may pass, but minutes later the DNS record could
   be flipped to point at internal space (DNS rebinding); the
   worker MUST re-check before fetching. Uses ``dns.resolver``
   (BSD-licensed; license-gate verified per Phase 250.5.B.6).

3. A unified :class:`SSRFViolationError` exception that downstream
   callers (model ``clean()``, view validators, worker fetchers)
   can catch uniformly. Re-exported from :mod:`hub.apps.webhooks
   .ssrf_guard` so existing imports keep working.

Design note — why not extend the existing
``webhooks.ssrf_guard.validate_webhook_url`` function?
The existing function has a fixed contract (raise
``ValidationError`` for serializer compat) that ASSET / model
callers don't want — they want the ``SSRFViolationError`` shape
so they can re-raise as Django's ``ValidationError`` or as an
HTTP-layer ``ApiError``. The class facade lets us add the
allowlist + dnspython without breaking the webhook caller's
existing behaviour.
"""

from __future__ import annotations

import ipaddress
from collections.abc import Iterable
from urllib.parse import urlparse

# Re-export the existing exception so callers have a single import
# point.
from hub.apps.webhooks.ssrf_guard import (  # noqa: F401
    _ALLOWED_SCHEMES,
    _BLOCKED_NETWORKS,
    SSRFViolationError,
    _is_private_ip,
    _resolve_and_check,
)

__all__ = [
    "SSRFGuard",
    "SSRFViolationError",
]


# Phase 250.5.B.3 — dnspython-based re-resolution timeout.
# Mirrors the stdlib path's 5s budget so the worker-time guard
# doesn't add a different latency profile. Configurable per-
# call via the ``timeout`` kwarg on
# :meth:`SSRFGuard.revalidate_resolved_ip`.
_DNS_RESOLVE_TIMEOUT_SECONDS: float = 5.0


def _normalise_allowlist(
    allowlist: Iterable[str] | None,
) -> set[str]:
    """Lowercase + strip every allowlist entry once so per-call
    matching doesn't pay the normalization cost."""
    if not allowlist:
        return set()
    return {entry.strip().lower() for entry in allowlist if entry}


class SSRFGuard:
    """Phase 250.5.B canonical SSRF validator.

    Two methods:

    * :meth:`validate` — save-/registration-time URL validation.
      Reuses the existing webhook SSRF logic for the IP-literal
      and stdlib-DNS paths; layers allowlist support on top.

    * :meth:`revalidate_resolved_ip` — worker-time re-resolution
      using ``dnspython`` for explicit nameserver / timeout
      control. Use this immediately before a network fetch so a
      DNS-rebinding attack between registration and fetch is
      caught.
    """

    @classmethod
    def validate(
        cls,
        url: str,
        allowlist: Iterable[str] | None = None,
    ) -> None:
        """Validate ``url`` for SSRF safety. Raises
        :class:`SSRFViolationError` on any of:

        * Disallowed scheme (anything other than ``http`` /
          ``https``). NOT short-circuited by the allowlist.
        * Bare IP literal in the blocked-network list AND not
          on the allowlist.
        * Hostname that resolves to a blocked-network IP AND not
          on the allowlist.

        Args:
            url: Target URL to validate.
            allowlist: Optional iterable of trusted hostnames /
                IP literals. Exact-match (case-insensitive) only
                — no suffix / wildcard semantics, to prevent the
                ``evil-example.com.attacker.com`` substring-
                confusion bypass. ``None`` (default) applies the
                strict blocked-network rules.
        """
        # 1. Parse the URL.
        try:
            parsed = urlparse(url)
        except Exception as exc:
            raise SSRFViolationError(
                f"Invalid URL '{url}': {exc}",
            ) from exc

        # 2. Scheme is the first gate — NEVER short-circuited by
        # the allowlist. ``file://`` / ``gopher://`` / ``ftp://``
        # are categorically not safe regardless of host.
        if parsed.scheme not in _ALLOWED_SCHEMES:
            raise SSRFViolationError(
                f"URL scheme '{parsed.scheme}' is not allowed. "
                "Only 'http' and 'https' are permitted."
            )

        # 3. Hostname must be present.
        hostname = parsed.hostname
        if not hostname:
            raise SSRFViolationError(
                "URL must contain a valid hostname.",
            )

        # 4. Allowlist check — case-insensitive exact match
        # against the parsed hostname. Allowlist entries are
        # NOT regex / suffix patterns — explicit hosts only.
        normalised = _normalise_allowlist(allowlist)
        if hostname.lower() in normalised:
            return

        # 5. IP-literal fast path: reject blocked-network IPs
        # before any DNS lookup.
        try:
            addr = ipaddress.ip_address(hostname)
            if _is_private_ip(str(addr)):
                raise SSRFViolationError(
                    f"URL '{url}' targets a private/reserved IP "
                    f"address '{hostname}' which is not permitted."
                )
        except ValueError:
            # Not an IP literal — fall through to DNS resolution.
            pass

        # 6. DNS resolution + per-record blocked-network check
        # (uses the existing webhook helper for stdlib resolution).
        _resolve_and_check(hostname)

    @classmethod
    def revalidate_resolved_ip(
        cls,
        hostname: str,
        allowlist: Iterable[str] | None = None,
        timeout: float = _DNS_RESOLVE_TIMEOUT_SECONDS,
    ) -> None:
        """Phase 250.5.B.3 — worker-time DNS re-resolution using
        ``dnspython``. Re-resolves ``hostname`` (independent of
        the OS resolver cache) and rechecks every resolved A /
        AAAA record against the blocked-network list.

        This is the DNS-rebinding guard: between the registration-
        time :meth:`validate` and the worker-time fetch, the DNS
        record may have been flipped to point at internal space.
        The worker MUST re-check before fetching.

        Args:
            hostname: The hostname to re-resolve.
            allowlist: Optional iterable of trusted hostnames /
                IP literals. Same semantics as :meth:`validate`.
            timeout: DNS query timeout in seconds. Default
                ``_DNS_RESOLVE_TIMEOUT_SECONDS`` (5.0).
        """
        normalised = _normalise_allowlist(allowlist)
        if hostname.lower() in normalised:
            return

        # Lazy import — dnspython is only needed at worker time;
        # importing it at module load forces every Django app
        # boot to pay the import cost even when SSRFGuard isn't
        # used. The lazy import also makes the package optional
        # for non-worker-deploy footprints.
        try:
            import dns.exception
            import dns.resolver
        except ImportError as exc:  # pragma: no cover — boundary
            raise SSRFViolationError(
                "dnspython is required for worker-time DNS "
                "re-resolution but is not installed. Install "
                "via 'pip install dnspython>=2.4'."
            ) from exc

        addresses = []
        for rdtype in ("A", "AAAA"):
            try:
                answer = dns.resolver.resolve(
                    hostname,
                    rdtype,
                    lifetime=timeout,
                )
            except dns.resolver.NoAnswer:
                continue
            except dns.resolver.NXDOMAIN as exc:
                raise SSRFViolationError(
                    f"Hostname '{hostname}' does not resolve (NXDOMAIN): {exc}"
                ) from exc
            except dns.exception.Timeout as exc:
                raise SSRFViolationError(
                    f"DNS resolution of '{hostname}' timed out after {timeout}s: {exc}"
                ) from exc
            except Exception as exc:
                raise SSRFViolationError(f"DNS resolution of '{hostname}' failed: {exc}") from exc

            for rdata in answer:
                addresses.append(str(rdata))

        if not addresses:
            raise SSRFViolationError(f"Hostname '{hostname}' resolved to no addresses.")

        for ip_str in addresses:
            if _is_private_ip(ip_str):
                raise SSRFViolationError(
                    f"Hostname '{hostname}' resolves to "
                    f"private/reserved IP '{ip_str}' "
                    "(post-registration DNS rebinding rejected)."
                )
