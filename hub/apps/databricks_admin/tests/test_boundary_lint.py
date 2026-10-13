"""TDD pins for the P12 boundary-lint contract (openspec
add-databricks-ml-assets task 12.5) — the Databricks estate imports
ZERO code from the paid apps (`ml`/`ai` first among them), and the
spec's "boundary checker stays green" scenario holds.

- The AST pin walks EVERY estate .py file (services, models, tests,
  migrations, fixtures) at ANY nesting level and reports any
  `from hub.apps.<paid> ...` / `import hub.apps.<paid>` node — plus
  the `from hub.apps import <paid>` alias form the checker's
  module-prefix match misses (the pin is a superset, never a subset).
- The schema-isolation pin covers the estate's migrations for
  `to='<paid>.'` FK references (the checker's third invariant).
- The gate pins run the REAL `scripts/check_core_boundary.py` — the
  same command GATE-29 runs in CI — asserting the gate exits green
  and reports ZERO estate violations.
- The injected-violation pin proves the suite is NOT vacuous: a paid
  import planted inside the estate is reported by the in-process AST
  collector AND makes the REAL gate fail (rc 1) in its scoped
  pre-commit mode — then the file is removed.

No mocks: the REAL manifest membership (`hub.apps.manifest`), the
REAL estate tree on disk, and the REAL gate script via subprocess —
the same invocation CI uses.
"""

from __future__ import annotations

import ast
import pathlib
import re
import subprocess
import sys

import pytest

from hub.apps.manifest import _PAID_MODULES

pytestmark = pytest.mark.unit

_ESTATE_DIR = pathlib.Path(__file__).resolve().parents[1]  # hub/apps/databricks_admin
_REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]  # the repository root
_GATE = _REPO_ROOT / "scripts" / "check_core_boundary.py"

_PAID_FULL = sorted(_PAID_MODULES)
_PAID_SHORT = {m.rsplit(".", 1)[-1] for m in _PAID_MODULES}

# The checker's migration FK pattern, derived from the manifest (never
# a hand-maintained copy of the paid-app list).
_PAID_LABEL_RE = re.compile(r"\bto\s*=\s*['\"](?:" + "|".join(sorted(_PAID_SHORT)) + r")\.")


def _estate_py_files() -> list[pathlib.Path]:
    return sorted(p for p in _ESTATE_DIR.rglob("*.py") if "__pycache__" not in p.parts)


def _paid_import_sites(
    files: list[pathlib.Path],
) -> list[tuple[str, int, str]]:
    """(repo-relpath, lineno, module) for every paid import at ANY nesting
    level — mirrors the checker's scan, plus the alias form."""
    sites: list[tuple[str, int, str]] = []
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError):
            continue
        rel = str(path.relative_to(_REPO_ROOT))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                paid = any(node.module == m or node.module.startswith(m + ".") for m in _PAID_FULL)
                if not paid and node.module in ("hub.apps", "hub"):
                    # `from hub.apps import ml` — the checker's module-prefix
                    # match misses this alias form; the pin must not.
                    paid = any(alias.name in _PAID_SHORT for alias in node.names)
                if paid:
                    sites.append((rel, node.lineno, node.module))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if any(alias.name == m or alias.name.startswith(m + ".") for m in _PAID_FULL):
                        sites.append((rel, node.lineno, alias.name))
    return sites


def _run_gate(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_GATE), *args],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


class TestEstateBoundary:
    """The estate tree carries zero paid imports and zero paid model
    references — the design D4 constraint, proven on disk."""

    def test_the_estate_imports_zero_paid_modules(self):
        sites = _paid_import_sites(_estate_py_files())
        assert not sites, "paid-import sites inside the Databricks estate:\n" + "\n".join(
            f"  {rel}:{lineno}: {module}" for rel, lineno, module in sites
        )

    def test_the_estate_migrations_reference_no_paid_models(self):
        offenders: list[tuple[str, int, str]] = []
        for path in _estate_py_files():
            if "/migrations/" not in str(path):
                continue
            for lineno, line in enumerate(path.read_text().splitlines(), 1):
                if _PAID_LABEL_RE.search(line):
                    offenders.append((str(path.relative_to(_REPO_ROOT)), lineno, line.strip()[:90]))
        assert not offenders, "paid-model FK references inside estate migrations:\n" + "\n".join(
            f"  {rel}:{lineno}: {line}" for rel, lineno, line in offenders
        )


class TestTheBoundaryGate:
    """The REAL gate — the same command GATE-29 runs in CI — stays green
    and reports zero estate violations (the spec's WHEN/THEN)."""

    def test_the_boundary_checker_runs_green(self):
        result = _run_gate()
        assert result.returncode == 0, result.stdout + result.stderr

    def test_the_boundary_checker_reports_no_estate_violations(self):
        result = _run_gate("--list")
        assert result.returncode == 0, result.stdout + result.stderr
        estate_lines = [line for line in result.stdout.splitlines() if "databricks_admin/" in line]
        assert not estate_lines, "the boundary checker reports estate violations:\n" + "\n".join(
            estate_lines
        )


class TestThePinIsNotVacuous:
    """A paid import planted inside the estate is reported by the AST
    collector AND fails the REAL gate — the suite catches the violation
    class it exists to forbid."""

    def test_the_gate_fails_on_an_injected_estate_import(self):
        injected = _ESTATE_DIR / "tests" / "_boundary_violation_injected.py"
        injected.write_text(
            "from hub.apps.ml.models import MLModel  # noqa: F401 — the injected boundary violation\n"
        )
        try:
            sites = _paid_import_sites([injected])
            assert any(
                rel.endswith("_boundary_violation_injected.py") and module.startswith("hub.apps.ml")
                for rel, _lineno, module in sites
            ), f"the AST collector missed the injected import: {sites!r}"

            result = _run_gate(
                "--paths", "hub/apps/databricks_admin/tests/_boundary_violation_injected.py"
            )
            assert result.returncode == 1, (
                "the scoped gate must FAIL on the injected import:\n"
                + result.stdout
                + result.stderr
            )
            assert "_boundary_violation_injected.py" in result.stdout, (
                "the scoped gate must name the injected file:\n" + result.stdout
            )
        finally:
            injected.unlink(missing_ok=True)
