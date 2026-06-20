"""
Phase 216.X.8 — drift test asserting ``sdk/python/tests/_pytest_helpers.py::_parse_bool_env``
is byte-equivalent to canonical ``hub/apps/api/mvp_mode.py::_parse_bool_env``.

Same doctrine as Phase 215's drift sync (no regex, no Django import).
"""

from __future__ import annotations

import ast
from pathlib import Path

CANONICAL_PATH = Path(__file__).resolve().parents[3] / "hub" / "apps" / "api" / "mvp_mode.py"
LOCAL_PATH = Path(__file__).resolve().parent / "_pytest_helpers.py"
FUNC_NAME = "_parse_bool_env"


def _extract_function_source(path: Path, name: str) -> str:
    """Return the AST-normalized source of a top-level function."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.unparse(node)
    raise AssertionError(f"function {name!r} not found in {path}")


def _imported_module_names() -> set[str]:
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_canonical_and_local_files_exist() -> None:
    assert CANONICAL_PATH.is_file(), f"missing canonical at {CANONICAL_PATH}"
    assert LOCAL_PATH.is_file(), f"missing local at {LOCAL_PATH}"


def test_parse_bool_env_is_byte_equivalent() -> None:
    canonical = _extract_function_source(CANONICAL_PATH, FUNC_NAME)
    local = _extract_function_source(LOCAL_PATH, FUNC_NAME)
    assert canonical == local, (
        "_parse_bool_env has drifted between canonical and SDK duplicate.\n"
        f"  canonical ({CANONICAL_PATH}):\n{canonical}\n"
        f"  local     ({LOCAL_PATH}):\n{local}"
    )


def test_drift_test_does_not_import_django() -> None:
    imported = _imported_module_names()
    assert "django" not in imported, f"forbidden import: django ({imported})"


def test_parse_bool_env_truthy_values_are_correct(monkeypatch) -> None:
    from tests._pytest_helpers import _parse_bool_env

    for v in ("true", "TRUE", "True", "1", "yes", "YES", "on", "y", "t"):
        monkeypatch.setenv("__PHASE216_TEST", v)
        assert _parse_bool_env("__PHASE216_TEST") is True, f"{v!r} should be truthy"
    for v in ("false", "0", "no", "off", "n", "f", "", "  ", "maybe"):
        monkeypatch.setenv("__PHASE216_TEST", v)
        assert _parse_bool_env("__PHASE216_TEST") is False, f"{v!r} should be falsy"
    monkeypatch.delenv("__PHASE216_TEST", raising=False)
    assert _parse_bool_env("__PHASE216_TEST") is False
