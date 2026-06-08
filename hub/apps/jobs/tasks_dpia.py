"""Job handlers for DPIA tooling — Phase 232.5."""

from __future__ import annotations
from hub.apps.dpia.services.review_due import run_dpia_review_due_scan


def _execute_dpia_review_due_job(job_obj) -> dict:
    """
    Cross-tenant periodic scan: reopen APPROVED DPIAs past next_review_due_at.

    Wrapped scan disables strict RLS for this connection so rows across tenants
    are visible (mirrors management command behaviour).
    """
    return run_dpia_review_due_scan()
