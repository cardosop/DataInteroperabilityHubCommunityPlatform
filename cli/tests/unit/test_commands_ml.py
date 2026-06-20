from tests.pytest_mvp_skip import skip_if_mvp_mode

pytestmark = skip_if_mvp_mode

"""
Comprehensive unit tests for ML Model Registry CLI commands.

Tests command group registration, help text, argument validation, and command structure.
These tests focus on CLI command registration and validation without API calls.
"""
import json

import pytest
from click.testing import CliRunner
from datahub_cli.commands import ml
from datahub_cli.main import cli
from datahub_cli.ml_errors import (
    ODHMLModelParameterError,
    validate_model_status,
    validate_model_type,
    validate_uuid,
)


class TestMLCommandGroup:
    """Test ML command group registration and structure"""

    @pytest.fixture
    def runner(self):
        """Create CLI runner"""
        return CliRunner()

    def test_ml_command_group_registered(self, runner):
        """Test that ML command group is registered in main CLI"""
        result = runner.invoke(cli, ["ml", "--help"])
        assert result.exit_code == 0
        assert "ML Model Registry management commands" in result.output

    def test_ml_command_group_help(self, runner):
        """Test ML command group help text"""
        result = runner.invoke(ml.ml, ["--help"])
        assert result.exit_code == 0
        assert "ML Model Registry management commands" in result.output

    def test_ml_command_group_importable(self):
        """Test that ML command group can be imported"""
        from datahub_cli.commands.ml import ml as ml_group

        assert ml_group is not None
        assert callable(ml_group)

    def test_ml_command_group_in_main_cli(self):
        """Test that ML command group is available in main CLI"""
        from datahub_cli.main import cli as main_cli

        # Check that ML command is registered
        commands = [cmd.name for cmd in main_cli.commands.values()]
        assert "ml" in commands

    def test_ml_command_group_in_commands_init(self):
        """Test that ML is exported from commands __init__"""
        from datahub_cli.commands import ml as ml_module

        assert ml_module is not None
        assert hasattr(ml_module, "ml")

    def test_ml_invalid_subcommand(self, runner):
        """Test handling invalid ML subcommand"""
        result = runner.invoke(ml.ml, ["invalid-subcommand"])
        assert result.exit_code != 0
        assert "No such command" in result.output or "Usage:" in result.output

    def test_ml_command_group_structure(self):
        """Test that ML command group has correct structure"""
        from datahub_cli.commands.ml import ml as ml_group

        # Should be a Click group
        assert hasattr(ml_group, "commands")
        assert isinstance(ml_group.commands, dict)

    def test_ml_commands_in_main_cli_help(self, runner):
        """Test that ML command appears in main CLI help"""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "ml" in result.output.lower()
        assert "ML" in result.output

    def test_ml_module_exported_correctly(self):
        """Test that ML module is correctly exported from commands package"""
        from datahub_cli.commands import ml as ml_module

        assert hasattr(ml_module, "ml")
        ml_cmd = ml_module.ml
        assert ml_cmd is not None
        assert callable(ml_cmd)


class TestMLModelsCommandGroup:
    """Test ML models command group"""

    @pytest.fixture
    def runner(self):
        """Create CLI runner"""
        return CliRunner()

    def test_ml_models_command_group_accessible(self, runner):
        """Test that ML models command group is accessible"""
        result = runner.invoke(cli, ["ml", "models", "--help"])
        assert result.exit_code == 0
        assert "Model registry commands" in result.output

    def test_ml_models_list_command_help(self, runner):
        """Test ML models list command help"""
        result = runner.invoke(cli, ["ml", "models", "list", "--help"])
        assert result.exit_code == 0
        assert "List ML models" in result.output
        assert "--asset-id" in result.output
        assert "--status" in result.output
        assert "--limit" in result.output
        assert "--offset" in result.output
        assert "--format" in result.output

    def test_ml_models_get_command_help(self, runner):
        """Test ML models get command help"""
        result = runner.invoke(cli, ["ml", "models", "get", "--help"])
        assert result.exit_code == 0
        assert "Get model details" in result.output
        assert "MODEL_ID" in result.output
        assert "--format" in result.output

    def test_ml_models_create_command_help(self, runner):
        """Test ML models create command help"""
        result = runner.invoke(cli, ["ml", "models", "create", "--help"])
        assert result.exit_code == 0
        assert "Create a new ML model link" in result.output
        assert "--odh-model-id" in result.output
        assert "--odh-model-name" in result.output
        assert "--odh-model-version" in result.output
        assert "--model-type" in result.output
        assert "--asset-id" in result.output
        assert "--contract-id" in result.output

    def test_ml_models_update_command_help(self, runner):
        """Test ML models update command help"""
        result = runner.invoke(cli, ["ml", "models", "update", "--help"])
        assert result.exit_code == 0
        assert "Update ML model" in result.output
        assert "MODEL_ID" in result.output
        assert "--asset-id" in result.output
        assert "--contract-id" in result.output
        assert "--status" in result.output

    def test_ml_models_delete_command_help(self, runner):
        """Test ML models delete command help"""
        result = runner.invoke(cli, ["ml", "models", "delete", "--help"])
        assert result.exit_code == 0
        assert "Delete ML model" in result.output
        assert "MODEL_ID" in result.output

    def test_ml_models_versions_command_help(self, runner):
        """Test ML models versions command help"""
        result = runner.invoke(cli, ["ml", "models", "versions", "--help"])
        assert result.exit_code == 0
        assert "List all versions of a model" in result.output
        assert "MODEL_ID" in result.output
        assert "--format" in result.output


