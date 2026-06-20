"""
Phase 118E — CLI New Features Tests

Tests all new commands parse correctly (--help exits 0)
and required arguments/options are enforced.
Uses Click's CliRunner for isolated CLI testing.
"""

import pytest
from click.testing import CliRunner
from datahub_cli.commands.baas import baas
from datahub_cli.commands.billing import billing
from datahub_cli.commands.compliance import compliance
from datahub_cli.commands.dq import dq
from datahub_cli.commands.governance import governance
from datahub_cli.commands.ml import ml
from datahub_cli.commands.scheduled_export import (
    scheduled_export,
)
from datahub_cli.commands.scheduled_ingestion import (
    scheduled_ingestion,
)
from datahub_cli.commands.semantic import semantic
from datahub_cli.commands.transformation import transformation


@pytest.fixture
def runner():
    return CliRunner()


# ── 118E.1: transformation commands ──────────────────────


class TestTransformation:
    def test_pipelines_list_help(self, runner):
        r = runner.invoke(
            transformation,
            ["pipelines", "list", "--help"],
        )
        assert r.exit_code == 0
        assert "List transformation pipelines" in r.output

    def test_pipelines_get_help(self, runner):
        r = runner.invoke(
            transformation,
            ["pipelines", "get", "--help"],
        )
        assert r.exit_code == 0
        assert "Get pipeline details" in r.output
        assert "PIPELINE_ID" in r.output

    def test_pipelines_create_help(self, runner):
        r = runner.invoke(
            transformation,
            ["pipelines", "create", "--help"],
        )
        assert r.exit_code == 0
        assert "--name" in r.output

    def test_pipelines_create_requires_name(self, runner):
        r = runner.invoke(
            transformation,
            ["pipelines", "create"],
        )
        assert r.exit_code != 0

    def test_pipelines_update_help(self, runner):
        r = runner.invoke(
            transformation,
            ["pipelines", "update", "--help"],
        )
        assert r.exit_code == 0
        assert "Update a transformation pipeline" in r.output
        assert "PIPELINE_ID" in r.output

    def test_pipelines_delete_help(self, runner):
        r = runner.invoke(
            transformation,
            ["pipelines", "delete", "--help"],
        )
        assert r.exit_code == 0
        assert "Delete a transformation pipeline" in r.output
        assert "PIPELINE_ID" in r.output

    def test_pipelines_validate_help(self, runner):
        r = runner.invoke(
            transformation,
            ["pipelines", "validate", "--help"],
        )
        assert r.exit_code == 0
        assert "Validate a transformation pipeline" in r.output
        assert "PIPELINE_ID" in r.output

    def test_runs_list_help(self, runner):
        r = runner.invoke(
            transformation,
            ["runs", "list", "--help"],
        )
        assert r.exit_code == 0
        assert "List transformation runs" in r.output

    def test_runs_get_help(self, runner):
        r = runner.invoke(
            transformation,
            ["runs", "get", "--help"],
        )
        assert r.exit_code == 0
        assert "Get transformation run details" in r.output
        assert "RUN_ID" in r.output

    def test_runs_submit_help(self, runner):
        r = runner.invoke(
            transformation,
            ["runs", "submit", "--help"],
        )
        assert r.exit_code == 0
        assert "Submit a new transformation run" in r.output
        assert "PIPELINE_ID" in r.output

    def test_runs_cancel_help(self, runner):
        r = runner.invoke(
            transformation,
            ["runs", "cancel", "--help"],
        )
        assert r.exit_code == 0
        assert "Cancel a running transformation" in r.output
        assert "RUN_ID" in r.output

    def test_plan_limits_help(self, runner):
        r = runner.invoke(
            transformation,
            ["plan-limits", "--help"],
        )
        assert r.exit_code == 0
        assert "Show transformation plan limits" in r.output


# ── 118E.10: semantic commands ───────────────────────────


