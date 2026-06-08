"""Unit tests for Phase 232 CLI catalogue."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from datahub_cli.commands.phase232_programme import (
    _PHASE232_LIST_ROUTES,
    format_phase232_catalogue_table,
    phase232_group,
)


@pytest.mark.unit
def test_phase232_catalogue_has_seven_subsystems() -> None:
    assert len(_PHASE232_LIST_ROUTES) == 7


@pytest.mark.unit
def test_format_table_includes_compliance_path() -> None:
    text = format_phase232_catalogue_table(_PHASE232_LIST_ROUTES)
    assert "compliance/runs/" in text
    assert "governance/dsar-requests/" in text


@pytest.mark.unit
def test_cli_catalogue_json() -> None:
    runner = CliRunner()
    result = runner.invoke(phase232_group, ["catalogue", "--format", "json"])
    assert result.exit_code == 0, result.output
    assert "compliance_runs" in result.output