class TestMLParameterValidation:
    """Test ML parameter validation functions"""

    def test_validate_uuid_valid(self):
        """Test UUID validation with valid UUID"""
        valid_uuid = "123e4567-e89b-12d3-a456-426614174000"
        # Should not raise
        validate_uuid(valid_uuid, "test-id")

    def test_validate_uuid_invalid_format(self):
        """Test UUID validation with invalid format"""
        invalid_uuid = "not-a-uuid"
        with pytest.raises(ODHMLModelParameterError) as exc_info:
            validate_uuid(invalid_uuid, "test-id")
        assert "INVALID_UUID_FORMAT" in str(exc_info.value.error_code) or "Invalid" in str(
            exc_info.value
        )

    def test_validate_uuid_empty(self):
        """Test UUID validation with empty string"""
        with pytest.raises(ODHMLModelParameterError) as exc_info:
            validate_uuid("", "test-id")
        assert (
            "EMPTY_UUID" in str(exc_info.value.error_code) or "empty" in str(exc_info.value).lower()
        )

    def test_validate_model_type_valid(self):
        """Test model type validation with valid types"""
        valid_types = [
            "CLASSIFICATION",
            "REGRESSION",
            "CLUSTERING",
            "NLP",
            "COMPUTER_VISION",
            "RECOMMENDATION",
            "TIME_SERIES",
            "ANOMALY_DETECTION",
            "OTHER",
        ]
        for model_type in valid_types:
            # Should not raise
            validate_model_type(model_type)

    def test_validate_model_type_invalid(self):
        """Test model type validation with invalid type"""
        with pytest.raises(ODHMLModelParameterError) as exc_info:
            validate_model_type("INVALID_TYPE")
        assert "INVALID_MODEL_TYPE" in str(exc_info.value.error_code) or "Invalid" in str(
            exc_info.value
        )

    def test_validate_model_status_valid(self):
        """Test model status validation with valid statuses"""
        valid_statuses = ["TRAINING", "TRAINED", "DEPLOYED", "FAILED", "ARCHIVED"]
        for status in valid_statuses:
            # Should not raise
            validate_model_status(status)

    def test_validate_model_status_invalid(self):
        """Test model status validation with invalid status"""
        with pytest.raises(ODHMLModelParameterError) as exc_info:
            validate_model_status("INVALID_STATUS")
        assert "INVALID_MODEL_STATUS" in str(exc_info.value.error_code) or "Invalid" in str(
            exc_info.value
        )


