"""
P3-1 (close-oss-release-conditions, B-1) — estate-migration-surgery pins.

The condition: ``warehouses.0007`` (the estate-FK split — two FKs from
``WarehouseConnection`` to ``databricks_admin`` models) hard-depends on
``databricks_admin.0005`` and adds the FKs unconditionally. In the
core-only (public) tree ``databricks_admin`` is not installed, so the
migration graph cannot build — ``NodeNotFoundError`` at every
``migrate``/``makemigrations`` in core mode (the W9.2 stranger-path
signature; the W7.3 public-CI 8th job's blocker). The model itself
already carries the 313.1 conditional-paid-FK contract
(``if not HUB_CORE_ONLY:`` around the fields) — the surgery makes 0007
the migration twin of that contract: the estate FK adds + the
cross-app dependency exist only when ``databricks_admin`` is
installed.

Pins, each at the weakest point (no mocks — the real migration graph
through real ``manage.py`` subprocesses):

1. **The dual-path contract** — 0007's dependency list must not
   hard-reference ``databricks_admin``; the estate FK adds are gated
   on ``apps.is_installed("databricks_admin")`` (the structural
   regression shape).
2. **The real graph** — ``manage.py migrate --plan`` builds in BOTH
   modes: core-only (exit 0, 0007 in the plan) and full (exit 0,
   0007 + the databricks_admin chain in the plan).
3. **The autodetector** — ``makemigrations --check --dry-run`` stays
   "No changes detected" in BOTH modes (a conditional migration that
   mismatches its model's state in either mode would drift here).
4. **The boot smoke** — ``scripts/core_boot_smoke.py`` (the public
   CI's core-boot-smoke job substance) stays green.

The real-DB drills (fresh-DB chain both modes + clone → reverse →
forward on an estate clone) are the one-shot execution legs recorded
in the P3-1 evidence, not always-on pins (dedicated-DB drills are
operator-run by the repo convention).
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

scripts_dir = Path(__file__).parent.parent
ROOT = scripts_dir.parent
sys.path.insert(0, str(ROOT))

MIGRATION = (
    ROOT / "hub/apps/warehouses/migrations/"
    "0007_warehouseconnection_databricks_credential_and_more.py"
)
MANAGE = ROOT / "hub/manage.py"
BOOT_SMOKE = scripts_dir / "core_boot_smoke.py"

_STEP_TIMEOUT = 240


def _base_env() -> dict:
    """The G12 explicit-config env block: everything the settings
    import requires comes verbatim (the host recipe exports the real
    POSTGRES_* values — see docs/runbooks/HOST_SIDE_VERIFICATION.md;
    on a runner without a postgres the settings probe warns and goes
    lazy, the same behavior the existing manage.py gates rely on)."""
    env = dict(os.environ)
    env.setdefault("ENVIRONMENT", "test")
    env.setdefault("POSTGRES_HOST", "localhost")
    env.setdefault("POSTGRES_PORT", "5432")
    env.setdefault("POSTGRES_USER", "hub")
    env.setdefault("POSTGRES_PASSWORD", "hub")
    env.setdefault("POSTGRES_DB", "hub")
    env.setdefault("REDIS_URL", "redis://:pin@127.0.0.1:6379/0")
    env.setdefault("REDIS_CACHE_URL", "redis://:pin@127.0.0.1:6379/13")
    env.setdefault("REDIS_QUEUE_URL", "redis://:pin@127.0.0.1:6379/0")
    return env


def _manage(*argv: str, core_only: bool = False) -> subprocess.CompletedProcess[str]:
    env = _base_env()
    if core_only:
        env["HUB_CORE_ONLY"] = "1"
    return subprocess.run(
        [sys.executable, str(MANAGE), *argv],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=_STEP_TIMEOUT,
        env=env,
        check=False,
    )


# ── 1. The dual-path contract ───────────────────────────────────────────────


def test_0007_dual_path_contract():
    """The structural regression shape: 0007's unconditional dependency
    list must not reference databricks_admin, and the estate FK adds
    must ride behind ``apps.is_installed("databricks_admin")`` (the
    313.1 conditional-paid-FK contract's migration twin)."""
    src = MIGRATION.read_text(encoding="utf-8")
    tree = ast.parse(src)
    assert '"databricks_admin"' in src, "the FK targets must stay"
    assert "apps.is_installed" in src, (
        "the estate FK adds must be gated on databricks_admin being "
        "installed — the migration twin of the model's conditional contract"
    )
    assert "databricks_admin.databrickscredential" in src
    assert "databricks_admin.databricksworkspace" in src
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "is_installed"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            assert node.args[0].value == "hub.apps.databricks_admin", (
                "apps.is_installed() matches the AppConfig NAME (the full "
                "dotted path) — the label form is always False and would "
                "silently no-op this migration on estate databases"
            )
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "dependencies"
        ):
            continue
        for elt in node.value.elts:  # type: ignore[attr-defined]
            if (
                isinstance(elt, ast.Tuple)
                and len(elt.elts) == 2
                and isinstance(elt.elts[0], ast.Constant)
                and elt.elts[0].value == "databricks_admin"
            ):
                raise AssertionError(
                    "0007 hard-depends on databricks_admin — a core-only "
                    "graph cannot build (the NodeNotFoundError shape)"
                )


# ── 2. The real graph ───────────────────────────────────────────────────────


def test_core_only_migration_graph_builds():
    """The exact blocked step of the public CI's test-core job and the
    quickstart api migrate: core-only ``migrate --plan`` must build the
    graph (no NodeNotFoundError). Plan CONTENT is not asserted — a
    fully-migrated database shows no planned operations; the graph
    build is the contract."""
    result = _manage("migrate", "--plan", core_only=True)
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-800:]
    assert "NodeNotFoundError" not in result.stderr + result.stdout


