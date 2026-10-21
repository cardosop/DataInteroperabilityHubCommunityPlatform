"""W3.10 — the volume-backed ``DLT_PIPELINES_DIR`` default and the
restart-preserves-cursor evidence.

The pre-fix state (verified live): ``dlt_pipeline._get_dlt`` set the
``DLT_PIPELINES_DIR`` ENV VAR before the first dlt import — which dlt
1.30 IGNORES (the 6.7 trap): the config getter read None and real
pipelines resolved to ``/tmp/dlt-staging/.dlt/data/pipelines`` (derived
from the DLT_DATA_DIR env, /tmp = ephemeral).  Every container
re-create therefore wiped the pipeline STATE — the processed keys and
the DATABRICKS_SOURCE SQL cursors that W3.3/W3.4 made the correctness
anchor — and the next run re-ingested everything / re-read from
scratch.  The W3.10 fix: a settings-level ``DLT_PIPELINES_DIR`` default
to a VOLUME-backed path, applied through the mechanism dlt ACTUALLY
honors (``dlt.config["pipelines.pipelines_dir"]``), with the compose
named volume mounted into every container that runs pipelines.

Pins:

  1. **The injection applies the volume-backed default** — after the
     real ``_get_dlt()`` chokepoint, ``dlt.config`` carries the
     configured path and a REAL pipeline resolves under it (pre-fix
     RED: config None, resolved under /tmp).
  2. **restart-preserves-cursor** — real state (processed keys + a
     DATABRICKS_SOURCE cursor) written in THIS interpreter, then read
     back from a FRESH subprocess interpreter that re-configures the
     same path — the container-restart equivalent for the state-dir
     resolution.
  3. **The compose contract** — the test stack declares the named
     volume, mounts it on the api AND worker services at the
     configured path, and pins the env default.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

pytestmark = pytest.mark.django_db(transaction=True)

REPO_ROOT = Path(__file__).resolve().parents[3]


def _configured_dir():
    from django.conf import settings

    return getattr(settings, "DLT_PIPELINES_DIR", None)


class TestPipelinesDirInjection:
    def test_config_injection_applies_the_volume_backed_default(self):
        from hub.data_movement.dlt_pipeline import _get_dlt

        configured = _configured_dir()
        assert configured, "settings.DLT_PIPELINES_DIR must exist (W3.10 default)"
        assert not configured.startswith("/tmp"), (
            f"the default must be VOLUME-backed, not the ephemeral /tmp (got {configured})"
        )
        try:
            os.makedirs(configured, exist_ok=True)
        except OSError:
            pytest.skip(f"configured dir {configured} not creatable here (W16 local skip)")
            return

        dlt = _get_dlt()
        assert dlt.config.get("pipelines.pipelines_dir") == configured, (
            "the config injection (the mechanism dlt honors) must apply the "
            "settings default — the env-var approach dlt ignores"
        )

        pipeline = dlt.pipeline(pipeline_name=f"w310-dir-{uuid.uuid4().hex[:8]}")
        resolved = str(pipeline.pipelines_dir)
        assert resolved == configured or resolved.startswith(configured + os.sep), (
            f"a REAL pipeline must resolve under the volume-backed dir: {resolved}"
        )


class TestRestartPreservesCursor:
    def test_restart_preserves_cursor(self):
        """Fresh-interpreter restart: the state written here is read back
        from a NEW process that re-resolves the same configured dir."""
        configured = _configured_dir()
        try:
            os.makedirs(configured, exist_ok=True)
        except OSError:
            pytest.skip(f"configured dir {configured} not creatable here (W16 local skip)")
            return

        pipeline_name = f"w310-restart-{uuid.uuid4().hex[:8]}"
        asset_key = f"asset-{uuid.uuid4().hex[:8]}"

        from hub.data_movement.dlt_incremental import (
            advance_databricks_source_cursor,
            mark_processed,
        )

        mark_processed(pipeline_name, ["staging/a.csv", "staging/b.csv"])
        advance_databricks_source_cursor(
            pipeline_name,
            asset_key,
            cursor_field="updated_at",
            rows=[{"updated_at": "2026-01-01T00:00:00Z"}, {"updated_at": "2026-01-02T00:00:00Z"}],
        )

        # A FRESH interpreter — the restart equivalent: it configures
        # the same settings path via its own _get_dlt and reads back.
        script = (
            "import django, os, json, sys\n"
            "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')\n"
            "django.setup()\n"
            "from hub.data_movement.dlt_pipeline import _get_dlt\n"
            "dlt = _get_dlt()\n"
            "from hub.data_movement.dlt_incremental import (\n"
            "    get_databricks_source_cursor, get_processed_keys,\n"
            ")\n"
            "keys = sorted(get_processed_keys(sys.argv[1]))\n"
            "cursor = get_databricks_source_cursor(sys.argv[1], sys.argv[2])\n"
            "print(json.dumps({'keys': keys, 'cursor': cursor}))\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", script, pipeline_name, asset_key],
            capture_output=True,
            text=True,
            timeout=180,
            cwd=REPO_ROOT,
            check=False,
        )
        assert result.returncode == 0, result.stderr[-2000:]
        payload = json.loads(result.stdout.strip().splitlines()[-1])

        assert payload["keys"] == ["staging/a.csv", "staging/b.csv"], (
            "the processed keys must survive the restart"
        )
        assert payload["cursor"] is not None, "the SQL cursor must survive the restart"
        assert payload["cursor"]["last_value"] == "2026-01-02T00:00:00Z"


class TestComposeContract:
    def test_compose_declares_the_volume_and_mounts(self):
        compose = (REPO_ROOT / "docker-compose.test.yml").read_text()
        assert "dlt-pipelines-test-data:" in compose, (
            "the named volume must be declared in docker-compose.test.yml"
        )
        assert "dlt-pipelines-test-data:/dlt-data/pipelines" in compose, (
            "the volume must mount at /dlt-data/pipelines"
        )
        assert "DLT_PIPELINES_DIR: ${DLT_PIPELINES_DIR:-/dlt-data/pipelines}" in compose, (
            "the env default must pin the volume path"
        )
        # The mount must exist on BOTH containers that run pipelines.
        assert compose.count("dlt-pipelines-test-data:/dlt-data/pipelines") >= 2, (
            "api AND worker must mount the volume"
        )
