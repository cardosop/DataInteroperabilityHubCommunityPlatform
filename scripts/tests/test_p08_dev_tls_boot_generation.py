"""P0-8 (close-oss-release-conditions, H-4) — dev TLS keys: boot generation.

The pre-fix state: six TLS artifacts (three PRIVATE KEYS included) were
committed under ``infrastructure/postgres/certs/`` for the
docker-compose.production.yml stack, and the compose file told operators
to run ``ssl-setup.sh`` BY HAND before first boot — a manual step that
silently degrades (no certs → postgres starts without SSL, per
04-ssl-copy.sh's warning path) and keeps key material in git.

The fix contract (all text/git-based, Django-free, CI lint tier):

1. No TLS artifact — key or cert — is tracked under the dev certs dir;
   the dir itself is gitignored so generated material can never be
   re-committed (the regrowth blocker).
2. The dev certs are generated AT BOOT, idempotently, by the canonical
   ``infrastructure/postgres/ssl-setup.sh`` (no --force — a fresh set is
   skipped), executed by a one-shot init service in
   docker-compose.production.yml that both postgres and pgbouncer
   depend on (``service_completed_successfully``) — every bring-up path
   (compose up, Makefile, scripts) gets certs without a manual step.
3. No production/helm path references the dev certs dir — helm's
   postgres is AWS RDS and pgbouncer gets its TLS material from
   Kubernetes secrets; the dev dir must stay a compose-only concern.
4. The runbook documents the boot generation + regeneration + the
   never-commit-keys contract.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
COMPOSE = REPO_ROOT / "docker-compose.production.yml"
GITIGNORE = REPO_ROOT / ".gitignore"
CERTS_DIR = "infrastructure/postgres/certs"
SSL_SETUP = "infrastructure/postgres/ssl-setup.sh"
RUNBOOK = REPO_ROOT / "docs" / "runbooks" / "postgres-tls-dev-certs.md"
HELM_DIR = REPO_ROOT / "helm"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "tests"))


def _git(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args], capture_output=True, text=True, cwd=str(REPO_ROOT), check=False
    )
    assert proc.returncode == 0, f"git {' '.join(args)} failed: {proc.stderr}"
    return proc.stdout


def test_no_tls_artifact_is_tracked_under_the_dev_certs_dir():
    tracked = _git("ls-files", CERTS_DIR).split()
    assert tracked == [], (
        "the dev TLS artifacts must be GENERATED-ONLY (no committed keys or "
        f"certs) — still tracked: {tracked}"
    )


def test_certs_dir_is_gitignored():
    ignore = GITIGNORE.read_text(encoding="utf-8")
    assert f"{CERTS_DIR}/" in ignore, (
        f".gitignore must cover {CERTS_DIR}/ — generated material must "
        "never be re-committed (the regrowth blocker)"
    )


def test_boot_generation_service_runs_the_canonical_script_idempotently():
    compose = COMPOSE.read_text(encoding="utf-8")
    assert "tls-certs-init:" in compose, (
        "docker-compose.production.yml must carry the boot-generation service"
    )
    init_block = compose.split("tls-certs-init:", 1)[1]
    init_block = init_block.split("\n  postgres:", 1)[0] if "\n  postgres:" in init_block else init_block
    assert SSL_SETUP in init_block, (
        "the boot-generation service must run the CANONICAL ssl-setup.sh "
        "(no duplicated generation logic)"
    )
    assert "--force" not in init_block, (
        "the boot run must be IDEMPOTENT — a --force regeneration on every "
        "boot would churn the CA on every stack start"
    )
    # The postgres copy step reads the keys as UID 70 — the init service
    # must hand the generated artifacts to the postgres user.
    assert "chown" in init_block, (
        "the generated artifacts must be chown'd to the postgres user"
    )
    assert "70" in init_block, (
        "the chown target must be the postgres user (UID 70) so "
        "04-ssl-copy.sh can read the 0600 keys"
    )


def test_postgres_and_pgbouncer_wait_for_the_boot_generation():
    compose = COMPOSE.read_text(encoding="utf-8")
    for service in ("postgres", "pgbouncer"):
        block = compose.split(f"  {service}:", 1)[1]
        block = block.split("\n  ", 1)[1] if "\n  " in block else block
        # The service's depends_on must gate on the init service COMPLETING
        # (not merely starting) — certs must exist before postgres initdb
        # runs 04-ssl-copy.sh.
        assert "tls-certs-init" in block, (
            f"{service}: must depends_on the tls-certs-init boot generation"
        )
        assert "service_completed_successfully" in block, (
            f"{service}: the gate must be service_completed_successfully — "
            "the copy step would otherwise race the generation"
        )


def test_no_helm_or_production_path_references_the_dev_cert_dir():
    for path in sorted(HELM_DIR.rglob("*")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        assert CERTS_DIR not in text, (
            f"helm artifact {path.relative_to(REPO_ROOT)} references the dev "
            "certs dir — production TLS must come from Kubernetes secrets"
        )
        assert "/etc/postgresql/tls" not in text, (
            f"helm artifact {path.relative_to(REPO_ROOT)} mounts the dev "
            "postgres TLS path — production postgres is AWS RDS"
        )


def test_runbook_documents_the_boot_generation():
    assert RUNBOOK.is_file(), "docs/runbooks/postgres-tls-dev-certs.md missing"
    text = RUNBOOK.read_text(encoding="utf-8")
    assert "ssl-setup.sh" in text, "the runbook must name the generator"
    assert "--force" in text, "the runbook must document forced regeneration"
    assert "git" in text, "the runbook must carry the never-commit-keys contract"
    assert "commit" in text, "the runbook must carry the never-commit-keys contract"