class TestSemantic:
    def test_sparql_query_help(self, runner):
        r = runner.invoke(
            semantic,
            ["sparql", "query", "--help"],
        )
        assert r.exit_code == 0
        assert "--query" in r.output
        assert "--file" in r.output

    def test_sparql_service_description_help(self, runner):
        r = runner.invoke(
            semantic,
            ["sparql", "service-description", "--help"],
        )
        assert r.exit_code == 0
        assert "Get SPARQL service description" in r.output

    def test_ontology_help(self, runner):
        r = runner.invoke(
            semantic,
            ["ontology", "--help"],
        )
        assert r.exit_code == 0
        assert "Get ontology definition" in r.output

    def test_context_help(self, runner):
        # Phase 230.6 self-audit GAP-1 — public docs advertise
        # ``meshant semantic context`` (semantic-resources.md line 118),
        # so the CLI MUST expose it.
        r = runner.invoke(
            semantic,
            ["context", "--help"],
        )
        assert r.exit_code == 0
        assert "JSON-LD" in r.output
        assert "Get the JSON-LD context document." in r.output

    def test_void_help(self, runner):
        r = runner.invoke(
            semantic,
            ["void", "--help"],
        )
        assert r.exit_code == 0
        assert "Get VoID dataset description" in r.output

    def test_shacl_validate_help(self, runner):
        r = runner.invoke(
            semantic,
            ["shacl", "validate", "--help"],
        )
        assert r.exit_code == 0
        assert "Validate RDF data against SHACL shapes" in r.output


# ── 118E.4: billing new commands ─────────────────────────


class TestBilling:
    def test_plan_limits_help(self, runner):
        r = runner.invoke(billing, ["plan-limits", "--help"])
        assert r.exit_code == 0
        assert "Show current plan limits and usage" in r.output

    def test_usage_help(self, runner):
        r = runner.invoke(billing, ["usage", "--help"])
        assert r.exit_code == 0
        assert "--resource-type" in r.output

    def test_refund_help(self, runner):
        r = runner.invoke(billing, ["refund", "--help"])
        assert r.exit_code == 0
        assert "--amount" in r.output
        assert "--reason" in r.output

    def test_refund_requires_args(self, runner):
        r = runner.invoke(billing, ["refund"])
        assert r.exit_code != 0

    def test_reconcile_help(self, runner):
        r = runner.invoke(billing, ["reconcile", "--help"])
        assert r.exit_code == 0
        assert "--dry-run" in r.output


# ── 118E.5-6: baas new commands ──────────────────────────


class TestBaaS:
    def test_customers_list_help(self, runner):
        r = runner.invoke(
            baas,
            ["customers", "list", "--help"],
        )
        assert r.exit_code == 0
        assert "List BaaS customers" in r.output

    def test_customers_usage_help(self, runner):
        r = runner.invoke(
            baas,
            ["customers", "usage", "--help"],
        )
        assert r.exit_code == 0
        assert "--period" in r.output

    def test_billing_reports_list_help(self, runner):
        r = runner.invoke(
            baas,
            ["billing-reports", "list", "--help"],
        )
        assert r.exit_code == 0
        assert "List billing reports" in r.output

    def test_billing_reports_generate_help(self, runner):
        r = runner.invoke(
            baas,
            ["billing-reports", "generate", "--help"],
        )
        assert r.exit_code == 0
        assert "--period" in r.output

    def test_api_keys_rotate_help(self, runner):
        r = runner.invoke(
            baas,
            ["api-keys", "rotate", "--help"],
        )
        assert r.exit_code == 0
        assert "--grace-hours" in r.output


# ── 118E.7: ml new commands ──────────────────────────────


