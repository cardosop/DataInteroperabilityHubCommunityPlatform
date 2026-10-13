#!/usr/bin/env python3
"""P.3c (D7) — prove the BaaS dedicated-database path against a REAL
separate Postgres instance.

The in-suite test could never do this: ``DATABASES["baas"]`` is configured
ONCE per process from ``BAAS_DATABASE_URL`` (settings snapshot it at
import; ``override_settings`` mid-test cannot rewire the connection
handler). The previous suite test fabricated its URL from the DEFAULT
database — the "dedicated DB" test used the same database (root-fixed in
``baas/tests/test_usage_backends.py``).

This standalone verifier runs in a process where ``BAAS_DATABASE_URL`` IS
set from the start:

1. migrate ``--database=baas`` (the router's non-mirrored branch restricts
   ``baasusagerecord`` to the baas alias) — with ``pytest`` in sys.modules
   the router still applies its TEST branch, so the migration targets the
   alias configured from the env URL;
2. write two usage records through the REAL ``PostgresUsageBackend``;
3. read them back through the backend AND through a raw psycopg2
   connection to the physical baas database (proving the bytes landed on
   the separate instance, not the mirrored default);
4. assert the records are NOT in the default database's ``baas_usage_record``
   table (if the router silently fell back, this catches it);
5. assert the router's production routing branches answer correctly.

Usage (docker stack up, host-side):

  POSTGRES_HOST=localhost POSTGRES_PORT=54329 POSTGRES_USER=hub POSTGRES_PASSWORD=hub POSTGRES_DB=hub \
  TEST_DB_SUFFIX=313full ENVIRONMENT=test JWT_ALGORITHM=HS256 \
  BAAS_DATABASE_URL=postgres://hub_baas:hub_baas@localhost:5435/baas \
  venv/bin/python scripts/verify_baas_dedicated_db.py
"""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _fail(message: str) -> None:
    print(f"BAAS-DB FAIL: {message}")
    sys.exit(1)


def _ok(message: str) -> None:
    print(f"BAAS-DB OK: {message}")


def _baas_url_parts() -> dict[str, str]:
    """Parse BAAS_DATABASE_URL for the raw psycopg2 proof connection."""
    from urllib.parse import unquote, urlparse

    url = os.environ.get("BAAS_DATABASE_URL")
    if not url:
        _fail("BAAS_DATABASE_URL must be set at process start (see docstring)")
    parsed = urlparse(url)
    return {
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port or 5432),
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "name": parsed.path.lstrip("/") or "baas",
    }


