"""Shared `--scope {full,core}` support for traceability gates (Phase 313.2).

Core scope semantics (single source: the manifest + CRITICAL yaml paid tags):
- scan dirs: hub/apps narrowed to CORE app dirs (+ hub/data_movement);
  services/ narrowed to the shipped core dirs (api/worker/shared); tests/,
  cli/tests/, sdk/python/tests/ unchanged (paid files there are absent in
  the public mirror).
- paid IDs tagged in docs/CRITICAL_UC_JOURNEY_IDS.yaml `paid_ids:` are out
  of scope on BOTH the docs side and the markers side.

Pure stdlib — no Django imports.
"""

from __future__ import annotations

import argparse  # noqa: TCH003 — runtime (add_scope_argument)
import re
import sys
from pathlib import Path

CORE_SERVICE_DIRS = ("services/api", "services/worker", "services/shared")

# AppConfig-class suffix pattern — identical semantics to
# scripts/check_core_boundary._normalise (module paths like
# "hub.apps.semantic" contain ".apps." inside the path and must not split).
_APPS_CONFIG_SUFFIX_RE = re.compile(
    r"^(hub\.apps\.[A-Za-z_][A-Za-z0-9_]*)\.apps\.[A-Za-z_][A-Za-z0-9_]*$"
)


def add_scope_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--scope",
        choices=["full", "core"],
        default="full",
        help="full: all scan dirs (private default); core: exclude paid apps/services",
    )


def _module_name(entry: str) -> str:
    m = _APPS_CONFIG_SUFFIX_RE.match(entry)
    return m.group(1) if m else entry


def paid_module_names() -> set[str]:
    """Paid module paths from the manifest (AST-parsed — no Django)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from check_core_boundary import _read_paid_modules

    paid, _all = _read_paid_modules(Path("hub/apps/manifest.py"))
    return {_module_name(m) for m in paid}


def core_hub_app_dirs() -> list[str]:
    """Relative dirs for every CORE app (for hub/apps narrowing)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from check_core_boundary import _read_paid_modules

    paid, all_apps = _read_paid_modules(Path("hub/apps/manifest.py"))
    paid_set = {_module_name(m) for m in paid}
    dirs = []
    for entry in all_apps:
        mod = _module_name(entry)
        if mod in paid_set:
            continue
        dirs.append(mod.replace(".", "/"))
    dirs.append("hub/data_movement")
    return dirs


def build_scan_dirs(repo_root: Path, scan_dirs: list[str], scope: str) -> list[Path]:
    """Build the effective scan dir list for the requested scope."""
    if scope != "core":
        return [repo_root / d for d in scan_dirs]
    out: list[Path] = []
    for d in scan_dirs:
        if d == "hub/apps":
            out.extend(repo_root / c for c in core_hub_app_dirs())
        elif d == "services":
            out.extend(repo_root / s for s in CORE_SERVICE_DIRS)
        else:
            out.append(repo_root / d)
    return out


def paid_ids(repo_root: Path) -> set[str]:
    """Paid-tagged UC/JOURNEY IDs from the CRITICAL yaml (`paid_ids:` key)."""
    import yaml

    path = repo_root / "docs" / "CRITICAL_UC_JOURNEY_IDS.yaml"
    if not path.exists():
        return set()
    data = yaml.safe_load(path.read_text()) or {}
    return {str(i).strip() for i in data.get("paid_ids") or []}