class TestMLCommandArgumentValidation:
    """Test ML command argument validation"""

    @pytest.fixture
    def runner(self):
        """Create CLI runner"""
        return CliRunner()

    def test_ml_models_list_with_invalid_asset_id_format(self, runner):
        """Test ML models list with invalid asset ID format"""
        result = runner.invoke(cli, ["ml", "models", "list", "--asset-id", "not-a-uuid"])
        assert result.exit_code != 0
        assert "Invalid" in result.output or "UUID" in result.output

    def test_ml_models_get_with_invalid_model_id_format(self, runner):
        """Test ML models get with invalid model ID format"""
        result = runner.invoke(cli, ["ml", "models", "get", "not-a-uuid"])
        assert result.exit_code != 0
        assert "Invalid" in result.output or "UUID" in result.output

    def test_ml_models_create_missing_required_options(self, runner):
        """Test ML models create with missing required options"""
        result = runner.invoke(cli, ["ml", "models", "create"])
        assert result.exit_code != 0
        # Should fail because required options are missing

    def test_ml_models_create_with_invalid_model_type(self, runner):
        """Test ML models create with invalid model type"""
        result = runner.invoke(
            cli,
            [
                "ml",
                "models",
                "create",
                "--odh-model-id",
                "test-id",
                "--odh-model-name",
                "test-name",
                "--odh-model-version",
                "1.0.0",
                "--model-type",
                "INVALID_TYPE",
            ],
        )
        # Click should validate the choice and show error
        assert result.exit_code != 0

    def test_ml_models_create_with_invalid_asset_id_format(self, runner):
        """Test ML models create with invalid asset ID format"""
        result = runner.invoke(
            cli,
            [
                "ml",
                "models",
                "create",
                "--odh-model-id",
                "test-id",
                "--odh-model-name",
                "test-name",
                "--odh-model-version",
                "1.0.0",
                "--model-type",
                "CLASSIFICATION",
                "--asset-id",
                "not-a-uuid",
            ],
        )
        assert result.exit_code != 0
        assert "Invalid" in result.output or "UUID" in result.output

    def test_ml_models_update_with_invalid_model_id_format(self, runner):
        """Test ML models update with invalid model ID format"""
        result = runner.invoke(cli, ["ml", "models", "update", "not-a-uuid"])
        assert result.exit_code != 0
        assert "Invalid" in result.output or "UUID" in result.output

    def test_ml_models_update_with_no_fields(self, runner):
        """Test ML models update with no fields to update"""
        valid_uuid = "123e4567-e89b-12d3-a456-426614174000"
        result = runner.invoke(cli, ["ml", "models", "update", valid_uuid])
        assert result.exit_code != 0
        assert "At least one field" in result.output or "required" in result.output.lower()

    def test_ml_models_delete_with_invalid_model_id_format(self, runner):
        """Test ML models delete with invalid model ID format"""
        result = runner.invoke(cli, ["ml", "models", "delete", "not-a-uuid"])
        assert result.exit_code != 0
        assert "Invalid" in result.output or "UUID" in result.output

    def test_ml_models_versions_with_invalid_model_id_format(self, runner):
        """Test ML models versions with invalid model ID format"""
        result = runner.invoke(cli, ["ml", "models", "versions", "not-a-uuid"])
        assert result.exit_code != 0
        assert "Invalid" in result.output or "UUID" in result.output

    def test_ml_models_list_with_invalid_status(self, runner):
        """Test ML models list with invalid status"""
        result = runner.invoke(cli, ["ml", "models", "list", "--status", "INVALID_STATUS"])
        # Click should validate the choice and show error
        assert result.exit_code != 0

    def test_ml_models_update_with_invalid_status(self, runner):
        """Test ML models update with invalid status"""
        valid_uuid = "123e4567-e89b-12d3-a456-426614174000"
        result = runner.invoke(
            cli, ["ml", "models", "update", valid_uuid, "--status", "INVALID_STATUS"]
        )
        # Click should validate the choice and show error
        assert result.exit_code != 0

    def test_ml_models_list_with_invalid_format(self, runner):
        """Test ML models list with invalid format"""
        result = runner.invoke(cli, ["ml", "models", "list", "--format", "invalid"])
        # Click should validate the choice and show error
        assert result.exit_code != 0

    def test_ml_models_list_with_negative_limit(self, runner):
        """Test ML models list rejects --limit < 1"""
        result = runner.invoke(cli, ["ml", "models", "list", "--limit", "0"])
        assert result.exit_code != 0
        assert "limit must be at least 1" in result.output.lower()

    def test_ml_models_list_with_negative_limit_value(self, runner):
        """Test ML models list rejects negative --limit"""
        result = runner.invoke(cli, ["ml", "models", "list", "--limit", "-1"])
        assert result.exit_code != 0
        assert "limit must be at least 1" in result.output.lower()


