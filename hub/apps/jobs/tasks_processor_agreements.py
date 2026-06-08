"""RQ handler for PROCESSOR_AGREEMENT_EXPIRY_CHECK (cross-tenant scan)."""


def _execute_processor_agreement_expiry_check_job(job_obj) -> dict:
    """Mirror management command ``processor_agreement_expiry_check`` semantics."""
    from hub.apps.processor_agreements.expiry_scan import run_processor_agreement_expiry_scan

    counters = run_processor_agreement_expiry_scan()
    return {"success": True, "summary": counters}
