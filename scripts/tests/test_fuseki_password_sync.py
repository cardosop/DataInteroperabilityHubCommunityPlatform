"""Fuseki admin-password sync script tests (Phase P.1 root fix).

RED story: the upstream stain/jena-fuseki entrypoint writes shiro.ini only
when the persisted file does not exist. On a named volume the FIRST password
wins forever; rotating FUSEKI_ADMIN_PASSWORD (or an initial boot that left
the base-image literal ``admin=admin``) diverges the volume from the env
contract. Every authenticated write to ``/hub/update`` then 401s, the
semantic-service marks resources DEGRADED, and the semantic suite fails en
masse while the unauthenticated healthcheck stays green.

Measured on the P.1 full-mode run (2026-08-23): 40 semantic failures, root-
caused to ``insert_triples failed: status=401`` against a volume whose
shiro.ini still held ``admin=admin`` while the services used the env value.

GREEN: ``scripts/fuseki_password_sync.sh`` re-applies the upstream
envsubst on every start, so the volume converges to the current
ADMIN_PASSWORD. It is a no-op when the template is missing or the env
password is unset (upstream-generated random passwords stay authoritative).

No mocks: the real script is executed against synthetic FUSEKI_BASE /
FUSEKI_HOME trees. ``envsubst`` is a runtime requirement of the target
image; on hosts without it the suite skips with a reason.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SYNC_SCRIPT = REPO_ROOT / "scripts" / "fuseki_password_sync.sh"

# Minimal stand-in for /jena-fuseki/shiro.ini — same substitution token the
# upstream entrypoint envsubst's on first boot.
TEMPLATE_BODY = """# The admin password will be replaced by value of ADMIN_PASSWORD
admin=${ADMIN_PASSWORD}
/$/** = authcBasic,user[admin]
"""


def _run(env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(SYNC_SCRIPT)],
        capture_output=True,
        text=True,
        env={**os.environ, **env},
        timeout=30,
    )


@pytest.fixture
def fake_fuseki(tmp_path: Path) -> tuple[Path, Path]:
    """Return (FUSEKI_BASE, template path) with the upstream layout."""
    fuseki_home = tmp_path / "jena-fuseki"
    fuseki_base = tmp_path / "fuseki"
    fuseki_home.mkdir()
    fuseki_base.mkdir()
    template = fuseki_home / "shiro.ini"
    template.write_text(TEMPLATE_BODY)
    return fuseki_base, template


def _envsubst_available() -> bool:
    return shutil.which("envsubst") is not None


@pytest.mark.skipif(not _envsubst_available(), reason="envsubst not installed on this host")
class TestFusekiPasswordSync:
    def test_converges_stale_volume_to_env_password(self, fake_fuseki):
        """The measured P.1 defect: volume holds the old/base password."""
        base, template = fake_fuseki
        (base / "shiro.ini").write_text("admin=admin\n")

        result = _run(
            {
                "FUSEKI_BASE": str(base),
                "FUSEKI_HOME": str(template.parent),
                "ADMIN_PASSWORD": "new-secret",
            }
        )

        assert result.returncode == 0, result.stderr
        content = (base / "shiro.ini").read_text()
        assert "admin=new-secret" in content
        assert "admin=admin" not in content

    def test_idempotent_when_volume_already_synced(self, fake_fuseki):
        base, template = fake_fuseki
        (base / "shiro.ini").write_text("admin=same-secret\n")

        first = _run(
            {
                "FUSEKI_BASE": str(base),
                "FUSEKI_HOME": str(template.parent),
                "ADMIN_PASSWORD": "same-secret",
            }
        )
        second = _run(
            {
                "FUSEKI_BASE": str(base),
                "FUSEKI_HOME": str(template.parent),
                "ADMIN_PASSWORD": "same-secret",
            }
        )

        assert first.returncode == 0, first.stderr
        assert second.returncode == 0, second.stderr
        assert "admin=same-secret" in (base / "shiro.ini").read_text()

    def test_empty_env_password_leaves_existing_file_alone(self, fake_fuseki):
        """Upstream-generated random passwords stay authoritative."""
        base, template = fake_fuseki
        (base / "shiro.ini").write_text("admin=upstream-random\n")

        result = _run(
            {
                "FUSEKI_BASE": str(base),
                "FUSEKI_HOME": str(template.parent),
                "ADMIN_PASSWORD": "",
            }
        )

        assert result.returncode == 0, result.stderr
        assert (base / "shiro.ini").read_text() == "admin=upstream-random\n"

    def test_missing_template_is_a_clean_noop(self, fake_fuseki):
        base, template = fake_fuseki
        template.unlink()
        (base / "shiro.ini").write_text("admin=whatever\n")

        result = _run(
            {
                "FUSEKI_BASE": str(base),
                "FUSEKI_HOME": str(template.parent),
                "ADMIN_PASSWORD": "x",
            }
        )

        assert result.returncode == 0, result.stderr
        assert (base / "shiro.ini").read_text() == "admin=whatever\n"

    def test_missing_base_dir_fails_loudly(self, fake_fuseki):
        base, template = fake_fuseki
        shutil.rmtree(base)

        result = _run(
            {
                "FUSEKI_BASE": str(base),
                "FUSEKI_HOME": str(template.parent),
                "ADMIN_PASSWORD": "x",
            }
        )

        assert result.returncode != 0
