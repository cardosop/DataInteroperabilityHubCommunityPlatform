"""
Phase 118A — CLI Endpoint & Parameter Fixes (GF-22.1–22.7)

TDD tests verifying that CLI commands send the correct endpoint paths
and filter parameter names to match the backend ViewSet implementations.

These tests mock the api_client to assert the exact API call parameters,
ensuring CLI-backend contract alignment without requiring a running server.
"""
import json

import pytest
from click.testing import CliRunner
from unittest.mock import Mock

from datahub_cli.main import cli


@pytest.fixture
def runner():
    """CLI runner fixture"""
    return CliRunner()


# ---------------------------------------------------------------------------
# 118A.1 — compliance.py: filter param must be 'asset' (not 'asset_id')
# Backend: ComplianceRunViewSet.get_queryset() reads query_params.get("asset")
# ---------------------------------------------------------------------------
class TestComplianceFilterParam:
    """Verify compliance list sends 'asset' (not 'asset_id') to backend."""

    @pytest.fixture
    def mock_api_client(self, monkeypatch):
        mock_client = Mock()
        monkeypatch.setattr("datahub_cli.commands.compliance.api_client", mock_client)
        return mock_client

    def test_list_sends_asset_not_asset_id(self, runner, mock_api_client):
        """compliance list --asset-id should send param key 'asset'."""
        mock_api_client.get.return_value = {"results": []}

        result = runner.invoke(cli, [
            "compliance", "list",
            "--asset-id", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "--format", "json",
        ])

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        mock_api_client.get.assert_called_once()
        call_args = mock_api_client.get.call_args
        params = call_args[1].get("params") or call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("params", {})
        # The key MUST be 'asset', NOT 'asset_id'
        assert "asset" in params, f"Expected 'asset' in params, got: {params}"
        assert "asset_id" not in params, f"'asset_id' should NOT be in params: {params}"
        assert params["asset"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

    def test_report_sends_asset_not_asset_id(self, runner, mock_api_client):
        """compliance report fetches runs with param key 'asset'."""
        # The report command first fetches asset, then fetches compliance runs
        mock_api_client.get.side_effect = [
            {"name": "Test Asset"},  # GET assets/{id}/
            {"results": [{"id": "run-1", "overall_status": "COMPLIANT",
                          "risk_level": "LOW", "allowed_to_store": True,
                          "detected_categories_json": {}, "regulation_mapping_json": {},
                          "completed_at": "2026-01-01"}]},  # GET compliance/runs/
        ]

        result = runner.invoke(cli, [
            "compliance", "report",
            "--asset-id", "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "--regulation", "GDPR",
            "--format", "json",
        ])

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        # Second call is to compliance/runs/ with filter params
        compliance_call = mock_api_client.get.call_args_list[1]
        params = compliance_call[1].get("params") or compliance_call[0][1] if len(compliance_call[0]) > 1 else compliance_call[1].get("params", {})
        assert "asset" in params, f"Expected 'asset' in params, got: {params}"
        assert "asset_id" not in params, f"'asset_id' should NOT be in params: {params}"

    def test_list_without_asset_id_omits_param(self, runner, mock_api_client):
        """compliance list without --asset-id should not include 'asset' param."""
        mock_api_client.get.return_value = {"results": []}

        result = runner.invoke(cli, ["compliance", "list", "--format", "json"])

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        call_args = mock_api_client.get.call_args
        params = call_args[1].get("params") or call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("params", {})
        assert "asset" not in params
        assert "asset_id" not in params


# ---------------------------------------------------------------------------
# 118A.5 — lineage.py: field lineage path must NOT include model_name segment
# Backend URL: contracts/{id}/fields/{field_name}/lineage/
# model_name is passed as query param: ?model_name=xxx
# ---------------------------------------------------------------------------
class TestLineageFieldEndpoint:
    """Verify field lineage sends correct URL path (no model_name in path)."""

    @pytest.fixture
    def mock_api_client(self, monkeypatch):
        mock_client = Mock()
        monkeypatch.setattr("datahub_cli.commands.lineage.api_client", mock_client)
        return mock_client

    def test_field_lineage_url_has_no_model_name_segment(self, runner, mock_api_client):
        """Field lineage URL must be contracts/{id}/fields/{field}/lineage/."""
        mock_api_client.get.return_value = {
            "lineage": {"input_fields": []}
        }

        result = runner.invoke(cli, [
            "lineage", "field", "contract-1", "model1", "field1",
        ])

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        mock_api_client.get.assert_called_once()
        call_args = mock_api_client.get.call_args

        # URL must be contracts/{id}/fields/{field_name}/lineage/
        # NOT contracts/{id}/fields/{model_name}/{field_name}/lineage/
        url = call_args[0][0]
        assert url == "contracts/contract-1/fields/field1/lineage/", (
            f"Expected 'contracts/contract-1/fields/field1/lineage/', got: {url}"
        )

    def test_field_lineage_passes_model_name_as_query_param(self, runner, mock_api_client):
        """model_name must be passed as query parameter, not path segment."""
        mock_api_client.get.return_value = {
            "lineage": {"input_fields": []}
        }

        result = runner.invoke(cli, [
            "lineage", "field", "contract-1", "model1", "field1",
        ])

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        call_args = mock_api_client.get.call_args
        params = call_args[1].get("params", {})
        assert params.get("model_name") == "model1", (
            f"Expected model_name='model1' in params, got: {params}"
        )

    def test_field_lineage_display_still_works(self, runner, mock_api_client):
        """Field lineage table output still shows model.field notation."""
        mock_api_client.get.return_value = {
            "lineage": {
                "input_fields": [
                    {"namespace": "ns1", "name": "c1", "model_name": "m1", "field": "f1"}
                ]
            }
        }

        result = runner.invoke(cli, [
            "lineage", "field", "contract-1", "model1", "field1",
        ])

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        assert "Field Lineage: model1.field1" in result.output
        assert "ns1/c1/m1.f1" in result.output


# ---------------------------------------------------------------------------
# 118A.7 — dq.py: endpoint must be 'dq/runs/' (not 'dq-runs/')
# Backend: api/urls.py has path("dq/", include("hub.apps.dq.urls"))
#          dq/urls.py has router.register(r"runs", ...)
#          Final path: /api/v1/dq/runs/
# ---------------------------------------------------------------------------
class TestDQEndpointPath:
    """Verify DQ commands use 'dq/runs/' endpoint path."""

    @pytest.fixture
    def mock_api_client(self, monkeypatch):
        mock_client = Mock()
        monkeypatch.setattr("datahub_cli.commands.dq.api_client", mock_client)
        return mock_client

    def test_dq_run_post_uses_correct_endpoint(self, runner, mock_api_client):
        """dq run POST must hit dq/runs/, not dq-runs/."""
        mock_api_client.post.return_value = {
            "dq_run": {"id": "run-1", "status": "PENDING", "profile_key": "intake_basic_gx"},
            "job": {"id": "job-1"},
        }

        result = runner.invoke(cli, [
            "dq", "run",
            "--asset-id", "asset-1",
            "--format", "json",
        ])

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        call_args = mock_api_client.post.call_args
        url = call_args[0][0]
        assert url == "dq/runs/", f"Expected 'dq/runs/', got: {url}"

    def test_dq_get_uses_correct_endpoint(self, runner, mock_api_client):
        """dq get must hit dq/runs/{id}/, not dq-runs/{id}/."""
        mock_api_client.get.return_value = {
            "id": "run-1", "status": "SUCCEEDED",
            "overall_status": "PASS", "quality_score": 95,
        }

        result = runner.invoke(cli, ["dq", "get", "run-1", "--format", "json"])

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        call_args = mock_api_client.get.call_args
        url = call_args[0][0]
        assert url == "dq/runs/run-1/", f"Expected 'dq/runs/run-1/', got: {url}"

    def test_dq_list_uses_correct_endpoint(self, runner, mock_api_client):
        """dq list must hit dq/runs/, not dq-runs/."""
        mock_api_client.get.return_value = {"results": []}

        result = runner.invoke(cli, ["dq", "list", "--format", "json"])

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        call_args = mock_api_client.get.call_args
        url = call_args[0][0]
        assert url == "dq/runs/", f"Expected 'dq/runs/', got: {url}"

    def test_dq_watch_uses_correct_endpoint(self, runner, mock_api_client):
        """dq watch must hit dq/runs/{id}/, not dq-runs/{id}/."""
        mock_api_client.get.return_value = {
            "id": "run-1", "status": "SUCCEEDED",
            "overall_status": "PASS", "quality_score": 95,
        }

        result = runner.invoke(cli, [
            "dq", "watch", "run-1",
            "--interval", "0",
            "--timeout", "1",
            "--format", "json",
        ])

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        call_args = mock_api_client.get.call_args
        url = call_args[0][0]
        assert url == "dq/runs/run-1/", f"Expected 'dq/runs/run-1/', got: {url}"

    def test_dq_list_filter_uses_dataset_id(self, runner, mock_api_client):
        """dq list --dataset-id should send 'dataset_id' param (matches backend)."""
        mock_api_client.get.return_value = {"results": []}

        result = runner.invoke(cli, [
            "dq", "list",
            "--dataset-id", "ds-1",
            "--format", "json",
        ])

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        call_args = mock_api_client.get.call_args
        params = call_args[1].get("params", {})
        assert params.get("dataset_id") == "ds-1"


# ---------------------------------------------------------------------------
# Verified-correct endpoints (no-fix-needed regression tests)
# ---------------------------------------------------------------------------
class TestBillingEndpointCorrect:
    """118A.2: Verify billing subscription endpoint is correct."""

    @pytest.fixture
    def mock_api_client(self, monkeypatch):
        mock_client = Mock()
        monkeypatch.setattr("datahub_cli.commands.billing.api_client", mock_client)
        return mock_client

    def test_subscription_uses_correct_endpoint(self, runner, mock_api_client):
        """billing subscription must hit billing/subscription/current/."""
        mock_api_client.get.return_value = {
            "id": "sub-1", "plan_name": "Pro", "plan_slug": "pro",
            "plan_tier": "PROFESSIONAL", "status": "ACTIVE",
        }

        result = runner.invoke(cli, ["billing", "subscription", "--format", "json"])

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        call_args = mock_api_client.get.call_args
        url = call_args[0][0]
        assert url == "billing/subscription/current/"


class TestGovernanceFieldsCorrect:
    """118A.3: Verify governance access request field names are correct."""

    @pytest.fixture
    def mock_api_client(self, monkeypatch):
        mock_client = Mock()
        monkeypatch.setattr("datahub_cli.commands.governance.api_client", mock_client)
        return mock_client

    def test_create_sends_correct_field_names(self, runner, mock_api_client):
        """access-request create sends asset_id, reason, requested_access_type."""
        mock_api_client.post.return_value = {
            "id": "req-1", "status": "PENDING",
            "requested_access_type": "READ",
        }

        result = runner.invoke(cli, [
            "governance", "access-request", "create",
            "--asset-id", "asset-1",
            "--reason", "Need access for analysis",
            "--format", "json",
        ])

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        call_args = mock_api_client.post.call_args
        data = call_args[1].get("json_data", {})
        assert data.get("asset_id") == "asset-1"
        assert data.get("reason") == "Need access for analysis"
        assert data.get("requested_access_type") == "READ"

    def test_list_filter_sends_asset_id(self, runner, mock_api_client):
        """access-request list --asset-id sends 'asset_id' param (matches backend)."""
        mock_api_client.get.return_value = {"results": []}

        result = runner.invoke(cli, [
            "governance", "access-request", "list",
            "--asset-id", "asset-1",
            "--format", "json",
        ])

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        call_args = mock_api_client.get.call_args
        params = call_args[1].get("params", {})
        assert params.get("asset_id") == "asset-1"


class TestFilesEndpointCorrect:
    """118A.4: Verify files endpoints use 'files/' not doubled 'files/files/'."""

    @pytest.fixture
    def mock_api_client(self, monkeypatch):
        mock_client = Mock()
        monkeypatch.setattr("datahub_cli.commands.files.api_client", mock_client)
        return mock_client

    def test_list_uses_files_not_files_files(self, runner, mock_api_client):
        """files list must hit files/, not files/files/."""
        mock_api_client.get.return_value = {"results": []}

        result = runner.invoke(cli, ["files", "list", "--format", "json"])

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        call_args = mock_api_client.get.call_args
        url = call_args[0][0]
        assert url == "files/", f"Expected 'files/', got: {url}"
        assert "files/files/" not in url

    def test_upload_init_uses_files_init(self, runner, mock_api_client, tmp_path):
        """files upload init must hit files/init/, not files/files/init/."""
        test_file = tmp_path / "test.csv"
        test_file.write_text("a,b,c\n1,2,3\n")

        mock_api_client.post.side_effect = [
            {"file_id": "file-1", "upload_url": "https://s3.example.com/upload"},
            {"id": "file-1", "name": "test.csv", "size": 14, "status": "ACTIVE"},
        ]

        import requests
        from unittest.mock import patch
        with patch.object(requests, "put") as mock_put:
            mock_put.return_value = Mock(status_code=200, raise_for_status=Mock())
            result = runner.invoke(cli, [
                "files", "upload", str(test_file),
                "--format", "json",
            ])

        # Check the init call uses correct path
        init_call = mock_api_client.post.call_args_list[0]
        init_url = init_call[0][0]
        assert init_url == "files/init/", f"Expected 'files/init/', got: {init_url}"

        # Check upload_method is sent
        init_data = init_call[1].get("json_data", {})
        assert init_data.get("upload_method") == "sdk"

        # Check complete call uses correct path
        complete_call = mock_api_client.post.call_args_list[1]
        complete_url = complete_call[0][0]
        assert complete_url == "files/file-1/complete/", (
            f"Expected 'files/file-1/complete/', got: {complete_url}"
        )

    def test_download_uses_files_id(self, runner, mock_api_client):
        """files download must hit files/{id}/, not files/files/{id}/."""
        mock_api_client.get.return_value = {"id": "f1", "name": "test.csv", "size": 10}
        mock_api_client.post.return_value = {"download_url": "https://s3.example.com/dl"}

        import requests
        from unittest.mock import patch
        with patch.object(requests, "get") as mock_get:
            mock_resp = Mock()
            mock_resp.raise_for_status = Mock()
            mock_resp.iter_content.return_value = [b"data"]
            mock_get.return_value = mock_resp
            result = runner.invoke(cli, [
                "files", "download", "f1",
                "--output", "/dev/null",
            ])

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        get_url = mock_api_client.get.call_args[0][0]
        assert get_url == "files/f1/", f"Expected 'files/f1/', got: {get_url}"
        post_url = mock_api_client.post.call_args[0][0]
        assert post_url == "files/f1/download/", f"Expected 'files/f1/download/', got: {post_url}"

    def test_delete_uses_files_id(self, runner, mock_api_client):
        """files delete must hit files/{id}/, not files/files/{id}/."""
        mock_api_client.delete.return_value = {}

        result = runner.invoke(cli, ["files", "delete", "f1", "--confirm"])

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        del_url = mock_api_client.delete.call_args[0][0]
        assert del_url == "files/f1/", f"Expected 'files/f1/', got: {del_url}"


class TestScheduledExportEndpointCorrect:
    """118A.6: Verify scheduled export uses correct endpoint path."""

    @pytest.fixture
    def mock_api_client(self, monkeypatch):
        mock_client = Mock()
        monkeypatch.setattr("datahub_cli.commands.scheduled_export.api_client", mock_client)
        return mock_client

    def test_list_uses_correct_endpoint(self, runner, mock_api_client):
        """scheduled_export list must hit scheduled-exports/."""
        mock_api_client.get.return_value = {"results": []}

        result = runner.invoke(cli, ["scheduled-export", "list", "--format", "json"])

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        call_args = mock_api_client.get.call_args
        url = call_args[0][0]
        assert url == "scheduled-exports/"


class TestAuditFilterParamsCorrect:
    """118A.7 (audit): Verify audit filter param names match backend."""

    @pytest.fixture
    def mock_api_client(self, monkeypatch):
        mock_client = Mock()
        monkeypatch.setattr("datahub_cli.commands.audit.api_client", mock_client)
        return mock_client

    def test_query_sends_correct_filter_params(self, runner, mock_api_client):
        """audit query sends actor_user_id, resource_type, action, start_date, end_date."""
        mock_api_client.get.return_value = {"results": []}

        result = runner.invoke(cli, [
            "audit", "query",
            "--resource-type", "CONTRACT",
            "--action", "CREATE",
            "--actor-user-id", "user-1",
            "--start-date", "2026-01-01T00:00:00Z",
            "--end-date", "2026-12-31T23:59:59Z",
            "--format", "json",
        ])

        assert result.exit_code == 0, f"CLI failed: {result.output}"
        call_args = mock_api_client.get.call_args
        params = call_args[1].get("params", {})
        assert params.get("resource_type") == "CONTRACT"
        assert params.get("action") == "CREATE"
        assert params.get("actor_user_id") == "user-1"
        assert params.get("start_date") == "2026-01-01T00:00:00Z"
        assert params.get("end_date") == "2026-12-31T23:59:59Z"
