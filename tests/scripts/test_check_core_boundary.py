"""GATE-29 self-tests — real script invocation against fixture trees, no mocks.

Covers the acceptance surface of openspec preprod01 313.1.11:
planted violations caught, allowlisted entries tolerated, new unallowlisted
entries fail, paid subtrees never scanned.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_core_boundary.py"


def _write(root: Path, rel: str, content: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def _manifest(root: Path, paid: list[str]) -> None:
    body = "\n".join(f'    "{m}",' for m in paid)
    _write(
        root,
        "hub/apps/manifest.py",
        "_PAID_MODULES: frozenset[str] = frozenset({\n"
        + body
        + '\n})\n'
        + 'ALL_HUB_APPS: tuple[str, ...] = ("hub.apps.core",)\n',
    )


def _run(root: Path, allowlist: Path | None = None, extra: list[str] | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SCRIPT), "--root", str(root)]
    if allowlist is not None:
        cmd += ["--allowlist", str(allowlist)]
    if extra:
        cmd += extra
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    _manifest(tmp_path, ["hub.apps.semantic", "hub.apps.marketplace"])
    allow = tmp_path / "allow.txt"
    allow.write_text("")
    return tmp_path, allow


def test_planted_violation_is_caught(tmp_path):
    root, allow = _fixture(tmp_path)
    _write(root, "hub/apps/core/somewhere.py", "from hub.apps.semantic.models import X\n")
    result = _run(root, allowlist=allow)
    assert result.returncode == 1
    assert "hub/apps/core/somewhere.py:1" in result.stdout
    assert "imports paid module: hub.apps.semantic" in result.stdout


def test_allowlisted_entry_is_tolerated(tmp_path):
    root, allow = _fixture(tmp_path)
    _write(root, "hub/apps/core/somewhere.py", "from hub.apps.semantic.models import X\n")
    allow.write_text(
        "hub/apps/core/somewhere.py:1:audited transitional entry\n"
    )
    result = _run(root, allowlist=allow)
    assert result.returncode == 0, result.stdout
    assert "1 allowlisted" in result.stdout


def test_new_unallowlisted_entry_fails(tmp_path):
    root, allow = _fixture(tmp_path)
    _write(root, "hub/apps/core/somewhere.py", "from hub.apps.semantic.models import X\n")
    _write(root, "hub/apps/core/elsewhere.py", "from hub.apps.marketplace.models import Y\n")
    allow.write_text("hub/apps/core/somewhere.py:1:audited\n")
    result = _run(root, allowlist=allow)
    assert result.returncode == 1
    assert "hub/apps/core/elsewhere.py:1" in result.stdout


def test_core_importing_core_is_clean(tmp_path):
    root, allow = _fixture(tmp_path)
    _write(root, "hub/apps/core/somewhere.py", "from hub.apps.tenants.models import Tenant\n")
    result = _run(root, allowlist=allow)
    assert result.returncode == 0, result.stdout


def test_paid_subtree_is_not_scanned(tmp_path):
    """Paid apps importing their own paid siblings are legal by construction."""
    root, allow = _fixture(tmp_path)
    _write(
        root,
        "hub/apps/semantic/views.py",
        "from hub.apps.marketplace.models import Listing\n",
    )
    result = _run(root, allowlist=allow)
    assert result.returncode == 0, result.stdout


def test_migration_fk_to_paid_model_is_caught(tmp_path):
    root, allow = _fixture(tmp_path)
    _write(
        root,
        "hub/apps/assets/migrations/0001_x.py",
        "field = models.ForeignKey(to='marketplace.Listing', on_delete=models.CASCADE)\n",
    )
    result = _run(root, allowlist=allow)
    assert result.returncode == 1
    assert "migration FK references paid model" in result.stdout
