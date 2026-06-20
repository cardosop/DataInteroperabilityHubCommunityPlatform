"""
Unit tests for Processor Agreements CLI commands.

Tests: processors (list, create, get, update, delete), agreements (list, create, sign, revoke).
"""

from datahub_cli.main import cli


class TestProcessorList:
    """Test processors list command"""

    def test_list_processors(self, runner, mock_api_client):
        """Test listing registered processors"""
        mock_api_client.get.return_value = {
            "results": [
                {
                    "id": "proc-1",
                    "name": "AWS",
                    "country_code": "US",
                    "created_at": "2026-01-01T00:00:00Z",
                }
            ]
        }

        result = runner.invoke(cli, ["processor-agreements", "processors", "list"])

        assert result.exit_code == 0
        assert "AWS" in result.output
        mock_api_client.get.assert_called_once_with(
            "governance/processors/", params={"page": 1, "page_size": 25}
        )

    def test_list_processors_empty(self, runner, mock_api_client):
        """Test listing processors when none registered"""
        mock_api_client.get.return_value = {"results": [], "count": 0}

        result = runner.invoke(cli, ["processor-agreements", "processors", "list"])

        assert result.exit_code == 0
        assert "No processors" in result.output

    def test_list_processors_json(self, runner, mock_api_client):
        """Test listing processors in JSON format"""
        mock_api_client.get.return_value = {"results": []}

        result = runner.invoke(
            cli, ["processor-agreements", "processors", "list", "--format", "json"]
        )

        assert result.exit_code == 0


class TestProcessorCreate:
    """Test processors create command"""

    def test_create_processor(self, runner, mock_api_client):
        """Test creating a processor"""
        mock_api_client.post.return_value = {"id": "proc-new", "name": "GCP", "country_code": "US"}

        result = runner.invoke(
            cli,
            [
                "processor-agreements",
                "processors",
                "create",
                "--name",
                "GCP",
                "--country-code",
                "US",
            ],
        )

        assert result.exit_code == 0
        assert "GCP" in result.output


class TestProcessorGet:
    """Test processors get command"""

    def test_get_processor(self, runner, mock_api_client):
        """Test getting a processor by ID"""
        mock_api_client.get.return_value = {"id": "proc-1", "name": "AWS", "country_code": "US"}

        result = runner.invoke(cli, ["processor-agreements", "processors", "get", "proc-1"])

        assert result.exit_code == 0
        assert "AWS" in result.output


class TestAgreementList:
    """Test agreements list command"""

    def test_list_agreements(self, runner, mock_api_client):
        """Test listing processor agreements"""
        mock_api_client.get.return_value = {
            "results": [{"id": "agr-1", "processor_name": "AWS", "status": "ACTIVE"}]
        }

        result = runner.invoke(cli, ["processor-agreements", "agreements", "list"])

        assert result.exit_code == 0
        assert "AWS" in result.output


class TestAgreementCreate:
    """Test agreements create command"""

    def test_create_agreement(self, runner, mock_api_client):
        """Test creating an agreement"""
        mock_api_client.post.return_value = {"id": "agr-new", "status": "DRAFT"}

        result = runner.invoke(
            cli,
            [
                "processor-agreements",
                "agreements",
                "create",
                "--processor-id",
                "proc-1",
                "--transfer-purpose",
                "Cloud hosting",
                "--data-categories",
                "PII",
            ],
        )

        assert result.exit_code == 0
        assert "DRAFT" in result.output


class TestAgreementSign:
    """Test agreements sign command"""

    def test_sign_agreement(self, runner, mock_api_client):
        """Test signing an agreement"""
        mock_api_client.post.return_value = {
            "status": "SIGNED",
            "signed_at": "2026-01-01T00:00:00Z",
        }

        result = runner.invoke(cli, ["processor-agreements", "agreements", "sign", "agr-1"])

        assert result.exit_code == 0
        assert "SIGNED" in result.output


class TestAgreementRevoke:
    """Test agreements revoke command"""

    def test_revoke_agreement(self, runner, mock_api_client):
        """Test revoking an agreement"""
        mock_api_client.post.return_value = {"status": "REVOKED"}

        result = runner.invoke(cli, ["processor-agreements", "agreements", "revoke", "agr-1"])

        assert result.exit_code == 0
        assert "REVOKED" in result.output
