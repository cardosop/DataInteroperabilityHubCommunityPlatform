"""
Phase 250.1.C.3 — pre-removal readiness check for the v1 asset-creation
workflow.

Background
----------
Phase 250.1.C.2 ships dual-version registration: ``register_workflow``
lands BOTH v1.0.0 (legacy post-asset-gate DSL) AND v2.0.0 (Phase 250.1.A
fail-closed-at-intake DSL). v1 is grandfathered for a 14-day soak window
per D250.7 so any in-flight v1 instances complete on the v1 handler
even after v2 is deployed.

Phase 250.1.C.3 — the removal of the v1 handler — is **timing-dependent**:
it must wait for telemetry to confirm zero v1 in-flight runs at the
end of the soak window. This command produces that go/no-go signal.

What it does
------------
1. Queries ``WorkflowInstance`` for every workflow_name (default:
   ``asset_creation``) at version ``1.0.0`` whose ``status`` is
   non-terminal (``DRAFT``, ``RUNNING``, ``PAUSED``, ``ROLLING_BACK``,
   ``COMPENSATION_INCOMPLETE``).
2. Confirms via ``WorkflowVersionManager.is_version_eligible_for_inflight``
   that the v1 version is OUTSIDE the configured soak window
   (``soak_days``, default 14 per D250.7).
3. Emits a structured PASS / FAIL verdict on stdout (human-readable
   table + optional JSON via ``--json``).

Exit codes
----------
* **0 — READY** — zero v1 in-flight runs AND v1 outside the soak
  window. Removal PR is safe to merge.
* **1 — NOT READY** — at least one v1 in-flight run still active OR v1
  still inside the soak window. Re-run after the in-flight runs
  terminate or the soak completes.
* **2 — DATA ERROR** — environment misconfigured (workflow definitions
  missing, etc.).

Usage
-----
::

    # Default: check asset_creation, soak_days=14
    python manage.py check_workflow_v1_removal_readiness

    # Custom workflow + soak override
    python manage.py check_workflow_v1_removal_readiness \
        --workflow=asset_creation \
        --version=1.0.0 \
        --soak-days=14

    # JSON output for CI / Slack-digest pipelines
    python manage.py check_workflow_v1_removal_readiness --json

This command is a READ-ONLY check — it makes no DB writes; safe to run
on production at any time. SRE runs it daily during the soak; the
removal PR's CI gate runs it once at merge time.
"""
from __future__ import annotations

import json
import sys

from django.core.management.base import BaseCommand

from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
from hub.apps.orchestration.versioning import WorkflowVersionManager


# Non-terminal statuses — instances in any of these states are "still
# alive" and would be affected by handler removal. The terminal statuses
# (COMPLETED, FAILED, CANCELLED, ROLLED_BACK) are safe; their state is
# already at rest in the DB and v1 handler removal cannot affect them.
_NON_TERMINAL_STATUSES: tuple[str, ...] = (
    WorkflowStatus.DRAFT,
    WorkflowStatus.RUNNING,
    WorkflowStatus.PAUSED,
    WorkflowStatus.ROLLING_BACK,
    WorkflowStatus.COMPENSATION_INCOMPLETE,
)


_EXIT_READY = 0
_EXIT_NOT_READY = 1
_EXIT_DATA_ERROR = 2


