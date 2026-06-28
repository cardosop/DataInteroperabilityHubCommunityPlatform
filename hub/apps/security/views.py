"""
hub/apps/security/views.py

CSP (Content-Security-Policy) violation report endpoint.

Browsers POST a JSON payload to /api/csp-report/ whenever a CSP violation
occurs.  The endpoint is intentionally unauthenticated:
  - The browser sends reports before page scripts run.
  - Reports may arrive for the login page or when the user's session has
    already expired.
  - RFC 7034 / MDN guidance explicitly notes that report endpoints must be
    accessible without authentication.

Request content types accepted:
  - application/csp-report        (legacy, single-report object wrapped in
                                   {"csp-report": {...}})
  - application/json              (modern browsers, same wrapped format)
  - application/reports+json      (Reporting API v1, array of report objects)

Response: 204 No Content — browsers discard the response body entirely.

References:
  https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy/report-uri
  https://www.w3.org/TR/CSP3/#deprecated-serialize-violation
"""

import json
from urllib.parse import urlparse

import structlog
from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from hub.apps.observability.otel_metrics import _CounterWrapper

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# OpenTelemetry metric
# ---------------------------------------------------------------------------

# Lazy-initialised via _CounterWrapper so the OTel provider can be set up
# after Django settings are loaded (consistent with all other hub metrics).
_CSP_VIOLATIONS = _CounterWrapper(
    "hub_csp_violations_total",
    "Total number of Content-Security-Policy violations reported by browsers.",
    unit="1",
    # violated_directive: e.g. "script-src", "img-src", "connect-src"
    # document_uri_path:  path component of the page that triggered the
    #                     violation (full URI stripped to avoid label explosion)
    expected_labels=("violated_directive", "document_uri_path"),
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ACCEPTED_CONTENT_TYPES = frozenset(
    [
        "application/csp-report",
        "application/json",
        "application/reports+json",
    ]
)


def _extract_report(payload: dict | list) -> list[dict]:
    """
    Normalise both legacy and Reporting-API-v1 payloads to a flat list of
    report dicts containing the CSP fields we care about.
    """
    if isinstance(payload, list):
        # Reporting API v1: [{type, url, body: {...}}, ...]
        reports = []
        for item in payload:
            if isinstance(item, dict):
                body = item.get("body", item)
                reports.append(body if isinstance(body, dict) else item)
        return reports

    # Legacy single-report: {"csp-report": {...}} or unwrapped {...}
    return [payload.get("csp-report", payload)]


def _uri_path(uri: str) -> str:
    """Return the path component of a URI, falling back to 'unknown'."""
    try:
        path = urlparse(uri).path
        return path if path else "unknown"
    except (ValueError, AttributeError):
        return "unknown"


def _directive_label(raw: str) -> str:
    """
    Normalise a violated-directive value for use as a Prometheus label.

    The raw value can look like 'script-src sha256-abc123' (with inline hash)
    or 'script-src-elem'.  We take only the directive keyword so labels stay
    low-cardinality.
    """
    return raw.split()[0].strip().lower() if raw else "unknown"


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------


@csrf_exempt
@require_POST
def csp_report_view(request: HttpRequest) -> HttpResponse:
    """
    Accept, validate, log, and meter CSP violation reports from browsers.

    The view always returns 204 — browsers do not process the response body
    and a non-2xx status would cause some browsers to stop sending reports.
    """
    content_type = (request.content_type or "").split(";")[0].strip().lower()

    if content_type not in _ACCEPTED_CONTENT_TYPES:
        # Unknown content type — could be a probe or misconfigured client.
        # Return 204 silently rather than 415 to avoid leaking info.
        return HttpResponse(status=204)

    try:
        payload = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, ValueError):
        # Malformed JSON — drop silently; don't log (avoids log flooding from
        # broken browser extensions or network truncation).
        return HttpResponse(status=204)

    if not isinstance(payload, (dict, list)):
        return HttpResponse(status=204)

    reports = _extract_report(payload)

    # Resolve tenant_id from authenticated session (best-effort — most CSP
    # reports arrive unauthenticated or before session is established).
    tenant_id: str | None = None
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        raw_tid = getattr(user, "tenant_id", None)
        tenant_id = str(raw_tid) if raw_tid is not None else None

    for report in reports:
        if not isinstance(report, dict):
            continue

        # Prefer 'effectiveDirective' (CSP3) over 'violated-directive' (CSP2).
        violated_directive: str = report.get(
            "effectiveDirective",
            report.get("violated-directive", "unknown"),
        )
        document_uri: str = report.get("document-uri", "")
        blocked_uri: str = report.get("blocked-uri", "")
        source_file: str = report.get("source-file", "")
        line_number: int | None = report.get("line-number")
        column_number: int | None = report.get("column-number")
        status_code: int = report.get("status-code", 0)

        directive_label = _directive_label(violated_directive)
        document_path = _uri_path(document_uri)

        # Increment OTel counter — low-cardinality labels only.
        _CSP_VIOLATIONS.labels(
            violated_directive=directive_label,
            document_uri_path=document_path,
        ).inc()

        logger.warning(
            "csp_violation",
            violated_directive=violated_directive,
            document_uri=document_uri,
            blocked_uri=blocked_uri,
            source_file=source_file,
            line_number=line_number,
            column_number=column_number,
            status_code=status_code,
            tenant_id=tenant_id,
        )

    return HttpResponse(status=204)