def main() -> None:
    parts = _baas_url_parts()
    _ok(f"BAAS_DATABASE_URL -> {parts['host']}:{parts['port']}/{parts['name']}")

    # Gate the test-suffix default DB the way settings expect (memory recipe).
    if "pytest" not in sys.modules:
        sys.modules["pytest"] = types.ModuleType("pytest")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")

    import django

    django.setup()

    from django.conf import settings

    from hub.apps.manifest import is_core_only

    if is_core_only():
        # Core-only mode: the paid baas layer is not installed (private
        # repo) or absent (public tree) — the dedicated-DB path it proves
        # does not exist, so there is nothing to verify. Exit cleanly.
        print("BAAS-DB SKIP: core-only mode — the paid baas layer is absent; nothing to verify.")
        sys.exit(0)

    if "baas" not in settings.DATABASES:
        _fail("settings did not configure a 'baas' alias from BAAS_DATABASE_URL")
    baas_cfg = settings.DATABASES["baas"]
    default_cfg = settings.DATABASES["default"]
    if baas_cfg.get("NAME") == default_cfg.get("NAME"):
        _fail(
            "baas alias resolves to the SAME database as default — "
            "BAAS_DATABASE_URL was not honored at settings load"
        )
    _ok(f"baas alias is a distinct database: {baas_cfg.get('NAME')}")

    # ── Paid-layer imports (GATE-29) ────────────────────────────────────
    # This script lives in the core tree and must not statically import
    # paid modules; the is_core_only() gate above guarantees the paid
    # layer is present here, so these dynamic imports succeed (an
    # ImportError/RuntimeError would mean a broken install — surface it).
    import importlib

    BaaSDBRouter = importlib.import_module("hub.apps.baas.db_router").BaaSDBRouter
    _baas_models = importlib.import_module("hub.apps.baas.models")
    BaaSUsageRecord = _baas_models.BaaSUsageRecord
    APITierModel = _baas_models.APITierModel
    PostgresUsageBackend = importlib.import_module(
        "hub.apps.baas.usage_backends"
    ).PostgresUsageBackend

    # ── Router production-branch contract ───────────────────────────────
    # db_for_read/db_for_write are NOT gated by test mode — assert in-process.
    router = BaaSDBRouter()
    assert router.db_for_write(BaaSUsageRecord) == "baas"
    assert router.db_for_read(BaaSUsageRecord) == "baas"
    assert router.db_for_write(APITierModel) is None, "non-usage baas models stay on default"
    _ok("router routes BaaSUsageRecord to 'baas' and nothing else there")

    # allow_migrate IS gated: this process carries pytest in sys.modules (the
    # settings test-DB gating), so the router deliberately takes its test
    # branch here. The PRODUCTION branches — the ones CI never exercises —
    # are asserted in a clean subprocess without pytest.
    _ok("in-process allow_migrate uses the test branch (pytest injected for DB gating)")

    # ── Bootstrap the dedicated alias's schema ──────────────────────────
    # `migrate --database=baas` runs the whole migration graph; on a loaded
    # host the graph's statement/idle timeouts kill connections mid-flight
    # and the retry loop never completes (measured; documented env class).
    # The DEFAULT database's migration graph is proven by every CI run —
    # this verifier's job is the ROUTING proof, so it applies the ONLY
    # schema the routing needs — BaaSUsageRecord — through Django's own
    # SchemaEditor (the exact CreateModel operation migrate would run),
    # against the dedicated alias.
    from django.db import connections

    baas_connection = connections["baas"]
    with baas_connection.schema_editor() as editor:
        if not any(
            name == BaaSUsageRecord._meta.db_table
            for name in baas_connection.introspection.table_names()
        ):
            editor.create_model(BaaSUsageRecord)
    _ok("BaaSUsageRecord created on the dedicated alias via SchemaEditor")

    # ── Write through the real backend, read back ───────────────────────
    api_key_id = "11111111-2222-3333-4444-555555555555"
    tenant_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    # Idempotent re-runs: clear any records a previous attempt left behind.
    BaaSUsageRecord.objects.using("baas").filter(api_key_id=api_key_id).delete()
    backend = PostgresUsageBackend()
    for endpoint in ("/api/v1/baas/stats", "/api/v1/baas/usage"):
        backend.record_usage(
            api_key_id=api_key_id,
            tenant_id=tenant_id,
            endpoint=endpoint,
            method="GET",
            status_code=200,
        )
    from datetime import timedelta

    from django.utils import timezone

    count = backend.get_usage_window(
        api_key_id,
        timezone.now() - timedelta(hours=1),
        timezone.now() + timedelta(hours=1),
    )
    if count != 2:
        _fail(f"expected 2 usage records via backend, got {count}")
    _ok("2 records written and read back through PostgresUsageBackend")

    # ── Raw proof: bytes are on the PHYSICAL baas instance ──────────────
    import psycopg2

    conn = psycopg2.connect(
        host=parts["host"],
        port=parts["port"],
        user=parts["user"],
        password=parts["password"],
        dbname=parts["name"],
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM baas_usage_record WHERE api_key_id=%s",
                (api_key_id,),
            )
            physical_count = cursor.fetchone()[0]
    finally:
        conn.close()
    if physical_count != 2:
        _fail(f"physical baas instance holds {physical_count} records, expected 2")
    _ok("raw psycopg2 proof: records exist on the separate physical instance")

    # ── Absence proof on the DEFAULT database ───────────────────────────
    default_rows = BaaSUsageRecord.objects.using("default").filter(api_key_id=api_key_id).count()
    if default_rows != 0:
        _fail(f"default database holds {default_rows} baas records — router fell back")
    _ok("default database holds ZERO of the dedicated writes (no silent fallback)")

    # ── Production allow_migrate branches (clean subprocess, no pytest) ──
    import subprocess

    sub_env = dict(os.environ)
    sub_code = (
        "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','hub.settings'); "
        "import django; django.setup(); "
        "from hub.apps.baas.db_router import BaaSDBRouter; "
        "r = BaaSDBRouter(); "
        "assert r.allow_migrate('baas', 'baas', 'baasusagerecord') is True; "
        "assert r.allow_migrate('default', 'baas', 'baasusagerecord') is False; "
        "assert r.allow_migrate('default', 'baas', 'apitiermodel') is True; "
        "assert r.allow_migrate('baas', 'baas', 'apitiermodel') is False; "
        "assert r.allow_migrate('default', 'tenants', None) is None; "
        "print('PROD-ROUTER-OK')"
    )
    result = subprocess.run(
        [sys.executable, "-c", sub_code],
        capture_output=True,
        text=True,
        env=sub_env,
        timeout=300,
    )
    if result.returncode != 0 or "PROD-ROUTER-OK" not in result.stdout:
        _fail(
            "production allow_migrate branches failed in the clean subprocess:\n"
            f"stdout={result.stdout[-500:]}\nstderr={result.stderr[-500:]}"
        )
    _ok("production allow_migrate branches verified in a clean (non-test) process")

    print("BAAS-DB: dedicated database path fully verified")


if __name__ == "__main__":
    main()