class TestML:
    def test_deploy_help(self, runner):
        r = runner.invoke(ml, ["deploy", "--help"])
        assert r.exit_code == 0
        assert "--config-file" in r.output

    def test_undeploy_help(self, runner):
        r = runner.invoke(ml, ["undeploy", "--help"])
        assert r.exit_code == 0
        assert "Undeploy an ML model" in r.output

    def test_rollback_help(self, runner):
        r = runner.invoke(ml, ["rollback", "--help"])
        assert r.exit_code == 0
        assert "--version" in r.output

    def test_plan_show_help(self, runner):
        r = runner.invoke(ml, ["plan", "show", "--help"])
        assert r.exit_code == 0
        assert "Show current ML subscription plan" in r.output

    def test_plan_limits_help(self, runner):
        r = runner.invoke(ml, ["plan", "limits", "--help"])
        assert r.exit_code == 0
        assert "Show ML plan limits" in r.output

    def test_marketplace_publish_help(self, runner):
        r = runner.invoke(
            ml,
            ["marketplace-publish", "--help"],
        )
        assert r.exit_code == 0
        assert "--pricing-model" in r.output


# ── 118E.8: compliance new commands ──────────────────────


class TestCompliance:
    def test_scan_async_help(self, runner):
        r = runner.invoke(
            compliance,
            ["scan-async", "--help"],
        )
        assert r.exit_code == 0
        assert "--file-id" in r.output
        assert "--regulations" in r.output

    def test_scan_result_help(self, runner):
        r = runner.invoke(
            compliance,
            ["scan-result", "--help"],
        )
        assert r.exit_code == 0
        assert "Get async compliance scan result" in r.output
        assert "JOB_ID" in r.output

    def test_regulations_list_help(self, runner):
        r = runner.invoke(
            compliance,
            ["regulations", "list", "--help"],
        )
        assert r.exit_code == 0
        assert "List available regulations" in r.output

    def test_regulations_get_help(self, runner):
        r = runner.invoke(
            compliance,
            ["regulations", "get", "--help"],
        )
        assert r.exit_code == 0
        assert "Get regulation details" in r.output


# ── 118E.9: governance workflows ─────────────────────────


class TestGovernance:
    def test_workflows_list_help(self, runner):
        r = runner.invoke(
            governance,
            ["workflows", "list", "--help"],
        )
        assert r.exit_code == 0
        assert "--status" in r.output

    def test_workflows_get_help(self, runner):
        r = runner.invoke(
            governance,
            ["workflows", "get", "--help"],
        )
        assert r.exit_code == 0
        assert "Get workflow details" in r.output
        assert "WORKFLOW_ID" in r.output

    def test_workflows_retry_help(self, runner):
        r = runner.invoke(
            governance,
            ["workflows", "retry", "--help"],
        )
        assert r.exit_code == 0
        assert "Retry a failed governance workflow" in r.output
        assert "WORKFLOW_ID" in r.output


# ── 118E.11-13: display field & watch tests ──────────────


class TestDQ:
    def test_watch_help(self, runner):
        r = runner.invoke(dq, ["watch", "--help"])
        assert r.exit_code == 0
        assert "--timeout" in r.output
        assert "--interval" in r.output


class TestScheduledIngestion:
    def test_get_help(self, runner):
        r = runner.invoke(
            scheduled_ingestion,
            ["get", "--help"],
        )
        assert r.exit_code == 0
        assert "Get scheduled ingestion details" in r.output

    def test_run_detail_help(self, runner):
        r = runner.invoke(
            scheduled_ingestion,
            ["run-detail", "--help"],
        )
        assert r.exit_code == 0
        assert "Get scheduled ingestion run details" in r.output
        assert "RUN_ID" in r.output


class TestScheduledExport:
    def test_get_help(self, runner):
        r = runner.invoke(
            scheduled_export,
            ["get", "--help"],
        )
        assert r.exit_code == 0
        assert "Get scheduled export details" in r.output


# ── 118E.2: main.py registration ─────────────────────────


class TestMainRegistration:
    def test_transformation_registered(self, runner):
        from datahub_cli.main import cli

        r = runner.invoke(cli, ["transformation", "--help"])
        assert r.exit_code == 0
        assert "pipelines" in r.output
        assert "runs" in r.output

    def test_semantic_registered(self, runner):
        from datahub_cli.main import cli

        r = runner.invoke(cli, ["semantic", "--help"])
        assert r.exit_code == 0
        assert "sparql" in r.output
