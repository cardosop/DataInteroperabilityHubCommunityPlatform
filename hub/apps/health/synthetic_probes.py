"""
280.B.2.4 — Synthetic Probers for Critical Journeys.

Runs black-box probes against the API, records pass/fail/latency to Prometheus
via the OpenTelemetry metrics pipeline, and exposes a summary for alerting.

Probes covered:
  1. login          — POST /api/v1/auth/login/  (JWT auth round-trip)
  2. asset_list     — GET /api/v1/assets/        (authenticated list)
  3. search         — GET /api/v1/search/?q=test (unified search)
  4. health         — GET /health                (Django health endpoint)

Each probe:
  - Times the full HTTP round-trip
  - Records a counter for success/failure
  - Records a gauge for the latest latency in ms
  - Returns a ProbeResult for aggregation

Alerting contract (Prometheus):
  synthetic_probe_failures_total{probe="<name>"} — counter of failures
  synthetic_probe_success_total{probe="<name>"}  — counter of successes
  synthetic_probe_latency_ms{probe="<name>"}      — gauge, latest latency

Alert fires when:
  rate(synthetic_probe_failures_total[5m]) /
    rate(synthetic_probe_success_total[5m] + synthetic_probe_failures_total[5m])
    > 0.01   (1% failure rate) for 5 minutes.
"""
from __future__ import annotations
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Dict

import requests
import structlog

logger = structlog.get_logger(__name__)

# ── Prometheus metrics via OpenTelemetry bridge ──────────────────────────
# These are the metrics that the synthetic-probes.yml alert rules query.

try:
    from hub.apps.observability.otel_metrics import Counter, Gauge
    _METRICS_AVAILABLE = True
except ImportError:
    _METRICS_AVAILABLE = False
    Counter = None  # type: ignore[assignment]
    Gauge = None    # type: ignore[assignment]

_probe_failures: dict = {}
_probe_successes: dict = {}
_probe_latency_gauge: dict = {}

if _METRICS_AVAILABLE:
    for probe_name in ("login", "asset_list", "search", "health"):
        try:
            _probe_failures[probe_name] = Counter(
                "synthetic_probe_failures_total",
                "Total synthetic probe failures",
                ["probe"],
            )
            _probe_successes[probe_name] = Counter(
                "synthetic_probe_success_total",
                "Total synthetic probe successes",
                ["probe"],
            )
            _probe_latency_gauge[probe_name] = Gauge(
                "synthetic_probe_latency_ms",
                "Latest synthetic probe latency in milliseconds",
                ["probe"],
            )
        except Exception:
            _METRICS_AVAILABLE = False
            break


def _record_probe_metrics(probe_name: str, success: bool, latency_ms: float) -> None:
    """Emit Prometheus metrics for a probe result."""
    if not _METRICS_AVAILABLE:
        return
    try:
        labels = {"probe": probe_name}
        if success:
            _probe_successes.get(probe_name, lambda: None)  # no-op if missing
            if probe_name in _probe_successes:
                _probe_successes[probe_name].labels(**labels).inc()
        else:
            if probe_name in _probe_failures:
                _probe_failures[probe_name].labels(**labels).inc()
        if probe_name in _probe_latency_gauge:
            _probe_latency_gauge[probe_name].labels(**labels).set(latency_ms)
    except Exception:
        pass  # metrics failure must never block probe execution


@dataclass
class ProbeResult:
    """Result of a single synthetic probe execution."""

    probe_name: str
    success: bool
    latency_ms: float
    status_code: Optional[int] = None
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    request_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    # Response body captured for auth token extraction (avoids double-request)
    response_body: Optional[dict] = None


# ── Probe runner ──────────────────────────────────────────────────────────

