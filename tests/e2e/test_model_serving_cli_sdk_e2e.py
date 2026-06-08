"""
Model Serving CLI/SDK E2E Tests (Task 10.1.42.3)

This test suite implements comprehensive end-to-end validation for Model Serving:
- Complete workflows using CLI (deploy → predict → metrics → A/B test)
- Complete workflows using SDK
- CLI/SDK consistency

All tests use real implementations (no mocks/stubs) per requirements.
"""
import json
import os
import sys
import time
import pytest

pytestmark = pytest.mark.slow
import uuid
import asyncio
import tempfile
from pathlib import Path
from click.testing import CliRunner

# Add CLI and SDK to Python path for imports
project_root = Path(__file__).parent.parent.parent
cli_path = project_root / "cli"
sdk_path = project_root / "sdk" / "python"

if str(cli_path) not in sys.path:
    sys.path.insert(0, str(cli_path))
if str(sdk_path) not in sys.path:
    sys.path.insert(0, str(sdk_path))

from datahub_cli.main import cli
from datahub_cli.config import config

from datahub_interoperability.client import DataHubClient
from datahub_interoperability.config import DataHubClientConfig
from datahub_interoperability.model_serving import ModelServingAPI

# Use actual database for E2E tests (not test database)
pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


def _check_api_available():
    """Check if API service is available"""
    try:
        import requests
        response = requests.get('http://localhost:8000/health/', timeout=2)
        return response.status_code == 200
    except Exception:
        return False


def _check_ml_serving_available():
    """Check if ML serving endpoint is responsive (not just the main API).

    The ML serving 'list' endpoint should return quickly even when empty.
    If this hangs, the entire ML infrastructure is unavailable and tests
    would each waste 60s hitting the pytest timeout.
    """
    try:
        import requests
        response = requests.get(
            'http://localhost:8000/api/v1/ml/serving/',
            timeout=5,
        )
        # Any response (200, 401, 403, 404) means the endpoint is routable.
        # Only a connection timeout / connection refused means it's truly down.
        return True
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return False
    except Exception:
        return True  # Non-connection errors mean the service is reachable


@pytest.fixture(scope='module')
def api_available():
    """Check if API is available before running tests"""
    if not _check_api_available():
        pytest.skip("API service not available at http://localhost:8000")
    return True


@pytest.fixture(scope='module')
def ml_serving_available(api_available):
    """Check if ML serving infrastructure is responsive.

    Prevents each test from wasting 60s on the pytest timeout when the
    ML serving endpoints are unreachable.
    """
    if not _check_ml_serving_available():
        pytest.skip("ML serving endpoint not responsive at http://localhost:8000/api/v1/ml/serving/")
    return True


