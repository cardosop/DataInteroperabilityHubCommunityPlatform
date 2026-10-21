"""
Unit tests for Processor Agreements CLI commands.

Tests: processors (list, create, get, delete), agreements (list, create, delete),
links (create).

Backend mount (hub/apps/api/urls.py): /api/v1/processor-agreements/.
"""

from datahub_cli.main import cli
from tests.fixtures.test_data import fresh_id

# Unique per test process (and per xdist worker) so a static literal
# can never collide across parallel runs — Phase 216.X.2.
ASSET_ID = fresh_id("asset")


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
            "processor-agreements/processors/", params={"page": 1, "page_size": 25}
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
        mock_api_client.get.assert_called_once_with("processor-agreements/processors/proc-1/")


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
        mock_api_client.post.return_value = {
            "id": "agr-new",
            "agreement_type": "DPA",
            "status": "ACTIVE",
        }

        result = runner.invoke(
            cli,
            [
                "processor-agreements",
                "agreements",
                "create",
                "--processor-id",
                "proc-1",
                "--type",
                "DPA",
                "--document-uri",
                "https://example.com/dpa.pdf",
                "--document-hash",
                "a" * 64,
                "--effective-from",
                "2026-01-01",
            ],
        )

        assert result.exit_code == 0
        assert "agr-new" in result.output
        assert "DPA" in result.output
        mock_api_client.post.assert_called_once_with(
            "processor-agreements/processor-agreements/",
            json_data={
                "processor": "proc-1",
                "agreement_type": "DPA",
                "document_uri": "https://example.com/dpa.pdf",
                "document_hash": "a" * 64,
                "effective_from": "2026-01-01",
            },
        )


class TestAgreementDelete:
    """Test agreements delete command"""

    def test_delete_agreement(self, runner, mock_api_client):
        """Test deleting an agreement"""
        result = runner.invoke(
            cli,
            ["processor-agreements", "agreements", "delete", "agr-1", "--yes"],
        )

        assert result.exit_code == 0
        assert "Deleted agreement: agr-1" in result.output
        mock_api_client.delete.assert_called_once_with(
            "processor-agreements/processor-agreements/agr-1/"
        )


class TestLinkCreate:
    """Test asset-processor links create command"""

    def test_create_link(self, runner, mock_api_client):
        """Test linking an asset to a processor"""
        mock_api_client.post.return_value = {"id": "link-1"}

        result = runner.invoke(
            cli,
            [
                "processor-agreements",
                "links",
                "create",
                "--asset-id",
                ASSET_ID,
                "--processor-id",
                "proc-1",
            ],
        )

        assert result.exit_code == 0
        assert "link-1" in result.output
        mock_api_client.post.assert_called_once_with(
            "processor-agreements/asset-processor-links/",
            json_data={"asset": ASSET_ID, "processor": "proc-1"},
        )
