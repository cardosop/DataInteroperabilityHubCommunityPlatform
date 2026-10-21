#!/usr/bin/env python3
"""
303.5 — API changelog generation from OpenAPI spec diffs.

Diffs the current OpenAPI spec against the previous version stored
in ``docs/api/openapi-specs/`` and appends changes to
``docs/api/CHANGELOG.md``.

Usage:
    python scripts/generate_api_changelog.py              # diff vs last spec
    python scripts/generate_api_changelog.py --base v0.1  # diff vs specific version
"""

import json
import os
import sys
from datetime import UTC, datetime

SPEC_DIR = "docs/api/openapi-specs"
CHANGELOG_PATH = "docs/api/CHANGELOG.md"


def load_spec(version: str) -> dict | None:
    path = os.path.join(SPEC_DIR, f"openapi-{version}.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def list_spec_versions() -> list[str]:
    if not os.path.exists(SPEC_DIR):
        return []
    versions = []
    for f in os.listdir(SPEC_DIR):
        if f.startswith("openapi-") and f.endswith(".json"):
            versions.append(f.replace("openapi-", "").replace(".json", ""))
    return sorted(versions)


def diff_paths(old: dict, new: dict) -> dict:
    old_paths = set(old.get("paths", {}).keys())
    new_paths = set(new.get("paths", {}).keys())
    return {
        "added": sorted(new_paths - old_paths),
        "removed": sorted(old_paths - new_paths),
        "modified": sorted(
            p for p in (old_paths & new_paths) if old["paths"][p] != new["paths"][p]
        ),
    }


def generate_changelog_entry(base_version: str, new_version: str = "current") -> str:
    old = load_spec(base_version)
    if old is None:
        return f"## {new_version} ({datetime.now(UTC).strftime('%Y-%m-%d')})\n\n- Initial API specification.\n\n"

    # Generate current spec (requires Django + drf-spectacular)
    new_path = os.path.join(SPEC_DIR, f"openapi-{new_version}.json")
    if not os.path.exists(new_path):
        return (
            f"## {new_version}\n\n"
            f"⚠️ OpenAPI spec not found at `{new_path}`.\n"
            f"Run: `python hub/manage.py spectacular --file {new_path}`\n\n"
        )

    new = load_spec(new_version)
    if new is None:
        return f"## {new_version}\n\n⚠️ Failed to parse `{new_path}`.\n\n"

    paths_diff = diff_paths(old, new)
    lines = [f"## {new_version} ({datetime.now(UTC).strftime('%Y-%m-%d')})", ""]

    if paths_diff["added"]:
        lines.append("### Added Endpoints")
        for p in paths_diff["added"]:
            lines.append(f"- `{p}`")
        lines.append("")

    if paths_diff["removed"]:
        lines.append("### Removed Endpoints")
        for p in paths_diff["removed"]:
            lines.append(f"- `{p}` (⚠️ breaking change)")
        lines.append("")

    if paths_diff["modified"]:
        lines.append("### Modified Endpoints")
        for p in paths_diff["modified"]:
            lines.append(f"- `{p}`")
        lines.append("")

    if not any(paths_diff.values()):
        lines.append("_No API surface changes._")
        lines.append("")

    return "\n".join(lines)


def main():
    versions = list_spec_versions()
    base = (
        sys.argv[2]
        if len(sys.argv) > 2 and sys.argv[1] == "--base"
        else (versions[-1] if len(versions) > 0 else "v0.1")
    )

    entry = generate_changelog_entry(base)
    print(entry)

    # Append to changelog
    os.makedirs(os.path.dirname(CHANGELOG_PATH), exist_ok=True)
    if os.path.exists(CHANGELOG_PATH):
        with open(CHANGELOG_PATH) as f:
            existing = f.read()
        # Prepend new entry (newest first)
        with open(CHANGELOG_PATH, "w") as f:
            f.write(entry + "\n" + existing)
    else:
        with open(CHANGELOG_PATH, "w") as f:
            f.write("# API Changelog\n\n" + entry)

    print(f"Changelog updated: {CHANGELOG_PATH}")


if __name__ == "__main__":
    main()