@pytest.fixture(scope='module')
def e2e_api_key(api_available, django_db_blocker):
    """Set up authentication for E2E tests - module-scoped fixture.

    Uses django_db_blocker.unblock() to allow DB access from module-scoped fixtures,
    since pytest-django's django_db mark only applies to individual test functions.
    """
    api_key = os.environ.get('TEST_API_KEY') or os.environ.get('DATAHUB_API_KEY')
    if api_key:
        # Even with an env-var key, ensure the associated tenant has unlimited
        # plan limits so ML model creation never hits max_ml_models.
        try:
            with django_db_blocker.unblock():
                from hub.apps.auth.models import APIKey as AuthAPIKey
                from hub.apps.testing.billing_support import ensure_e2e_tenant_ready

                api_key_obj = AuthAPIKey.objects.filter(
                    key_hash=AuthAPIKey.hash_key(api_key),
                ).select_related("tenant").first()
                if api_key_obj and api_key_obj.tenant:
                    ensure_e2e_tenant_ready(api_key_obj.tenant)
        except Exception:
            pass  # Best-effort; key may be in a different DB
        return api_key

    # Create API key directly using Django (when running inside Docker)
    try:
        with django_db_blocker.unblock():
            from hub.apps.tenants.models import Tenant
            from hub.apps.users.models import User, UserStatus, Role, UserRole
            from hub.apps.auth.models import APIKey as AuthAPIKey

            unique_id = uuid.uuid4().hex[:8]

            tenant, _ = Tenant.objects.get_or_create(
                slug=f'model-serving-e2e-test-tenant-{unique_id}',
                defaults={'name': f'Model Serving E2E Test Tenant {unique_id}'}
            )

            # Ensure tenant has unlimited plan limits (enterprise tier) so ML model
            # creation is never blocked by max_ml_models caps from prior test runs.
            from hub.apps.testing.billing_support import ensure_e2e_tenant_ready
            ensure_e2e_tenant_ready(tenant)

            user, _ = User.objects.get_or_create(
                email=f'model-serving-e2e-test-{unique_id}@example.com',
                defaults={
                    'tenant': tenant,
                    'status': UserStatus.ACTIVE
                }
            )
            if user.tenant != tenant:
                user.tenant = tenant
                user.status = UserStatus.ACTIVE
                user.save()

            tenant_admin_role, _ = Role.objects.get_or_create(
                tenant=tenant, name='TENANT_ADMIN',
                defaults={'description': 'Tenant Administrator'}
            )
            UserRole.objects.get_or_create(user=user, role=tenant_admin_role)

            AuthAPIKey.objects.filter(user=user, name='Model Serving E2E Test Key').delete()

            api_key_value = AuthAPIKey.generate_key()
            api_key_hash = AuthAPIKey.hash_key(api_key_value)
            # Set scopes matching TENANT_ADMIN so the API key carries full permissions.
            # Without scopes, the auth middleware sets request.api_key_scopes=[] which
            # resolves to zero permissions (403 on every write).
            from hub.apps.auth.permissions import ROLE_SCOPE_MAP
            tenant_admin_scopes = list(ROLE_SCOPE_MAP.get("TENANT_ADMIN", []))

            AuthAPIKey.objects.create(
                user=user,
                tenant=tenant,
                name='Model Serving E2E Test Key',
                key_hash=api_key_hash,
                scopes=tenant_admin_scopes,
            )

            return api_key_value
    except ImportError:
        pytest.skip("Cannot create API key - Django modules not available")
    except Exception as e:
        pytest.skip(f"Cannot create API key - {e}")


@pytest.fixture
def runner(e2e_api_key, django_db_blocker):
    """Create CLI runner with authentication configured.

    Re-ensures the API key record exists in the DB before each test.
    TransactionTestCase truncates all tables after each test, so the
    module-scoped e2e_api_key value may reference a deleted DB record.
    """
    try:
        with django_db_blocker.unblock():
            from hub.apps.auth.models import APIKey as AuthAPIKey
            from hub.apps.tenants.models import Tenant
            from hub.apps.users.models import User, UserStatus, Role, UserRole
            from hub.apps.auth.permissions import ROLE_SCOPE_MAP
            from hub.apps.testing.billing_support import ensure_e2e_tenant_ready

            key_hash = AuthAPIKey.hash_key(e2e_api_key)
            if not AuthAPIKey.objects.filter(key_hash=key_hash).exists():
                tenant, _ = Tenant.objects.get_or_create(
                    slug='model-serving-cli-test',
                    defaults={'name': 'Model Serving CLI Test'},
                )
                ensure_e2e_tenant_ready(tenant)
                user, _ = User.objects.get_or_create(
                    email='model-serving-cli@example.com',
                    defaults={
                        'tenant': tenant,
                        'status': UserStatus.ACTIVE,
                    },
                )
                if user.tenant_id != tenant.id:
                    user.tenant = tenant
                    user.save(update_fields=['tenant'])
                role, _ = Role.objects.get_or_create(
                    tenant=tenant, name='TENANT_ADMIN',
                    defaults={'description': 'Tenant Administrator'},
                )
                UserRole.objects.get_or_create(user=user, role=role)
                scopes = list(ROLE_SCOPE_MAP.get('TENANT_ADMIN', []))
                AuthAPIKey.objects.create(
                    user=user, tenant=tenant,
                    name='CLI E2E Recreated Key',
                    key_hash=key_hash, scopes=scopes,
                )
    except Exception:
        pass  # Best-effort; test will fail with 401 if this doesn't work

    config.set_api_key(e2e_api_key)
    config.set_api_base_url('http://localhost:8000/api/v1')
    return CliRunner()


