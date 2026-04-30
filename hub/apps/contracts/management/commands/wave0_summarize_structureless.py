"""
Phase 227 Wave 0 (227.0.2) — JSONL triage aggregator.

Consumes the JSONL artefact produced by `wave0_capture_structureless`
and emits a markdown report with totals, per-classification breakdown,
per-tenant breakdown joined with ``Tenant.name``, and an explicit list
of tenants without TENANT_ADMINs (escalation per runbook §227.0.3).

The aggregator opens the JSONL file directly rather than re-querying
the DB so the report reflects the *captured* state at the moment of
diagnosis, not whatever drift has happened since.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Phase 227 Wave 0 (227.0.2): summarize a structureless-contract "
        "JSONL artefact into a markdown triage report."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--input",
            required=True,
            help="Path to the JSONL artefact (output of wave0_capture_structureless).",
        )
        parser.add_argument(
            "--output",
            default=None,
            help="Optional path to write the markdown report. Defaults to stdout.",
        )

    def handle(self, *_args, **options):
        input_path = Path(options["input"])
        if not input_path.exists():
            self.stderr.write(self.style.ERROR(f"Input file not found: {input_path}"))
            return

        rows, malformed = self._read_jsonl(input_path)

        report = self._build_report(rows, malformed=malformed)

        output_path = options.get("output")
        if output_path:
            Path(output_path).write_text(report, encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"Wrote {output_path}"))
        else:
            self.stdout.write(report)

    # ------------------------------------------------------------------
    # JSONL ingestion
    # ------------------------------------------------------------------

    def _read_jsonl(self, path: Path) -> tuple[list[dict[str, Any]], int]:
        """Return (parsed rows, malformed-line count).

        Header / trailer lines (`# ...`) are skipped silently. Lines that
        look like JSON but fail to parse increment the malformed counter
        and emit a stderr warning so the operator can re-run the capture
        if needed.
        """
        rows: list[dict[str, Any]] = []
        malformed = 0
        with path.open("r", encoding="utf-8") as fp:
            for lineno, raw in enumerate(fp, start=1):
                stripped = raw.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                try:
                    obj = json.loads(stripped)
                except json.JSONDecodeError:
                    malformed += 1
                    self.stderr.write(self.style.WARNING(
                        f"  [warn] skipping malformed line {lineno}"
                    ))
                    continue
                if not isinstance(obj, dict) or "contract_id" not in obj:
                    # Not a structureless row — skip.
                    continue
                rows.append(obj)
        return rows, malformed

    # ------------------------------------------------------------------
    # Report builder
    # ------------------------------------------------------------------

    def _build_report(self, rows: list[dict[str, Any]], *, malformed: int) -> str:
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.services import get_tenant_admin_users

        total = len(rows)
        if total == 0:
            return self._empty_report(malformed=malformed)

        by_classification: Counter[str] = Counter(
            row.get("classification") or "unknown" for row in rows
        )
        by_spec_type: Counter[str] = Counter(
            row.get("spec_type") or "unknown" for row in rows
        )
        by_tenant: defaultdict[str | None, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            by_tenant[row.get("tenant_id")].append(row)

        # Resolve tenant names in one query for speed and to surface
        # tenants that no longer exist (escalation).
        tenant_ids = [tid for tid in by_tenant if tid]
        tenant_lookup = {
            str(t.id): t for t in Tenant.objects.filter(id__in=tenant_ids)
        }

        # Identify tenants without admins so the dispatcher (227.0.3)
        # operator can escalate before sending notifications.
        no_admin_tenants: list[tuple[str, str]] = []
        for tid in tenant_ids:
            tenant = tenant_lookup.get(tid)
            if tenant is None:
                continue
            if not list(get_tenant_admin_users(tenant)):
                no_admin_tenants.append((tid, getattr(tenant, "name", "?")))

        # ----- markdown -----
        lines: list[str] = []
        lines.append("# Structureless Contracts — Wave 0 Triage Summary")
        lines.append("")
        lines.append(f"- **Total structureless contracts**: {total}")
        lines.append(f"- **Distinct tenants affected**: {len(tenant_ids)}")
        if malformed:
            lines.append(f"- **Malformed JSONL lines skipped**: {malformed}")
        lines.append("")

        lines.append("## By classification")
        lines.append("")
        lines.append("| Classification | Count |")
        lines.append("|---|---|")
        for classification, count in by_classification.most_common():
            lines.append(f"| `{classification}` | {count} |")
        lines.append("")

        lines.append("## By spec type")
        lines.append("")
        lines.append("| Spec type | Count |")
        lines.append("|---|---|")
        for spec_type, count in by_spec_type.most_common():
            lines.append(f"| `{spec_type}` | {count} |")
        lines.append("")

        lines.append("## Per tenant")
        lines.append("")
        lines.append("| Tenant | Tenant ID | Contracts | Predominant classification |")
        lines.append("|---|---|---|---|")
        # Sort tenants by descending contract count for triage priority.
        tenant_buckets = sorted(
            by_tenant.items(), key=lambda kv: len(kv[1]), reverse=True,
        )
        for tid, contracts in tenant_buckets:
            tenant_name = self._tenant_label(tid, tenant_lookup)
            tenant_id_str = tid or "(null)"
            classifications = Counter(
                c.get("classification") or "unknown" for c in contracts
            )
            top_class, top_count = classifications.most_common(1)[0]
            top_label = f"`{top_class}` ({top_count})"
            lines.append(
                f"| {tenant_name} | `{tenant_id_str}` | {len(contracts)} | {top_label} |"
            )
        lines.append("")

        if no_admin_tenants:
            lines.append("## Tenants without admin (escalation)")
            lines.append("")
            lines.append(
                "These tenants have structureless contracts but **no "
                "TENANT_ADMIN user** to receive the T-14 heads-up. "
                "Escalate via the runbook §227.0.3 procedure (re-grant role) "
                "before running `wave0_send_structureless_notifications`."
            )
            lines.append("")
            for tid, name in no_admin_tenants:
                lines.append(f"- `{tid}` — {name}")
            lines.append("")
        else:
            lines.append("## Tenants without admin (escalation)")
            lines.append("")
            lines.append("None — every affected tenant has at least one TENANT_ADMIN.")
            lines.append("")

        lines.append("## Next step")
        lines.append("")
        lines.append(
            "Run the dispatcher in **dry-run** first to preview the per-tenant "
            "fan-out without sending email:"
        )
        lines.append("")
        lines.append("```bash")
        lines.append(
            "python manage.py wave0_send_structureless_notifications \\"
        )
        lines.append("    --input <jsonl-path> \\")
        lines.append("    --deadline 2026-05-14 \\")
        lines.append("    --dry-run")
        lines.append("```")
        lines.append("")

        return "\n".join(lines) + "\n"

    def _empty_report(self, *, malformed: int) -> str:
        lines = [
            "# Structureless Contracts — Wave 0 Triage Summary",
            "",
            "- **Total structureless contracts**: 0",
            "- **Result**: clean — no tenants need notification.",
        ]
        if malformed:
            lines.append(f"- **Malformed JSONL lines skipped**: {malformed}")
        lines.append("")
        lines.append(
            "If you expected non-zero rows, verify the staging-clone DB "
            "has the expected contract corpus before proceeding."
        )
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _tenant_label(tid: str | None, lookup: dict[str, Any]) -> str:
        if tid is None:
            return "(null tenant)"
        tenant = lookup.get(tid)
        if tenant is None:
            return "(unknown — tenant missing)"
        return getattr(tenant, "name", str(tid))
