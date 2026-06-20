"""
Phase 215.3 — assert that every CLI command group whose backend routes are
entirely MVP-gated carries a ``[Post-MVP]`` marker in its ``@click.group()``
docstring, so ``--help`` users learn the feature is gated *before* they make
a request.

The test imports the **real** Click group objects (no AST parsing, no string
matching against source) and asserts on ``group.help`` — the same string
Click renders to ``--help``. This guarantees the marker actually surfaces in
the user-facing help text rather than only existing in source comments.

Phase 215.3 — see openspec/changes/preprod01/specs/cli-sdk-mvp-awareness/spec.md
"""

from __future__ import annotations

import importlib
from pathlib import Path

import click
import pytest

# The 7 standalone CLI command modules whose backend routes are entirely
# MVP-gated. Marketplace is handled separately (it has both gated and
# ungated subgroups, so its top-level group must NOT carry the marker).
GATED_MODULES: tuple[tuple[str, str], ...] = (
    ("datahub_cli.commands.mesh", "mesh"),
    ("datahub_cli.commands.virtualization", "virtualization"),
    ("datahub_cli.commands.baas", "baas"),
    ("datahub_cli.commands.ml", "ml"),
    ("datahub_cli.commands.transformation", "transformation"),
    ("datahub_cli.commands.scheduled_ingestion", "scheduled_ingestion"),
    ("datahub_cli.commands.scheduled_export", "scheduled_export"),
)

# Marketplace integration subgroups inside ``marketplace.py`` that map to the
# canonical ``/api/v1/integrations/`` MVP-gated prefix. ``listings``,
# ``orders``, ``entitlements`` are intentionally absent — those would be
# MVP-included if/when they ship and MUST NOT be marked.
MARKETPLACE_GATED_SUBGROUPS: tuple[str, ...] = (
    "connections",
    "sync",
    "connectors",
    "mappings",
)

POST_MVP_MARKER = "[Post-MVP]"


def _load_group(module_path: str, attr: str) -> click.Group:
    module = importlib.import_module(module_path)
    obj = getattr(module, attr)
    assert isinstance(obj, click.Group), (
        f"{module_path}.{attr} is not a click.Group (got {type(obj).__name__})"
    )
    return obj


# ---------------------------------------------------------------------------
# 7 standalone gated command groups
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("module_path", "attr"), GATED_MODULES)
def test_gated_command_group_has_post_mvp_marker(module_path: str, attr: str) -> None:
    """Each of the 7 gated CLI groups MUST contain ``[Post-MVP]`` in its help text.

    The assertion is against ``group.help`` (the string Click derives from
    the function docstring) so the marker actually appears in ``--help``
    output, not merely in a source comment.
    """
    group = _load_group(module_path, attr)
    assert group.help, f"{module_path}.{attr} has no help/docstring at all"
    assert POST_MVP_MARKER in group.help, (
        f"{module_path}.{attr} group help does NOT contain {POST_MVP_MARKER!r}.\n"
        f"  Current help: {group.help!r}\n"
        f"Append {POST_MVP_MARKER} to the @click.group() docstring."
    )


# ---------------------------------------------------------------------------
# Marketplace surgical markers (D133)
# ---------------------------------------------------------------------------


def test_marketplace_top_level_group_is_NOT_marked() -> None:
    """The top-level ``marketplace`` group MUST NOT carry the marker.

    Listings, orders, and entitlements live under ``marketplace`` and are
    MVP-included; marking the top-level group would mislead users into
    thinking the entire surface is post-MVP.
    """
    group = _load_group("datahub_cli.commands.marketplace", "marketplace")
    assert group.help, "marketplace group has no help/docstring at all"
    assert POST_MVP_MARKER not in group.help, (
        "marketplace TOP-level group MUST NOT carry "
        f"{POST_MVP_MARKER}; only its integration subgroups should. "
        f"Current help: {group.help!r}"
    )


@pytest.mark.parametrize("subgroup_name", MARKETPLACE_GATED_SUBGROUPS)
def test_marketplace_integration_subgroup_carries_marker(subgroup_name: str) -> None:
    """Every ``marketplace <subgroup>`` that maps to /api/v1/integrations/
    MUST carry the ``[Post-MVP]`` marker in its docstring.
    """
    marketplace = _load_group("datahub_cli.commands.marketplace", "marketplace")
    sub = marketplace.commands.get(subgroup_name)
    assert sub is not None, (
        f"marketplace subgroup {subgroup_name!r} not found "
        f"(present: {sorted(marketplace.commands)})"
    )
    assert sub.help, f"marketplace.{subgroup_name} has no help/docstring at all"
    assert POST_MVP_MARKER in sub.help, (
        f"marketplace.{subgroup_name} subgroup MUST carry {POST_MVP_MARKER}.\n"
        f"  Current help: {sub.help!r}"
    )


# ---------------------------------------------------------------------------
# Regression guard for ai.py / social.py (currently absent)
# ---------------------------------------------------------------------------


COMMANDS_DIR = Path(__file__).resolve().parents[1] / "datahub_cli" / "commands"