def test_core_only_sqlmigrate_0007_is_a_noop():
    """In core mode the estate FK adds must not render — 0007's SQL is
    empty of ADD COLUMN (the conditional ops, proven behaviorally
    through the real sqlmigrate renderer)."""
    result = _manage("sqlmigrate", "warehouses", "0007", core_only=True)
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-800:]
    assert "ADD COLUMN" not in result.stdout, (
        "a core-only render must not add the estate FKs"
    )


def test_full_mode_sqlmigrate_0007_adds_the_estate_fks():
    """On an estate-installed database the render keeps the two FK
    adds (the full-mode invariant)."""
    result = _manage("sqlmigrate", "warehouses", "0007")
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-800:]
    assert "ADD COLUMN" in result.stdout
    assert "databricks_credential" in result.stdout
    assert "databricks_workspace" in result.stdout


def test_full_mode_migration_graph_builds():
    """The estate-installed graph still builds (the databricks_admin
    chain resolves in full mode)."""
    result = _manage("migrate", "--plan")
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-800:]
    assert "NodeNotFoundError" not in result.stderr + result.stdout


# ── 3. The autodetector ─────────────────────────────────────────────────────


def test_makemigrations_check_clean_full_mode():
    result = _manage("makemigrations", "--check", "--dry-run")
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-800:]
    assert "No changes detected" in result.stdout


def test_makemigrations_check_clean_core_mode():
    result = _manage("makemigrations", "--check", "--dry-run", core_only=True)
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-800:]
    assert "No changes detected" in result.stdout


# ── 4. The boot smoke ───────────────────────────────────────────────────────


def test_core_boot_smoke_green():
    """The public CI's core-boot-smoke job substance (check + help +
    sampled commands under HUB_CORE_ONLY=1) stays green."""
    env = _base_env()
    env["HUB_CORE_ONLY"] = "1"
    result = subprocess.run(
        [sys.executable, str(BOOT_SMOKE)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=_STEP_TIMEOUT,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-800:]


def test_makefile_and_lint_list_wiring():
    lint = (ROOT / ".github/workflows/_reusable.lint.yml").read_text(
        encoding="utf-8"
    )
    assert "scripts/tests/test_p31_estate_migration_surgery.py" in lint


def test_conftest_paid_regex_covers_manifest_paid_modules():
    """The root conftest's ``_PAID_MODULE_IMPORT_RE`` must cover every
    ``_PAID_MODULES`` manifest entry (its own "keep in sync" contract).
    The W7.3 manifest addition (databricks_admin) never propagated to
    the conftest — core-mode collection imported the estate models
    (``RuntimeError: Model class hub.apps.databricks_admin... isn't in
    an application in INSTALLED_APPS``), 93 collection errors on the
    exact core-only leg this condition unblocks."""
    conftest_src = (ROOT / "conftest.py").read_text(encoding="utf-8")
    conftest_tree = ast.parse(conftest_src)
    manifest_src = (ROOT / "hub/apps/manifest.py").read_text(encoding="utf-8")
    manifest_tree = ast.parse(manifest_src)

    regex_source = ""
    for node in ast.walk(conftest_tree):
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "_PAID_MODULE_IMPORT_RE"
            and isinstance(node.value, ast.Call)
        ):
            regex_source = node.value.args[0].value  # type: ignore[union-attr]
    assert regex_source, "the conftest paid-module regex must exist"

    paid_modules: set[str] = set()
    for node in ast.walk(manifest_tree):
        target_name = None
        value = None
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            target_name, value = node.targets[0].id, node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target_name, value = node.target.id, node.value
        if (
            target_name == "_PAID_MODULES"
            and isinstance(value, ast.Call)
            and value.args
        ):
            for elt in value.args[0].elts:  # type: ignore[union-attr]
                if isinstance(elt, ast.Constant):
                    paid_modules.add(elt.value.rsplit(".", 1)[-1])
    assert paid_modules, "the manifest paid-module set must exist"

    missing = sorted(m for m in paid_modules if m not in regex_source)
    assert not missing, (
        f"conftest paid-module regex misses manifest modules: {missing} — "
        "core-mode collection imports paid models and errors out"
    )


def test_by_name_estate_command_calls_are_installed_guarded():
    """Every ``call_command("seed_e2e_uc_mirror", ...)`` OUTSIDE the
    estate app must sit behind an ``apps.is_installed(
    "hub.apps.databricks_admin")`` guard in the same function — the
    quickstart seed chain (seed_demo_data → ensure_e2e_user_roles →
    seed_e2e_uc_mirror) crashed core mode with ``CommandError: Unknown
    command 'seed_e2e_uc_mirror'`` because the by-name invocation was
    gated on a tenant FLAG, not on the app being installed (the
    string-reference seam is invisible to the import-direction
    gates)."""
    violations: list[str] = []
    for path in sorted((ROOT / "hub/apps").rglob("*.py")):
        if "databricks_admin" in path.parts or "/tests/" in str(path):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            calls = [
                node
                for node in ast.walk(func)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "call_command"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == "seed_e2e_uc_mirror"
            ]
            guards = [
                node
                for node in ast.walk(func)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "is_installed"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == "hub.apps.databricks_admin"
            ]
            for call in calls:
                if not any(guard.lineno < call.lineno for guard in guards):
                    violations.append(
                        f"{path.relative_to(ROOT)}:{call.lineno}"
                    )
    assert not violations, (
        f"unguarded by-name estate-command calls: {violations} — core "
        "mode raises CommandError on the quickstart seed path"
    )
