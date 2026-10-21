"""
Unit tests for Health CLI commands.

Tests: check, components, circuit-breakers, live commands.
"""

import json
from unittest.mock import Mock, patch

from datahub_cli.main import cli


class TestHealthCheck:
    """Test health check command"""

    @patch("datahub_cli.commands.health._requests")
    def test_check_health_ok(self, mock_requests, runner, mock_api_client):
        """Test health check returns ok status"""
        mock_api_client._get_base_url.return_value = "http://localhost:8001/api/v1"
        mock_resp = Mock()
        mock_resp.json.return_value = {
            "status": "healthy",
            "database": "ok",
            "redis": {"cache": "ok", "queue": "ok"},
        }
        mock_resp.raise_for_status = Mock()
        mock_requests.get.return_value = mock_resp

        result = runner.invoke(cli, ["health", "check"])

        assert result.exit_code == 0
        assert "healthy" in result.output

    @patch("datahub_cli.commands.health._requests")
    def test_check_health_json_format(self, mock_requests, runner, mock_api_client):
        """Test health check with JSON output"""
        mock_api_client._get_base_url.return_value = "http://localhost:8001/api/v1"
        mock_resp = Mock()
        mock_resp.json.return_value = {"status": "healthy", "database": "ok"}
        mock_resp.raise_for_status = Mock()
        mock_requests.get.return_value = mock_resp

        result = runner.invoke(cli, ["health", "check", "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "healthy"

    @patch("datahub_cli.commands.health._requests")
    def test_check_health_unavailable(self, mock_requests, runner, mock_api_client):
        """Test health check when service is down"""
        mock_api_client._get_base_url.return_value = "http://localhost:8001/api/v1"
        mock_requests.get.side_effect = Exception("Connection refused")

        result = runner.invoke(cli, ["health", "check"])

        assert result.exit_code != 0
        assert "Failed to check health" in result.output


class TestHealthComponents:
    """Test components health command"""

    def test_components_ok(self, runner, mock_api_client):
        """Test components health check"""
        mock_api_client.get.return_value = {
            "status": "healthy",
            "database": "ok",
            "redis": {"cache": "ok", "queue": "ok"},
        }

        result = runner.invoke(cli, ["health", "components"])

        assert result.exit_code == 0
        assert "healthy" in result.output

    def test_components_error(self, runner, mock_api_client):
        """Test components check with API error"""
        mock_api_client.get.side_effect = Exception("Timeout")

        result = runner.invoke(cli, ["health", "components"])

        assert result.exit_code != 0


class TestHealthCircuitBreakers:
    """Test circuit-breakers health command"""

    def test_circuit_breakers(self, runner, mock_api_client):
        """Test circuit breaker status check"""
        mock_api_client.get.return_value = {"status": "ok", "total_breakers": 5, "open_breakers": 0}

        result = runner.invoke(cli, ["health", "circuit-breakers"])

        assert result.exit_code == 0
        assert "5" in result.output
        mock_api_client.get.assert_called_once_with("/health/circuit-breakers/")

    def test_circuit_breakers_error(self, runner, mock_api_client):
        """Test circuit breakers with auth error"""
        mock_api_client.get.side_effect = Exception("Unauthorized")

        result = runner.invoke(cli, ["health", "circuit-breakers"])

        assert result.exit_code != 0


class TestHealthLive:
    """Test liveness probe command"""

    def test_liveness_ok(self, runner, mock_api_client):
        """Test liveness probe returns ok"""
        mock_api_client.get.return_value = {"status": "ok"}

        result = runner.invoke(cli, ["health", "live"])

        assert result.exit_code == 0
        assert "ok" in result.output

    def test_liveness_failed(self, runner, mock_api_client):
        """Test liveness probe failure"""
        mock_api_client.get.return_value = {"status": "unhealthy"}

        result = runner.invoke(cli, ["health", "live"])

        assert result.exit_code != 0
