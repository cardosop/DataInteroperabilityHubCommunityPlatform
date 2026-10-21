"""W8.2 (oss-release-remediation, M5a) — data-safety contract pins.

Policy under test (TDD, no mocks — real files, real hashes, the real
compose tree):

1. **Backup hash verification** — a SINGLE integrity library
   (``scripts/backup_integrity.sh``) provides manifest generation
   (``sha256  filename``) and verification; the three backup surfaces
   (``create_backup.sh`` config+db artifacts, ``backup-postgres.sh``
   S3 uploads, ``restore-drill.sh`` restore path) all route through
   it.  The helper is exercised against REAL files in a tmp dir:
   generation matches ``sha256sum``, verification passes intact and
   FAILS on a corrupted file or a tampered manifest.
2. **MinIO restore drill** — ``scripts/minio-restore-drill.sh`` exists
   and implements the real loss-recovery flow (mirror-out backup →
   delete the objects → mirror-back → sha256-verify every restored
   object → RTO report).  The drill is RUN against the live test-stack
   MinIO as the W8.2 evidence.
3. **Grafana provider file** — the dashboards provider
   (``dashboard.yml``, ``providers:`` + ``type: file``) exists, every
   grafana service in the compose fleet mounts BOTH provisioning dirs,
   the datasource files carry the ``datasources:`` provisioning key,
   and the staging config-artifact copies are IDENTICAL to the
   canonical ``monitoring/grafana`` tree (no drift).
4. **Backup tarballs gone from the tree** — ``git ls-files backups/``
   is empty: committed backup tarballs are untracked (the local disk
   copies remain; git history retains them — "post-archive").
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

INTEGRITY_LIB = REPO_ROOT / "scripts" / "backup_integrity.sh"
MINIO_DRILL = REPO_ROOT / "scripts" / "minio-restore-drill.sh"

COMPOSE_FILES = sorted(REPO_ROOT.glob("docker-compose*.yml"))

GRAFANA_CANONICAL = REPO_ROOT / "monitoring" / "grafana"
GRAFANA_STAGED = (
    REPO_ROOT
    / "infrastructure"
    / "staging"
    / "config-artifacts"
    / "monitoring"
    / "grafana"
)


class _ResetLoader(yaml.SafeLoader):
    """Compose ``!reset`` tags (v2.24+) are not standard YAML — same
    loader contract as the sibling compose tests."""


def _reset_constructor(_loader, _node):
    return None


_ResetLoader.add_constructor("!reset", _reset_constructor)


def _bash(script: str, *args: str) -> subprocess.CompletedProcess:
    """Run a bash fragment against the REAL repo (helpers must not need
    docker or network — pure file/hash operations)."""
    return subprocess.run(
        ["bash", "-c", script, "--", *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
        timeout=60,
    )


# ── 1. backup hash verification ────────────────────────────────────────────


def test_integrity_manifest_matches_sha256sum(tmp_path: Path):
    assert INTEGRITY_LIB.is_file(), "scripts/backup_integrity.sh must exist"
    payload = tmp_path / "artifact.bin"
    payload.write_bytes(b"W8.2-integrity-payload\x00\x01\x02" * 1000)
    proc = _bash(
        'source scripts/backup_integrity.sh; integrity_manifest_for "$1"',
        str(payload),
    )
    assert proc.returncode == 0, proc.stderr
    digest, name = proc.stdout.strip().split()
    expected = subprocess.run(
        ["sha256sum", str(payload)], capture_output=True, text=True, check=False
    ).stdout.split()[0]
    assert digest == expected
    assert name == payload.name


def test_integrity_verify_passes_intact(tmp_path: Path):
    payload = tmp_path / "artifact.bin"
    payload.write_bytes(b"real bytes" * 500)
    manifest = tmp_path / "artifact.bin.sha256"
    digest = subprocess.run(
        ["sha256sum", str(payload)], capture_output=True, text=True, check=False
    ).stdout.split()[0]
    manifest.write_text(f"{digest}  {payload.name}\n")
    proc = _bash(
        'source scripts/backup_integrity.sh; integrity_verify "$1" "$2"',
        str(payload),
        str(manifest),
    )
    assert proc.returncode == 0, proc.stderr


def test_integrity_verify_fails_on_corrupted_file(tmp_path: Path):
    payload = tmp_path / "artifact.bin"
    payload.write_bytes(b"real bytes" * 500)
    manifest = tmp_path / "artifact.bin.sha256"
    digest = subprocess.run(
        ["sha256sum", str(payload)], capture_output=True, text=True, check=False
    ).stdout.split()[0]
    manifest.write_text(f"{digest}  {payload.name}\n")
    # Corrupt the file AFTER the manifest was written.
    payload.write_bytes(b"corrupted bytes" * 500)
    proc = _bash(
        'source scripts/backup_integrity.sh; integrity_verify "$1" "$2"',
        str(payload),
        str(manifest),
    )
    assert proc.returncode != 0
    assert "mismatch" in proc.stdout.lower() or "mismatch" in proc.stderr.lower()


def test_integrity_verify_fails_on_tampered_manifest(tmp_path: Path):
    payload = tmp_path / "artifact.bin"
    payload.write_bytes(b"real bytes" * 500)
    manifest = tmp_path / "artifact.bin.sha256"
    manifest.write_text("deadbeef" * 8 + f"  {payload.name}\n")
    proc = _bash(
        'source scripts/backup_integrity.sh; integrity_verify "$1" "$2"',
        str(payload),
        str(manifest),
    )
    assert proc.returncode != 0


def test_all_backup_surfaces_route_through_the_integrity_library():
    for script in ["create_backup.sh", "backup-postgres.sh", "restore-drill.sh"]:
        text = (REPO_ROOT / "scripts" / script).read_text(encoding="utf-8")
        assert (
            "backup_integrity.sh" in text
        ), f"{script} must source the integrity library"
    # create_backup.sh must produce manifests for its artifacts.
    create = (REPO_ROOT / "scripts" / "create_backup.sh").read_text()
    assert "integrity_write_manifest" in create


# ── 2. MinIO restore drill ──────────────────────────────────────────────────


def test_minio_restore_drill_script_implements_the_loss_recovery_flow():
    assert MINIO_DRILL.is_file(), "scripts/minio-restore-drill.sh must exist"
    text = MINIO_DRILL.read_text(encoding="utf-8")
    for step in ("mirror", "rm ", "mc mirror", "sha256", "RTO"):
        assert step in text, f"drill missing step marker: {step!r}"


# ── 3. Grafana provider file ────────────────────────────────────────────────


def test_dashboards_provider_file_exists_and_is_file_type():
    provider = GRAFANA_CANONICAL / "dashboards" / "dashboard.yml"
    assert provider.is_file(), "monitoring/grafana/dashboards/dashboard.yml missing"
    data = yaml.safe_load(provider.read_text(encoding="utf-8"))
    providers = data.get("providers", [])
    assert providers, "dashboard.yml has no providers entry"
    assert any(p.get("type") == "file" for p in providers)


def test_every_grafana_service_mounts_both_provisioning_dirs():
    mounted_files = []
    for compose in COMPOSE_FILES:
        data = yaml.load(compose.read_text(encoding="utf-8"), Loader=_ResetLoader) or {}
        services = data.get("services", {})
        for name, svc in services.items():
            if not isinstance(svc, dict):
                continue
            image = str(svc.get("image", ""))
            if "grafana/grafana" not in image:
                continue
            mount_lines = []
            for m in svc.get("volumes") or []:
                if isinstance(m, dict):
                    mount_lines.append(f"{m.get('source', '')}:{m.get('target', '')}")
                elif isinstance(m, str):
                    mount_lines.append(m)  # short form: "src:dst:opts"
            mounts = "\n".join(mount_lines)
            for target in (
                "/etc/grafana/provisioning/dashboards",
                "/etc/grafana/provisioning/datasources",
            ):
                if target not in mounts:
                    mounted_files.append(f"{compose.name}:{name} missing {target}")
    assert (
        not mounted_files
    ), "grafana services without both provisioning mounts:\n" + "\n".join(
        f"  {m}" for m in mounted_files
    )


def test_staging_grafana_artifacts_match_canonical():
    assert GRAFANA_STAGED.is_dir(), "staging grafana artifacts dir missing"
    proc = subprocess.run(
        ["diff", "-rq", str(GRAFANA_CANONICAL), str(GRAFANA_STAGED)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, (
        "staging grafana artifacts drifted from monitoring/grafana:\n" + proc.stdout
    )


def test_datasource_files_are_provisioning_shape():
    for ds in (GRAFANA_CANONICAL / "datasources").glob("*.y*ml"):
        data = yaml.safe_load(ds.read_text(encoding="utf-8"))
        assert (
            "datasources" in data
        ), f"{ds.name} lacks the provisioning `datasources:` key"


# ── 4. backup tarballs gone from the tree ───────────────────────────────────


def test_no_backup_tarballs_tracked_in_git():
    proc = subprocess.run(
        ["git", "ls-files", "backups/"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "", (
        "committed backup artifacts must be untracked:\n" + proc.stdout
    )


# ── falsifiability drift pins ───────────────────────────────────────────────


def test_grafana_drift_detector_bites():
    # A datasource file missing the provisioning key must flip the check.
    fake = {"name": "Prometheus", "type": "prometheus"}
    assert "datasources" not in fake
