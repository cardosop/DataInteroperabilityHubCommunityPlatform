from tests.pytest_mvp_skip import skip_if_mvp_mode

pytestmark = skip_if_mvp_mode

"""
ML API Integration Tests

Integration tests for ODHIntegrationAPI, TrainingAPI, and InferenceAPI classes.
Tests with real API endpoints running in Docker Compose.
"""
import os
import sys
import pytest
import uuid
import subprocess
from typing import Optional
from datahub_interoperability import DataHubClient, DataHubClientConfig
from datahub_interoperability.ml import ODHIntegrationAPI, TrainingAPI, InferenceAPI
from datahub_interoperability.errors import (
    ValidationError,
    NotFoundError,
    UnauthorizedError,
    ServerError,
)


def setup_authentication_for_sdk_tests(api_base_url: str) -> Optional[str]:
    """
    Set up authentication for SDK tests.

    Tries multiple methods:
    1. Use TEST_API_KEY environment variable if available
    2. Use DATAHUB_API_KEY environment variable
    3. Try to create API key via Django shell (if Docker Compose is available)
    4. Return None if no key available

    Args:
        api_base_url: API base URL

    Returns:
        API key string or None
    """
    # Method 1: Use environment variables
    api_key = os.environ.get('TEST_API_KEY') or os.environ.get('DATAHUB_API_KEY')
    if api_key:
        return api_key

    # Method 2: Try to create API key via Django shell in Docker Compose
    try:
        unique_id = uuid.uuid4().hex[:8]
        # Use .format() instead of f-string to avoid nested brace issues
        django_shell_script = """
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus, Role, UserRole
from hub.apps.auth.models import APIKey as AuthAPIKey
import os
import uuid

unique_id = '{unique_id}'

# Get or create tenant
tenant, _ = Tenant.objects.get_or_create(
    slug='ml-sdk-test-tenant-' + unique_id,
    defaults={{'name': 'ML SDK Test Tenant ' + unique_id}}
)

# Get or create user
user, _ = User.objects.get_or_create(
    email='ml-sdk-test-' + unique_id + '@example.com',
    defaults={{
        'tenant': tenant,
        'status': UserStatus.ACTIVE
    }}
)
if user.tenant != tenant:
    user.tenant = tenant
    user.status = UserStatus.ACTIVE
    user.save()

# Create tenant admin role
tenant_admin_role, _ = Role.objects.get_or_create(
    tenant=tenant, name='TENANT_ADMIN',
    defaults={{'description': 'Tenant Administrator'}}
)
UserRole.objects.get_or_create(user=user, role=tenant_admin_role)

# Delete existing API key if it exists
AuthAPIKey.objects.filter(user=user, name='ML SDK Test Key').delete()

# Create new API key
api_key_value = AuthAPIKey.generate_key()
api_key_hash = AuthAPIKey.hash_key(api_key_value)
api_key_obj = AuthAPIKey.objects.create(
    user=user,
    tenant=tenant,
    name='ML SDK Test Key',
    key_hash=api_key_hash
)

# Print the plaintext key (it's only available at creation time)
print('API_KEY_START')
print(api_key_value)
print('API_KEY_END')
""".format(unique_id=unique_id)
        # Check if docker compose is available
        try:
            subprocess.run(
                ['docker', 'compose', 'version'],
                capture_output=True,
                timeout=5,
                check=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            # Docker Compose not available, skip
            return None

        result = subprocess.run(
            ['docker', 'compose', 'exec', '-T', 'api-service', 'python', 'hub/manage.py', 'shell'],
            input=django_shell_script,
            text=True,
            capture_output=True,
            timeout=30,
            cwd='/home/ph/Desktop/DataInteroperabilityHub'
        )
        # Combine stdout and stderr (Django logs to stderr, output to stdout)
        combined_output = result.stdout + result.stderr if result.stderr else result.stdout

        if result.returncode == 0:
            # Extract API key from output using markers
            output_lines = combined_output.strip().split('\n')
            api_key = None
            in_api_key = False
            for line in output_lines:
                line = line.strip()
                if line == 'API_KEY_START':
                    in_api_key = True
                    continue
                elif line == 'API_KEY_END':
                    in_api_key = False
                    continue
                elif in_api_key and line:
                    api_key = line
                    break

            # Fallback: if markers didn't work, try old method
            if not api_key:
                for line in reversed(output_lines):
                    line = line.strip()
                    if not line or len(line) < 20:
                        continue
                    if line.startswith('>>>') or line.startswith('...'):
                        continue
                    if 'imported' in line.lower() or 'objects' in line.lower() or 'Error' in line:
                        continue
                    if ' ' in line:
                        continue
                    if all(c.isalnum() or c in '-_' for c in line):
                        api_key = line
                        break

            if api_key:
                return api_key
        else:
            # Log subprocess error for debugging
            print(f"Subprocess failed with return code {result.returncode}", file=sys.stderr)
            if result.stderr:
                print(f"Stderr: {result.stderr[:500]}", file=sys.stderr)
    except subprocess.TimeoutExpired:
        print("Subprocess timed out", file=sys.stderr)
    except Exception as e:
        # Log error for debugging but don't fail tests
        print(f"Error creating API key: {type(e).__name__}: {e}", file=sys.stderr)
    return None


def get_test_config():
    """Get test configuration from environment or create API key"""
    base_url = os.getenv("DATAHUB_API_BASE_URL", "http://localhost:8000/api/v1")
    api_token = setup_authentication_for_sdk_tests(base_url)

    if not api_token:
        pytest.skip("Could not obtain API key. Set DATAHUB_API_KEY or TEST_API_KEY environment variable, or ensure Docker Compose services are running.")

    return DataHubClientConfig(
        base_url=base_url,
        api_token=api_token,
        timeout=30.0,
        max_retries=3,
        user_agent="ml-sdk-test",
        enable_logging=False,
    )


@pytest.fixture
async def client():
    """Test client with real API"""
    config = get_test_config()
    async with DataHubClient(config) as client:
        yield client


@pytest.fixture
def ml_api(client):
    """ODH Integration API instance"""
    return client.ml


@pytest.fixture
def training_api(client):
    """Training API instance"""
    return client.training


@pytest.fixture
def inference_api(client):
    """Inference API instance"""
    return client.inference


class TestODHIntegrationAPIIntegration:
    """Integration tests for ODHIntegrationAPI"""

    @pytest.mark.asyncio
    async def test_list_models_real_api(self, ml_api):
        """Test list_models with real API"""
        try:
            models = await ml_api.list_models(limit=10)
            assert isinstance(models, list)
        except (UnauthorizedError, ServerError) as e:
            pytest.skip(f"API not available or not authenticated: {e}")

    @pytest.mark.asyncio
    async def test_list_models_with_filters_real_api(self, ml_api):
        """Test list_models with filters using real API"""
        try:
            # Test with status filter
            models = await ml_api.list_models(status="TRAINED", limit=5)
            assert isinstance(models, list)
        except (UnauthorizedError, ServerError) as e:
            pytest.skip(f"API not available or not authenticated: {e}")

    @pytest.mark.asyncio
    async def test_get_model_not_found_real_api(self, ml_api):
        """Test get_model with non-existent model ID"""
        non_existent_id = str(uuid.uuid4())
        try:
            with pytest.raises(NotFoundError):
                await ml_api.get_model(non_existent_id)
        except (UnauthorizedError, ServerError) as e:
            pytest.skip(f"API not available or not authenticated: {e}")

    @pytest.mark.asyncio
    async def test_create_model_validation_real_api(self, ml_api):
        """Test create_model parameter validation with real API"""
        # This should fail validation before making API call
        with pytest.raises(ValidationError):
            await ml_api.create_model("", "", "", "")

    @pytest.mark.asyncio
    async def test_update_model_validation_real_api(self, ml_api):
        """Test update_model parameter validation with real API"""
        # This should fail validation before making API call
        with pytest.raises(ValidationError):
            await ml_api.update_model("not-a-uuid")

    @pytest.mark.asyncio
    async def test_delete_model_not_found_real_api(self, ml_api):
        """Test delete_model with non-existent model ID"""
        non_existent_id = str(uuid.uuid4())
        try:
            with pytest.raises(NotFoundError):
                await ml_api.delete_model(non_existent_id)
        except (UnauthorizedError, ServerError) as e:
            pytest.skip(f"API not available or not authenticated: {e}")

    @pytest.mark.asyncio
    async def test_get_model_versions_not_found_real_api(self, ml_api):
        """Test get_model_versions with non-existent model ID"""
        non_existent_id = str(uuid.uuid4())
        try:
            with pytest.raises(NotFoundError):
                await ml_api.get_model_versions(non_existent_id)
        except (UnauthorizedError, ServerError) as e:
            pytest.skip(f"API not available or not authenticated: {e}")


class TestTrainingAPIIntegration:
    """Integration tests for TrainingAPI"""

    @pytest.mark.asyncio
    async def test_list_training_jobs_real_api(self, training_api):
        """Test list_training_jobs with real API"""
        try:
            jobs = await training_api.list_training_jobs(limit=10)
            assert isinstance(jobs, list)
        except (UnauthorizedError, ServerError) as e:
            pytest.skip(f"API not available or not authenticated: {e}")

    @pytest.mark.asyncio
    async def test_get_training_job_not_found_real_api(self, training_api):
        """Test get_training_job with non-existent job ID"""
        non_existent_id = "non-existent-job-id"
        try:
            with pytest.raises(NotFoundError):
                await training_api.get_training_job(non_existent_id)
        except (UnauthorizedError, ServerError) as e:
            pytest.skip(f"API not available or not authenticated: {e}")

    @pytest.mark.asyncio
    async def test_submit_training_job_validation_real_api(self, training_api):
        """Test submit_training_job parameter validation with real API"""
        # This should fail validation before making API call
        with pytest.raises(ValidationError):
            await training_api.submit_training_job("not-a-uuid", str(uuid.uuid4()), {})

    @pytest.mark.asyncio
    async def test_cancel_training_job_not_found_real_api(self, training_api):
        """Test cancel_training_job with non-existent job ID"""
        non_existent_id = "non-existent-job-id"
        try:
            with pytest.raises(NotFoundError):
                await training_api.cancel_training_job(non_existent_id)
        except (UnauthorizedError, ServerError) as e:
            pytest.skip(f"API not available or not authenticated: {e}")

    @pytest.mark.asyncio
    async def test_get_training_logs_not_found_real_api(self, training_api):
        """Test get_training_logs with non-existent job ID"""
        non_existent_id = "non-existent-job-id"
        try:
            with pytest.raises(NotFoundError):
                await training_api.get_training_logs(non_existent_id)
        except (UnauthorizedError, ServerError) as e:
            pytest.skip(f"API not available or not authenticated: {e}")


class TestInferenceAPIIntegration:
    """Integration tests for InferenceAPI"""

    @pytest.mark.asyncio
    async def test_list_deployments_real_api(self, inference_api):
        """Test list_deployments with real API"""
        try:
            deployments = await inference_api.list_deployments(limit=10)
            assert isinstance(deployments, list)
        except (UnauthorizedError, ServerError) as e:
            pytest.skip(f"API not available or not authenticated: {e}")

    @pytest.mark.asyncio
    async def test_get_deployment_not_found_real_api(self, inference_api):
        """Test get_deployment with non-existent deployment ID"""
        non_existent_id = "non-existent-deployment-id"
        try:
            with pytest.raises(NotFoundError):
                await inference_api.get_deployment(non_existent_id)
        except (UnauthorizedError, ServerError) as e:
            pytest.skip(f"API not available or not authenticated: {e}")

    @pytest.mark.asyncio
    async def test_deploy_model_validation_real_api(self, inference_api):
        """Test deploy_model parameter validation with real API"""
        # This should fail validation before making API call
        with pytest.raises(ValidationError):
            await inference_api.deploy_model("not-a-uuid")

    @pytest.mark.asyncio
    async def test_predict_validation_real_api(self, inference_api):
        """Test predict parameter validation with real API"""
        # This should fail validation before making API call
        with pytest.raises(ValidationError):
            await inference_api.predict("", {})

    @pytest.mark.asyncio
    async def test_undeploy_model_not_found_real_api(self, inference_api):
        """Test undeploy_model with non-existent deployment ID"""
        non_existent_id = "non-existent-deployment-id"
        try:
            with pytest.raises(NotFoundError):
                await inference_api.undeploy_model(non_existent_id)
        except (UnauthorizedError, ServerError) as e:
            pytest.skip(f"API not available or not authenticated: {e}")

    @pytest.mark.asyncio
    async def test_get_inference_metrics_not_found_real_api(self, inference_api):
        """Test get_inference_metrics with non-existent deployment ID"""
        non_existent_id = "non-existent-deployment-id"
        try:
            with pytest.raises(NotFoundError):
                await inference_api.get_inference_metrics(non_existent_id)
        except (UnauthorizedError, ServerError) as e:
            pytest.skip(f"API not available or not authenticated: {e}")


class TestMLAPIClientIntegration:
    """Test ML APIs are accessible from client"""

    @pytest.mark.asyncio
    async def test_ml_api_accessible_from_client(self, client):
        """Test that ML API is accessible from client"""
        assert hasattr(client, "ml")
        assert isinstance(client.ml, ODHIntegrationAPI)

    @pytest.mark.asyncio
    async def test_training_api_accessible_from_client(self, client):
        """Test that Training API is accessible from client"""
        assert hasattr(client, "training")
        assert isinstance(client.training, TrainingAPI)

    @pytest.mark.asyncio
    async def test_inference_api_accessible_from_client(self, client):
        """Test that Inference API is accessible from client"""
        assert hasattr(client, "inference")
        assert isinstance(client.inference, InferenceAPI)