class TestMLInferenceCommandGroup:
    """Test ML inference command group"""

    @pytest.fixture
    def runner(self):
        """Create CLI runner"""
        return CliRunner()

    def test_ml_inference_command_group_accessible(self, runner):
        """Test that ML inference command group is accessible"""
        result = runner.invoke(cli, ["ml", "inference", "--help"])
        assert result.exit_code == 0
        assert "Inference deployment and prediction commands" in result.output

    def test_ml_inference_deploy_command_help(self, runner):
        """Test ML inference deploy command help"""
        result = runner.invoke(cli, ["ml", "inference", "deploy", "--help"])
        assert result.exit_code == 0
        assert "Deploy a model for inference" in result.output
        assert "--model-id" in result.output
        assert "--config" in result.output
        assert "--format" in result.output

    def test_ml_inference_predict_command_help(self, runner):
        """Test ML inference predict command help"""
        result = runner.invoke(cli, ["ml", "inference", "predict", "--help"])
        assert result.exit_code == 0
        assert "Run inference prediction" in result.output
        assert "--deployment-id" in result.output
        assert "--input-data" in result.output
        assert "--format" in result.output

    def test_ml_inference_list_command_help(self, runner):
        """Test ML inference list command help"""
        result = runner.invoke(cli, ["ml", "inference", "list", "--help"])
        assert result.exit_code == 0
        assert "List inference deployments" in result.output
        assert "--model-id" in result.output
        assert "--status" in result.output
        assert "--limit" in result.output
        assert "--offset" in result.output

    def test_ml_inference_get_command_help(self, runner):
        """Test ML inference get command help"""
        result = runner.invoke(cli, ["ml", "inference", "get", "--help"])
        assert result.exit_code == 0
        assert "Get deployment details" in result.output
        assert "DEPLOYMENT_ID" in result.output
        assert "--format" in result.output

    def test_ml_inference_undeploy_command_help(self, runner):
        """Test ML inference undeploy command help"""
        result = runner.invoke(cli, ["ml", "inference", "undeploy", "--help"])
        assert result.exit_code == 0
        assert "Undeploy a model" in result.output
        assert "DEPLOYMENT_ID" in result.output

    def test_ml_inference_metrics_command_help(self, runner):
        """Test ML inference metrics command help"""
        result = runner.invoke(cli, ["ml", "inference", "metrics", "--help"])
        assert result.exit_code == 0
        assert "Get inference metrics" in result.output
        assert "DEPLOYMENT_ID" in result.output
        assert "--start-time" in result.output
        assert "--end-time" in result.output


class TestMLInferenceParameterValidation:
    """Test ML inference parameter validation"""

    def test_validate_json_valid(self):
        """Test JSON validation with valid JSON"""
        from datahub_cli.ml_errors import validate_json

        valid_json = '{"key": "value"}'
        result = validate_json(valid_json, "test-json")
        assert isinstance(result, dict)
        assert result["key"] == "value"

    def test_validate_json_invalid(self):
        """Test JSON validation with invalid JSON"""
        from datahub_cli.ml_errors import ODHMLModelParameterError, validate_json

        invalid_json = '{"key": "value"'
        with pytest.raises(ODHMLModelParameterError) as exc_info:
            validate_json(invalid_json, "test-json")
        assert "INVALID_JSON_FORMAT" in str(exc_info.value.error_code) or "Invalid" in str(
            exc_info.value
        )

    def test_validate_json_empty(self):
        """Test JSON validation with empty string"""
        from datahub_cli.ml_errors import ODHMLModelParameterError, validate_json

        with pytest.raises(ODHMLModelParameterError) as exc_info:
            validate_json("", "test-json")
        assert (
            "EMPTY_JSON" in str(exc_info.value.error_code) or "empty" in str(exc_info.value).lower()
        )


