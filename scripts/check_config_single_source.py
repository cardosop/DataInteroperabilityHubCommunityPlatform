#!/usr/bin/env python3
"""Phase Q.2.2 — config single-source gate (GATE-34).

A tool configured in BOTH a dedicated file AND a pyproject ``[tool.<name>]``
section silently shadows the pyproject block (mypy/ruff/pytest discovery
order prefers the dedicated file). This checker detects every
tool-configured-in-both-places case and compares a per-tool KEY SET —
including NESTED keys (``lint.select``, ``run.source``) and the mypy
per-module sections (``[mypy-*]`` vs ``[[tool.mypy.overrides]]`` — the exact
class that rotted silently in Phase 250.DoD.R10). Equivalent mirrors are
accepted (the repo's documented reconciliation pattern); divergent
duplicates are violations with the exact key diffs. A tool configured in
ONE place is always clean.

Special case: ``[tool.pytest]`` (flat) is NEVER read by pytest — its real
pyproject home is ``[tool.pytest.ini_options]`` — so a flat ``[tool.pytest]``
section is dead config and is a violation on its own.

Exit 0 clean, 1 on violations.
"""

from __future__ import annotations

import argparse
import configparser
import tomllib
from pathlib import Path

# tool -> {
#   files: dedicated-file candidates (first existing wins),
#   ini_primary: primary INI section whose items are compared at top level
#                (None = every section stays nested under its name),
#   keys: canonical dotted key paths to compare,
# }
TOOLS: dict[str, dict] = {
    "ruff": {
        "files": (".ruff.toml", "ruff.toml"),
        "ini_primary": None,  # TOML-only in practice
        "keys": (
            "line-length",
            "target-version",
            "exclude",
            "lint.select",
            "lint.ignore",
            "lint.per-file-ignores",
            "lint.isort.known-first-party",
        ),
    },
    "mypy": {
        "files": ("mypy.ini", ".mypy.ini"),
        "ini_primary": "mypy",
        "keys": (
            "python_version",
            "warn_return_any",
            "warn_unused_configs",
            "show_error_codes",
            "exclude",
        ),
    },
    "pytest": {
        "files": ("pytest.ini",),
        "ini_primary": "pytest",
        "keys": (
            "addopts",
            "testpaths",
            "python_files",
            "python_classes",
            "python_functions",
        ),
    },
    "isort": {
        "files": (".isort.cfg",),
        "ini_primary": "settings",
        "keys": ("line_length", "profile"),
    },
    "coverage": {
        "files": (".coveragerc",),
        "ini_primary": None,  # [run] / [report] stay nested
        "keys": ("run.source", "run.omit"),
    },
    "bandit": {
        "files": (".bandit",),
        "ini_primary": "bandit",
        "keys": (
            "exclude_dirs",
            "skips",
            "tests",
            "severity_level",
            "confidence_level",
        ),
    },
}


def _nested(config: dict, path: str):
    """Resolve a dotted path inside a nested dict; None when missing."""
    value = config
    for part in path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def _normalize(value):
    """Cross-format value comparison.

    configparser yields strings ('true'), tomllib yields booleans (True);
    INI continuation lines yield '\n'-joined strings, TOML yields arrays.
    Empty string / None both mean "default" (e.g. bandit ``tests =``).
    List ORDER is preserved — select-order IS rule precedence for ruff.
    """
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ",".join(str(item).lower() for item in value)
    if isinstance(value, dict):
        return ";".join(f"{k}={_normalize(v)}" for k, v in sorted(value.items()))
    return str(value).lower()


def _load_pyproject_section(root: Path, tool: str) -> dict:
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return {}
    data = tomllib.loads(pyproject.read_text())
    section: dict = data.get("tool", {}).get(tool, {})
    if tool == "pytest":
        # pytest reads [tool.pytest.ini_options]; a flat [tool.pytest] is
        # dead config (flagged by collect_violations).
        section = section.get("ini_options", {})
    return section


