"""
Compliance scan RQ task — Phase 19.12.2

Runs the full PII-detection / risk-scoring / policy-evaluation pipeline
*in-process* using the ``compliance_engine`` package bundled into the worker
Docker image at build time (``/app/compliance_engine/``).

No HTTP round-trip is made to the compliance-service microservice; the same
logic executes directly inside the worker process.  This eliminates network
latency, removes the compliance-service as a single point of failure for async
scans, and makes the heavy worker self-contained.

Result layout in Redis
----------------------
On completion the task writes a JSON blob to::

    compliance:result:{job_id}   TTL = 3600 s

Shape on success::

    {"status": "COMPLETED", "job_id": "<uuid>", "result": {<report>}}

Shape on failure::

    {"status": "FAILED", "job_id": "<uuid>", "error": "<sanitised msg>"}

Both ``hub.apps.compliance.service_client`` and the compliance-service
``/scan-result/{job_id}`` endpoint understand this key/schema, so either
reader works regardless of whether the scan was run via HTTP or in-process.

Autodiscovery
-------------
RQ resolves tasks by importable dotted path.  Because the project root is
inserted into ``sys.path`` by ``services/worker/main.py``, this function is
reachable as::

    services.worker.tasks.compliance.compliance_scan_job

Enqueue example (from hub Django code)::

    from django_rq import get_queue
    queue = get_queue("job_default")
    rq_job = queue.enqueue(
        "services.worker.tasks.compliance.compliance_scan_job",
        args=(str(run.id), payload),
        result_ttl=3600,
        failure_ttl=86400,
    )
"""

from __future__ import annotations

import base64
import contextlib
import json
import logging
import os
import re
import time
from io import BytesIO
from typing import Any, cast

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Error sanitisation — mirrors compliance-service/main.py patterns (19.1.3).
# Compiled once at import time; defined before the task function so
# static-analysis tools and readers encounter definitions before first use.
# ---------------------------------------------------------------------------

_SANITIZE_CARD_RE = re.compile(r"\b\d{4}[\s\-]*\d{4}[\s\-]*\d{4}[\s\-]*\d{4}\b")
_SANITIZE_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_SANITIZE_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def _sanitise_error(msg: str) -> str:
    """Remove common PII patterns from exception strings before storing."""
    msg = _SANITIZE_CARD_RE.sub("[CARD]", msg)
    msg = _SANITIZE_SSN_RE.sub("[SSN]", msg)
    msg = _SANITIZE_EMAIL_RE.sub("[EMAIL]", msg)
    return msg


# ---------------------------------------------------------------------------
# Redis result key helpers
# ---------------------------------------------------------------------------

RESULT_KEY_PREFIX = "compliance:result:"
RESULT_TTL_SECONDS = 3600


def _result_key(job_id: str) -> str:
    return f"{RESULT_KEY_PREFIX}{job_id}"


def _get_redis_client() -> Any:
    """
    Return a synchronous redis-py client.

    Resolution order (first match wins):
      1. REDIS_QUEUE_URL  — async-scan Redis (compliance-service convention)
      2. RQ_REDIS_URL     — generic RQ worker override
      3. REDIS_URL        — Django-RQ default
      4. django_rq.get_connection("job_default") — reads settings.RQ_QUEUES

    The client does NOT decode responses; json.dumps str is encoded to bytes
    transparently by redis-py on SET.
    """
    import redis

    for env_var in ("REDIS_QUEUE_URL", "RQ_REDIS_URL", "REDIS_URL"):
        url = os.environ.get(env_var)
        if url:
            return redis.from_url(
                url,
                decode_responses=False,
                socket_connect_timeout=5,
            )

    # Fall back to Django-RQ connection pool — avoids duplicating config.
    try:
        from django_rq import get_connection

        return get_connection("job_default")
    except Exception:
        raise RuntimeError(
            "No Redis URL found. Set REDIS_QUEUE_URL, RQ_REDIS_URL, or "
            "REDIS_URL, or configure RQ_QUEUES in Django settings."
        )


def _write_result(
    redis_client: Any,
    job_id: str,
    payload: dict[str, Any],
) -> None:
    """Serialise *payload* to JSON and SET with TTL in Redis."""
    try:
        redis_client.set(
            _result_key(job_id),
            json.dumps(payload, default=str),
            ex=RESULT_TTL_SECONDS,
        )
    except Exception as exc:
        # Never let a result-write failure mask the original job outcome.
        logger.error(
            "compliance_scan_job result_write_failed job_id=%s error=%s",
            job_id,
            exc,
        )


# ---------------------------------------------------------------------------
# Main RQ task
# ---------------------------------------------------------------------------


