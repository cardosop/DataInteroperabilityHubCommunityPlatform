"""W7.4 (oss-release-remediation) — CI Node-version consistency pins.

The fleet drifted across Node 18/20/22 while the frontend package's
engines floor is >=20 — an 18 job would run a frontend that declares
itself unsupported, and 22 was bleeding-edge-only.  The contract: every
setup-node step in the workflow fleet pins the SAME version (20), with
one sanctioned escape hatch — an ``NODE_VERSION`` env-var reference
whose default must also be 20.
"""

from __future__ import annotations

import re
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parent.parent.parent / ".github" / "workflows"
CANONICAL = "20"

# The visual-regression workflow resolves node-version via an env var —
# the env var's default must still be canonical.
_NODE_VERSION_ENV_DEFAULT = re.compile(
    r"NODE_VERSION:\s*['\"](\d+)['\"]"
)


def _node_version_lines() -> dict[str, list[tuple[int, str]]]:
    out: dict[str, list[tuple[int, str]]] = {}
    for path in sorted(WORKFLOWS.glob("*.yml")):
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            if "node-version" in line:
                out.setdefault(path.name, []).append((lineno, line))
    return out


def test_every_node_version_site_is_canonical():
    """Every literal node-version in the fleet pins 20 (or references
    NODE_VERSION)."""
    violations = []
    for name, sites in _node_version_lines().items():
        for lineno, line in sites:
            stripped = line.strip()
            if "NODE_VERSION" in line:
                continue
            match = re.search(r"node-version:\s*['\"]?(\d+)", stripped)
            if match and match.group(1) != CANONICAL:
                violations.append(f"{name}:{lineno}: {stripped}")
    assert not violations, (
        f"non-canonical node-version pins (want {CANONICAL}):\n"
        + "\n".join(sorted(violations))
    )


def test_env_var_default_is_canonical():
    """The NODE_VERSION env default must be the canonical version."""
    for path in WORKFLOWS.glob("*.yml"):
        for match in _NODE_VERSION_ENV_DEFAULT.finditer(path.read_text()):
            assert match.group(1) == CANONICAL, (
                f"{path.name}: NODE_VERSION default {match.group(1)} "
                f"!= canonical {CANONICAL}"
            )


def test_at_least_one_node_site_exists():
    """Non-vacuity: the fleet actually has node jobs to check."""
    assert _node_version_lines(), "no node-version sites found"
