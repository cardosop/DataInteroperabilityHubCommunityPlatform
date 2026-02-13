"""
Phase 26 CLI Integration Tests

Tests for new CLI commands: scheduled ingestion, scheduled export, webhooks, audit, health,
billing, tenants, GDPR, and search.

All tests use real backend API - no mocks/stubs.
"""

import json
import os
import subprocess
from typing import Any, Dict, Optional

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.cli_sdk,
]

# Test configuration
HUB_BASE_URL = os.getenv("HUB_BASE_URL", "http://localhost:8000/api/v1")
API_KEY = os.getenv("DATAHUB_API_KEY", "")


@pytest.fixture(scope="module")
def cli_config():
    """Configure CLI for testing"""
    if not API_KEY:
        pytest.skip("DATAHUB_API_KEY not set")

    # Set API key in CLI config
    subprocess.run(
        ["datahub", "config", "set", "api_key", API_KEY], check=True, capture_output=True
    )
    subprocess.run(
        ["datahub", "config", "set", "api_base_url", HUB_BASE_URL], check=True, capture_output=True
    )

    yield

    # Cleanup (optional)


def run_cli_command(cmd: list) -> tuple[int, str, str]:
    """Run CLI command and return exit code, stdout, stderr"""
    result = subprocess.run(["datahub"] + cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


class TestScheduledIngestionCLI:
    """Test scheduled ingestion CLI commands"""

    def test_list_scheduled_ingestions(self, cli_config):
        """Test listing scheduled ingestions"""
        exit_code, stdout, stderr = run_cli_command(
            ["scheduled-ingestion", "list", "--format", "json"]
        )
        assert exit_code == 0, f"Command failed: {stderr}"
        # Should return valid JSON or empty list
        try:
            data = json.loads(stdout)
            assert isinstance(data, (list, dict))
        except json.JSONDecodeError:
            pytest.fail(f"Invalid JSON output: {stdout}")

    def test_create_scheduled_ingestion(self, cli_config):
        """Test creating scheduled ingestion"""
        # This test requires a valid source config
        # Skipping actual creation to avoid side effects
        # In real tests, create and then delete
        pytest.skip("Requires test data setup")

    def test_get_scheduled_ingestion(self, cli_config):
        """Test getting scheduled ingestion details"""
        # Requires existing ingestion ID
        pytest.skip("Requires test data setup")


class TestScheduledExportCLI:
    """Test scheduled export CLI commands"""

    def test_list_scheduled_exports(self, cli_config):
        """Test listing scheduled exports"""
        exit_code, stdout, stderr = run_cli_command(
            ["scheduled-export", "list", "--format", "json"]
        )
        assert exit_code == 0, f"Command failed: {stderr}"
        try:
            data = json.loads(stdout)
            assert isinstance(data, (list, dict))
        except json.JSONDecodeError:
            pytest.fail(f"Invalid JSON output: {stdout}")


class TestWebhooksCLI:
    """Test webhooks CLI commands"""

    def test_list_webhooks(self, cli_config):
        """Test listing webhooks"""
        exit_code, stdout, stderr = run_cli_command(["webhooks", "list", "--format", "json"])
        assert exit_code == 0, f"Command failed: {stderr}"
        try:
            data = json.loads(stdout)
            assert isinstance(data, (list, dict))
        except json.JSONDecodeError:
            pytest.fail(f"Invalid JSON output: {stdout}")

    def test_list_event_types(self, cli_config):
        """Test listing webhook event types"""
        exit_code, stdout, stderr = run_cli_command(["webhooks", "event-types", "--format", "json"])
        assert exit_code == 0, f"Command failed: {stderr}"
        try:
            data = json.loads(stdout)
            assert "event_types" in data or isinstance(data, dict)
        except json.JSONDecodeError:
            pytest.fail(f"Invalid JSON output: {stdout}")


class TestAuditCLI:
    """Test audit CLI commands"""

    def test_query_audit_events(self, cli_config):
        """Test querying audit events"""
        exit_code, stdout, stderr = run_cli_command(
            ["audit", "query", "--limit", "10", "--format", "json"]
        )
        assert exit_code == 0, f"Command failed: {stderr}"
        try:
            data = json.loads(stdout)
            assert isinstance(data, (list, dict))
        except json.JSONDecodeError:
            pytest.fail(f"Invalid JSON output: {stdout}")


class TestHealthCLI:
    """Test health CLI commands"""

    def test_health_check(self, cli_config):
        """Test health check"""
        exit_code, stdout, stderr = run_cli_command(["health", "check", "--format", "json"])
        assert exit_code == 0, f"Command failed: {stderr}"
        try:
            data = json.loads(stdout)
            assert "name" in data or "version" in data
        except json.JSONDecodeError:
            pytest.fail(f"Invalid JSON output: {stdout}")


class TestBillingCLI:
    """Test billing CLI commands (Phase 25)"""

    def test_get_subscription(self, cli_config):
        """Test getting subscription"""
        exit_code, stdout, stderr = run_cli_command(["billing", "subscription", "--format", "json"])
        # May fail if no subscription exists - that's OK
        if exit_code != 0:
            assert "not found" in stderr.lower() or "no subscription" in stderr.lower()
        else:
            try:
                data = json.loads(stdout)
                assert isinstance(data, dict)
            except json.JSONDecodeError:
                pytest.fail(f"Invalid JSON output: {stdout}")

    def test_list_invoices(self, cli_config):
        """Test listing invoices"""
        exit_code, stdout, stderr = run_cli_command(["billing", "invoices", "--format", "json"])
        assert exit_code == 0, f"Command failed: {stderr}"
        try:
            data = json.loads(stdout)
            assert isinstance(data, (list, dict))
        except json.JSONDecodeError:
            pytest.fail(f"Invalid JSON output: {stdout}")


class TestTenantsCLI:
    """Test tenants CLI commands (Phase 25)"""

    def test_get_usage(self, cli_config):
        """Test getting tenant usage"""
        exit_code, stdout, stderr = run_cli_command(["tenants", "usage", "--format", "json"])
        assert exit_code == 0, f"Command failed: {stderr}"
        try:
            data = json.loads(stdout)
            assert isinstance(data, dict)
            # Should have usage metrics
            assert "asset_count" in data or "plan_limits" in data
        except json.JSONDecodeError:
            pytest.fail(f"Invalid JSON output: {stdout}")


class TestGDPRCLI:
    """Test GDPR CLI commands (Phase 25)"""

    def test_list_export_jobs(self, cli_config):
        """Test listing export jobs"""
        exit_code, stdout, stderr = run_cli_command(["gdpr", "export-jobs", "--format", "json"])
        assert exit_code == 0, f"Command failed: {stderr}"
        try:
            data = json.loads(stdout)
            assert isinstance(data, (list, dict))
        except json.JSONDecodeError:
            pytest.fail(f"Invalid JSON output: {stdout}")

    def test_list_erasure_requests(self, cli_config):
        """Test listing erasure requests"""
        exit_code, stdout, stderr = run_cli_command(
            ["gdpr", "erasure-requests", "--format", "json"]
        )
        assert exit_code == 0, f"Command failed: {stderr}"
        try:
            data = json.loads(stdout)
            assert isinstance(data, (list, dict))
        except json.JSONDecodeError:
            pytest.fail(f"Invalid JSON output: {stdout}")


class TestSearchCLI:
    """Test search CLI commands"""

    def test_search(self, cli_config):
        """Test search command"""
        exit_code, stdout, stderr = run_cli_command(
            ["search", "search", "--query", "test", "--format", "json"]
        )
        assert exit_code == 0, f"Command failed: {stderr}"
        try:
            data = json.loads(stdout)
            assert isinstance(data, dict)
            # Should have results or count
            assert "results" in data or "count" in data
        except json.JSONDecodeError:
            pytest.fail(f"Invalid JSON output: {stdout}")

    def test_search_suggestions(self, cli_config):
        """Test search suggestions"""
        exit_code, stdout, stderr = run_cli_command(
            ["search", "suggestions", "--query", "test", "--format", "json"]
        )
        assert exit_code == 0, f"Command failed: {stderr}"
        try:
            data = json.loads(stdout)
            # API returns a list directly, not a dict
            assert isinstance(data, list)
        except json.JSONDecodeError:
            pytest.fail(f"Invalid JSON output: {stdout}")
