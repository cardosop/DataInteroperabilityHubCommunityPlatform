"""W11.3 (oss-release-remediation) — the ASVS V4 IDOR coverage gate.

DB-free by construction (the GATE-21 `check_throttle_coverage` house
pattern): re-enumerates the live tenant-scoped route inventory, compares
it against the checked-in probe manifest in BOTH directions (a new
tenant-scoped route without a probe, a manifest entry for a route that
no longer exists, a dead allowlist entry — each fails), validates that
every allowlisted route carries a written reason, enforces the ≥95%
coverage threshold, and writes the committed coverage report
``docs/audits/w113-idor-coverage-2026-10-15.md``.

Regeneration loop: when the drift check fails, run
``python manage.py generate_idor_probes`` to refresh the manifest, then
re-run this command.

Wired into CI next to GATE-21 (the lint workflow runs
``cd hub && python manage.py check_idor_coverage``).
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime

from django.core.management.base import BaseCommand

from hub.apps.core import idor_inventory as inv


class Command(BaseCommand):
    help = "Verify IDOR-probe coverage of tenant-scoped API routes (W11.3)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--write-report",
            action="store_true",
            help="Write/refresh the committed coverage report file.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print the coverage summary as JSON to stdout.",
        )

    def handle(self, *_args, **options):
        routes = inv.enumerate_routes()
        allowlist = inv.load_allowlist()

        if not inv.MANIFEST_PATH.is_file():
            self.stderr.write(
                self.style.ERROR(
                    "IDOR probe manifest missing: "
                    f"{inv.MANIFEST_PATH.relative_to(inv.REPO_ROOT)} — run "
                    "`python manage.py generate_idor_probes`"
                )
            )
            sys.exit(1)

        manifest = json.loads(inv.MANIFEST_PATH.read_text(encoding="utf-8"))
        problems, summary = inv.audit_coverage(routes, manifest, allowlist)
        manifest_routes = manifest.get("routes") or []
        summary["generated_at"] = datetime.now(UTC).isoformat()
        summary["problems"] = problems

        if options["json"]:
            self.stdout.write(json.dumps(summary, indent=2))
        elif problems:
            self.stderr.write(
                self.style.ERROR(f"IDOR-COVERAGE gate: FAILED — {len(problems)} problem(s)")
            )
            for problem in problems:
                self.stderr.write(f"  - {problem}")
            sys.exit(1)
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"IDOR-COVERAGE gate: PASSED — {summary['probed']}/"
                    f"{summary['tenant_scoped_route_keys']} tenant-scoped route keys "
                    f"probed ({summary['coverage_pct']}%)"
                )
            )

        if options["write_report"]:
            report = render_report(summary, allowlist, manifest_routes)
            inv.COVERAGE_REPORT_PATH.write_text(report, encoding="utf-8")
            self.stdout.write(
                f"Coverage report written: {inv.COVERAGE_REPORT_PATH.relative_to(inv.REPO_ROOT)}"
            )


def render_report(summary: dict, allowlist: dict, manifest_routes: list[dict]) -> str:
    """Render the committed W11.3 coverage report markdown."""
    allowlist_rows = sorted(
        (method, path_template, reason) for (method, path_template), reason in allowlist.items()
    )
    by_app: dict[str, int] = {}
    for route in manifest_routes:
        if route.get("disposition") == "probe":
            by_app[route.get("app") or "?"] = by_app.get(route.get("app") or "?", 0) + 1

    lines = [
        "# W11.3 — IDOR Probe Coverage Report",
        "",
        f"Generated: {summary['generated_at']} — by `python manage.py check_idor_coverage`.",
        "",
        "## Summary",
        "",
        f"- Tenant-scoped route keys in scope: **{summary['tenant_scoped_route_keys']}**",
        f"- Probed by the generated suite (strict cross-tenant contract): **{summary['probed']}**",
        f"- Allowlisted with written reasons: **{summary['allowlisted']}**",
        f"- Coverage: **{summary['coverage_pct']}%** (task threshold "
        f"{summary['coverage_threshold_pct']}%)",
        "",
        "## Probe coverage by app",
        "",
        "| App | Probed route keys |",
        "|---|---|",
    ]
    for app, count in sorted(by_app.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| {app} | {count} |")
    lines += [
        "",
        "## Allowlisted routes (the ≤5% remainder, each with its reason)",
        "",
        "| Method | Path | Reason |",
        "|---|---|---|",
    ]
    for method, path_template, reason in allowlist_rows:
        lines.append(f"| {method} | `{path_template}` | {reason} |")
    lines += [
        "",
        "The probe suite, manifest, and scope rule:",
        "`tests/security/test_w113_asvs_v4_access_control.py`,"
        " `docs/api-audit/idor-probe-manifest.json`,"
        " `docs/security/adversarial-matrices/w113-access-control-matrix.md`.",
        "",
    ]
    return "\n".join(lines) + "\n"
