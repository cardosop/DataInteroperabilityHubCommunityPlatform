"""
Contract tests for scripts/stage_config_artifacts.sh (oss-release-remediation
W0.7).

The stager copies the ro config artifacts the staging compose mounts
(init-db.sql, pgbouncer.ini, fuseki config + sync script, prefect
wait-script + integration tree, prometheus/grafana/alertmanager/traefik
configs) into the gitignored ``infrastructure/staging/config-artifacts/``
dir and writes a SHA256SUMS manifest — so the containers never see the
repo sources (the bind-mount exposure). These pins run the REAL script
against real tmp source trees — no mocks or stubs:

- every declared artifact lands in the dest dir with its relative path
  preserved, and the manifest carries one sha256 row per artifact;
- a missing source FAILS the stager (loud, not silent);
- re-runs are idempotent (same manifest, same content);
- the script never prints file CONTENTS (only paths + counts).
"""

import json
import subprocess
from pathlib import Path

scripts_dir = Path(__file__).parent.parent
STAGER = scripts_dir / "stage_config_artifacts.sh"
REPO_ROOT = scripts_dir.parent
DASHBOARDS_DIR = REPO_ROOT / "monitoring" / "grafana" / "dashboards"

ARTIFACT_RELPATHS = (
    "scripts/init-db.sql",
    "infrastructure/postgres/03-pgbouncer-user.sh",
    "infrastructure/pgbouncer/pgbouncer.staging.ini",
    "infrastructure/fuseki/config.ttl",
    "scripts/fuseki_password_sync.sh",
    "scripts/wait_for_prefect_db.py",
    "services/prefect-integration/flow.py",
    "monitoring/prometheus/prometheus.yml",
    "monitoring/prometheus/alerts.yml",
    "monitoring/prometheus/alerts/high.rules",
    "monitoring/grafana/dashboards/dash.json",
    "monitoring/grafana/datasources/ds.yml",
    "monitoring/alertmanager/alertmanager-staging.yml",
    "infrastructure/traefik/traefik-staging.yml",
    "infrastructure/traefik/dynamic/routes.yml",
)


def _make_source_root(tmp_path: Path) -> Path:
    root = tmp_path / "src"
    for rel in ARTIFACT_RELPATHS:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"artifact-content:{rel}\n")
    return root


def _run(source_root: Path, dest: Path, *extra: str):
    return subprocess.run(
        [
            "bash",
            str(STAGER),
            "--source-root",
            str(source_root),
            "--dest",
            str(dest),
            *extra,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


class TestStagerContract:
    def test_copies_every_declared_artifact_and_writes_the_manifest(self, tmp_path):
        source = _make_source_root(tmp_path)
        dest = tmp_path / "dest"
        result = _run(source, dest)
        assert result.returncode == 0, result.stderr

        for rel in ARTIFACT_RELPATHS:
            copied = dest / rel
            assert copied.is_file(), f"{rel} was not staged"
            assert copied.read_text() == f"artifact-content:{rel}\n"
        manifest = dest / "SHA256SUMS"
        assert manifest.is_file()
        rows = manifest.read_text().splitlines()
        assert len(rows) == len(ARTIFACT_RELPATHS)
        for row in rows:
            digest, name = row.split("  ", 1)
            assert len(digest) == 64
            assert name.removeprefix("./") in ARTIFACT_RELPATHS

    def test_missing_source_fails_loudly(self, tmp_path):
        source = _make_source_root(tmp_path)
        (source / "scripts" / "init-db.sql").unlink()
        result = _run(source, tmp_path / "dest")
        assert result.returncode != 0
        assert "init-db.sql" in result.stderr

    def test_rerun_is_idempotent(self, tmp_path):
        source = _make_source_root(tmp_path)
        dest = tmp_path / "dest"
        assert _run(source, dest).returncode == 0
        first = (dest / "SHA256SUMS").read_text()
        assert _run(source, dest).returncode == 0
        assert (dest / "SHA256SUMS").read_text() == first

    def test_never_prints_file_contents(self, tmp_path):
        source = _make_source_root(tmp_path)
        result = _run(source, tmp_path / "dest")
        out = result.stdout + result.stderr
        assert "artifact-content:" not in out

    def test_changed_source_refreshes_the_artifact(self, tmp_path):
        source = _make_source_root(tmp_path)
        dest = tmp_path / "dest"
        assert _run(source, dest).returncode == 0
        (source / "scripts" / "init-db.sql").write_text("NEW CONTENT\n")
        assert _run(source, dest).returncode == 0
        assert (dest / "scripts" / "init-db.sql").read_text() == "NEW CONTENT\n"
        # The manifest row changed with the content.
        manifest = (dest / "SHA256SUMS").read_text()
        assert "NEW CONTENT\n" not in manifest

    def test_directory_artifacts_keep_their_mount_identity(self, tmp_path):
        # W0.8: the stager must NEVER rm -rf + recreate a directory a
        # running container bind-mounts — docker keeps the mount attached
        # to the DELETED inode and the container sees "no such file or
        # directory" forever (the live grafana dashboards mount broke
        # after a re-stage while the stack was up). A symlink stand-in
        # for the live mount makes the contract deterministic (inode
        # numbers are reused too eagerly to compare). Content sync must
        # replace the CONTENTS through the existing path; stale content
        # is still refreshed out.
        source = _make_source_root(tmp_path)
        dest = tmp_path / "dest"
        real = tmp_path / "real-alerts"
        real.mkdir()
        (dest / "monitoring" / "prometheus").mkdir(parents=True)
        (dest / "monitoring" / "prometheus" / "alerts").symlink_to(real)
        assert _run(source, dest).returncode == 0
        target = dest / "monitoring" / "prometheus" / "alerts"
        assert target.is_symlink(), (
            "the stager replaced the staged directory — a live bind mount "
            "stays attached to the deleted inode and breaks (readdirent: "
            "no such file or directory) when the stager re-runs against "
            "a running stack"
        )
        assert (target / "high.rules").read_text() == (
            "artifact-content:monitoring/prometheus/alerts/high.rules\n"
        )


class TestDashboardProvisioningFormat:
    """W0.8 — the staged grafana dashboards must be PROVISIONING-format
    (the U.6 unwrap convention: top-level ``title``, NO ``{"dashboard":
    ...}`` API envelope). Wrapped dashboards fail the file provisioner
    ("Dashboard title cannot be empty") and its periodic re-provisioning
    retries then storm the sqlite database — the intermittent 500 class
    the post-deploy suite caught on the live stack's grafana auth path
    (locked retries exhausting after ~5 s)."""

    def test_every_dashboard_is_unwrapped_and_titled(self):
        files = sorted(DASHBOARDS_DIR.glob("*.json"))
        assert files, "no dashboard JSONs found — the pin is vacuous"
        offenders = []
        for path in files:
            try:
                doc = json.loads(path.read_text())
            except json.JSONDecodeError as exc:
                offenders.append(f"{path.name}: unparseable JSON ({exc})")
                continue
            if "dashboard" in doc and "title" not in doc:
                offenders.append(f"{path.name}: API-envelope wrapped")
                continue
            if not str(doc.get("title", "")).strip():
                offenders.append(f"{path.name}: empty title")
        assert not offenders, (
            "grafana provisioning-format violations in "
            f"monitoring/grafana/dashboards/: {offenders}. Unwrap the "
            "envelope and keep the top-level title (the U.6 convention) — "
            "wrapped dashboards keep failing provisioning every interval "
            "and storm the sqlite lock."
        )
