"""
SSRF Guard for Webhook URLs

Validates webhook URLs to prevent Server-Side Request Forgery (SSRF) attacks:
- Rejecting non-http(s) schemes
- Resolving hostnames and blocking RFC-1918, loopback, link-local, multicast
- Providing re-validation at delivery time for DNS rebinding protection
- DNS resolution timeout (5s) to prevent slow-loris style attacks
"""

import concurrent.futures
import ipaddress
import re
import socket
from urllib.parse import urlparse

from rest_framework import serializers

# ---------------------------------------------------------------------------
# Blocked network ranges (module-level constant — computed once at import)
# ---------------------------------------------------------------------------

# Private, loopback, link-local and multicast networks to block
_BLOCKED_NETWORKS = [
    # Loopback IPv4
    ipaddress.ip_network("127.0.0.0/8"),
    # Loopback IPv6
    ipaddress.ip_network("::1/128"),
    # RFC-1918 private ranges
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    # Link-local (includes AWS IMDS 169.254.169.254)
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("fe80::/10"),
    # IPv4-mapped loopback (::ffff:127.x.x.x)
    ipaddress.ip_network("::ffff:127.0.0.0/104"),
    # Multicast
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("ff00::/8"),
    # Unspecified / broadcast
    ipaddress.ip_network("0.0.0.0/8"),
]

_ALLOWED_SCHEMES = frozenset({"http", "https"})


# ---------------------------------------------------------------------------
# Exception — defined before the functions that raise it
# ---------------------------------------------------------------------------


class SSRFViolationError(Exception):
    """Raised when a URL violates SSRF protection rules."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_private_ip(ip_str: str) -> bool:
    """Return True if the IP string falls in any blocked network.

    IPv4-mapped IPv6 addresses (::ffff:x.x.x.x) are unwrapped to their
    underlying IPv4 form before checking so that the same IPv4 blocked-network
    rules cover both representations.  Without unwrapping, ::ffff:10.0.0.1
    would bypass the 10.0.0.0/8 rule because an IPv6Address cannot be
    tested against an IPv4Network.
    """
    # Strip IPv6 scope ID (%<scope>) before parsing — e.g. "fe80::1%eth0"
    cleaned = re.sub(r"%[^%]*$", "", ip_str)
    try:
        addr = ipaddress.ip_address(cleaned)
    except ValueError:
        # Unparseable IP — treat as blocked to be safe
        return True
    # Unwrap IPv4-mapped IPv6 (::ffff:x.x.x.x) → IPv4Address so that
    # RFC-1918, loopback, and link-local IPv4 rules apply uniformly.
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    return any(addr in net for net in _BLOCKED_NETWORKS)


_DNS_TIMEOUT = 5.0  # seconds


def _resolve_and_check(hostname: str) -> None:
    """
    Resolve *hostname* to IP addresses and raise if any resolved address is
    in a blocked network.  Raises ``SSRFViolationError`` on violation.

    DNS resolution is bounded by a 5-second timeout to prevent slow-loris
    style attacks from stalling the calling thread indefinitely.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(socket.getaddrinfo, hostname, None)
        try:
            results = future.result(timeout=_DNS_TIMEOUT)
        except concurrent.futures.TimeoutError:
            raise SSRFViolationError(f"DNS resolution of '{hostname}' timed out")
        except socket.gaierror as exc:
            raise SSRFViolationError(f"Hostname '{hostname}' could not be resolved: {exc}") from exc

    for _family, _type, _proto, _canonname, sockaddr in results:
        ip = str(sockaddr[0])
        if _is_private_ip(ip):
            raise SSRFViolationError(
                f"Hostname '{hostname}' resolves to private/reserved IP '{ip}'"
            )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_webhook_url(url: str, *, raise_as_validation_error: bool = True) -> None:
    """
    Validate *url* for SSRF safety.

    Call with ``raise_as_validation_error=True`` (default) inside DRF
    serializer field validators.  Call with
    ``raise_as_validation_error=False`` in the
    delivery service for DNS-rebinding re-checks so the caller can wrap the
    error as an ``ODPSWebhookDeliveryError``.

    Args:
        url: The webhook target URL to validate.
        raise_as_validation_error: Select exception type on violation.

    Raises:
        serializers.ValidationError: when ``raise_as_validation_error=True``
        SSRFViolationError: when ``raise_as_validation_error=False``
    """

    def _fail(msg: str) -> None:
        if raise_as_validation_error:
            raise serializers.ValidationError(msg)
        raise SSRFViolationError(msg)

    # 1. Parse the URL
    try:
        parsed = urlparse(url)
    except ValueError as exc:
        _fail(f"Invalid webhook URL: {exc}")
        return  # unreachable but satisfies type checkers

    # 2. Scheme must be http or https
    if parsed.scheme not in _ALLOWED_SCHEMES:
        _fail(
            f"Webhook URL scheme '{parsed.scheme}' is not allowed. "
            "Only 'http' and 'https' are permitted."
        )
        return

    # 3. Hostname must be present
    hostname = parsed.hostname
    if not hostname:
        _fail("Webhook URL must contain a valid hostname.")
        return

    # 4. Fast-path: reject bare IP literals that are private before DNS lookup
    try:
        addr = ipaddress.ip_address(hostname)
        if _is_private_ip(str(addr)):
            _fail(
                f"Webhook URL '{url}' targets a private/reserved IP address "
                f"'{hostname}' which is not permitted."
            )
            return
    except ValueError:
        # Not an IP literal — fall through to DNS resolution
        pass

    # 5. DNS resolution check (also provides DNS-rebinding protection when
    #    called at delivery time, not just at registration time)
    try:
        _resolve_and_check(hostname)
    except SSRFViolationError as exc:
        _fail(str(exc))


def is_safe_url(url: str) -> bool:
    """
    Boolean convenience wrapper for SSRF URL validation.

    Returns True if *url* passes all SSRF checks, False otherwise.
    Handles $ref edge cases:
    - Local references starting with '#' are always safe (no network call).
    - Empty/None URLs are considered unsafe.

    This is the single canonical function that ref_resolver.py and any other
    module should call instead of maintaining their own blocked-network lists.
    """
    if not url:
        return False

    # Local JSON-pointer $ref — no network call needed
    if url.startswith("#"):
        return True

    try:
        validate_webhook_url(url, raise_as_validation_error=False)
        return True
    except SSRFViolationError:
        return False
