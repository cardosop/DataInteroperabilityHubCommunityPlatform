"""
285.6.3.3 — dlt retry handling replacing dead_letter_queue.py (260L).

dlt LoadInfo tracks failed loads natively. Failed resources can be
re-processed via pipeline.run() with the same resource definitions.
"""
from __future__ import annotations
from typing import Any, Dict, List

import dlt
import structlog

logger = structlog.get_logger(__name__)

MAX_RETRIES = 3


def get_failed_loads(pipeline_name: str) -> List[Dict[str, Any]]:
    """
    285.6.3.3 — Return failed loads from dlt pipeline.

    Replaces DeadLetterQueueManager.sync_from_ingestion_state().
    dlt tracks failed loads in _dlt_loads table automatically.
    """
    pipeline = dlt.pipeline(pipeline_name=pipeline_name)
    failed: List[Dict[str, Any]] = []

    if pipeline.last_trace and pipeline.last_trace.last_trace:
        for step in pipeline.last_trace.last_trace.get("steps", []):
            if step.get("step_exception"):
                failed.append({
                    "step": step.get("step", "unknown"),
                    "exception": step.get("step_exception", ""),
                    "started_at": step.get("started_at", ""),
                    "finished_at": step.get("finished_at", ""),
                })
    return failed


def retry_failed(
    pipeline_name: str,
    resources: List[Any],
    max_retries: int = MAX_RETRIES,
) -> Dict[str, Any]:
    """
    285.6.3.3 — Retry failed dlt loads with exponential backoff.

    Replaces DeadLetterQueueManager retry logic.
    dlt's pipeline.run() with the same resources automatically
    skips already-loaded data (dedup via primary_key) and only
    processes failed loads.
    """
    pipeline = dlt.pipeline(pipeline_name=pipeline_name)

    for attempt in range(max_retries):
        try:
            load_info = pipeline.run(resources)
            failed = [
                p for p in load_info.loads
                if p.status == "failed"
            ]
            if not failed:
                logger.info("dlt_retry_success", pipeline=pipeline_name, attempt=attempt + 1)
                return {"status": "success", "attempts": attempt + 1}

            delay = min(2 ** attempt, 60)  # 1s, 2s, 4s, 8s, 16s, 32s, 60s...
            logger.warning(
                "dlt_retry_failed", pipeline=pipeline_name,
                attempt=attempt + 1, failed_loads=len(failed),
                next_delay_seconds=delay,
            )
            import time
            time.sleep(delay)

        except Exception as e:
            logger.error("dlt_retry_exception", pipeline=pipeline_name, attempt=attempt + 1, error=str(e))
            if attempt == max_retries - 1:
                return {"status": "permanent_failure", "attempts": attempt + 1, "error": str(e)}

    return {"status": "max_retries_exceeded", "attempts": max_retries}


def classify_failure(error: str) -> str:
    """
    285.6.3.3 — Classify failure type for DLQ routing.

    Replaces DeadLetterQueueManager failure classification.
    """
    error_lower = error.lower()
    if "schema" in error_lower or "column" in error_lower or "type" in error_lower:
        return "SCHEMA_MISMATCH"
    if "connection" in error_lower or "timeout" in error_lower or "refused" in error_lower:
        return "CONNECTION_ERROR"
    if "permission" in error_lower or "access denied" in error_lower or "unauthorized" in error_lower:
        return "PERMISSION_DENIED"
    if "memory" in error_lower or "oom" in error_lower or "killed" in error_lower:
        return "RESOURCE_EXHAUSTED"
    return "UNKNOWN"
