from tests.pytest_mvp_skip import skip_if_mvp_mode

pytestmark = skip_if_mvp_mode

"""
ML API Tests

Unit tests for ODHIntegrationAPI, TrainingAPI, and InferenceAPI classes.
Tests parameter validation, error handling, and method structure.
"""
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from datahub_interoperability import DataHubClient, DataHubClientConfig
from datahub_interoperability.ml import ODHIntegrationAPI, TrainingAPI, InferenceAPI
from datahub_interoperability.errors import (
    ValidationError,
    NotFoundError,
    ConflictError,
    ServerError,
    ODHMLError,
    ODHMLValidationError,
    ODHMLNotFoundError,
    ODHMLConflictError,
)


@pytest.fixture
def config():
    """Test configuration"""
    return DataHubClientConfig(
        base_url="https://api.example.com/api/v1",
        api_token="test-token",
        timeout=30.0,
        max_retries=3,
        user_agent="test-agent",
        enable_logging=False,
    )


@pytest.fixture
async def client(config):
    """Test client"""
    async with DataHubClient(config) as client:
        yield client


@pytest.fixture
def ml_api(client):
    """ODH Integration API instance"""
    return ODHIntegrationAPI(client)


@pytest.fixture
def training_api(client):
    """Training API instance"""
    return TrainingAPI(client)


@pytest.fixture
def inference_api(client):
    """Inference API instance"""
    return InferenceAPI(client)


class TestODHIntegrationAPIInitialization:
    """Test ODHIntegrationAPI initialization"""

    def test_odh_integration_api_initialization(self, client):
        """Test ODHIntegrationAPI can be initialized"""
        api = ODHIntegrationAPI(client)
        assert api.client == client

    def test_odh_integration_api_from_client(self, client):
        """Test ODHIntegrationAPI accessible from client"""
        assert hasattr(client, "ml")
        assert isinstance(client.ml, ODHIntegrationAPI)


class TestODHIntegrationAPIParameterValidation:
    """Test parameter validation in ODHIntegrationAPI"""

    def test_validate_uuid_valid(self, ml_api):
        """Test UUID validation with valid UUID"""
        valid_uuid = str(uuid.uuid4())
        ml_api._validate_uuid(valid_uuid, "test_id")  # Should not raise

    def test_validate_uuid_empty(self, ml_api):
        """Test UUID validation with empty string"""
        with pytest.raises(ValidationError, match="is required"):
            ml_api._validate_uuid("", "test_id")

    def test_validate_uuid_none(self, ml_api):
        """Test UUID validation with None"""
        with pytest.raises(ValidationError, match="is required"):
            ml_api._validate_uuid(None, "test_id")  # type: ignore

    def test_validate_uuid_invalid_format(self, ml_api):
        """Test UUID validation with invalid format"""
        with pytest.raises(ValidationError, match="must be a valid UUID"):
            ml_api._validate_uuid("not-a-uuid", "test_id")

    def test_validate_model_type_valid(self, ml_api):
        """Test model type validation with valid types"""
        valid_types = ["CLASSIFICATION", "REGRESSION", "CLUSTERING", "NLP", "COMPUTER_VISION"]
        for model_type in valid_types:
            ml_api._validate_model_type(model_type)  # Should not raise

    def test_validate_model_type_invalid(self, ml_api):
        """Test model type validation with invalid type"""
        with pytest.raises(ValidationError, match="must be one of"):
            ml_api._validate_model_type("INVALID_TYPE")

    def test_validate_model_type_none(self, ml_api):
        """Test model type validation with None (optional)"""
        ml_api._validate_model_type(None)  # Should not raise

    def test_validate_model_status_valid(self, ml_api):
        """Test model status validation with valid statuses"""
        valid_statuses = ["TRAINING", "TRAINED", "DEPLOYED", "FAILED", "ARCHIVED"]
        for status in valid_statuses:
            ml_api._validate_model_status(status)  # Should not raise

    def test_validate_model_status_invalid(self, ml_api):
        """Test model status validation with invalid status"""
        with pytest.raises(ValidationError, match="must be one of"):
            ml_api._validate_model_status("INVALID_STATUS")

    def test_validate_model_status_none(self, ml_api):
        """Test model status validation with None (optional)"""
        ml_api._validate_model_status(None)  # Should not raise


