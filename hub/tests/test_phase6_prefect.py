"""
Phase 6 — Verify that Prefect internal monkey-patches have not been introduced.

arch-improvements-01 Phase 6 requires that the integration with Prefect is done
through the documented public API (PREFECT_API_URL, K8s job infrastructure) and
not by patching internal Prefect module attributes at runtime.

The patterns blocked are attribute assignments on:
  - prefect.flow_runs.*
  - prefect.deployments.*
  - prefect.workers.*
  - prefect.settings.*

These assignments (``prefect.settings.PREFECT_API_URL = …``) are a
maintenance hazard: they bind the code to undocumented Prefect internals that
can move or be removed without notice.  The correct approach is to pass values
via environment variables or the official Prefect client constructor.
"""

import ast
import pathlib

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PATCH_PREFIXES = (
    "prefect.flow_runs.",
    "prefect.deployments.",
    "prefect.workers.",
    "prefect.settings.",
)

_HUB_ROOT = pathlib.Path(__file__).parent.parent  # …/hub/


def _find_monkey_patches(path: pathlib.Path) -> list[str]:
    """Return a list of '<file>:<lineno>: <target>' strings for every
    detected Prefect monkey-patch assignment found under *path*.
    """
    violations: list[str] = []
    for py_file in sorted(path.rglob("*.py")):
        # Skip test files — a test that *checks* for a patch is allowed to
        # reference the pattern as a string literal.
        if py_file.name.startswith("test_"):
            continue
        try:
            source = py_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        # Quick string pre-filter to avoid AST-parsing every file.
        if not any(p in source for p in _PATCH_PREFIXES):
            continue

        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                try:
                    target_src = ast.unparse(target)
                except Exception:  # pragma: no cover — defensive
                    continue
                if any(target_src.startswith(p) for p in _PATCH_PREFIXES):
                    violations.append(
                        f"{py_file.relative_to(_HUB_ROOT)}:{node.lineno}: {target_src}"
                    )

    return violations


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNoPrefectMonkeyPatches:
    """The hub/ codebase must not monkey-patch Prefect internals."""

    def test_no_prefect_flow_runs_patches(self):
        """No assignments to prefect.flow_runs.* are permitted."""
        violations = [
            v
            for v in _find_monkey_patches(_HUB_ROOT)
            if v.split(": ", 1)[-1].startswith("prefect.flow_runs.")
        ]
        assert not violations, (
            "Prefect monkey-patches on prefect.flow_runs must not exist "
            "(arch-improvements-01 Phase 6):\n" + "\n".join(violations)
        )

    def test_no_prefect_deployments_patches(self):
        """No assignments to prefect.deployments.* are permitted."""
        violations = [
            v
            for v in _find_monkey_patches(_HUB_ROOT)
            if v.split(": ", 1)[-1].startswith("prefect.deployments.")
        ]
        assert not violations, (
            "Prefect monkey-patches on prefect.deployments must not exist "
            "(arch-improvements-01 Phase 6):\n" + "\n".join(violations)
        )

    def test_no_prefect_workers_patches(self):
        """No assignments to prefect.workers.* are permitted."""
        violations = [
            v
            for v in _find_monkey_patches(_HUB_ROOT)
            if v.split(": ", 1)[-1].startswith("prefect.workers.")
        ]
        assert not violations, (
            "Prefect monkey-patches on prefect.workers must not exist "
            "(arch-improvements-01 Phase 6):\n" + "\n".join(violations)
        )

    def test_no_prefect_settings_patches(self):
        """No assignments to prefect.settings.* are permitted."""
        violations = [
            v
            for v in _find_monkey_patches(_HUB_ROOT)
            if v.split(": ", 1)[-1].startswith("prefect.settings.")
        ]
        assert not violations, (
            "Prefect monkey-patches on prefect.settings must not exist "
            "(arch-improvements-01 Phase 6):\n" + "\n".join(violations)
        )

    def test_no_prefect_internal_patches_combined(self):
        """Aggregate test — any of the four blocked namespaces must be absent."""
        violations = _find_monkey_patches(_HUB_ROOT)
        assert not violations, (
            "Prefect internal monkey-patches detected "
            "(arch-improvements-01 Phase 6 requires removal):\n" + "\n".join(violations)
        )