class Command(BaseCommand):
    help = (
        "Phase 250.1.C.3 — verify v1 asset-creation workflow handler "
        "is safe to remove. Exit 0 = READY (no in-flight v1 + soak "
        "elapsed); exit 1 = NOT READY; exit 2 = data error."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--workflow",
            default="asset_creation",
            help="Workflow name to check (default: asset_creation).",
        )
        parser.add_argument(
            "--workflow-version",
            dest="version",
            default="1.0.0",
            help="Version being considered for removal (default: 1.0.0).",
        )
        parser.add_argument(
            "--soak-days",
            type=int,
            default=14,
            help=(
                "Soak window in days per D250.7 (default: 14). The v1 "
                "version MUST be outside this window before removal."
            ),
        )
        parser.add_argument(
            "--json",
            action="store_true",
            dest="emit_json",
            help="Emit a structured JSON verdict instead of human-readable text.",
        )

    def handle(self, *args, **options):
        workflow = options["workflow"]
        version = options["version"]
        soak_days = options["soak_days"]
        emit_json = options["emit_json"]

        # ── Check 1: in-flight runs ────────────────────────────────
        inflight_qs = WorkflowInstance.objects.filter(
            workflow_name=workflow,
            workflow_version=version,
            status__in=_NON_TERMINAL_STATUSES,
        )
        inflight_count = inflight_qs.count()

        # Capture per-tenant breakdown (helps SRE direct the cleanup) +
        # capture up to 10 example instance ids for the report.
        per_tenant: dict[str, int] = {}
        examples: list[dict] = []
        for instance in inflight_qs.values(
            "id", "tenant_id", "status", "started_at"
        )[:50]:  # cap query result for performance
            tenant_id = str(instance.get("tenant_id") or "(none)")
            per_tenant[tenant_id] = per_tenant.get(tenant_id, 0) + 1
            if len(examples) < 10:
                examples.append({
                    "instance_id": str(instance["id"]),
                    "tenant_id": tenant_id,
                    "status": instance["status"],
                    "started_at": (
                        instance["started_at"].isoformat()
                        if instance["started_at"] else None
                    ),
                })

        # ── Check 2: soak window elapsed ───────────────────────────
        # `is_version_eligible_for_inflight` returns True when the
        # version is STILL eligible (active OR within the soak window).
        # We want the OPPOSITE — eligible means soak is NOT elapsed.
        try:
            still_eligible = WorkflowVersionManager.is_version_eligible_for_inflight(
                workflow_name=workflow,
                version=version,
                soak_days=soak_days,
            )
        except Exception as exc:  # noqa: BLE001 — boundary
            verdict = {
                "ready": False,
                "exit_code": _EXIT_DATA_ERROR,
                "reason": "version_eligibility_check_failed",
                "error": str(exc),
                "workflow": workflow,
                "version": version,
                "soak_days": soak_days,
            }
            self._emit(verdict, emit_json=emit_json)
            return self._exit(_EXIT_DATA_ERROR)
        soak_elapsed = not still_eligible

        # ── Verdict ────────────────────────────────────────────────
        ready = (inflight_count == 0) and soak_elapsed
        if ready:
            exit_code = _EXIT_READY
            reason = "ready"
        else:
            exit_code = _EXIT_NOT_READY
            blockers = []
            if inflight_count > 0:
                blockers.append(f"{inflight_count}_inflight_runs")
            if not soak_elapsed:
                blockers.append("soak_window_not_elapsed")
            reason = "blocked: " + ", ".join(blockers)

        verdict = {
            "ready": ready,
            "exit_code": exit_code,
            "reason": reason,
            "workflow": workflow,
            "version": version,
            "soak_days": soak_days,
            "inflight_count": inflight_count,
            "soak_elapsed": soak_elapsed,
            "per_tenant_breakdown": per_tenant,
            "examples": examples,
        }
        self._emit(verdict, emit_json=emit_json)
        return self._exit(exit_code)

    # ------------------------------------------------------------------
    # Output helpers
    # ------------------------------------------------------------------

    def _emit(self, verdict: dict, *, emit_json: bool) -> None:
        if emit_json:
            self.stdout.write(json.dumps(verdict, indent=2, sort_keys=True))
            return
        # Human-readable.
        ready = verdict["ready"]
        marker = "✓ READY" if ready else "✗ NOT READY"
        self.stdout.write(
            f"\n{marker} — Phase 250.1.C.3 v1 handler removal readiness check\n"
        )
        self.stdout.write(f"  workflow:      {verdict['workflow']}\n")
        self.stdout.write(f"  version:       {verdict['version']}\n")
        self.stdout.write(f"  soak_days:     {verdict['soak_days']}\n")
        self.stdout.write(f"  reason:        {verdict['reason']}\n")
        self.stdout.write(
            f"  inflight runs: {verdict.get('inflight_count', '?')}\n"
        )
        self.stdout.write(
            f"  soak elapsed:  {verdict.get('soak_elapsed', '?')}\n"
        )
        if verdict.get("per_tenant_breakdown"):
            self.stdout.write("\n  Per-tenant breakdown:\n")
            for tenant_id, count in sorted(
                verdict["per_tenant_breakdown"].items(), key=lambda kv: -kv[1]
            ):
                self.stdout.write(f"    {tenant_id}: {count} run(s)\n")
        if verdict.get("examples"):
            self.stdout.write("\n  Example in-flight instances (up to 10):\n")
            for ex in verdict["examples"]:
                self.stdout.write(
                    f"    - {ex['instance_id']} "
                    f"(tenant={ex['tenant_id']}, "
                    f"status={ex['status']}, "
                    f"started_at={ex['started_at']})\n"
                )
        self.stdout.write("\n")

    def _exit(self, code: int) -> None:
        # BaseCommand.handle's return value is ignored by Django; explicit
        # sys.exit so the process returns the right code for CI.
        sys.exit(code)
