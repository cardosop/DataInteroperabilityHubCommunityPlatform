"""
W6.4 (oss-release-remediation) — RFC-8594 deprecation interceptor (SDK).

The backend emits the standard deprecation headers on sunsetting API
surfaces (``Deprecation: true``, ``Sunset: <RFC-7231 date>``,
``Link: <doc-url>; rel="deprecation"`` — the same contract the frontend
interceptor surfaces as a toast). The SDK surfaces them the Python way:
a ``DeprecationWarning`` fired ONCE per (endpoint-family, sunset-date)
pair, on every response — errors included.

The dedup key is ``(endpoint-family, sunset-date)``: a change in sunset
date re-warns; repeat hits stay quiet.  SDK consumers can filter the
warning with the standard ``warnings`` machinery (``-W`` /
``warnings.simplefilter``), which is why the interceptor uses
``DeprecationWarning`` instead of printing.
"""

from __future__ import annotations

import re
import warnings
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

# Dedup registry: (endpoint-family, sunset) pairs already warned about.
_SEEN: set[tuple[str, str]] = set()

_LINK_RE = re.compile(r"<(?P<url>[^>]+)>\s*;\s*rel=\"?deprecation\"?")


def _header(headers, name, default=""):
    """Case-insensitive header read — httpx lowercases header keys
    (requests preserves the server's casing); both must work."""
    for key, value in headers.items():
        if str(key).lower() == name.lower():
            return value
    return default


def _endpoint_family(url: str) -> str:
    """Group the URL into its endpoint family (first two path segments)."""
    path = url.split("?")[0]
    if "/api/v1/" in path:
        path = path.split("/api/v1/", 1)[1]
    segments = [p.strip("/") for p in path.split("/") if p]
    return "/".join(segments[:2]) or path


def _sunset_urgency(sunset: str | None) -> str:
    """Human urgency suffix: days remaining, or SUNSET PASSED."""
    if not sunset:
        return ""
    try:
        when = parsedate_to_datetime(sunset)
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        days = (when - datetime.now(timezone.utc)).days
    except (TypeError, ValueError):
        return f" (Sunset: {sunset})"
    if days < 0:
        return f" (Sunset: {sunset} — SUNSET PASSED)"
    return f" (Sunset: {sunset} — {days} days remaining)"


def check_deprecation_headers(url: str, headers: dict[str, Any]) -> bool:
    """Inspect an API response for RFC-8594 deprecation headers.

    Emits one ``DeprecationWarning`` per new (endpoint-family, sunset)
    pair.  Returns True when a NEW warning was emitted (dedup
    first-warning detection for tests).
    """
    if str(_header(headers, "Deprecation")).strip().lower() not in ("true", "1"):
        return False

    sunset = _header(headers, "Sunset", None)
    family = _endpoint_family(url)
    key = (family, sunset or "")
    if key in _SEEN:
        return False
    _SEEN.add(key)

    message = (
        f"API surface '{family}' is deprecated{_sunset_urgency(sunset)}."
    )
    link = _LINK_RE.search(str(_header(headers, "Link")))
    if link:
        message += f" See {link.group('url')}."
    warnings.warn(message, DeprecationWarning, stacklevel=2)
    return True
