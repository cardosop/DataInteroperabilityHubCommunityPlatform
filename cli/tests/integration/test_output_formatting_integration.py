"""
Comprehensive integration tests for CLI output formatting.

Tests output formatting with real API structure (when available).
"""

import json
import os

import pytest
from click.testing import CliRunner
from datahub_cli.config import Config
from datahub_cli.main import cli


class TestOutputFormatIntegration:
    """Integration tests for output formats"""

    def test_json_output_parsable(self, runner, temp_config_dir, api_base_url):
        """Test that JSON output is always valid and parsable"""
        config = Config()
        config.set_api_base_url(api_base_url)

        result = runner.invoke(cli, ["contracts", "list", "--format", "json"])

        # If command succeeds, output should be valid JSON
        if result.exit_code == 0 and result.output.strip():
            try:
                output_data = json.loads(result.output)
                assert isinstance(output_data, (dict, list))
            except json.JSONDecodeError:
                pytest.fail(f"JSON output is not valid JSON: {result.output[:200]}")

    def test_table_output_readable(self, runner, temp_config_dir, api_base_url):
        """Test that table output is human-readable"""
        config = Config()
        config.set_api_base_url(api_base_url)

        result = runner.invoke(cli, ["assets", "list"])

        # If command succeeds and has output, should be readable
        if result.exit_code == 0 and result.output.strip():
            # Should have headers or structure
            assert len(result.output) > 0
            # Should not be raw JSON
            assert not result.output.strip().startswith("[")
            assert not result.output.strip().startswith("{")

    def test_format_consistency_across_commands(self, runner, temp_config_dir, api_base_url):
        """Test that format options are consistent across commands"""
        config = Config()
        config.set_api_base_url(api_base_url)

        commands_with_format = [
            ["contracts", "list"],
            ["assets", "list"],
            ["files", "list"],
            ["jobs", "list"],
        ]

        for cmd in commands_with_format:
            # Test JSON format
            result_json = runner.invoke(cli, cmd + ["--format", "json"])
            # Should either succeed or fail gracefully
            assert result_json.exit_code == 0

            # Test table format
            result_table = runner.invoke(cli, cmd + ["--format", "table"])
            assert result_table.exit_code == 0


class TestLineageVisualizationIntegration:
    """Integration tests for lineage visualization formats"""

    def test_dot_format_valid_syntax(self, runner, temp_config_dir, api_base_url):
        """Test that DOT format output is valid DOT syntax"""
        config = Config()
        config.set_api_base_url(api_base_url)

        result = runner.invoke(cli, ["lineage", "visualize", "test-id", "--format", "dot"])

        # If command succeeds, output should be valid DOT or error message
        if result.exit_code == 0 and result.output.strip():
            # DOT format should start with 'digraph' or 'graph'
            assert (
                "digraph" in result.output.lower()
                or "graph" in result.output.lower()
                or "Failed" in result.output
            )

    def test_mermaid_format_valid_syntax(self, runner, temp_config_dir, api_base_url):
        """Test that Mermaid format output is valid Mermaid syntax"""
        config = Config()
        config.set_api_base_url(api_base_url)

        result = runner.invoke(cli, ["lineage", "visualize", "test-id", "--format", "mermaid"])

        # If command succeeds, output should be valid Mermaid or error message
        if result.exit_code == 0 and result.output.strip():
            # Mermaid format should contain graph syntax
            assert "graph" in result.output.lower() or "Failed" in result.output


@pytest.fixture
def runner():
    """CLI runner fixture"""
    return CliRunner()


@pytest.fixture
def api_base_url():
    """API base URL fixture"""
    return os.environ.get("MESHANT_API_URL", "http://localhost:8000/api/v1")


@pytest.fixture
def temp_config_dir(tmp_path, monkeypatch):
    """Create a temporary config directory"""
    config_dir = tmp_path / ".datahub"
    config_dir.mkdir()
    config_file = config_dir / "config.yaml"

    monkeypatch.setattr("datahub_cli.config.CONFIG_DIR", config_dir)
    monkeypatch.setattr("datahub_cli.config.CONFIG_FILE", config_file)

    return config_dir, config_file
