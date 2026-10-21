"""W12.10 (oss-release-remediation) — CLI naming parity pin.

The named drift: the databricks control-plane CLI exposed ``ls`` on
five groups (uc, warehouses, ml serving-endpoints, ml vector-endpoints,
workspaces credentials) while every sibling surface uses ``list``.
The listing verb is ``list``, period — this pin walks the REAL click
tree (no mocks) and fails when any ``ls`` command re-appears anywhere,
plus a source-level scan so a decorated-but-unregistered ``ls`` cannot
hide.

RED phase: before the rename, the tree scan found exactly the five
``ls`` commands (uc / warehouses / ml serving-endpoints /
ml vector-endpoints / workspaces credentials) and the source scan found
the five ``.command("ls")`` decorators.
"""

from __future__ import annotations

import re
from pathlib import Path

from datahub_cli.main import cli

CLI_DIR = Path(__file__).resolve().parent.parent.parent / "datahub_cli"

# The five groups that previously exposed `ls` — each must now expose
# `list` (the canonical listing verb).
LISTING_GROUPS = [
    ["databricks", "uc"],
    ["databricks", "warehouses"],
    ["databricks", "ml", "serving-endpoints"],
    ["databricks", "ml", "vector-endpoints"],
    ["databricks", "workspaces", "credentials"],
]


def _walk(group, path):
    for name, cmd in getattr(group, "commands", {}).items():
        yield [*path, name], cmd
        if hasattr(cmd, "commands"):
            yield from _walk(cmd, [*path, name])


def test_no_ls_commands_anywhere_in_the_cli_tree():
    """The real click tree must contain zero ``ls`` commands."""
    offenders = [path for path, _cmd in _walk(cli, []) if path[-1] == "ls"]
    assert not offenders, f"'ls' commands still present: {offenders}"


def test_listing_groups_expose_list():
    """Every previously-`ls` group must expose the canonical ``list``."""
    for path in LISTING_GROUPS:
        group = cli
        for segment in path:
            group = group.commands[segment]
        assert "list" in group.commands, (
            f"{' '.join(path)} must expose a `list` command"
        )


def test_no_ls_decorators_in_source():
    """A decorated-but-unregistered ``ls`` cannot hide from the tree
    scan — the source must carry no ``.command(\"ls\")`` either."""
    offenders = []
    for py_file in CLI_DIR.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        if re.search(r'\.command\(\s*["\']ls["\']\s*\)', text):
            offenders.append(str(py_file.relative_to(CLI_DIR)))
    assert not offenders, f"source still declares `ls` commands: {offenders}"