def compliance_scan_job(
    job_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    RQ task: run the full compliance scan pipeline in-process.

    Imports ``compliance_engine`` from the package bundled into the worker
    image at ``/app/compliance_engine/`` (see services/worker/Dockerfile).
    No network call is made to the compliance-service microservice.

    Parameters
    ----------
    job_id:
        UUID string identifying this scan job.  Used as the Redis result
        key suffix and forwarded to the audit log.
    payload:
        Scan parameters dict.  Expected keys:

        file_content_b64       Base64-encoded file bytes (str).
        file_format            "csv" | "json" | "jsonl" | "parquet".
        tenant_id              str (optional, defaults to "unknown").
        targeted_categories    list[str] | None
        applicable_regulations list[str] | None
        retention_seconds      int | None
        legal_basis            str | None
        correlation_id         str (optional)
        actor                  str (optional)
        filename               str (optional)

    Returns
    -------
    dict
        The compliance report dict (same shape as the compliance-service
        HTTP response body).  RQ also stores this as the job's native
        result so callers polling via ``rq.job.Job.fetch`` can read it.

    Side-effects
    ------------
    Writes ``{"status": "COMPLETED"|"FAILED", "job_id": ..., ...}`` to
    Redis key ``compliance:result:{job_id}`` with TTL 3600 s.
    """
    # ------------------------------------------------------------------
    # compliance_engine and audit_logger are available only inside the
    # worker Docker image (copied from services/compliance-service/ at
    # build time).  Deferred imports here prevent import-time failure
    # in test/development environments where the package is absent.
    # The type: ignore suppresses mypy's "module not found" for a path
    # that is intentionally runtime-only.
    # ------------------------------------------------------------------
    try:
        from audit_logger import (  # type: ignore[import-not-found]
            AuditLogger,
        )
        from compliance_engine import (  # type: ignore[import-not-found]
            ComplianceReport,
            PIIDetector,
            PolicyDecision,
            PolicyEngine,
            RiskCalculator,
        )
    except ImportError as exc:
        logger.error(
            "compliance_scan_job import_failed job_id=%s error=%s — "
            "PYTHONPATH must include /app and /app/compliance_engine",
            job_id,
            exc,
        )
        raise

    redis_client = _get_redis_client()
    start_time = time.time()

    try:
        # ------------------------------------------------------------------
        # 1. Deserialise DataFrame from base64-encoded file bytes
        # ------------------------------------------------------------------
        raw_bytes = base64.b64decode(payload["file_content_b64"])
        buf = BytesIO(raw_bytes)
        file_format = payload.get("file_format", "csv").lower()

        import pandas as pd  # type: ignore[import-untyped]

        if file_format == "csv":
            df = pd.read_csv(buf)
        elif file_format == "json":
            df = pd.read_json(buf)
        elif file_format == "jsonl":
            df = pd.read_json(buf, lines=True)
        elif file_format == "parquet":
            df = pd.read_parquet(buf)
        else:
            raise ValueError(f"Unsupported file_format in compliance job payload: {file_format!r}")

        # ------------------------------------------------------------------
        # 2. Extract optional scan parameters
        # ------------------------------------------------------------------
        categories_list: list[str] | None = payload.get("targeted_categories")
        regulations_list: list[str] | None = payload.get("applicable_regulations")
        legal_basis: str | None = payload.get("legal_basis")

        retention: int | None = None
        if payload.get("retention_seconds") is not None:
            with contextlib.suppress(ValueError, TypeError):
                retention = int(payload["retention_seconds"])

        # ------------------------------------------------------------------
        # 3. Run the compliance pipeline synchronously
        # ------------------------------------------------------------------
        detector = PIIDetector(sample_size=1000, min_match_ratio=0.01)
        risk_calc = RiskCalculator()
        policy = PolicyEngine()
        report_gen = ComplianceReport()

        findings = detector.detect_pii(df, target_categories=categories_list)
        risk_score = risk_calc.calculate_risk_score(findings)
        risk_level = risk_calc.determine_risk_level(risk_score)
        decision: PolicyDecision = policy.evaluate(findings, risk_score, total_rows=len(df))

        scan_duration = time.time() - start_time

        report = report_gen.generate_report(
            findings=findings,
            risk_score=risk_score,
            risk_level=risk_level,
            allowed_to_store=decision.allowed,
            compliance_status=decision.status,
            issues=decision.issues,
            total_rows=len(df),
            total_columns=len(df.columns),
            scan_duration_seconds=round(scan_duration, 3),
            applicable_regulations=regulations_list,
            retention_seconds=retention,
            legal_basis=legal_basis,
            cross_border_regulations=decision.cross_border_regulations,
            localization_regulations=decision.localization_regulations,
            estimated_affected_rows=decision.estimated_affected_rows,
        )

        # ------------------------------------------------------------------
        # 4. Emit audit record
        # ------------------------------------------------------------------
        _risk_level_str = risk_level.value if hasattr(risk_level, "value") else str(risk_level)
        AuditLogger().log_scan(
            correlation_id=payload.get("correlation_id") or "",
            tenant_id=payload.get("tenant_id") or "unknown",
            actor=payload.get("actor") or "",
            action="scan_file_worker",
            filename=payload.get("filename") or "",
            rows_scanned=len(df),
            columns_scanned=len(df.columns),
            risk_level=_risk_level_str,
            regulations_triggered=(report.get("applicable_regulations") or []),
            allowed=decision.allowed,
            duration_ms=int(scan_duration * 1000),
        )

        # ------------------------------------------------------------------
        # 5. Persist result to Redis under compliance:result:{job_id}
        # ------------------------------------------------------------------
        _write_result(
            redis_client,
            job_id,
            {
                "status": "COMPLETED",
                "job_id": job_id,
                "result": report,
            },
        )

        logger.info(
            "compliance_scan_job completed job_id=%s duration_ms=%d risk_level=%s allowed=%s",
            job_id,
            int(scan_duration * 1000),
            _risk_level_str,
            decision.allowed,
        )

        return cast("dict[str, Any]", report)

    except Exception as exc:
        scan_duration = time.time() - start_time
        # Sanitise exception message before storing — never log raw PII.
        error_msg = _sanitise_error(str(exc))
        _write_result(
            redis_client,
            job_id,
            {
                "status": "FAILED",
                "job_id": job_id,
                "error": error_msg,
            },
        )
        logger.error(
            "compliance_scan_job failed job_id=%s duration_ms=%d error=%s",
            job_id,
            int(scan_duration * 1000),
            error_msg,
        )
        raise  # Re-raise so RQ marks the job as failed and stores exc_info