class TestODHIntegrationAPIMethods:
    """Test ODHIntegrationAPI methods"""

    @pytest.mark.asyncio
    async def test_list_models_validation(self, ml_api):
        """Test list_models parameter validation"""
        # Invalid asset_id format
        with pytest.raises(ValidationError):
            await ml_api.list_models(asset_id="not-a-uuid")

        # Invalid status
        with pytest.raises(ValidationError):
            await ml_api.list_models(status="INVALID_STATUS")

        # Invalid limit
        with pytest.raises(ValidationError):
            await ml_api.list_models(limit=-1)

        # Invalid offset
        with pytest.raises(ValidationError):
            await ml_api.list_models(offset=-1)

    @pytest.mark.asyncio
    async def test_get_model_validation(self, ml_api):
        """Test get_model parameter validation"""
        # Invalid model_id format
        with pytest.raises(ValidationError):
            await ml_api.get_model("not-a-uuid")

    @pytest.mark.asyncio
    async def test_create_model_validation(self, ml_api):
        """Test create_model parameter validation"""
        valid_uuid = str(uuid.uuid4())

        # Missing required parameters
        with pytest.raises(ValidationError):
            await ml_api.create_model("", "", "", "")

        # Invalid asset_id format
        with pytest.raises(ValidationError):
            await ml_api.create_model("odh-id", "1.0", "not-a-uuid", "CLASSIFICATION")

        # Invalid model_type
        with pytest.raises(ValidationError):
            await ml_api.create_model("odh-id", "1.0", valid_uuid, "INVALID_TYPE")

        # Invalid contract_id format
        with pytest.raises(ValidationError):
            await ml_api.create_model("odh-id", "1.0", valid_uuid, "CLASSIFICATION", contract_id="not-a-uuid")

    @pytest.mark.asyncio
    async def test_update_model_validation(self, ml_api):
        """Test update_model parameter validation"""
        valid_uuid = str(uuid.uuid4())

        # Invalid model_id format
        with pytest.raises(ValidationError):
            await ml_api.update_model("not-a-uuid")

        # Invalid asset_id format
        with pytest.raises(ValidationError):
            await ml_api.update_model(valid_uuid, asset_id="not-a-uuid")

        # Invalid contract_id format
        with pytest.raises(ValidationError):
            await ml_api.update_model(valid_uuid, contract_id="not-a-uuid")

        # Invalid status
        with pytest.raises(ValidationError):
            await ml_api.update_model(valid_uuid, status="INVALID_STATUS")

        # No fields provided
        with pytest.raises(ValidationError, match="At least one field"):
            await ml_api.update_model(valid_uuid)

    @pytest.mark.asyncio
    async def test_delete_model_validation(self, ml_api):
        """Test delete_model parameter validation"""
        with pytest.raises(ValidationError):
            await ml_api.delete_model("not-a-uuid")

    @pytest.mark.asyncio
    async def test_get_model_versions_validation(self, ml_api):
        """Test get_model_versions parameter validation"""
        with pytest.raises(ValidationError):
            await ml_api.get_model_versions("not-a-uuid")

    @pytest.mark.asyncio
    async def test_link_model_to_asset_validation(self, ml_api):
        """Test link_model_to_asset parameter validation"""
        valid_uuid = str(uuid.uuid4())

        with pytest.raises(ValidationError):
            await ml_api.link_model_to_asset("not-a-uuid", valid_uuid)

        with pytest.raises(ValidationError):
            await ml_api.link_model_to_asset(valid_uuid, "not-a-uuid")

    @pytest.mark.asyncio
    async def test_link_model_to_dataset_validation(self, ml_api):
        """Test link_model_to_dataset parameter validation"""
        valid_uuid = str(uuid.uuid4())

        with pytest.raises(ValidationError):
            await ml_api.link_model_to_dataset("not-a-uuid", valid_uuid, "TRAINING")

        with pytest.raises(ValidationError):
            await ml_api.link_model_to_dataset(valid_uuid, "not-a-uuid", "TRAINING")

        with pytest.raises(ValidationError):
            await ml_api.link_model_to_dataset(valid_uuid, valid_uuid, "INVALID_ROLE")


