"""GATE-38 TDD suite (Phase P.2b).

The gate exists because the runtime seam test (P.2a) only runs in the paid
suite: a deleted ``set_*`` call in a paid ``AppConfig.ready()`` must ALSO
fail in public/core CI, where the paid test files do not exist.

No mocks: synthetic trees are parsed by the REAL checker
(``check_paid_ready_registrations.collect_violations``) against the REAL
``HOOK_API_CONTRACT``. The synthetic manifest mirrors the real one's shape
(``_PAID_MODULES`` frozenset + ``ALL_HUB_APPS`` tuple) so the shared
``_read_paid_modules`` reader from ``check_core_boundary.py`` applies
unchanged — one manifest reader for both gates by construction.

RED drills (guard-the-guard):
- removing a ``set_*`` call from a paid apps.py → "invoked by no paid
  apps.py" violation naming the setter;
- renaming a setter → violations in BOTH directions (the new name is
  unlisted; the old contract row is orphaned);
- a paid module without apps.py → structural violation.
GREEN: a clean synthetic tree with every contract setter invoked
somewhere passes with zero violations.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from check_paid_ready_registrations import (
    _contract_setters,
    collect_violations,
)

#: Sentinel marker the synthetic apps.py files use so each fixture body can
#: be produced without string-escaping the real setter list.
_SET_CALLS = "\n".join(
    f"        {name}(lambda *a, **k: None)" for name in sorted(_contract_setters())
)


def _write_manifest(root: Path, paid_modules: list[str]) -> None:
    hub_apps = root / "hub" / "apps"
    hub_apps.mkdir(parents=True, exist_ok=True)
    (hub_apps / "__init__.py").write_text("")
    # Both containers must be literal expressions — _read_paid_modules
    # evaluates them with ast.literal_eval (no name references allowed),
    # mirroring the real manifest's shape.
    (hub_apps / "manifest.py").write_text(
        "from __future__ import annotations\n"
        f"_PAID_MODULES = frozenset({paid_modules!r})\n"
        f"ALL_HUB_APPS = {tuple(paid_modules)!r}\n"
    )


def _write_apps_py(root: Path, module: str, body: str) -> None:
    path = root / module.replace(".", "/") / "apps.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    # Every name the body CALLS must be imported from the hooks module, or
    # the checker (correctly) does not count it as a hooks invocation. The
    # body lines arrive indented for a method scope, so parse them inside a
    # synthetic method to discover the called names.
    import ast

    called_names = sorted(
        {
            node.func.id
            for node in ast.walk(ast.parse("def _body():\n" + body))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
    )
    import_lines = ",\n".join(f"            {name}" for name in called_names)
    path.write_text(
        "from __future__ import annotations\n"
        "from django.apps import AppConfig\n"
        "\n"
        "class AppConfigShim(AppConfig):\n"
        "    def ready(self):\n"
        "        from hub.apps.core.commercial_hooks import (\n" + import_lines + ",\n"
        "        )\n" + body + "\n"
    )


@pytest.fixture
def clean_tree(tmp_path: Path) -> Path:
    """Synthetic tree whose paid apps invoke EVERY contract setter."""
    _write_manifest(tmp_path, ["hub.apps.marketplace"])
    _write_apps_py(tmp_path, "hub.apps.marketplace", _SET_CALLS)
    return tmp_path


class TestGate38:
    def test_clean_tree_passes(self, clean_tree):
        assert collect_violations(clean_tree) == []

    def test_removed_setter_call_is_flagged(self, clean_tree):
        """RED — the exact dropped-registration class P.2 exists to catch."""
        stripped = "\n".join(
            line for line in _SET_CALLS.splitlines() if "set_entitlement_provider" not in line
        )
        _write_apps_py(clean_tree, "hub.apps.marketplace", stripped)

        violations = collect_violations(clean_tree)

        assert any(
            "set_entitlement_provider" in v and "invoked by no paid apps.py" in v
            for v in violations
        ), violations

    def test_renamed_setter_is_flagged_in_both_directions(self, clean_tree):
        """RED — a renamed setter orphans its contract row AND is unlisted."""
        renamed = _SET_CALLS.replace("set_entitlement_provider(", "set_entitlement_provider_v2(")
        _write_apps_py(clean_tree, "hub.apps.marketplace", renamed)

        violations = collect_violations(clean_tree)

        assert any(
            "set_entitlement_provider_v2" in v and "no HOOK_API_CONTRACT row" in v
            for v in violations
        ), violations
        assert any(
            "set_entitlement_provider" in v and "invoked by no paid apps.py" in v
            for v in violations
        ), violations

    def test_paid_module_without_apps_py_is_flagged(self, tmp_path):
        _write_manifest(tmp_path, ["hub.apps.semantic", "hub.apps.marketplace"])
        _write_apps_py(tmp_path, "hub.apps.marketplace", _SET_CALLS)

        violations = collect_violations(tmp_path)

        assert any("hub.apps.semantic" in v and "no apps.py" in v for v in violations)

    def test_runtime_keyed_factory_call_is_not_flagged(self, clean_tree):
        """``register_service_client_factory`` has no constant registry key
        but IS a legitimate paid ready() call — regression pin for the
        real-tree false positive found on first run."""
        _write_apps_py(
            clean_tree,
            "hub.apps.marketplace",
            _SET_CALLS + "\n        register_service_client_factory('X', lambda: None)",
        )

        violations = collect_violations(clean_tree)

        assert all("register_service_client_factory" not in v for v in violations)

    def test_real_tree_has_zero_violations(self):
        """The committed tree must stay clean — this is the CI gate itself."""
        real_root = Path(__file__).resolve().parent.parent.parent
        assert collect_violations(real_root) == []
