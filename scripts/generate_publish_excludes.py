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

from hub.apps import manifest  # noqa: E402

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
    "helm/",
    # Community chart ships (negation re-includes it in the publish tree)
    "!helm/community/",
    "k8s/",
    "monitoring/",
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
    # Secrets + local configs (313.0)
    ".env.dev", ".env.staging", ".env.test", ".env", ".env.e2e", ".env.test.ckan", ".env.local",
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