class TestMLInferenceCommandArgumentValidation:
    """Test ML inference command argument validation"""

    @pytest.fixture
    def runner(self):
        """Create CLI runner"""
        return CliRunner()

    def test_ml_inference_deploy_missing_required_options(self, runner):
        """Test ML inference deploy with missing required options"""
        result = runner.invoke(cli, ["ml", "inference", "deploy"])
        assert result.exit_code != 0
        # Should fail because --model-id is required

    def test_ml_inference_deploy_with_invalid_model_id_format(self, runner):
        """Test ML inference deploy with invalid model ID format"""
        result = runner.invoke(cli, ["ml", "inference", "deploy", "--model-id", "not-a-uuid"])
        assert result.exit_code != 0
        assert "Invalid" in result.output or "UUID" in result.output

    def test_ml_inference_deploy_with_invalid_json_config(self, runner):
        """Test ML inference deploy with invalid JSON config"""
        valid_uuid = "123e4567-e89b-12d3-a456-426614174000"
        result = runner.invoke(
            cli,
            [
                "ml",
                "inference",
                "deploy",
                "--model-id",
                valid_uuid,
                "--config",
                '{"invalid": json}',
            ],
        )
        assert result.exit_code != 0
        assert "Invalid" in result.output or "JSON" in result.output

    def test_ml_inference_predict_missing_required_options(self, runner):
        """Test ML inference predict with missing required options"""
        result = runner.invoke(cli, ["ml", "inference", "predict"])
        assert result.exit_code != 0
        # Should fail because --deployment-id and --input are required

    def test_ml_inference_predict_with_invalid_json_input(self, runner):
        """Test ML inference predict with invalid JSON input"""
        result = runner.invoke(
            cli,
            [
                "ml",
                "inference",
                "predict",
                "--deployment-id",
                "test-deployment",
                "--input-data",
                '{"invalid": json}',
            ],
        )
        assert result.exit_code != 0
        assert "Invalid" in result.output or "JSON" in result.output

    def test_ml_inference_list_with_invalid_model_id_format(self, runner):
        """Test ML inference list with invalid model ID format"""
        result = runner.invoke(cli, ["ml", "inference", "list", "--model-id", "not-a-uuid"])
        assert result.exit_code != 0
        assert "Invalid" in result.output or "UUID" in result.output

    def test_ml_inference_list_with_invalid_format(self, runner):
        """Test ML inference list with invalid format"""
        result = runner.invoke(cli, ["ml", "inference", "list", "--format", "invalid"])
        # Click should validate the choice and show error
        assert result.exit_code != 0

    def test_ml_inference_get_with_invalid_format(self, runner):
        """Test ML inference get with invalid format"""
        result = runner.invoke(cli, ["ml", "inference", "get", "test-id", "--format", "invalid"])
        # Click should validate the choice and show error
        assert result.exit_code != 0

    def test_ml_inference_metrics_with_invalid_format(self, runner):
        """Test ML inference metrics with invalid format"""
        result = runner.invoke(
            cli, ["ml", "inference", "metrics", "test-id", "--format", "invalid"]
        )
        # Click should validate the choice and show error
        assert result.exit_code != 0


class TestMLServingCommandGroup:
    """Test ML serving command group registration and structure"""

    @pytest.fixture
    def runner(self):
        """Create CLI runner"""
        return CliRunner()

    def test_ml_serving_command_group_accessible(self, runner):
        """Test that ML serving command group is accessible"""
        result = runner.invoke(cli, ["ml", "serving", "--help"])
        assert result.exit_code == 0
        assert "Model serving commands" in result.output

    def test_ml_serving_deploy_command_help(self, runner):
        """Test ML serving deploy command help"""
        result = runner.invoke(cli, ["ml", "serving", "deploy", "--help"])
        assert result.exit_code == 0
        assert "Deploy a model for serving" in result.output
        assert "--model-id" in result.output
        assert "--endpoint" in result.output

    def test_ml_serving_predict_command_help(self, runner):
        """Test ML serving predict command help"""
        result = runner.invoke(cli, ["ml", "serving", "predict", "--help"])
        assert result.exit_code == 0
        assert "Run inference prediction" in result.output
        assert "--model-id" in result.output
        assert "--input" in result.output

    def test_ml_serving_list_command_help(self, runner):
        """Test ML serving list command help"""
        result = runner.invoke(cli, ["ml", "serving", "list", "--help"])
        assert result.exit_code == 0
        assert "List model serving deployments" in result.output
        assert "--model-id" in result.output
        assert "--status" in result.output

    def test_ml_serving_get_command_help(self, runner):
        """Test ML serving get command help"""
        result = runner.invoke(cli, ["ml", "serving", "get", "--help"])
        assert result.exit_code == 0
        assert "Get serving deployment details" in result.output

    def test_ml_serving_undeploy_command_help(self, runner):
        """Test ML serving undeploy command help"""
        result = runner.invoke(cli, ["ml", "serving", "undeploy", "--help"])
        assert result.exit_code == 0
        assert "Undeploy a model serving deployment" in result.output

    def test_ml_serving_metrics_command_help(self, runner):
        """Test ML serving metrics command help"""
        result = runner.invoke(cli, ["ml", "serving", "metrics", "--help"])
        assert result.exit_code == 0
        assert "Get quality metrics" in result.output


