"""
Smoke test — Phase 260.A acceptance criterion.

Closes the last open acceptance bullet for ``260.A``:

    "Prometheus metric ``cross_tenant_denied_total`` is non-zero in staging
    integration test."

Companion in-process test
-------------------------
The same contract is asserted in
``hub/apps/observability/tests/test_cross_tenant_metric_exposition.py``
against a Django in-process stack (deterministic, single-process). This
file asserts it against deployed staging.

Execution path (real HTTP — no mocks)
-------------------------------------
1. Authenticate as the smoke admin (``conftest.py`` fixtures).
2. Resolve the smoke admin's ``tenant_id`` via ``GET /api/v1/auth/me/``.
3. Snapshot ``cross_tenant_denied_total{endpoint="semantic.ingest_rdf"}``
   from ``GET /metrics/``, polling ``METRIC_POLL_ITERATIONS`` times with
   fresh TCP connections (``Connection: close``) so the polls fan out
   across gunicorn workers.
4. Drive ``METRIC_DRIVE_ITERATIONS`` cross-tenant attempts at
   ``POST /api/v1/semantic/rdf/ingest`` with a body ``tenant_id`` set to
   a fresh random UUID per attempt. Each drive uses its own
   ``requests.Session`` with ``Connection: close`` so attempts fan out
   across workers — without this the keep-alive sticks every probe to a
   single worker and the metric remains hidden from polls that land
   elsewhere.
5. Assert every attempt returns ``HTTP 403`` with body
   ``{"code": "CROSS_TENANT_FORBIDDEN", ...}``.
6. Re-poll ``GET /metrics/`` and assert the counter strictly increased
   AND is ``> 0``.

Why fan-out matters
-------------------
The deployed API runs gunicorn with N workers (3 in staging, 9 in
production); the ``prometheus_client`` Counter is per-process. Without
explicit fan-out, a keep-alive Session sticks every probe to the worker
that handled the first request. The poller then rolls the dice on which
worker answers — if it lands on a worker that saw zero denials, the test
fails despite the increment having happened. Forcing
``Connection: close`` on both halves of the test resolves this without
introducing a Prometheus multiprocess collector dependency.

Required env vars (provided by ``conftest.py``)
-----------------------------------------------
``SMOKE_ADMIN_EMAIL`` / ``SMOKE_ADMIN_PASSWORD`` — authenticated session.

Optional env vars
-----------------
``SMOKE_PHASE260_DRIVE_ITERATIONS``
    Number of cross-tenant attempts (default: 30 — 10× the staging
    worker count to make worker fan-out near-certain).
``SMOKE_PHASE260_POLL_ITERATIONS``
    Number of ``/metrics/`` polls per snapshot (default: 12 — 4× the
    staging worker count to ensure we see at least one worker that
    handled a denial).
``SMOKE_PHASE260_DRIVE_JITTER_MS``
    Jitter between drives (default: 25). Helps gunicorn distribute new
    TCP connections across workers via the OS accept queue.
"""

from __future__ import annotations

import os
import random
import re
import time
import uuid

import pytest
import requests

METRICS_PATH = "/metrics/"
SEMANTIC_INGEST_PATH = "/api/v1/semantic/rdf/ingest"
AUTH_ME_PATH = "/api/v1/auth/me/"

METRIC_DRIVE_ITERATIONS = int(os.getenv("SMOKE_PHASE260_DRIVE_ITERATIONS", "30"))
METRIC_POLL_ITERATIONS = int(os.getenv("SMOKE_PHASE260_POLL_ITERATIONS", "12"))
DRIVE_JITTER_MS = int(os.getenv("SMOKE_PHASE260_DRIVE_JITTER_MS", "25"))

COUNTER_NAME = "cross_tenant_denied_total"

