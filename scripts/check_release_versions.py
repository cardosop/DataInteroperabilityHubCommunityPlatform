#!/usr/bin/env python3
"""W9.1 (oss-release-remediation) — single-source release-version gate.

``VERSION`` (repo root) is the ONE source of the platform release
version.  Every shipped artifact that carries a version — hub
``__version__``, cli ``__version__`` (+ its setup.py derivation), the
python SDK's PEP-621 project (dynamic, read from its ``__init__``), the
JS SDK + frontend ``package.json``, and the helm ``appVersion`` — must
agree with it.

Modes:
  * default (``--check``): exit 1 with a per-artifact drift report when
    any artifact disagrees with VERSION — the CI gate (wired in the
    lint workflow; the W12.6 item inherits this checker).
  * ``--sync``: rewrite every drifted artifact to VERSION (used by the
    release process and by ``make`` tooling).

release-please bumps VERSION itself (``version-file`` in
.release-please-config.json) and its ``extra-files`` rewrite the same
artifacts at release time; this checker is the invariant that catches
any path that breaks the agreement.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = REPO_ROOT / "VERSION"


def _json_version(text: str, version: str) -> str:
    data = json.loads(text)
    data["version"] = version
    return json.dumps(data, indent=2) + "\n"


def _json_lockfile_version(text: str, version: str) -> str:
    data = json.loads(text)
    data["version"] = version
    if "" in data.get("packages", {}):
        data["packages"][""]["version"] = version
    return json.dumps(data, indent=2) + "\n"


# (path, extract(current_text) -> version, update(text, version) -> text)
ARTIFACTS: tuple[tuple[Path, object, object], ...] = (
    (
        REPO_ROOT / "hub" / "__init__.py",
        lambda t: (
            re.search(r'^__version__ = "([^"]+)"', t, re.M).group(1)
            if re.search(r'^__version__ = "([^"]+)"', t, re.M)
            else None
        ),
        lambda t, v: (
            t + f'\n__version__ = "{v}"\n'
            if '__version__ = "' not in t
            else re.sub(
                r'^__version__ = "[^"]+"', f'__version__ = "{v}"', t, flags=re.M
            )
        ),
    ),
    (
        REPO_ROOT / "cli" / "datahub_cli" / "__init__.py",
        lambda t: (
            re.search(r'^__version__ = "([^"]+)"', t, re.M).group(1)
            if re.search(r'^__version__ = "([^"]+)"', t, re.M)
            else None
        ),
        lambda t, v: re.sub(
            r'^__version__ = "[^"]+"', f'__version__ = "{v}"', t, flags=re.M
        ),
    ),
    (
        REPO_ROOT / "sdk" / "python" / "datahub_interoperability" / "__init__.py",
        lambda t: (
            re.search(r'^__version__ = "([^"]+)"', t, re.M).group(1)
            if re.search(r'^__version__ = "([^"]+)"', t, re.M)
            else None
        ),
        lambda t, v: re.sub(
            r'^__version__ = "[^"]+"', f'__version__ = "{v}"', t, flags=re.M
        ),
    ),
    (
        REPO_ROOT / "sdk" / "js" / "package.json",
        lambda t: json.loads(t)["version"],
        _json_version,
    ),
    (
        # The npm lockfile carries the package's OWN version in two
        # places (root + packages[""]) — W9.1 synced package.json but
        # missed this, leaving the SDK's lockfile at the pre-fix 1.0.0.
        REPO_ROOT / "sdk" / "js" / "package-lock.json",
        lambda t: (
            data["version"]
            if (data := json.loads(t)).get("version")
            == data.get("packages", {}).get("", {}).get("version")
            else None
        ),
        _json_lockfile_version,
    ),
    (
        REPO_ROOT / "frontend" / "package.json",
        lambda t: json.loads(t)["version"],
        _json_version,
    ),
    (
        REPO_ROOT / "helm" / "Chart.yaml",
        lambda t: re.search(r'^appVersion: "?([^"\n]+)"?', t, re.M).group(1),
        lambda t, v: re.sub(
            r'^appVersion: "?[^"\n]+"?', f'appVersion: "{v}"', t, flags=re.M
        ),
    ),
)


def canonical_version() -> str:
    if not VERSION_FILE.is_file():
        print(f"ERROR: {VERSION_FILE} missing", file=sys.stderr)
        raise SystemExit(1)
    value = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", value):
        print(f"ERROR: {VERSION_FILE} is not a bare semver: {value!r}", file=sys.stderr)
        raise SystemExit(1)
    return value


def drift() -> list[tuple[str, str | None]]:
    """(artifact-name, current-version-or-None) for every disagreement."""
    version = canonical_version()
    drifted: list[tuple[str, str | None]] = []
    for path, extract, _update in ARTIFACTS:
        name = str(path.relative_to(REPO_ROOT))
        if not path.is_file():
            drifted.append((name, None))
            continue
        current = extract(path.read_text(encoding="utf-8"))
        if current != version:
            drifted.append((name, current))
    return drifted


def sync() -> int:
    version = canonical_version()
    changed = 0
    for path, extract, update in ARTIFACTS:
        text = path.read_text(encoding="utf-8")
        if extract(text) == version:
            continue
        new_text = update(text, version)
        path.write_text(new_text, encoding="utf-8")
        changed += 1
        print(f"synced {path.relative_to(REPO_ROOT)} -> {version}")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report drift (default mode; exit 1 on disagreement)",
    )
    parser.add_argument(
        "--sync", action="store_true", help="rewrite drifted artifacts to VERSION"
    )
    args = parser.parse_args()

    if args.sync:
        changed = sync()
        print(f"synced {changed} artifact(s) to {canonical_version()}")
        return 0

    drifted = drift()
    if drifted:
        print(f"VERSION={canonical_version()} but these artifacts disagree:")
        for name, current in drifted:
            print(f"  {name}: {current!r}")
        print("Fix: python scripts/check_release_versions.py --sync")
        return 1
    print(f"all release versions agree on {canonical_version()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
