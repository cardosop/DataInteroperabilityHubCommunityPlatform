"""Generate scripts/publish_paths_exclude.txt from the manifest (313.3.2).

Single source of truth: paid-app dirs come from hub/apps/manifest.py; the
static EXTRA list covers ops/private/junk material. Semantics: the list is
consumed by `git filter-repo --invert-paths` (history scrub) and by
publish_public.sh (tree build) — new core files default to INCLUDED.
A "!prefix" entry NEGATES a preceding exclusion in the publish tree filter
(e.g. helm/ is excluded wholesale; "!helm/community/" ships the chart).

Run: python scripts/generate_publish_excludes.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hub.apps import manifest

PAID_SERVICES = (
    "services/semantic-service/",
    "services/dq-service/",
    "services/datacontract-service/",
    "services/compliance-service/",
    "services/prefect-integration/",
    "services/prefect-server/",
    "services/odh-training-operator/",
    "services/odh-integration/",
    "services/odh-inference-scheduler/",
    "services/webhook-service/",
    "services/observability-service/",
    "services/workflow_engine/",
    "services/tests/",
)

EXTRA = (
    # Meshant-ops-specific (internal hostnames)
    "infrastructure/",
    # Dev-postgres init script (base compose mounts it); certs/private
    # scripts stay excluded.
    "!infrastructure/postgres/02-pg-hba-host.sh",
    # S3 bucket-policy terraform (security-contract tests assert it; the
    # files are policy/config only — internal hostnames are scrubbed).
    "!infrastructure/terraform/s3/",
    # Traefik static + dynamic config (base compose bind-mounts them; the
    # quickstart stack cannot route without them — 313.DoD.5 round 4).
    "!infrastructure/traefik/traefik.yml",
    "!infrastructure/traefik/traefik.core.yml",
    "!infrastructure/traefik/dynamic/",
    "helm/",
    # Community chart ships (negation re-includes it in the publish tree)
    "!helm/community/",
    "k8s/",
    "monitoring/",
    # Test-stack observability configs (docker-compose.test.yml bind-mounts
    # them; a fresh public clone must boot the test stack — 313.DoD.3
    # public-clone parity). loki/tempo/otel/promtail stay excluded.
    "!monitoring/prometheus/prometheus.yml",
    "!monitoring/prometheus/prometheus-test.yml",
    # Phase P.8 — core-safe monitoring variants the core overlay mounts:
    # no paid-only scrape jobs (no `up == 0` storms for absent services),
    # no env-placeholder routes. Pinned by
    # scripts/tests/test_monitoring_core_safety.py.
    "!monitoring/prometheus/prometheus.core.yml",
    "!monitoring/prometheus/alerts.yml",
    "!monitoring/prometheus/alerts/",
    "!monitoring/grafana/dashboards/",
    "!monitoring/grafana/datasources/",
    "!monitoring/alertmanager/alertmanager-test.yml",
    "!monitoring/alertmanager/alertmanager.core.yml",
    # Pre-split compose files reference paid services — EXCEPT the two bases
    # the core overlays stack on (the overlays are not standalones; the
    # bases ship and their paid service definitions are profiled out).
    "docker-compose.dev.yml",
    "docker-compose.staging.yml",
    "docker-compose.production.yml",
    "docker-compose.mvp.yml",
    "docker-compose.e2e-mailhog.yml",
    "docker-compose.override.memory.yml",
    "docker-compose.override.test-run.yml",
    "docker-compose.test.marquez.yml",
    "docker-compose.test.mvp.yml",
    # Private-only dev/ops tooling (313.H.2.3) — these import paid modules
    # and are never part of the public product surface:
    #   validate_odps_final_checklist.py   — private PR checklist validator
    #   provision_smoke_fixtures.py        — staging-QA fixture provisioning
    #   semantic_memento_capacity_test.py  — capacity benchmark (paid semantic)
    #   performance/profile_p1_endpoints.py — P1 endpoint profiling
    "scripts/validate_odps_final_checklist.py",
    "scripts/provision_smoke_fixtures.py",
    "scripts/semantic_memento_capacity_test.py",
    "scripts/performance/profile_p1_endpoints.py",
    # Secrets + local configs (313.0)
    ".env.dev",
    ".env.staging",
    ".env.test",
    ".env",
    ".env.e2e",
    ".env.test.ckan",
    ".env.local",
    "infrastructure/postgres/certs/",
    # Duplicated docs trees
    "docs/docs/",
    "docs/deprecated-doc/",
    # Private CI (50+ jobs, paid services, internal URLs) never ships; the
    # overlay provides the public workflows instead.
    ".github/workflows/",
    # Publish machinery, not product content.
    "scripts/publish_public_overlay/",
    "openspec/",
    "archive/",
    # Phase 227 W6.4 rollout-evidence manifest + hash-linked JSONL — a
    # compliance breadcrumb the contracts tests assert ships (hash-match
    # contract); the rest of archive/ stays private.
    "!archive/phase-227-rollout/",
    "examples/",
    "backups/",
    "product-site/",
    # Junk/artifacts
    "*.log",
    "server.*.log",
    "deployment_logs/",
    "test_reports_comprehensive/",
    "htmlcov/",
    "htmlcov-unit/",
    ".mypy_cache/",
    ".ruff_cache/",
    "node_modules/",
    "awscliv2.zip",
    ".gcp-sa-test.json",
    # Local tooling
    ".claude/",
)


def main() -> int:
    paid_app_dirs = [manifest.module_name(e).replace(".", "/") + "/" for e in manifest.PAID_APPS]
    paid_app_dirs.append("hub/apps/graphql_graphene/")
    lines = [
        "# scripts/publish_paths_exclude.txt — GENERATED from hub/apps/manifest.py (313.3.2).",
        "# Regenerate with: python scripts/generate_publish_excludes.py",
        "# Semantics: git filter-repo --invert-paths; new core files default to INCLUDED.",
        '# "!prefix" entries NEGATE a preceding exclusion (publish tree filter).',
    ]
    lines += paid_app_dirs + list(PAID_SERVICES) + list(EXTRA)
    Path("scripts/publish_paths_exclude.txt").write_text("\n".join(lines) + "\n")
    print(f"exclusion list regenerated: {len(lines) - 2} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