# Match a counter line for our pinned endpoint label, label-order-tolerant.
# We build the patterns as plain raw strings (no f-string interpolation)
# so the `{` / `}` characters don't fight Python f-string escaping —
# splitting `{{` / `}}` across an f-string boundary silently produces a
# different regex than intended.
_COUNTER_LINE_RE = re.compile(
    r"^" + re.escape(COUNTER_NAME) + r"\{[^}]*"
    r'endpoint="semantic\.ingest_rdf"'
    r"[^}]*\}\s+"
    r"(?P<value>[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)\s*$",
    re.MULTILINE,
)
# Match the family-wide HELP/TYPE lines so we can tell "metric exists but
# value=0 on this worker" from "metric not registered at all".
_FAMILY_HEADER_RE = re.compile(
    r"^# (?:HELP|TYPE) " + re.escape(COUNTER_NAME) + r"\b",
    re.MULTILINE,
)
# Match ANY label combination of the counter — used as a debug signal so
# the test failure message can say "the family exists, but no row has
# our endpoint label".
_ANY_COUNTER_LINE_RE = re.compile(
    r"^" + re.escape(COUNTER_NAME) + r"\{[^}]*\}\s+"
    r"(?P<value>[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)\s*$",
    re.MULTILINE,
)


def _scrape_metrics(base_url: str, timeout: int) -> str | None:
    """Single ``/metrics/`` scrape with a fresh TCP connection.

    Returns the response body text on 200, ``None`` on transient 5xx /
    network failure (caller decides whether to retry).
    """
    try:
        resp = requests.get(
            f"{base_url}{METRICS_PATH}",
            timeout=timeout,
            headers={"Connection": "close"},
        )
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None
    return resp.text


def _max_counter_value(body: str) -> float:
    max_value = 0.0
    for match in _COUNTER_LINE_RE.finditer(body):
        try:
            value = float(match.group("value"))
        except ValueError:
            continue
        max_value = max(max_value, value)
    return max_value


def _read_counter_max(base_url: str, timeout: int) -> tuple[float, dict]:
    """Poll ``/metrics/`` ``METRIC_POLL_ITERATIONS`` times. Return
    ``(max_value, diagnostics)`` where ``diagnostics`` carries info we
    surface in failure messages so engineers can triage fast without
    rerunning the test.
    """
    observed: list[float] = []
    family_present = False
    any_label_max = 0.0
    successful_polls = 0

    for _ in range(max(METRIC_POLL_ITERATIONS, 1)):
        body = _scrape_metrics(base_url, timeout)
        if body is None:
            continue
        successful_polls += 1
        if _FAMILY_HEADER_RE.search(body):
            family_present = True
        for match in _ANY_COUNTER_LINE_RE.finditer(body):
            try:
                value = float(match.group("value"))
            except ValueError:
                continue
            any_label_max = max(any_label_max, value)
        observed.append(_max_counter_value(body))

    diagnostics = {
        "successful_polls": successful_polls,
        "polls_attempted": METRIC_POLL_ITERATIONS,
        "family_present_in_at_least_one_poll": family_present,
        "max_value_any_label_combo": any_label_max,
        "per_poll_endpoint_max_values": observed,
    }
    return (max(observed) if observed else 0.0), diagnostics


def _resolve_tenant_id(
    base_url: str,
    session: requests.Session,
    timeout: int,
) -> str | None:
    resp = session.get(f"{base_url}{AUTH_ME_PATH}", timeout=timeout)
    if resp.status_code != 200:
        return None
    body = resp.json()
    return (
        body.get("tenant")
        or body.get("tenant_id")
        or (body.get("tenant_membership") or {}).get("tenant_id")
    )


def _drive_one_probe(
    base_url: str,
    auth_token: str,
    timeout: int,
    foreign_tenant_id: str,
) -> requests.Response:
    """Send a single cross-tenant probe with a fresh TCP connection.

    A fresh ``requests.Session()`` per probe guarantees the TCP connection
    is not reused, which lets gunicorn distribute the request to a
    different worker than the previous probe.
    """
    with requests.Session() as session:
        session.headers.update(
            {
                "Authorization": f"Bearer {auth_token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Connection": "close",
            }
        )
        return session.post(
            f"{base_url}{SEMANTIC_INGEST_PATH}",
            json={
                "graph_data": "@prefix : <http://smoke/> . :a :b :c .",
                "format": "turtle",
                "tenant_id": foreign_tenant_id,
            },
            timeout=timeout,
        )