# ---------------------------------------------------------------------------
# End-to-end subprocess smoke — proves the marker actually reaches --help
# rendered output, not just the click.Group.help attribute. This guards
# against future click upgrades or main.py wiring changes that could
# accidentally drop docstrings from the rendered output.
# ---------------------------------------------------------------------------


import subprocess
import sys


def _extract_group_description(help_stdout: str) -> str:
    """Pull the group's own description block out of ``click --help`` output.

    Click's help format is::

        Usage: ... [OPTIONS] COMMAND [ARGS]...

          <group description, possibly multi-line, indented>

        Options:
          --help  ...

        Commands:
          subcommand1  <subcommand description>
          ...

    The group's *own* description is the indented block between the first
    blank line after ``Usage:`` and the next section header (``Options:``).
    Subcommand descriptions live under ``Commands:`` and MUST NOT be
    inspected when checking whether the *group itself* carries the marker.
    """
    lines = help_stdout.splitlines()
    # Step 1: find the Usage: header line.
    usage_idx = None
    for idx, line in enumerate(lines):
        if line.startswith("Usage:"):
            usage_idx = idx
            break
    if usage_idx is None:
        return ""
    # Step 2: skip past the Usage block. Click may wrap the Usage line across
    # multiple lines for long command paths (e.g.
    # ``marketplace connections [OPTIONS] COMMAND\n          [ARGS]...``);
    # the first blank line marks the end of the wrapped Usage block.
    start = None
    for idx in range(usage_idx + 1, len(lines)):
        if lines[idx].strip() == "":
            start = idx + 1
            break
    if start is None:
        return ""
    # Step 3: collect the description block (indented content) until the
    # next blank line or section header.
    description_lines: list[str] = []
    saw_content = False
    for line in lines[start:]:
        stripped = line.strip()
        if stripped in ("Options:", "Commands:"):
            break
        if stripped:
            saw_content = True
            description_lines.append(stripped)
        elif saw_content:
            break
    return " ".join(description_lines)


@pytest.mark.parametrize(
    ("argv", "must_contain_marker"),
    [
        (["mesh"], True),
        (["virtualization"], True),
        (["baas"], True),
        (["ml"], True),
        (["transformation"], True),
        (["scheduled-ingestion"], True),
        (["scheduled-export"], True),
        (["marketplace"], False),  # top-level marketplace MUST NOT be marked
        (["marketplace", "connections"], True),
        (["marketplace", "sync"], True),
        (["marketplace", "connectors"], True),
        (["marketplace", "mappings"], True),
    ],
)
def test_rendered_help_output_contains_marker(argv: list[str], must_contain_marker: bool) -> None:
    """Run the real CLI with ``--help`` and assert the marker is/isn't in the
    GROUP'S OWN description (not the subcommand list).

    Spawns ``python -m datahub_cli.main <argv> --help`` as a subprocess and
    inspects stdout. This is the strongest possible end-to-end proof: the
    same code path a real user hits when they type ``datahub mesh --help``.
    Only the group description block is inspected — the rendered Commands
    section legitimately contains markers from gated subcommands and would
    otherwise produce false positives on the top-level marketplace check.
    """
    result = subprocess.run(
        [sys.executable, "-m", "datahub_cli.main", *argv, "--help"],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"CLI exited {result.returncode} for {argv} --help\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    description = _extract_group_description(result.stdout)
    assert description, (
        f"Could not extract group description from {' '.join(argv)} --help output:\n{result.stdout}"
    )
    if must_contain_marker:
        assert POST_MVP_MARKER in description, (
            f"{' '.join(argv)} --help group description is missing "
            f"{POST_MVP_MARKER!r}.\n"
            f"  Description: {description!r}\n"
            f"  Full stdout:\n{result.stdout}"
        )
    else:
        assert POST_MVP_MARKER not in description, (
            f"{' '.join(argv)} --help group description unexpectedly "
            f"contains {POST_MVP_MARKER!r} (should be unmarked).\n"
            f"  Description: {description!r}"
        )


@pytest.mark.parametrize("module_stem", ["ai", "social"])
def test_future_ai_and_social_modules_must_carry_marker(module_stem: str) -> None:
    """If a future contributor adds ``commands/ai.py`` or ``commands/social.py``,
    the new module MUST carry ``[Post-MVP]`` on its top-level click group.

    Both backend prefixes (``ai/``, ``social/``) are MVP-gated, so any CLI
    surface that ever appears under those names is by definition post-MVP.
    Today neither file exists; the test is skipped. The day someone
    adds one without a marker, the test fails.
    """
    module_file = COMMANDS_DIR / f"{module_stem}.py"
    if not module_file.exists():
        pytest.skip(f"{module_file.name} does not exist yet — guard inactive")
    module = importlib.import_module(f"datahub_cli.commands.{module_stem}")
    group = getattr(module, module_stem, None)
    assert isinstance(group, click.Group), (
        f"datahub_cli.commands.{module_stem}.{module_stem} must be a click.Group"
    )
    assert group.help, f"{module_stem} group has no docstring"
    assert POST_MVP_MARKER in group.help, (
        f"{module_stem}.py exists but its click group docstring lacks "
        f"{POST_MVP_MARKER}. The {module_stem}/ backend prefix is MVP-gated; "
        "every CLI surface under it MUST advertise that in --help."
    )