class TestMLServingParameterValidation:
    """Test ML serving command parameter validation"""

    @pytest.fixture
    def runner(self):
        """Create CLI runner"""
        return CliRunner()

    def test_ml_serving_deploy_missing_required_options(self, runner):
        """Test ML serving deploy without required --model-id"""
        result = runner.invoke(cli, ["ml", "serving", "deploy"])
        assert result.exit_code != 0
        assert "Missing option" in result.output or "required" in result.output.lower()

    def test_ml_serving_deploy_with_invalid_model_id_format(self, runner):
        """Test ML serving deploy with invalid model ID format"""
        result = runner.invoke(
            cli, ["ml", "serving", "deploy", "--model-id", "invalid-uuid", "--format", "json"]
        )
        assert result.exit_code != 0
        assert "Invalid model-id format" in result.output or "Invalid UUID" in result.output

    def test_ml_serving_predict_missing_required_options(self, runner):
        """Test ML serving predict without required options"""
        result = runner.invoke(cli, ["ml", "serving", "predict"])
        assert result.exit_code != 0
        assert "Missing option" in result.output or "required" in result.output.lower()

    def test_ml_serving_predict_with_invalid_model_id_format(self, runner):
        """Test ML serving predict with invalid model ID format"""
        result = runner.invoke(
            cli,
            [
                "ml",
                "serving",
                "predict",
                "--model-id",
                "invalid-uuid",
                "--input",
                '{"data": [1, 2, 3]}',
                "--format",
                "json",
            ],
        )
        assert result.exit_code != 0
        assert "Invalid model-id format" in result.output or "Invalid UUID" in result.output

    def test_ml_serving_predict_with_invalid_json_input(self, runner):
        """Test ML serving predict with invalid JSON input"""
        valid_uuid = "123e4567-e89b-12d3-a456-426614174000"
        result = runner.invoke(
            cli,
            [
                "ml",
                "serving",
                "predict",
                "--model-id",
                valid_uuid,
                "--input",
                "invalid json",
                "--format",
                "json",
            ],
        )
        assert result.exit_code != 0
        assert "Invalid input format" in result.output or "Invalid JSON" in result.output

    def test_ml_serving_list_with_invalid_model_id_format(self, runner):
        """Test ML serving list with invalid model ID format"""
        result = runner.invoke(
            cli, ["ml", "serving", "list", "--model-id", "invalid-uuid", "--format", "json"]
        )
        assert result.exit_code != 0
        assert "Invalid model-id format" in result.output or "Invalid UUID" in result.output

    def test_ml_serving_list_with_invalid_format(self, runner):
        """Test ML serving list with invalid format"""
        result = runner.invoke(cli, ["ml", "serving", "list", "--format", "invalid"])
        # Click should validate the choice and show error
        assert result.exit_code != 0

    def test_ml_serving_get_with_invalid_format(self, runner):
        """Test ML serving get with invalid format"""
        result = runner.invoke(cli, ["ml", "serving", "get", "test-id", "--format", "invalid"])
        # Click should validate the choice and show error
        assert result.exit_code != 0

    def test_ml_serving_metrics_with_invalid_format(self, runner):
        """Test ML serving metrics with invalid format"""
        result = runner.invoke(cli, ["ml", "serving", "metrics", "test-id", "--format", "invalid"])
        # Click should validate the choice and show error
        assert result.exit_code != 0


class TestMLServingABTestCommandGroup:
    """Test ML serving A/B testing command group"""

    @pytest.fixture
    def runner(self):
        """Create CLI runner"""
        return CliRunner()

    def test_ml_serving_ab_test_command_group_accessible(self, runner):
        """Test that ML serving ab-test command group is accessible"""
        result = runner.invoke(cli, ["ml", "serving", "ab-test", "--help"])
        assert result.exit_code == 0
        assert "A/B testing commands" in result.output

    def test_ml_serving_ab_test_create_command_help(self, runner):
        """Test ML serving ab-test create command help"""
        result = runner.invoke(cli, ["ml", "serving", "ab-test", "create", "--help"])
        assert result.exit_code == 0
        assert "Create an A/B test" in result.output
        assert "--model-id" in result.output
        assert "--variant-id" in result.output
        assert "--traffic-split" in result.output

    def test_ml_serving_ab_test_list_command_help(self, runner):
        """Test ML serving ab-test list command help"""
        result = runner.invoke(cli, ["ml", "serving", "ab-test", "list", "--help"])
        assert result.exit_code == 0
        assert "List A/B tests" in result.output

    def test_ml_serving_ab_test_get_command_help(self, runner):
        """Test ML serving ab-test get command help"""
        result = runner.invoke(cli, ["ml", "serving", "ab-test", "get", "--help"])
        assert result.exit_code == 0
        assert "Get A/B test details" in result.output


