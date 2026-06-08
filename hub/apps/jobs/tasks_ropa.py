"""RQ handler for async RoPA artefacts (Phase 232.4)."""

from __future__ import annotations
from hub.apps.jobs.models import Job
from hub.apps.ropa.models import RopaGeneration
from hub.apps.ropa.services.pipeline import failure_generation, materialize_generation


def _execute_ropa_generate_job(job_obj: Job) -> dict:
    det = job_obj.details_json or {}
    rid = det.get("ropa_generation_id")
    if not rid:
        raise ValueError("ropa_generation_id missing from job details_json")
    gen = RopaGeneration.objects.select_related("tenant").get(pk=rid)
    user = job_obj.created_by
    try:
        materialize_generation(generation=gen, actor_user=user)
    except Exception as exc:  # noqa: BLE001 — surface to job framework
        failure_generation(gen, str(exc))
        raise
    return {
        "ropa_generation_id": str(gen.id),
        "object_key": gen.object_key,
        "byte_size": gen.byte_size,
    }
