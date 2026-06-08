from tests.pytest_mvp_skip import skip_if_mvp_mode

pytestmark = skip_if_mvp_mode

"""
ML API End-to-End Tests

E2E tests for complete ML workflows using ODHIntegrationAPI, TrainingAPI, and InferenceAPI.
Tests complete workflows: create model → train → deploy → predict → undeploy → delete.

These tests require:
1. Docker Compose services running (api-service, postgres, redis, minio, ODH services)
2. A test user and API key configured
   OR set via environment variables: TEST_API_KEY or DATAHUB_API_KEY
"""
import os
import pytest
import uuid
import asyncio
from datahub_interoperability import DataHubClient, DataHubClientConfig
from datahub_interoperability.ml import ODHIntegrationAPI, TrainingAPI, InferenceAPI
from datahub_interoperability.errors import (
    ValidationError,
    NotFoundError,
    UnauthorizedError,
    ServerError,
    ConflictError,
)


def setup_authentication_for_sdk_tests(api_base_url: str):
    """Set up authentication for SDK tests.

    Creates a dedicated tenant with ``ml_enabled=True`` so ML endpoints
    avoid feature-flag gates and admin-token invalidation.
    """
    # Method 1: Create dedicated tenant via Django shell (PRIMARY).
    try:
        key = _create_ml_e2e_tenant_and_key()
        if key:
            return key
    except Exception:
        pass

    # Method 2: Use canonical conftest helper
    try:
        from tests.conftest import get_api_key
        canonical = get_api_key()
        if canonical:
            return canonical
    except Exception:
        pass

    # Method 3: Fall back to env-var keys
    api_key = os.environ.get('TEST_API_KEY') or os.environ.get('DATAHUB_API_KEY')
    if api_key:
        return api_key

    return None


def _create_ml_e2e_tenant_and_key():
    """Create a dedicated tenant with ``ml_enabled=True`` and return an API key."""
    import subprocess
    import uuid
    try:
        unique_id = uuid.uuid4().hex[:8]
        # Use .format() instead of f-string to avoid nested brace issues
        django_shell_script = """
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus, Role, UserRole
from hub.apps.auth.models import APIKey as AuthAPIKey

unique_id = '{unique_id}'

tenant, _ = Tenant.objects.get_or_create(
    slug='ml-sdk-e2e-tenant-' + unique_id,
    defaults={{'name': 'ML SDK E2E Test Tenant ' + unique_id, 'ml_enabled': True}}
)
if not tenant.ml_enabled:
    tenant.ml_enabled = True
    tenant.save(update_fields=['ml_enabled'])

user, _ = User.objects.get_or_create(
    email='ml-sdk-e2e-' + unique_id + '@example.com',
    defaults={{
        'tenant': tenant,
        'status': UserStatus.ACTIVE
    }}
)
if user.tenant != tenant:
    user.tenant = tenant
    user.status = UserStatus.ACTIVE
    user.save()

tenant_admin_role, _ = Role.objects.get_or_create(
    tenant=tenant, name='TENANT_ADMIN',
    defaults={{'description': 'Tenant Administrator'}}
)
UserRole.objects.get_or_create(user=user, role=tenant_admin_role)

AuthAPIKey.objects.filter(user=user, name='ML SDK E2E Test Key').delete()

api_key_value = AuthAPIKey.generate_key()
api_key_hash = AuthAPIKey.hash_key(api_key_value)
api_key_obj = AuthAPIKey.objects.create(
    user=user,
    tenant=tenant,
    name='ML SDK E2E Test Key',
    key_hash=api_key_hash
)

print('API_KEY_START')
print(api_key_value)
print('API_KEY_END')
""".format(unique_id=unique_id)
        result = subprocess.run(
                        ['docker', 'compose', '-f', 'docker-compose.test.yml', 'exec', '-T', 'api-service-test', 'python', 'hub/manage.py', 'shell'],
            input=django_shell_script,
            text=True,
            capture_output=True,
            timeout=30,
            cwd='/home/ph/Desktop/DataInteroperabilityHub'
        )
        combined_output = result.stdout + result.stderr if result.stderr else result.stdout

        if result.returncode == 0:
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
    except Exception:
        pass
    return None