class TestTrainingAPIInitialization:
    """Test TrainingAPI initialization"""

    def test_training_api_initialization(self, client):
        """Test TrainingAPI can be initialized"""
        api = TrainingAPI(client)
        assert api.client == client

    def test_training_api_from_client(self, client):
        """Test TrainingAPI accessible from client"""
        assert hasattr(client, "training")
        assert isinstance(client.training, TrainingAPI)


class TestTrainingAPIMethods:
    """Test TrainingAPI methods"""

    @pytest.mark.asyncio
    async def test_submit_training_job_validation(self, training_api):
        """Test submit_training_job parameter validation"""
        valid_uuid = str(uuid.uuid4())

        # Invalid model_id format
        with pytest.raises(ValidationError):
            await training_api.submit_training_job("not-a-uuid", valid_uuid, {})

        # Invalid dataset_id format
        with pytest.raises(ValidationError):
            await training_api.submit_training_job(valid_uuid, "not-a-uuid", {})

        # Invalid config type
        with pytest.raises(ValidationError):
            await training_api.submit_training_job(valid_uuid, valid_uuid, "not-a-dict")  # type: ignore

    @pytest.mark.asyncio
    async def test_get_training_job_validation(self, training_api):
        """Test get_training_job parameter validation"""
        # Empty training_job_id
        with pytest.raises(ValidationError):
            await training_api.get_training_job("")

        # None training_job_id
        with pytest.raises(ValidationError):
            await training_api.get_training_job(None)  # type: ignore

    @pytest.mark.asyncio
    async def test_list_training_jobs_validation(self, training_api):
        """Test list_training_jobs parameter validation"""
        # Invalid model_id format
        with pytest.raises(ValidationError):
            await training_api.list_training_jobs(model_id="not-a-uuid")

        # Invalid limit
        with pytest.raises(ValidationError):
            await training_api.list_training_jobs(limit=-1)

        # Invalid offset
        with pytest.raises(ValidationError):
            await training_api.list_training_jobs(offset=-1)

    @pytest.mark.asyncio
    async def test_cancel_training_job_validation(self, training_api):
        """Test cancel_training_job parameter validation"""
        with pytest.raises(ValidationError):
            await training_api.cancel_training_job("")

    @pytest.mark.asyncio
    async def test_get_training_logs_validation(self, training_api):
        """Test get_training_logs parameter validation"""
        with pytest.raises(ValidationError):
            await training_api.get_training_logs("")


class TestInferenceAPIInitialization:
    """Test InferenceAPI initialization"""

    def test_inference_api_initialization(self, client):
        """Test InferenceAPI can be initialized"""
        api = InferenceAPI(client)
        assert api.client == client

    def test_inference_api_from_client(self, client):
        """Test InferenceAPI accessible from client"""
        assert hasattr(client, "inference")
        assert isinstance(client.inference, InferenceAPI)


class TestInferenceAPIMethods:
    """Test InferenceAPI methods"""

    @pytest.mark.asyncio
    async def test_deploy_model_validation(self, inference_api):
        """Test deploy_model parameter validation"""
        # Invalid model_id format
        with pytest.raises(ValidationError):
            await inference_api.deploy_model("not-a-uuid")

        # Invalid config type
        with pytest.raises(ValidationError):
            await inference_api.deploy_model(str(uuid.uuid4()), config="not-a-dict")  # type: ignore

    @pytest.mark.asyncio
    async def test_predict_validation(self, inference_api):
        """Test predict parameter validation"""
        # Empty deployment_id
        with pytest.raises(ValidationError):
            await inference_api.predict("", {})

        # Invalid input_data type
        with pytest.raises(ValidationError):
            await inference_api.predict("deployment-id", "not-a-dict")  # type: ignore

    @pytest.mark.asyncio
    async def test_get_deployment_validation(self, inference_api):
        """Test get_deployment parameter validation"""
        with pytest.raises(ValidationError):
            await inference_api.get_deployment("")

    @pytest.mark.asyncio
    async def test_list_deployments_validation(self, inference_api):
        """Test list_deployments parameter validation"""
        # Invalid model_id format
        with pytest.raises(ValidationError):
            await inference_api.list_deployments(model_id="not-a-uuid")

        # Invalid limit
        with pytest.raises(ValidationError):
            await inference_api.list_deployments(limit=-1)

        # Invalid offset
        with pytest.raises(ValidationError):
            await inference_api.list_deployments(offset=-1)

    @pytest.mark.asyncio
    async def test_undeploy_model_validation(self, inference_api):
        """Test undeploy_model parameter validation"""
        with pytest.raises(ValidationError):
            await inference_api.undeploy_model("")

    @pytest.mark.asyncio
    async def test_get_inference_metrics_validation(self, inference_api):
        """Test get_inference_metrics parameter validation"""
        with pytest.raises(ValidationError):
            await inference_api.get_inference_metrics("")


