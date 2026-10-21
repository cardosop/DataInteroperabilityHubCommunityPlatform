"""
W6.4 (oss-release-remediation) — parity-gate pins.

The pre-fix `check_cli_sdk_parity` hardcoded a 14-entry subset of the CLI
command tree, matched the SDK by FUZZY substring, and always exited 0 —
a CLI module could vanish from the SDK and the gate would still print
"all CLI commands have SDK counterparts". The W6.4 contract: every CLI
command module MUST have an SDK counterpart; a missing module FAILS the
gate (exit 1) unless it is explicitly listed in the documented
CLI-only floor with a reason (and that floor must never grow silently).

These pins run the REAL checker (subprocess) against real and planted
directory trees via the --cli-dir/--sdk-dir seams — no mocks of the
unit under test.
"""

import subprocess
import sys
from pathlib import Path

_CHECKER = Path(__file__).resolve().parents[1] / "check_cli_sdk_parity.py"


def run_checker(cli_dir: Path, sdk_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(_CHECKER),
            "--cli-dir",
            str(cli_dir),
            "--sdk-dir",
            str(sdk_dir),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def make_tree(base: Path, modules: dict[str, str]):
    for name, content in modules.items():
        path = base / f"{name}.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def test_current_tree_passes(tmp_path):
    """The real CLI tree is green (every non-exempt module has an SDK peer)."""
    repo = Path(__file__).resolve().parents[2]
    result = run_checker(
        repo / "cli" / "datahub_cli" / "commands",
        repo / "sdk" / "python" / "datahub_interoperability",
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_missing_module_fails_the_gate(tmp_path):
    """A CLI module without an SDK counterpart flips the gate to exit 1."""
    cli_dir = tmp_path / "cli"
    sdk_dir = tmp_path / "sdk"
    make_tree(cli_dir, {"assets": "ASSETS = 1\n", "contracts": "CONTRACTS = 1\n"})
    make_tree(sdk_dir, {"assets": "ASSETS = 1\n"})

    result = run_checker(cli_dir, sdk_dir)
    assert result.returncode == 1
    assert "contracts" in result.stdout + result.stderr


def test_every_exemption_has_a_reason(tmp_path):
    """The CLI-only floor entries all carry a documented reason."""
    source = _CHECKER.read_text()
    # The exemption table is the single source; parse the reasons out of it.
    import re

    table = re.search(
        r"_CLI_ONLY_MODULES\s*(?::[^=]*)?=\s*\{(?P<body>.*?)\n\}", source, re.S
    ).group("body")
    entries = re.findall(r'"(?P<name>[a-z_0-9]+)":\s*"(?P<reason>[^"]+)"', table)
    assert entries, "exemption table not found"
    for name, reason in entries:
        assert len(reason.strip()) >= 10, f"exemption {name!r} lacks a real reason"
    assert len(entries) >= 1


def test_cli_only_floor_never_grows_silently(tmp_path):
    """The documented floor (7) is pinned — reductions update the pin."""
    repo = Path(__file__).resolve().parents[2]
    result = run_checker(
        repo / "cli" / "datahub_cli" / "commands",
        repo / "sdk" / "python" / "datahub_interoperability",
    )
    # The gate reports the floor count; it must match the documented plan.
    assert "CLI-only floor:" in result.stdout
    floor = int(result.stdout.split("CLI-only floor:")[1].strip().split()[0])
    assert floor <= 7, (
        f"the CLI-only floor grew from 7 to {floor} — the reduction plan "
        "must shrink it, not grow it"
    )