class SyntheticProbe:
    """A single black-box probe that hits an API endpoint and records metrics."""

    def __init__(
        self,
        name: str,
        method: str,
        url_path: str,
        base_url: str,
        expected_status: int = 200,
        request_body: Optional[dict] = None,
        auth_token: Optional[str] = None,
        extra_headers: Optional[dict] = None,
        timeout: float = 10.0,
        retries: int = 1,
    ):
        self.name = name
        self.method = method.upper()
        self.url_path = url_path
        self.base_url = base_url.rstrip("/")
        self.expected_status = expected_status
        self.request_body = request_body
        self.auth_token = auth_token
        self.extra_headers = extra_headers or {}
        self.timeout = timeout
        self.retries = retries

    def run(self) -> ProbeResult:
        """Execute the probe. Retries once on connection errors."""
        last_error = None
        last_status = None
        elapsed_ms = 0.0
        response_body = None

        for attempt in range(self.retries + 1):
            start = time.monotonic()
            try:
                headers = {
                    "Accept": "application/json",
                    "User-Agent": "Meshant-SyntheticProber/1.0",
                    **self.extra_headers,
                }
                if self.auth_token:
                    headers["Authorization"] = f"Bearer {self.auth_token}"

                url = f"{self.base_url}{self.url_path}"

                if self.method == "GET":
                    resp = requests.get(
                        url, headers=headers, timeout=self.timeout,
                    )
                elif self.method == "POST":
                    resp = requests.post(
                        url, json=self.request_body, headers=headers,
                        timeout=self.timeout,
                    )
                elif self.method == "HEAD":
                    resp = requests.head(
                        url, headers=headers, timeout=self.timeout,
                    )
                else:
                    return self._finalize(ProbeResult(
                        probe_name=self.name,
                        success=False,
                        latency_ms=(time.monotonic() - start) * 1000,
                        error_message=f"Unsupported method: {self.method}",
                    ))

                elapsed_ms = (time.monotonic() - start) * 1000
                last_status = resp.status_code

                # Capture JSON body on success for token extraction
                try:
                    if resp.status_code == 200 and resp.headers.get(
                        "Content-Type", ""
                    ).startswith("application/json"):
                        response_body = resp.json()
                except Exception:
                    response_body = None

                if resp.status_code == self.expected_status:
                    return self._finalize(ProbeResult(
                        probe_name=self.name,
                        success=True,
                        latency_ms=elapsed_ms,
                        status_code=resp.status_code,
                        response_body=response_body,
                    ))
                else:
                    last_error = (
                        f"Expected {self.expected_status}, "
                        f"got {resp.status_code}: {resp.text[:200]}"
                    )
                    # Only retry on 5xx; 4xx is a probe configuration error
                    if resp.status_code < 500:
                        break

            except requests.exceptions.Timeout:
                elapsed_ms = (time.monotonic() - start) * 1000
                last_error = f"Timeout after {self.timeout}s"
            except requests.exceptions.ConnectionError as e:
                elapsed_ms = (time.monotonic() - start) * 1000
                last_error = f"Connection error: {e}"
            except Exception as e:
                elapsed_ms = (time.monotonic() - start) * 1000
                last_error = f"Unexpected error: {e}"
                break

        return self._finalize(ProbeResult(
            probe_name=self.name,
            success=False,
            latency_ms=elapsed_ms,
            status_code=last_status,
            error_message=last_error,
        ))

    def _finalize(self, result: ProbeResult) -> ProbeResult:
        """Record metrics and return the result."""
        _record_probe_metrics(result.probe_name, result.success, result.latency_ms)
        return result


# ── Probe registry ────────────────────────────────────────────────────────

# The 4 critical probes required by 280.B.2.4
CRITICAL_PROBE_NAMES = ["login", "asset_list", "search", "health"]


def create_probes(
    base_url: str,
    auth_email: Optional[str] = None,
    auth_password: Optional[str] = None,
) -> Dict[str, SyntheticProbe]:
    """Create the set of 4 critical synthetic probes.

    If auth_email/auth_password are provided, the login probe uses them
    and the authenticated probes (asset_list, search) reuse the obtained JWT.
    """
    probes = {}

    # 1. Health probe (no auth required)
    probes["health"] = SyntheticProbe(
        name="health",
        method="GET",
        url_path="/health",
        base_url=base_url,
        expected_status=200,
        timeout=5.0,
    )

    # 2. Login probe
    login_body = None
    if auth_email and auth_password:
        login_body = {"email": auth_email, "password": auth_password}

    probes["login"] = SyntheticProbe(
        name="login",
        method="POST",
        url_path="/api/v1/auth/login/",
        base_url=base_url,
        expected_status=200,
        request_body=login_body,
        timeout=10.0,
    )

    # 3 & 4 — Authenticated probes. These will need a token obtained
    # at runtime by the runner.
    probes["asset_list"] = SyntheticProbe(
        name="asset_list",
        method="GET",
        url_path="/api/v1/assets/?page_size=1",
        base_url=base_url,
        expected_status=200,
        timeout=10.0,
    )

    probes["search"] = SyntheticProbe(
        name="search",
        method="GET",
        url_path="/api/v1/search/?q=test&page_size=1",
        base_url=base_url,
        expected_status=200,
        timeout=10.0,
    )

    return probes


# ── Probe runner (orchestrates all probes in a cycle) ─────────────────────

@dataclass
class ProbeRunSummary:
    """Aggregated results from one cycle of all probes."""

    timestamp: datetime
    total_probes: int
    passed: int
    failed: int
    results: List[ProbeResult]

    @property
    def failure_rate(self) -> float:
        if self.total_probes == 0:
            return 0.0
        return self.failed / self.total_probes


def run_all_probes(
    probes: Dict[str, SyntheticProbe],
    auth_token: Optional[str] = None,
) -> ProbeRunSummary:
    """Run all probes and return aggregated results.

    Authenticated probes get the auth_token injected before execution.
    """
    results = []
    for name, probe in probes.items():
        # Inject auth token for authenticated probes
        if name in ("asset_list", "search") and auth_token:
            probe.auth_token = auth_token

        result = probe.run()
        results.append(result)

        status = "PASS" if result.success else "FAIL"
        log = logger.info if result.success else logger.warning
        log(
            "synthetic_probe_result",
            probe=name,
            status=status,
            latency_ms=result.latency_ms,
            status_code=result.status_code,
            error=result.error_message,
        )

    passed = sum(1 for r in results if r.success)
    failed = len(results) - passed

    return ProbeRunSummary(
        timestamp=datetime.now(timezone.utc),
        total_probes=len(results),
        passed=passed,
        failed=failed,
        results=results,
    )
