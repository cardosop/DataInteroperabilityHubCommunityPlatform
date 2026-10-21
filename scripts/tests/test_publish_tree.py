"""Tests for the public-tree build (Phase 313.3.5 / 313.DoD.5).

Invokes the REAL publish tree builder via subprocess (no mocks, no stubs):
the published Makefile must be byte-identical to the private repo's
``Makefile.core`` so ``make quickstart`` behaves identically from a fresh
public clone. The tree is built from the git INDEX exactly as
``publish_public.sh`` ships it.
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PUBLISH_TREE_SH = REPO_ROOT / "scripts" / "publish_tree.sh"

# The public tree ships neither ``.github/workflows/ci.yml`` (publish_tree.sh
# treats it as the PRIVATE-repo sentinel) nor ``venv/`` — so the publish-tree
# tests can only run in the private checkout. Detecting that up front turns
# what was a ``FileNotFoundError`` burst (4 of 5 tests) into one skip reason.
_PUBLIC_TREE_REASON = (
    "public checkout: .github/workflows/ci.yml does not exist — "
    "publish-tree tests build from the PRIVATE repo's git index and cannot "
    "run here"
)


def _public_tree_skip_reason() -> str | None:
    """None when this is the private repo; a reason to skip otherwise."""
    if (REPO_ROOT / ".github" / "workflows" / "ci.yml").exists():
        return None
    return _PUBLIC_TREE_REASON


def _skip_if_public_tree() -> None:
    reason = _public_tree_skip_reason()
    if reason is not None:
        pytest.skip(reason)


def _build_tree(out_dir: Path) -> Path:
    """Run the real tree builder (exclusion filter + checkout-index +
    overlay + sanitize) into ``out_dir``."""
    replace_file = out_dir.parent / "replace.txt"
    # The interpreter running THIS test is authoritative: hardcoding
    # ``REPO_ROOT/venv/bin/python`` previously exploded with FileNotFoundError
    # on any checkout that has no venv directory.
    subprocess.run(
        [sys.executable, "scripts/build_replace_text.py", "--out", str(replace_file)],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            "bash",
            "-c",
            f'source "{PUBLISH_TREE_SH}" && build_publish_tree "{out_dir}" "{replace_file}"',
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return out_dir


@pytest.fixture(scope="module")
def built_tree(tmp_path_factory):
    """Build the publish tree once per module — the build is ~12k files."""
    _skip_if_public_tree()
    return _build_tree(tmp_path_factory.mktemp("publish") / "tree")


def test_published_makefile_is_byte_identical_to_makefile_core(built_tree):
    """The public Makefile is Makefile.core — single source of truth."""
    assert (built_tree / "Makefile").read_bytes() == (REPO_ROOT / "Makefile.core").read_bytes()


def test_no_stale_makefile_duplicate_in_overlay():
    """The hand-maintained overlay Makefile drifted (stale quickstart);
    the duplicate must not exist anymore."""
    # This test needs no built tree, but the overlay path itself is
    # private-repo-only — skip alongside the tree tests on a public checkout
    # so the module reports one coherent skip reason, not a partial run.
    _skip_if_public_tree()
    assert not (REPO_ROOT / "scripts" / "publish_public_overlay" / "Makefile").exists()


def test_core_files_ship_and_paid_layer_is_absent(built_tree):
    for rel in (
        "docker-compose.yml",
        "docker-compose.core.yml",
        "docker-compose.test.yml",
        "docker-compose.test.core.yml",
        "requirements-core.txt",
        "scripts/make_dev_env.py",
        "scripts/publish_tree.sh",
        "helm/community/Chart.yaml",
        # Bind-mounted by the compose stacks — a missing re-include
        # negation here is a boot failure (313.DoD.5 round 4).
        "infrastructure/traefik/traefik.yml",
        "infrastructure/traefik/traefik.core.yml",
        "infrastructure/traefik/dynamic/routes.yml",
        "infrastructure/postgres/02-pg-hba-host.sh",
        # Test-stack observability mounts (public-clone make test-core).
        "monitoring/prometheus/prometheus-test.yml",
        "monitoring/prometheus/alerts.yml",
        "monitoring/grafana/dashboards/",
        "monitoring/alertmanager/alertmanager-test.yml",
        # GUARD-313.H — both boundary files must ship so the public CI can
        # run the guard gate.
        "scripts/core_boundary_allowlist.txt",
        "scripts/core_guard_exceptions.txt",
    ):
        assert (built_tree / rel).exists(), f"{rel} missing from publish tree"
    assert not (built_tree / "hub" / "apps" / "marketplace").exists()
    assert not (built_tree / "hub" / "apps" / "baas").exists()


def test_quickstart_uses_core_overlay_and_env_bootstrap(built_tree):
    makefile = (built_tree / "Makefile").read_text()
    assert "docker-compose.core.yml" in makefile
    assert "make_dev_env.py" in makefile
    # The stale quickstart referenced a nonexistent `redis` service.
    assert "docker compose up -d postgres redis minio" not in makefile


def test_rebuild_overwrites_stale_docker_created_directories(tmp_path_factory):
    """A previous stack boot bind-mounts files OUT of the tree; when the
    source is missing docker creates a DIRECTORY there. Rebuilding into
    that same directory must produce files again (313.DoD.5 quickstart
    churn root cause — traefik read '/etc/traefik/traefik.yml: is a
    directory' after a poisoned rebuild)."""
    _skip_if_public_tree()
    out = tmp_path_factory.mktemp("poisoned") / "tree"
    poison = out / "infrastructure" / "traefik" / "traefik.yml"
    poison.mkdir(parents=True)  # docker-created directory, not a file
    assert poison.is_dir()
    tree = _build_tree(out)
    assert (tree / "infrastructure" / "traefik" / "traefik.yml").is_file()
    assert (tree / "infrastructure" / "traefik" / "dynamic").is_dir()
    assert list((tree / "infrastructure" / "traefik" / "dynamic").iterdir())


# ---------------------------------------------------------------------------
# Phase U / U.3 — the public tree's CLI test layer must collect cleanly.
# The W18/D1 defect class: a module-level import of a paid app in
# cli/tests/ ships in the public tree (which excludes every paid app) and
# collection-errors the public sdk-cli.yml job. The guard contract is
# decision 3: paid-app test modules carry a module-level
# ``pytest.importorskip("hub.apps.<paid>")`` so they SKIP cleanly.
# ---------------------------------------------------------------------------

_PAID_MODULES = (
    "semantic",
    "marketplace",
    "billing",
    "baas",
    "rate_limiting",
    "ai",
    "ml",
    "social",
    "graphql",
    "graphql_ld",
    "graphql_graphene",
)
_PAID_IMPORT_RE = r"^(?:from|import)\s+hub\.apps\.(?:" + "|".join(_PAID_MODULES) + r")\b"


def _module_level_paid_imports(tree: Path) -> list[str]:
    """Module-level paid-app import NODES in the staged cli/tests layer.

    AST-based on purpose: a line regex false-positives on heredoc/string
    CONTENTS (the baas suites embed ``from hub.apps.baas...`` inside
    docker-exec shell scripts — runtime text, not collection-time
    imports). Only real module-level Import/ImportFrom nodes break
    collection in the public tree.
    """
    import ast

    violations: list[str] = []
    for py_file in (tree / "cli" / "tests").rglob("*.py"):
        try:
            tree_ast = ast.parse(py_file.read_text(encoding="utf-8"))
        except SyntaxError:
            continue  # collection test reports syntax separately
        for node in tree_ast.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("hub.apps."):
                        root = alias.name.split(".")[2]
                        if root in _PAID_MODULES:
                            violations.append(
                                f"{py_file.relative_to(tree)}:{node.lineno}: import {alias.name}"
                            )
            elif (
                isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.startswith("hub.apps.")
                and node.module.split(".")[2] in _PAID_MODULES
            ):
                violations.append(
                    f"{py_file.relative_to(tree)}:{node.lineno}: from {node.module} import ..."
                )
    return violations


def test_no_module_level_paid_imports_in_staged_cli_tests(built_tree):
    """The collection-error class: every module-level paid-app import in
    cli/tests would ImportError in the public tree (the paid apps are
    excluded). Paid-app test modules must importorskip instead."""
    violations = _module_level_paid_imports(built_tree)
    assert violations == [], (
        "module-level paid-app import(s) in the staged cli/tests layer — "
        "the public sdk-cli.yml job would collection-error. Guard with "
        'pytest.importorskip("hub.apps.<paid>") instead: ' + "; ".join(violations)
    )


def test_paid_import_scan_bites_on_injected_violation(built_tree):
    """RED drill: the exact defect class must be detected."""
    probe = built_tree / "cli" / "tests" / "integration" / "test_probe_paid_import.py"
    probe.write_text("from hub.apps.baas.models import APITierModel\n", encoding="utf-8")
    try:
        violations = _module_level_paid_imports(built_tree)
        assert any("test_probe_paid_import.py" in v for v in violations), (
            "the paid-import scan did not detect the injected violation"
        )
    finally:
        probe.unlink()


def test_staged_cli_tests_collect_without_errors(built_tree):
    """Integration proof: real pytest collection over the staged tree's
    cli/tests with the paid layer absent must produce zero collection
    errors. Runs with the private repo's environment (the conftest chain
    bootstraps Django core, which ships)."""
    import os

    env = dict(os.environ)
    env.setdefault("POSTGRES_HOST", "localhost")
    env.setdefault("POSTGRES_PORT", os.environ.get("POSTGRES_PORT", "5432"))
    env.setdefault("POSTGRES_USER", "meshant")
    env.setdefault("POSTGRES_PASSWORD", "meshant")
    env.setdefault("POSTGRES_DB", "meshant")
    env.setdefault("ENVIRONMENT", "test")
    # G12 (W9.2) — settings requires explicit keys in every environment and
    # the staged tree has no .env.dev (untracked by design), so the pin
    # declares inert test keys for its subprocess — the same contract as the
    # CI lint job's manage.py gates.
    env.setdefault("SECRET_KEY", "publish-tree-pin-explicit-secret-key")
    env.setdefault("JWT_SECRET_KEY", "publish-tree-pin-explicit-jwt-key")
    env.setdefault("ENCRYPTION_KEY", "publish-tree-pin-explicit-encryption-key")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "cli/tests",
            "--collect-only",
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
        ],
        cwd=built_tree,
        env=env,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    error_markers = (
        "ERROR collecting",
        "ModuleNotFoundError",
        "ImportError",
        "SyntaxError",
        "errors during collection",
        "INTERNALERROR",
        "error during collection",
        "Exit code",
    )
    errors = [
        line
        for line in (result.stdout + result.stderr).splitlines()
        if any(marker in line for marker in error_markers)
    ]
    assert result.returncode == 0, "staged cli/tests collection exited non-zero:\n" + "\n".join(
        errors[:20]
    )
    assert not errors, "staged cli/tests collection produced errors:\n" + "\n".join(errors[:20])