class TestMLServingABTestParameterValidation:
    """Test ML serving A/B testing command parameter validation"""

    @pytest.fixture
    def runner(self):
        """Create CLI runner"""
        return CliRunner()

    def test_ml_serving_ab_test_create_missing_required_options(self, runner):
        """Test ML serving ab-test create without required options"""
        result = runner.invoke(cli, ["ml", "serving", "ab-test", "create"])
        assert result.exit_code != 0
        assert "Missing option" in result.output or "required" in result.output.lower()

    def test_ml_serving_ab_test_create_with_invalid_model_id_format(self, runner):
        """Test ML serving ab-test create with invalid model ID format"""
        valid_uuid = "123e4567-e89b-12d3-a456-426614174000"
        result = runner.invoke(
            cli,
            [
                "ml",
                "serving",
                "ab-test",
                "create",
                "--model-id",
                "invalid-uuid",
                "--variant-id",
                valid_uuid,
                "--traffic-split",
                "50:50",
                "--format",
                "json",
            ],
        )
        assert result.exit_code != 0
        assert "Invalid model-id format" in result.output or "Invalid UUID" in result.output

    def test_ml_serving_ab_test_create_with_invalid_variant_id_format(self, runner):
        """Test ML serving ab-test create with invalid variant ID format"""
        valid_uuid = "123e4567-e89b-12d3-a456-426614174000"
        result = runner.invoke(
            cli,
            [
                "ml",
                "serving",
                "ab-test",
                "create",
                "--model-id",
                valid_uuid,
                "--variant-id",
                "invalid-uuid",
                "--traffic-split",
                "50:50",
                "--format",
                "json",
            ],
        )
        assert result.exit_code != 0
        assert "Invalid variant-id format" in result.output or "Invalid UUID" in result.output

    def test_ml_serving_ab_test_create_with_invalid_traffic_split_format(self, runner):
        """Test ML serving ab-test create with invalid traffic split format"""
        valid_uuid = "123e4567-e89b-12d3-a456-426614174000"
        result = runner.invoke(
            cli,
            [
                "ml",
                "serving",
                "ab-test",
                "create",
                "--model-id",
                valid_uuid,
                "--variant-id",
                valid_uuid,
                "--traffic-split",
                "invalid",
                "--format",
                "json",
            ],
        )
        assert result.exit_code != 0
        assert "Invalid traffic split format" in result.output

    def test_ml_serving_ab_test_create_with_traffic_split_not_summing_to_100(self, runner):
        """Test ML serving ab-test create with traffic split not summing to 100"""
        valid_uuid = "123e4567-e89b-12d3-a456-426614174000"
        result = runner.invoke(
            cli,
            [
                "ml",
                "serving",
                "ab-test",
                "create",
                "--model-id",
                valid_uuid,
                "--variant-id",
                valid_uuid,
                "--traffic-split",
                "60:50",
                "--format",
                "json",
            ],
        )
        assert result.exit_code != 0
        assert "Traffic split percentages must sum to 100" in result.output

    def test_ml_serving_ab_test_create_with_invalid_percentage_range(self, runner):
        """Test ML serving ab-test create with invalid percentage range"""
        valid_uuid = "123e4567-e89b-12d3-a456-426614174000"
        result = runner.invoke(
            cli,
            [
                "ml",
                "serving",
                "ab-test",
                "create",
                "--model-id",
                valid_uuid,
                "--variant-id",
                valid_uuid,
                "--traffic-split",
                "150:50",
                "--format",
                "json",
            ],
        )
        assert result.exit_code != 0
        assert "Traffic split percentages must be between 0 and 100" in result.output

    def test_ml_serving_ab_test_list_with_invalid_model_id_format(self, runner):
        """Test ML serving ab-test list with invalid model ID format"""
        result = runner.invoke(
            cli,
            ["ml", "serving", "ab-test", "list", "--model-id", "invalid-uuid", "--format", "json"],
        )
        assert result.exit_code != 0
        assert "Invalid model-id format" in result.output