def _load_dedicated_file(root: Path, tool: str) -> tuple[str | None, dict]:
    candidates = TOOLS[tool]["files"]
    ini_primary = TOOLS[tool]["ini_primary"]
    for name in candidates:
        path = root / name
        if not path.exists():
            continue
        text = path.read_text()
        if name.endswith(".toml"):
            return name, tomllib.loads(text)
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read_string(text)
        except configparser.MissingSectionHeaderError:
            # Bandit 1.8+ configs are YAML (the old INI form silently fails
            # to PARSE for bandit itself — the Q.1 review's dead-scan find).
            # Parse the modern form so the gate keeps working either way.
            import yaml

            loaded = yaml.safe_load(text)
            return name, loaded if isinstance(loaded, dict) else {}
        canonical: dict = {}
        for section in parser.sections():
            items = dict(parser.items(section))
            if section == ini_primary:
                canonical.update(items)  # primary section compares at top level
            else:
                canonical[section] = items
        return name, canonical
    return None, {}


def _mypy_per_module_entries(config: dict, is_toml: bool) -> list[str]:
    """Normalize [mypy-*] sections / [[tool.mypy.overrides]] to one shape."""
    entries: list[str] = []
    if is_toml:
        for override in config.get("overrides", []):
            modules = override.get("module", [])
            if isinstance(modules, str):  # module may be a single pattern string
                modules = [modules]
            rest = {k: v for k, v in override.items() if k != "module"}
            for module in modules:
                entries.append(f"{module} => {_normalize(rest)}")
    else:
        for section, items in config.items():
            if isinstance(items, dict) and section.startswith("mypy-"):
                entries.append(f"{section[5:]} => {_normalize(items)}")
    return sorted(entries)


def _compare(tool: str, filename: str, file_config: dict, pyproject_config: dict) -> list[str]:
    violations: list[str] = []
    for key in TOOLS[tool]["keys"]:
        file_value = _nested(file_config, key)
        py_value = _nested(pyproject_config, key)
        if _normalize(file_value) == _normalize(py_value):
            continue
        violations.append(
            f"{tool}: {key} diverges — {filename}={file_value!r} vs "
            f"pyproject [tool.{tool}]={py_value!r} "
            f"({filename} wins; the pyproject value is dead)"
        )
    if tool == "mypy":
        file_pm = _mypy_per_module_entries(file_config, is_toml=filename.endswith(".toml"))
        py_pm = _mypy_per_module_entries(pyproject_config, is_toml=True)
        if file_pm != py_pm:
            violations.append(
                f"mypy: per-module overrides diverge — {filename}={file_pm} "
                f"vs pyproject [tool.mypy.overrides]={py_pm} "
                f"({filename} wins; the pyproject overrides are dead)"
            )
    return violations


def collect_violations(root: Path) -> list[str]:
    violations: list[str] = []
    for tool in TOOLS:
        filename, file_config = _load_dedicated_file(root, tool)
        pyproject_config = _load_pyproject_section(root, tool)
        if filename is None and not pyproject_config:
            continue  # unconfigured tool
        if filename is None or not pyproject_config:
            continue  # single source — clean
        violations.extend(_compare(tool, filename, file_config, pyproject_config))

    # pytest-specific dead-config rule: pytest NEVER reads a flat
    # [tool.pytest] section (its pyproject home is [tool.pytest.ini_options]).
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        data = tomllib.loads(pyproject.read_text())
        flat_pytest = data.get("tool", {}).get("pytest", {})
        if isinstance(flat_pytest, dict) and "ini_options" not in flat_pytest and flat_pytest:
            violations.append(
                "pytest: flat [tool.pytest] section in pyproject.toml is never "
                "read by pytest — move it to [tool.pytest.ini_options]"
            )
    return sorted(violations)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Config single-source gate")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)

    violations = collect_violations(args.root)
    if violations:
        print(f"CONFIG-SSO: {len(violations)} divergent duplicate(s):")
        for entry in violations:
            print(f"  {entry}")
        return 1
    print("CONFIG-SSO: every tool has one effective source (or documented-equivalent mirrors)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