class TestODHMLErrorClasses:
    """Test ODH ML error classes"""

    def test_odh_ml_error_initialization(self):
        """Test ODHMLError can be initialized"""
        error = ODHMLError("Test error", "TEST_ERROR", 400)
        assert error.message == "Test error"
        assert error.code == "TEST_ERROR"
        assert error.http_status == 400

    def test_odh_ml_validation_error_initialization(self):
        """Test ODHMLValidationError can be initialized"""
        error = ODHMLValidationError("Validation failed", field_path="/test", expected="string", actual="int")
        assert error.message == "Validation failed"
        assert error.field_path == "/test"
        assert error.expected == "string"
        assert error.actual == "int"

    def test_odh_ml_not_found_error_initialization(self):
        """Test ODHMLNotFoundError can be initialized"""
        error = ODHMLNotFoundError("Resource not found")
        assert error.message == "Resource not found"
        assert error.http_status == 404

    def test_odh_ml_conflict_error_initialization(self):
        """Test ODHMLConflictError can be initialized"""
        error = ODHMLConflictError("Conflict occurred")
        assert error.message == "Conflict occurred"
        assert error.http_status == 409


# ── Success-path integration tests (real API, no mocks) ────────────────────
# These verify that key read-only ML API methods are callable against the
# real API and return responses with the expected structure.  They do NOT
# require pre-seeded data — empty lists / default plans are valid responses.


class TestMLAPISuccessPaths:
    """Success-path integration tests for ML API methods."""

    @pytest.fixture
    def real_config(self):
        """Real API config for integration tests."""
        import os as _os

        from tests.conftest import is_api_available, get_api_key, default_api_base_url

        if not is_api_available():
            pytest.skip("API service is not available.")
        api_key = get_api_key()
        if not api_key:
            pytest.skip("No API key available.")
        api_base_url = _os.environ.get(
            "API_BASE_URL", f"{default_api_base_url()}/api/v1"
        )
        return DataHubClientConfig(
            base_url=api_base_url,
            api_token=api_key,
            timeout=30.0,
            max_retries=3,
            user_agent="test-agent",
            enable_logging=False,
        )

    @pytest.fixture
    async def real_client(self, real_config):
        """Real client for integration tests."""
        async with DataHubClient(real_config) as client:
            yield client

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_models_success(self, real_client):
        """Test list_models returns a well-structured response."""
        api = ODHIntegrationAPI(real_client)
        result = await api.list_models()
        assert isinstance(result, list), f"Expected list, got {type(result)}"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_training_jobs_success(self, real_client):
        """Test list_training_jobs returns a well-structured response."""
        api = TrainingAPI(real_client)
        result = await api.list_training_jobs()
        assert isinstance(result, list), f"Expected list, got {type(result)}"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_list_deployments_success(self, real_client):
        """Test list_deployments returns a well-structured response."""
        api = InferenceAPI(real_client)
        result = await api.list_deployments()
        assert isinstance(result, list), f"Expected list, got {type(result)}"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_ml_plan_success(self, real_client):
        """Test get_ml_plan returns plan info or NotFoundError if no subscription."""
        api = ODHIntegrationAPI(real_client)
        try:
            result = await api.get_ml_plan()
            assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        except NotFoundError as exc:
            if "ML subscription" in str(exc):
                pytest.skip("No ML subscription configured for this tenant")
            raise

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_get_ml_plan_limits_success(self, real_client):
        """Test get_ml_plan_limits returns limits or NotFoundError if no subscription."""
        api = ODHIntegrationAPI(real_client)
        try:
            result = await api.get_ml_plan_limits()
            assert isinstance(result, dict), f"Expected dict, got {type(result)}"
        except NotFoundError as exc:
            if "ML subscription" in str(exc):
                pytest.skip("No ML subscription configured for this tenant")
            raise