class TestMLModelsAPI:
    """API-mock tests for ml models commands — validates API calls, payloads,
    response parsing, and output formatting."""

    @pytest.fixture
    def runner(self):
        return CliRunner()

    @pytest.fixture
    def mock_api(self, monkeypatch):
        from unittest.mock import Mock

        mock_client = Mock()
        monkeypatch.setattr("datahub_cli.commands.ml.api_client", mock_client)
        return mock_client

    def test_list_models_success_table(self, runner, mock_api):
        """Test list_models with paginated API response in table format"""
        mock_api.get.return_value = {
            "results": [
                {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "odh_model_name": "bert-classifier",
                    "odh_model_version": "1.0.0",
                    "model_type": "CLASSIFICATION",
                    "status": "DEPLOYED",
                    "asset_id": "223e4567-e89b-12d3-a456-426614174000",
                }
            ]
        }

        result = runner.invoke(cli, ["ml", "models", "list"])

        assert result.exit_code == 0
        assert "bert-classifier" in result.output
        assert "CLASSIFICATION" in result.output
        assert "DEPLOYED" in result.output
        mock_api.get.assert_called_once_with("ml/models/", params={"limit": 20, "offset": 0})

    def test_list_models_success_json(self, runner, mock_api):
        """Test list_models with paginated API response in JSON format"""
        mock_api.get.return_value = {
            "results": [
                {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "odh_model_name": "gpt-finetuned",
                    "odh_model_version": "2.0.0",
                    "model_type": "NLP",
                    "status": "TRAINED",
                    "asset_id": None,
                }
            ]
        }

        result = runner.invoke(cli, ["ml", "models", "list", "--format", "json"])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert isinstance(output_data, list)
        assert len(output_data) == 1
        assert output_data[0]["odh_model_name"] == "gpt-finetuned"

    def test_list_models_empty(self, runner, mock_api):
        """Test list_models with empty results"""
        mock_api.get.return_value = {"results": []}

        result = runner.invoke(cli, ["ml", "models", "list"])

        assert result.exit_code == 0
        assert "No models found" in result.output

    def test_list_models_with_filters(self, runner, mock_api):
        """Test list_models with status and limit filters"""
        mock_api.get.return_value = {"results": []}

        result = runner.invoke(
            cli, ["ml", "models", "list", "--status", "DEPLOYED", "--limit", "10", "--offset", "5"]
        )

        assert result.exit_code == 0
        mock_api.get.assert_called_once_with(
            "ml/models/", params={"limit": 10, "offset": 5, "status": "DEPLOYED"}
        )

    def test_list_models_direct_list_response(self, runner, mock_api):
        """Test list_models when API returns a direct list (not paginated)"""
        mock_api.get.return_value = [
            {
                "id": "direct-list-model-id",
                "odh_model_name": "sklearn-classifier",
                "odh_model_version": "1.0.0",
                "model_type": "CLASSIFICATION",
                "status": "DEPLOYED",
            }
        ]

        result = runner.invoke(cli, ["ml", "models", "list"])

        assert result.exit_code == 0
        assert "sklearn-classifier" in result.output

    def test_get_model_success_table(self, runner, mock_api):
        """Test get_model in table format"""
        mock_api.get.return_value = {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "odh_model_id": "odh-model-abc",
            "odh_model_name": "bert-classifier",
            "odh_model_version": "1.0.0",
            "model_type": "CLASSIFICATION",
            "status": "DEPLOYED",
            "asset_id": "223e4567-e89b-12d3-a456-426614174000",
            "contract_id": "323e4567-e89b-12d3-a456-426614174000",
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-01T00:00:00Z",
        }

        result = runner.invoke(cli, ["ml", "models", "get", "123e4567-e89b-12d3-a456-426614174000"])

        assert result.exit_code == 0
        assert "bert-classifier" in result.output
        assert "CLASSIFICATION" in result.output
        assert "DEPLOYED" in result.output
        mock_api.get.assert_called_once_with("ml/models/123e4567-e89b-12d3-a456-426614174000/")

    def test_get_model_success_json(self, runner, mock_api):
        """Test get_model in JSON format"""
        mock_api.get.return_value = {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "odh_model_name": "bert-classifier",
            "odh_model_version": "1.0.0",
            "model_type": "CLASSIFICATION",
            "status": "DEPLOYED",
        }

        result = runner.invoke(
            cli, ["ml", "models", "get", "123e4567-e89b-12d3-a456-426614174000", "--format", "json"]
        )

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data["odh_model_name"] == "bert-classifier"