class TestPhase260CrossTenantDenialMetric:
    """260.A acceptance — staging metric must increment on cross-tenant abuse."""

    def test_cross_tenant_denial_increments_metric(
        self,
        base_url: str,
        auth_token: str,
        authenticated_session: requests.Session,
        timeout: int,
    ) -> None:
        own_tenant_id = _resolve_tenant_id(base_url, authenticated_session, timeout)
        if not own_tenant_id:
            pytest.skip(  # noqa: skip-in-body — runtime service dependency
                "Could not resolve smoke admin tenant via /auth/me/ — "
                "cannot construct a cross-tenant probe."
            )

        before, before_diag = _read_counter_max(base_url, timeout)

        status_codes: list[int] = []
        denial_codes: list[str] = []
        for i in range(max(METRIC_DRIVE_ITERATIONS, 1)):
            # Fresh random UUID per probe so every probe is a distinct
            # cross-tenant attempt (no caching artifact possible).
            foreign_tenant_id = str(uuid.uuid4())
            assert foreign_tenant_id != str(own_tenant_id)

            resp = _drive_one_probe(base_url, auth_token, timeout, foreign_tenant_id)
            status_codes.append(resp.status_code)

            if resp.status_code == 404:
                pytest.skip(  # noqa: skip-in-body — runtime service dependency
                    f"{SEMANTIC_INGEST_PATH} not exposed in this environment — "
                    "smoke needs the semantic.ingest_rdf cross-tenant gate live."
                )
            assert resp.status_code == 403, (
                f"Cross-tenant probe #{i} expected 403, got {resp.status_code}: {resp.text[:300]}"
            )
            payload = resp.json()
            denial_code = payload.get("code")
            denial_codes.append(str(denial_code))
            assert denial_code == "CROSS_TENANT_FORBIDDEN", (
                f"Cross-tenant probe #{i} missing CROSS_TENANT_FORBIDDEN: {payload}"
            )

            # Jitter between probes so consecutive new TCP connections
            # don't all hit the same worker via OS-level accept-queue
            # locality.
            if DRIVE_JITTER_MS > 0 and i + 1 < METRIC_DRIVE_ITERATIONS:
                sleep_seconds = (DRIVE_JITTER_MS + random.randint(0, DRIVE_JITTER_MS)) / 1000.0
                time.sleep(sleep_seconds)  # noqa: sleep-needed — polling loop

        after, after_diag = _read_counter_max(base_url, timeout)

        # Strict acceptance assertions.
        assert after > before, (
            f"cross_tenant_denied_total did not increase after "
            f"{METRIC_DRIVE_ITERATIONS} cross-tenant probes. "
            f"before={before} after={after}. "
            f"Status codes seen: {status_codes}. "
            f"Pre-poll diagnostics:  {before_diag}. "
            f"Post-poll diagnostics: {after_diag}. "
            "Possible causes: "
            "(a) the metric is registered but on a different "
            "    prometheus_client REGISTRY than /metrics/ exposes — "
            "    inspect hub/apps/observability/otel_metrics.py and "
            "    hub/apps/observability/cross_tenant_metrics.py; "
            "(b) the deployed API has more workers than fan-out can "
            "    cover — increase SMOKE_PHASE260_DRIVE_ITERATIONS or "
            "    SMOKE_PHASE260_POLL_ITERATIONS; "
            "(c) the cross-tenant gate is not wired on the "
            "    semantic.ingest_rdf endpoint — check the cross_tenant_denied "
            "    helper call site in hub/apps/semantic/views.py."
        )
        assert after > 0, (
            f"cross_tenant_denied_total is {after} after probes — "
            "the counter must be strictly positive (260.A acceptance). "
            f"Diagnostics: {after_diag}."
        )