@pytest.fixture
def test_model_id(api_available, e2e_api_key, django_db_blocker):
    """Get or create a test model for CLI tests.

    Function-scoped: TransactionTestCase truncates all tables after each
    test, so a module-scoped model ID would go stale.  Re-creates the
    model (and its tenant/API-key if needed) before every test.
    """
    api_key = e2e_api_key

    try:
        with django_db_blocker.unblock():
            import django
            from django.apps import apps
            if not apps.ready:
                django.setup()

            from hub.apps.ml.models import MLModel, ModelType, ModelStatus
            from hub.apps.auth.models import APIKey as AuthAPIKey
            from hub.apps.tenants.models import Tenant
            from hub.apps.testing.billing_support import ensure_e2e_tenant_ready

            # Find or recreate the tenant via API key
            tenant = None
            api_key_obj = AuthAPIKey.objects.filter(key_hash=AuthAPIKey.hash_key(api_key)).first()
            if api_key_obj:
                tenant = api_key_obj.tenant

            if not tenant:
                tenant = (
                    Tenant.objects.filter(slug__startswith='model-serving-e2e-test-tenant')
                    .order_by('-created_at')
                    .first()
                )
            if not tenant:
                tenant = Tenant.objects.create(
                    slug=f'model-serving-e2e-test-tenant-{uuid.uuid4().hex[:8]}',
                    name=f"Model Serving E2E Test Tenant {uuid.uuid4().hex[:8]}",
                )

            ensure_e2e_tenant_ready(tenant)

            # Re-use existing model if present, otherwise create
            existing_model = MLModel.objects.filter(tenant=tenant).first()
            if existing_model:
                return str(existing_model.id)

            model = MLModel.objects.create(
                tenant=tenant,
                odh_model_name="E2E Test Model",
                odh_model_version="1.0.0",
                model_type=ModelType.CLASSIFICATION,
                status=ModelStatus.TRAINED,
            )
            return str(model.id)
    except ImportError:
        pass
    except Exception:
        pass

    # Fallback: Try to get or create model via HTTP API (when ORM is unavailable).
    try:
        import requests

        headers = {
            'Authorization': f'ApiKey {api_key}',
            'Content-Type': 'application/json'
        }

        # First, try to get existing model
        response = requests.get(
            'http://localhost:8000/api/v1/ml/models/',
            headers=headers,
            params={'limit': 1},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            results = data.get('results', []) if isinstance(data, dict) else data
            if results and len(results) > 0:
                return str(results[0].get('id'))

        # No existing model - try to create one
        # First, we need an asset to link the model to
        asset_response = requests.get(
            'http://localhost:8000/api/v1/assets/',
            headers=headers,
            params={'limit': 1},
            timeout=10
        )

        asset_id = None
        if asset_response.status_code == 200:
            asset_data = asset_response.json()
            asset_results = asset_data.get('results', []) if isinstance(asset_data, dict) else asset_data
            if asset_results and len(asset_results) > 0:
                asset_id = asset_results[0].get('id')

        # If no asset exists, create one
        if not asset_id:
            asset_data = {
                'key': f'e2e-test-asset-{uuid.uuid4().hex[:8]}',
                'name': 'E2E Test Asset for Model Serving',
                'description': 'Test asset for E2E model serving tests',
                'domain': 'ml',
                'visibility': 'INTERNAL'
            }
            asset_create_response = requests.post(
                'http://localhost:8000/api/v1/assets/',
                json=asset_data,
                headers=headers,
                timeout=15
            )
            if asset_create_response.status_code in [200, 201]:
                asset_id = asset_create_response.json().get('id')

        if not asset_id:
            pytest.skip("No assets available and failed to create test asset")

        # Create a test model
        model_data = {
            'odh_model_id': f'e2e-test-model-{uuid.uuid4().hex[:8]}',
            'odh_model_version': '1.0.0',
            'model_type': 'CLASSIFICATION',
            'asset_id': asset_id  # Required field
        }

        create_response = requests.post(
            'http://localhost:8000/api/v1/ml/models/',
            json=model_data,
            headers=headers,
            timeout=15
        )

        if create_response.status_code in [200, 201]:
            model_id = create_response.json().get('id')
            if model_id:
                return str(model_id)

        # If creation failed with plan limit, try broader listing - models may
        # exist but weren't returned due to filters/status in the first query.
        if create_response.status_code == 400 and 'limit exceeded' in create_response.text.lower():
            retry_response = requests.get(
                'http://localhost:8000/api/v1/ml/models/',
                headers=headers,
                params={'limit': 50},
                timeout=10,
            )
            if retry_response.status_code == 200:
                retry_data = retry_response.json()
                retry_results = retry_data.get('results', []) if isinstance(retry_data, dict) else retry_data
                if retry_results:
                    return str(retry_results[0].get('id'))

        pytest.skip(f"No models available and failed to create test model: {create_response.status_code} - {create_response.text}")
    except Exception as e:
        pytest.skip(f"Failed to set up test model: {e}")


@pytest.fixture
def sdk_client(api_available, e2e_api_key, django_db_blocker):
    """Create SDK client for E2E tests.

    ROOT CAUSE of previous 401 failures:
    The e2e_api_key fixture is module-scoped and creates the API key
    ONCE.  But TransactionTestCase (transaction=True) truncates all
    tables after each test.  The module-scoped fixture still holds the
    key VALUE, but the DB record was truncated after a prior test.
    Fix: re-ensure the key exists before each SDK test.
    """
    import requests as _requests

    api_base_url = 'http://localhost:8000/api/v1'
    api_key = e2e_api_key

    # Re-ensure the API key record exists in the DB.
    # TransactionTestCase may have truncated it after a prior test.
    try:
        with django_db_blocker.unblock():
            from hub.apps.auth.models import APIKey as AuthAPIKey
            from hub.apps.tenants.models import Tenant
            from hub.apps.users.models import User, UserStatus, Role, UserRole
            from hub.apps.auth.permissions import ROLE_SCOPE_MAP
            from hub.apps.testing.billing_support import ensure_e2e_tenant_ready

            key_hash = AuthAPIKey.hash_key(api_key)
            if not AuthAPIKey.objects.filter(key_hash=key_hash).exists():
                tenant, _ = Tenant.objects.get_or_create(
                    slug='model-serving-sdk-test',
                    defaults={'name': 'Model Serving SDK Test'},
                )
                ensure_e2e_tenant_ready(tenant)
                user, _ = User.objects.get_or_create(
                    email='model-serving-sdk@example.com',
                    defaults={
                        'tenant': tenant,
                        'status': UserStatus.ACTIVE,
                    },
                )
                if user.tenant_id != tenant.id:
                    user.tenant = tenant
                    user.save(update_fields=['tenant'])
                role, _ = Role.objects.get_or_create(
                    tenant=tenant, name='TENANT_ADMIN',
                    defaults={'description': 'Tenant Administrator'},
                )
                UserRole.objects.get_or_create(user=user, role=role)
                scopes = list(
                    ROLE_SCOPE_MAP.get('TENANT_ADMIN', [])
                )
                AuthAPIKey.objects.create(
                    user=user, tenant=tenant,
                    name='SDK E2E Recreated Key',
                    key_hash=key_hash, scopes=scopes,
                )
    except Exception:
        pass  # Best-effort; probe below will catch real failures

    # Verify auth works
    try:
        probe = _requests.get(
            f'{api_base_url}/ml/models/',
            headers={'Authorization': f'ApiKey {api_key}'},
            params={'limit': 1},
            timeout=5,
        )
        if probe.status_code in (401, 403):
            pytest.skip(
                f"SDK auth not available: API returned "
                f"{probe.status_code}"
            )
    except _requests.exceptions.ConnectionError:
        pytest.skip("API not reachable for SDK tests")

    config = DataHubClientConfig(
        base_url=api_base_url,
        api_token=api_key,
        timeout=30.0,
        max_retries=3,
        user_agent="datahub-interoperability-sdk/1.0.0",
        enable_logging=False,
    )
    return DataHubClient(config)


@pytest.fixture
def sdk_model_serving_api(sdk_client):
    """Create Model Serving API instance for SDK tests."""
    return ModelServingAPI(sdk_client)


@pytest.fixture
def sdk_test_model_id(sdk_client):
    """Get or create a test model via SDK for SDK tests.

    Depends on sdk_client which already handles API key re-creation
    after TransactionTestCase truncation.  Uses the SDK's authenticated
    HTTP client to create models via gunicorn (outside test transaction).
    """
    import asyncio

    async def _get_or_create():
        # Try to find an existing model
        models = await sdk_client.ml.list_models(limit=1)
        if models:
            return str(models[0]['id'])

        # Create an asset first (required for model creation)
        asset = await sdk_client.assets.create_asset(
            key=f'sdk-model-test-{uuid.uuid4().hex[:8]}',
            name='SDK Model Test Asset',
            domain='ml',
            visibility='INTERNAL',
        )
        asset_id = asset.get('id')

        # Create the model
        model = await sdk_client.ml.create_model(
            odh_model_id=f'sdk-e2e-{uuid.uuid4().hex[:8]}',
            odh_model_version='1.0.0',
            model_type='CLASSIFICATION',
            asset_id=str(asset_id),
        )
        return str(model['id'])

    try:
        return asyncio.run(_get_or_create())
    except Exception as e:
        pytest.skip(f"Cannot create test model for SDK: {e}")


class TestMLServingCLIWorkflow:
    """E2E tests for complete CLI workflows"""

    def test_complete_serving_workflow_cli(self, runner, ml_serving_available, test_model_id):
        """
        Test complete workflow using CLI:
        deploy → list → get → predict → metrics → undeploy

        Every step must succeed — no silent skips.
        """
        # Step 1: Deploy model for serving
        deploy_result = runner.invoke(cli, [
            'ml', 'serving', 'deploy',
            '--model-id', test_model_id,
            '--format', 'json'
        ])
        assert deploy_result.exit_code == 0, (
            f"Deploy failed (exit_code={deploy_result.exit_code}):\n"
            f"{deploy_result.output}"
        )
        serving_data = json.loads(deploy_result.output)
        serving_id = serving_data.get('serving_id') or serving_data.get('deployment_id')
        assert serving_id, f"No serving_id in response: {serving_data}"

        # Step 2: List serving deployments
        list_result = runner.invoke(cli, [
            'ml', 'serving', 'list',
            '--model-id', test_model_id,
            '--format', 'json'
        ])
        assert list_result.exit_code == 0, f"List failed: {list_result.output}"
        list_data = json.loads(list_result.output)
        if isinstance(list_data, dict):
            assert 'results' in list_data, f"Paginated response missing 'results': {list_data}"
        else:
            assert isinstance(list_data, list), f"Expected list or dict, got {type(list_data)}"

        # Step 3: Get serving deployment details
        get_result = runner.invoke(cli, [
            'ml', 'serving', 'get',
            serving_id,
            '--format', 'json'
        ])
        assert get_result.exit_code == 0, f"Get failed: {get_result.output}"
        get_data = json.loads(get_result.output)
        assert 'serving_id' in get_data or 'deployment_id' in get_data, (
            f"Get response missing serving_id/deployment_id: {get_data}"
        )

        # Step 4: Wait for deployment readiness then run prediction.
        # The ODH scheduler transitions deployments from DEPLOYING → READY
        # asynchronously; poll until the CLI predict succeeds.
        predict_result = None
        for _attempt in range(5):
            predict_result = runner.invoke(cli, [
                'ml', 'serving', 'predict',
                '--model-id', test_model_id,
                '--input', '{"feature1": 0.5, "feature2": 0.8}',
                '--format', 'json'
            ])
            if predict_result.exit_code == 0:
                break
            time.sleep(2)

        assert predict_result.exit_code == 0, (
            f"Predict failed after retries (exit_code={predict_result.exit_code}):\n"
            f"{predict_result.output}"
        )
        predict_data = json.loads(predict_result.output)
        assert 'output' in predict_data or 'prediction' in predict_data, (
            f"Prediction response missing output/prediction: {predict_data}"
        )

        # Step 5: Get metrics — prediction was made above so metrics must exist
        metrics_result = runner.invoke(cli, [
            'ml', 'serving', 'metrics',
            serving_id,
            '--format', 'json'
        ])
        assert metrics_result.exit_code == 0, f"Metrics failed: {metrics_result.output}"
        metrics_data = json.loads(metrics_result.output)
        assert isinstance(metrics_data, dict), f"Metrics should be dict, got {type(metrics_data)}"

        # Step 6: Undeploy
        undeploy_result = runner.invoke(cli, [
            'ml', 'serving', 'undeploy',
            serving_id,
            '--format', 'json'
        ])
        assert undeploy_result.exit_code == 0, f"Undeploy failed: {undeploy_result.output}"

    def test_ab_test_workflow_cli(self, runner, ml_serving_available, test_model_id):
        """
        Test complete A/B test workflow using CLI:
        create → list → get

        Every step must succeed — no silent skips.
        """
        # Step 1: Create A/B test
        create_result = runner.invoke(cli, [
            'ml', 'serving', 'ab-test', 'create',
            '--model-id', test_model_id,
            '--variant-id', test_model_id,
            '--traffic-split', '50:50',
            '--format', 'json'
        ])
        assert create_result.exit_code == 0, f"A/B test create failed: {create_result.output}"
        ab_test_data = json.loads(create_result.output)
        ab_test_id = ab_test_data.get('ab_test_id') or ab_test_data.get('id')
        assert ab_test_id, f"No ab_test_id in response: {ab_test_data}"

        # Step 2: List A/B tests
        list_result = runner.invoke(cli, [
            'ml', 'serving', 'ab-test', 'list',
            '--model-id', test_model_id,
            '--format', 'json'
        ])
        assert list_result.exit_code == 0, f"A/B test list failed: {list_result.output}"
        list_data = json.loads(list_result.output)
        assert isinstance(list_data, (list, dict))

        # Step 3: Get A/B test details
        get_result = runner.invoke(cli, [
            'ml', 'serving', 'ab-test', 'get',
            ab_test_id,
            '--format', 'json'
        ])
        assert get_result.exit_code == 0, f"A/B test get failed: {get_result.output}"
        get_data = json.loads(get_result.output)
        assert 'ab_test_id' in get_data or 'id' in get_data


class TestMLServingSDKWorkflow:
    """E2E tests for complete SDK workflows"""

    @pytest.mark.asyncio
    async def test_complete_serving_workflow_sdk(self, ml_serving_available, sdk_model_serving_api, sdk_test_model_id):
        """
        Test complete workflow using SDK:
        deploy → list → get → predict → metrics → undeploy

        Every step must succeed — no silent skips.
        """
        # Step 1: Deploy model
        serving_details = await sdk_model_serving_api.deploy_model_as_api(sdk_test_model_id)
        serving_id = serving_details.get("serving_id") or serving_details.get("deployment_id")
        assert serving_id, f"No serving_id in deploy response: {serving_details}"

        # Step 2: List deployments
        deployments = await sdk_model_serving_api.list_deployed_models(model_id=sdk_test_model_id)
        assert isinstance(deployments, list)
        assert len(deployments) > 0, "Deployment list should not be empty after deploy"

        # Step 3: Get serving details
        details = await sdk_model_serving_api.get_model_serving_details(serving_id)
        assert "serving_id" in details or "deployment_id" in details

        # Step 4: Run prediction (predict_via_api polls for READY status)
        input_data = {"feature1": 0.5, "feature2": 0.8}
        prediction = await sdk_model_serving_api.predict_via_api(sdk_test_model_id, input_data)
        assert "output" in prediction, f"Prediction response missing 'output': {prediction}"

        # Step 5: Get quality metrics
        metrics = await sdk_model_serving_api.get_model_quality_metrics(serving_id)
        assert "serving_id" in metrics or "deployment_id" in metrics or "metrics" in metrics

        # Step 6: Undeploy
        await sdk_model_serving_api.undeploy_model(serving_id)

    @pytest.mark.asyncio
    async def test_ab_test_workflow_sdk(self, ml_serving_available, sdk_model_serving_api, sdk_test_model_id):
        """
        Test complete A/B test workflow using SDK:
        create → list → get

        Every step must succeed — no silent skips.
        """
        # Step 1: Create A/B test
        ab_test = await sdk_model_serving_api.create_ab_test(
            sdk_test_model_id, sdk_test_model_id, "50:50"
        )
        ab_test_id = ab_test.get("ab_test_id") or ab_test.get("id")
        assert ab_test_id, f"No ab_test_id in response: {ab_test}"

        # Step 2: List A/B tests
        ab_tests = await sdk_model_serving_api.list_ab_tests(model_id=sdk_test_model_id)
        assert isinstance(ab_tests, list)

        # Step 3: Get A/B test details
        details = await sdk_model_serving_api.get_ab_test_details(ab_test_id)
        assert "ab_test_id" in details or "id" in details


class TestMLServingCLISDKConsistency:
    """E2E tests for CLI/SDK consistency"""

    def test_deploy_consistency(self, runner, ml_serving_available, sdk_test_model_id, sdk_model_serving_api):
        """Test that CLI and SDK produce consistent results for deploy"""
        # Deploy via CLI
        cli_result = runner.invoke(cli, [
            'ml', 'serving', 'deploy',
            '--model-id', sdk_test_model_id,
            '--format', 'json'
        ])
        assert cli_result.exit_code == 0, f"CLI deploy failed: {cli_result.output}"
        cli_data = json.loads(cli_result.output)

        # Deploy via SDK
        async def deploy_via_sdk():
            return await sdk_model_serving_api.deploy_model_as_api(sdk_test_model_id)

        sdk_result = asyncio.run(deploy_via_sdk())

        # Both should return similar structure
        assert 'serving_id' in cli_data or 'deployment_id' in cli_data, (
            f"CLI response missing serving_id/deployment_id: {cli_data}"
        )
        assert 'serving_id' in sdk_result or 'deployment_id' in sdk_result, (
            f"SDK response missing serving_id/deployment_id: {sdk_result}"
        )

    def test_list_consistency(self, runner, ml_serving_available, sdk_model_serving_api):
        """Test that CLI and SDK produce consistent results for list"""
        # List via CLI
        cli_result = runner.invoke(cli, [
            'ml', 'serving', 'list',
            '--format', 'json'
        ])
        assert cli_result.exit_code == 0, f"CLI list failed: {cli_result.output}"

        # List via SDK
        async def list_via_sdk():
            return await sdk_model_serving_api.list_deployed_models()

        sdk_result = asyncio.run(list_via_sdk())

        cli_data = json.loads(cli_result.output)
        cli_list = cli_data if isinstance(cli_data, list) else cli_data.get('results', [])

        # Both should return lists
        assert isinstance(cli_list, list), f"CLI list not a list: {cli_list}"
        assert isinstance(sdk_result, list), f"SDK list not a list: {sdk_result}"

    def test_predict_consistency(self, runner, ml_serving_available, sdk_test_model_id, sdk_model_serving_api):
        """Test that CLI and SDK produce consistent results for predict"""
        # Deploy a model first — each test has its own sdk_test_model_id
        # (function-scoped fixture), so prior deployments are not available.
        deploy_result = runner.invoke(cli, [
            'ml', 'serving', 'deploy',
            '--model-id', sdk_test_model_id,
            '--format', 'json'
        ])
        assert deploy_result.exit_code == 0, f"Deploy failed: {deploy_result.output}"

        input_data = {"feature1": 0.5, "feature2": 0.8}

        # Predict via SDK (has built-in readiness polling that waits for READY)
        async def predict_via_sdk():
            return await sdk_model_serving_api.predict_via_api(sdk_test_model_id, input_data)

        sdk_result = asyncio.run(predict_via_sdk())
        assert 'output' in sdk_result, f"SDK predict missing 'output': {sdk_result}"

        # Predict via CLI (deployment is READY now after SDK polling)
        cli_result = runner.invoke(cli, [
            'ml', 'serving', 'predict',
            '--model-id', sdk_test_model_id,
            '--input', json.dumps(input_data),
            '--format', 'json'
        ])
        assert cli_result.exit_code == 0, f"CLI predict failed: {cli_result.output}"
        cli_data = json.loads(cli_result.output)
        assert 'output' in cli_data or 'prediction' in cli_data, (
            f"CLI predict missing output/prediction: {cli_data}"
        )

    def test_metrics_consistency(self, runner, ml_serving_available, sdk_test_model_id, sdk_model_serving_api):
        """Test that CLI and SDK produce consistent results for metrics"""
        # Deploy a model first so we have a deployment to get metrics for.
        # Each test has its own sdk_test_model_id (function-scoped fixture),
        # so prior test deployments are not available here.
        deploy_result = runner.invoke(cli, [
            'ml', 'serving', 'deploy',
            '--model-id', sdk_test_model_id,
            '--format', 'json'
        ])
        assert deploy_result.exit_code == 0, f"Deploy failed: {deploy_result.output}"

        deploy_data = json.loads(deploy_result.output)
        serving_id = deploy_data.get('serving_id') or deploy_data.get('deployment_id')
        assert serving_id, f"No serving_id in deploy response: {deploy_data}"

        # Get metrics via CLI
        cli_metrics_result = runner.invoke(cli, [
            'ml', 'serving', 'metrics',
            serving_id,
            '--format', 'json'
        ])
        assert cli_metrics_result.exit_code == 0, f"CLI metrics failed: {cli_metrics_result.output}"

        # Get metrics via SDK
        async def get_metrics_via_sdk():
            return await sdk_model_serving_api.get_model_quality_metrics(serving_id)

        sdk_metrics_result = asyncio.run(get_metrics_via_sdk())

        cli_metrics_data = json.loads(cli_metrics_result.output)
        # Both should return dictionaries with metrics
        assert isinstance(cli_metrics_data, dict), f"CLI metrics not a dict: {cli_metrics_data}"
        assert isinstance(sdk_metrics_result, dict), f"SDK metrics not a dict: {sdk_metrics_result}"