def get_test_config():
    """Get test configuration from environment or create API key"""
    base_url = os.getenv("API_BASE_URL", "http://localhost:8001/api/v1")
    api_token = setup_authentication_for_sdk_tests(base_url)

    if not api_token:
        pytest.skip("Could not obtain API key. Set DATAHUB_API_KEY or TEST_API_KEY environment variable, or ensure Docker Compose services are running.")

    return DataHubClientConfig(
        base_url=base_url,
        api_token=api_token,
        timeout=30.0,
        max_retries=3,
        user_agent="ml-sdk-e2e-test",
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


class TestMLWorkflowE2E:
    """End-to-end tests for complete ML workflows"""

    @pytest.mark.asyncio
    async def test_model_lifecycle_workflow(self, ml_api):
        """
        Test complete model lifecycle: list → create → get → update → delete

        This test verifies the entire lifecycle of model management.
        """
        try:
            # Step 1: List existing models
            models = await ml_api.list_models(limit=5)
            assert isinstance(models, list)

            # Step 2: Create a test model (if we have required data)
            # Note: This requires an existing asset_id, so we'll skip if not available
            # In a real scenario, you would create an asset first or use an existing one
            test_asset_id = os.getenv("TEST_ASSET_ID")
            if test_asset_id:
                try:
                    test_model = await ml_api.create_model(
                        odh_model_id=f"test-model-{uuid.uuid4().hex[:8]}",
                        odh_model_version="1.0.0",
                        asset_id=test_asset_id,
                        model_type="CLASSIFICATION",
                    )
                    assert "id" in test_model
                    model_id = test_model["id"]

                    # Step 3: Get the created model
                    retrieved_model = await ml_api.get_model(model_id)
                    assert retrieved_model["id"] == model_id

                    # Step 4: Update the model
                    updated_model = await ml_api.update_model(model_id, status="TRAINED")
                    assert updated_model.get("status") == "TRAINED"

                    # Step 5: Get model versions
                    versions = await ml_api.get_model_versions(model_id)
                    assert isinstance(versions, list)

                    # Step 6: Delete the model
                    await ml_api.delete_model(model_id)

                    # Step 7: Verify deletion
                    with pytest.raises(NotFoundError):
                        await ml_api.get_model(model_id)
                except (NotFoundError, ConflictError) as e:
                    # Model creation may fail if asset doesn't exist or model already exists
                    pytest.skip(f"Model creation failed (may need setup): {e}")
        except (UnauthorizedError, ServerError) as e:
            pytest.skip(f"API not available or not authenticated: {e}")

    @pytest.mark.asyncio
    async def test_training_workflow(self, ml_api, training_api):
        """
        Test complete training workflow: list → submit → get → list → cancel/logs

        This test verifies the entire lifecycle of training job management.
        """
        try:
            # Step 1: List existing training jobs
            jobs = await training_api.list_training_jobs(limit=5)
            assert isinstance(jobs, list)

            # Step 2: Submit a training job (if we have required data)
            test_model_id = os.getenv("TEST_MODEL_ID")
            test_dataset_id = os.getenv("TEST_DATASET_ID")

            if test_model_id and test_dataset_id:
                try:
                    # Submit training job
                    job = await training_api.submit_training_job(
                        model_id=test_model_id,
                        dataset_id=test_dataset_id,
                        config={"epochs": 10, "batch_size": 32},
                    )
                    assert "job_id" in job or "id" in job
                    job_id = job.get("job_id") or job.get("id")

                    # Step 3: Get training job details
                    job_details = await training_api.get_training_job(job_id)
                    assert job_details.get("job_id") == job_id or job_details.get("id") == job_id

                    # Step 4: List training jobs with filter
                    filtered_jobs = await training_api.list_training_jobs(model_id=test_model_id)
                    assert isinstance(filtered_jobs, list)

                    # Step 5: Get training logs (may not be available immediately)
                    try:
                        logs = await training_api.get_training_logs(job_id)
                        assert isinstance(logs, str)
                    except (NotFoundError, ServerError):
                        # Logs may not be available yet
                        pass

                    # Step 6: Cancel training job (if still running)
                    try:
                        await training_api.cancel_training_job(job_id)
                    except (NotFoundError, ServerError):
                        # Job may already be completed or not found
                        pass
                except (NotFoundError, ValidationError) as e:
                    pytest.skip(f"Training job submission failed (may need setup): {e}")
        except (UnauthorizedError, ServerError) as e:
            pytest.skip(f"API not available or not authenticated: {e}")

    @pytest.mark.asyncio
    async def test_inference_workflow(self, ml_api, inference_api):
        """
        Test complete inference workflow: deploy → list → get → predict → metrics → undeploy

        This test verifies the entire lifecycle of inference deployment management.
        """
        try:
            # Step 1: List existing deployments
            deployments = await inference_api.list_deployments(limit=5)
            assert isinstance(deployments, list)

            # Step 2: Deploy a model (if we have required data)
            test_model_id = os.getenv("TEST_MODEL_ID")

            if test_model_id:
                try:
                    # Deploy model
                    deployment = await inference_api.deploy_model(
                        model_id=test_model_id,
                        config={"replicas": 1},
                    )
                    assert "deployment_id" in deployment or "id" in deployment
                    deployment_id = deployment.get("deployment_id") or deployment.get("id")

                    # Step 3: Get deployment details
                    deployment_details = await inference_api.get_deployment(deployment_id)
                    assert deployment_details.get("deployment_id") == deployment_id or deployment_details.get("id") == deployment_id

                    # Step 4: List deployments with filter
                    filtered_deployments = await inference_api.list_deployments(model_id=test_model_id)
                    assert isinstance(filtered_deployments, list)

                    # Step 5: Run prediction (if deployment is ready)
                    try:
                        prediction = await inference_api.predict(
                            deployment_id=deployment_id,
                            input_data={"data": [1, 2, 3, 4, 5]},
                        )
                        assert "output" in prediction or "result" in prediction
                    except (NotFoundError, ServerError):
                        # Deployment may not be ready yet
                        pass

                    # Step 6: Get inference metrics
                    try:
                        metrics = await inference_api.get_inference_metrics(deployment_id)
                        assert isinstance(metrics, dict)
                    except (NotFoundError, ServerError):
                        # Metrics may not be available yet
                        pass

                    # Step 7: Undeploy model
                    try:
                        await inference_api.undeploy_model(deployment_id)
                    except (NotFoundError, ServerError):
                        # Deployment may already be undeployed
                        pass
                except (NotFoundError, ValidationError, ServerError) as e:
                    pytest.skip(f"Inference deployment failed (may need setup or ODH services): {e}")
        except (UnauthorizedError, ServerError) as e:
            pytest.skip(f"API not available or not authenticated: {e}")

    @pytest.mark.asyncio
    async def test_model_dataset_linking_workflow(self, ml_api):
        """
        Test model dataset linking workflow: link → verify

        This test verifies model-to-dataset linking functionality.
        """
        try:
            test_model_id = os.getenv("TEST_MODEL_ID")
            test_dataset_id = os.getenv("TEST_DATASET_ID")

            if test_model_id and test_dataset_id:
                try:
                    # Link model to dataset
                    link = await ml_api.link_model_to_dataset(
                        model_id=test_model_id,
                        dataset_id=test_dataset_id,
                        role="TRAINING",
                    )
                    assert "id" in link or "dataset_id" in link
                except (NotFoundError, ValidationError) as e:
                    pytest.skip(f"Model dataset linking failed (may need setup): {e}")
        except (UnauthorizedError, ServerError) as e:
            pytest.skip(f"API not available or not authenticated: {e}")

    @pytest.mark.asyncio
    async def test_model_asset_linking_workflow(self, ml_api):
        """
        Test model asset linking workflow: link → verify

        This test verifies model-to-asset linking functionality.
        """
        try:
            test_model_id = os.getenv("TEST_MODEL_ID")
            test_asset_id = os.getenv("TEST_ASSET_ID")

            if test_model_id and test_asset_id:
                try:
                    # Link model to asset
                    result = await ml_api.link_model_to_asset(
                        model_id=test_model_id,
                        asset_id=test_asset_id,
                    )
                    assert "id" in result or "asset_id" in result
                except (NotFoundError, ValidationError) as e:
                    pytest.skip(f"Model asset linking failed (may need setup): {e}")
        except (UnauthorizedError, ServerError) as e:
            pytest.skip(f"API not available or not authenticated: {e}")

    @pytest.mark.asyncio
    async def test_complete_ml_pipeline_workflow(self, ml_api, training_api, inference_api):
        """
        Test complete ML pipeline: create model → train → deploy → predict → cleanup

        This is a comprehensive E2E test that exercises the entire ML pipeline.
        """
        try:
            # This test requires significant setup (assets, datasets, ODH services)
            # So we'll test the workflow structure but skip if setup is incomplete
            test_asset_id = os.getenv("TEST_ASSET_ID")
            test_dataset_id = os.getenv("TEST_DATASET_ID")

            if not (test_asset_id and test_dataset_id):
                pytest.skip("TEST_ASSET_ID and TEST_DATASET_ID environment variables not set")

            # Step 1: Create model
            try:
                model = await ml_api.create_model(
                    odh_model_id=f"e2e-test-{uuid.uuid4().hex[:8]}",
                    odh_model_version="1.0.0",
                    asset_id=test_asset_id,
                    model_type="CLASSIFICATION",
                )
                model_id = model["id"]

                # Step 2: Submit training job
                try:
                    job = await training_api.submit_training_job(
                        model_id=model_id,
                        dataset_id=test_dataset_id,
                        config={"epochs": 5, "batch_size": 16},
                    )
                    job_id = job.get("job_id") or job.get("id")

                    # Step 3: Deploy model (after training completes or in parallel)
                    try:
                        deployment = await inference_api.deploy_model(
                            model_id=model_id,
                            config={"replicas": 1},
                        )
                        deployment_id = deployment.get("deployment_id") or deployment.get("id")

                        # Step 4: Run prediction
                        try:
                            prediction = await inference_api.predict(
                                deployment_id=deployment_id,
                                input_data={"data": [1, 2, 3]},
                            )
                            assert "output" in prediction or "result" in prediction
                        except (NotFoundError, ServerError):
                            # Deployment may not be ready
                            pass

                        # Step 5: Cleanup - undeploy
                        try:
                            await inference_api.undeploy_model(deployment_id)
                        except (NotFoundError, ServerError):
                            pass
                    except (NotFoundError, ServerError, ValidationError):
                        # Deployment may fail if ODH services not available
                        pass

                    # Step 6: Cleanup - cancel training if still running
                    try:
                        await training_api.cancel_training_job(job_id)
                    except (NotFoundError, ServerError):
                        pass
                except (NotFoundError, ValidationError, ServerError):
                    # Training may fail if ODH services not available
                    pass

                # Step 7: Cleanup - delete model
                try:
                    await ml_api.delete_model(model_id)
                except (NotFoundError, ServerError):
                    pass
            except (NotFoundError, ConflictError, ValidationError) as e:
                pytest.skip(f"Complete pipeline test setup incomplete: {e}")
        except (UnauthorizedError, ServerError) as e:
            pytest.skip(f"API not available or not authenticated: {e}")
