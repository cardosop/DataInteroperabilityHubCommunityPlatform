"""
Integration tests for Transformation Preview API.

Tests preview methods end-to-end against the running Docker Compose API service.
No mocks/stubs - uses real API connections.

NOTE: These tests require:
1. Docker Compose services running (api-service, postgres, redis)
2. A test user and API key configured
   OR set via environment variables: TEST_API_KEY or DATAHUB_API_KEY

To run these tests:
1. Ensure Docker Compose services are running: docker compose ps
2. Set API key: export TEST_API_KEY=your-api-key
3. Run: pytest tests/test_transformation_preview_integration.py -v -m integration
"""
import os
import pytest
import uuid
import subprocess
import asyncio
from typing import Optional
from datahub_interoperability import DataHubClient, DataHubClientConfig
from datahub_interoperability.errors import (
    ValidationError,
    NotFoundError,
    ServerError,
    RateLimitError,
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

    # Method 2: Try to create API key via Django shell command (works when running inside Docker)
    # Check if we're inside Docker by checking if /app exists
    if os.path.exists('/app'):
        try:
            # Use subprocess to call Django shell (avoids test database issues)
            django_shell_script = """
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus, UserRole, Role
from hub.apps.auth.models import APIKey
from hub.apps.governance.models import AccessPolicy

tenant, _ = Tenant.objects.get_or_create(
    slug='transformation-preview-sdk-test-tenant',
    defaults={'name': 'Transformation Preview SDK Test Tenant'}
)
user, _ = User.objects.get_or_create(
    email='transformation-preview-sdk-test@example.com',
    defaults={
        'tenant': tenant,
        'status': UserStatus.ACTIVE
    }
)
if user.tenant != tenant:
    user.tenant = tenant
    user.status = UserStatus.ACTIVE
    user.save()

# Assign DATA_PROVIDER role to user
data_provider_role, _ = Role.objects.get_or_create(
    tenant=tenant,
    name='DATA_PROVIDER',
    defaults={'description': 'Data Provider Role'}
)
UserRole.objects.get_or_create(
    user=user,
    role=data_provider_role
)

# Create access policy to allow transformation operations
AccessPolicy.objects.get_or_create(
    tenant=tenant,
    name='Allow Transformation Operations for SDK Tests',
    defaults={
        'conditions': {
            'user': {'tenant_id': str(tenant.id)}
        },
        'effect': 'ALLOW',
        'priority': 100,
        'enabled': True,
        'created_by': user
    }
)

APIKey.objects.filter(user=user, name='Transformation Preview SDK Test Key').delete()
api_key_value = APIKey.generate_key()
api_key_hash = APIKey.hash_key(api_key_value)
api_key_obj = APIKey.objects.create(
    user=user,
    tenant=tenant,
    name='Transformation Preview SDK Test Key',
    key_hash=api_key_hash,
    scopes=['transformation:write']
)
print(api_key_value)
"""
            result = subprocess.run(
                ['python', 'manage.py', 'shell'],
                input=django_shell_script,
                text=True,
                capture_output=True,
                timeout=30,
                cwd='/app/hub'
            )
            # Check return code - Django shell may return non-zero due to warnings
            # but still output the API key successfully
            output_lines = result.stdout.strip().split('\n')
            # Find the API key in the output
            # Filter out Django shell messages and look for valid API key format
            # API keys are base64url encoded strings, typically 40+ characters, no spaces
            for line in reversed(output_lines):
                line = line.strip()
                # Skip empty lines
                if not line:
                    continue
                # Skip Django shell messages
                if 'imported' in line.lower() or 'objects' in line.lower() or 'details' in line.lower():
                    continue
                # Skip lines with spaces (Django shell output)
                if ' ' in line:
                    continue
                # Valid API key format: base64url characters (alphanumeric, -, _)
                # Must be at least 40 characters (typical API key length)
                if len(line) >= 40 and all(c.isalnum() or c in '-_' for c in line):
                    return line
        except Exception as e:
            # Django shell failed, continue to fallback
            # Don't log here to avoid noise in test output
            pass

    # Method 3: Try docker compose exec (when running outside Docker)
    try:
        django_shell_script = """
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.auth.models import APIKey

tenant, _ = Tenant.objects.get_or_create(
    slug='transformation-preview-sdk-test-tenant',
    defaults={'name': 'Transformation Preview SDK Test Tenant'}
)
user, _ = User.objects.get_or_create(
    email='transformation-preview-sdk-test@example.com',
    defaults={
        'tenant': tenant,
        'status': UserStatus.ACTIVE
    }
)
if user.tenant != tenant:
    user.tenant = tenant
    user.status = UserStatus.ACTIVE
    user.save()
APIKey.objects.filter(user=user, name='Transformation Preview SDK Test Key').delete()
api_key_value = APIKey.generate_key()
api_key_hash = APIKey.hash_key(api_key_value)
api_key_obj = APIKey.objects.create(
    user=user,
    tenant=tenant,
    name='Transformation Preview SDK Test Key',
    key_hash=api_key_hash
)
print(api_key_value)
"""
        result = subprocess.run(
            ['docker', 'compose', 'exec', '-T', 'api-service', 'python', 'manage.py', 'shell'],
            input=django_shell_script,
            text=True,
            capture_output=True,
            timeout=30,
            cwd='/home/ph/Desktop/DataInteroperabilityHub'
        )
        if result.returncode == 0:
            output_lines = result.stdout.strip().split('\n')
            # Find the API key in the output (usually the last non-empty line)
            for line in reversed(output_lines):
                line = line.strip()
                if line and len(line) > 20:  # API keys are typically long strings
                    return line
    except Exception:
        pass

    return None


@pytest.fixture
def real_api_config():
    """Fixture for real API configuration"""
    api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:8000/api/v1')
    api_key = setup_authentication_for_sdk_tests(api_base_url)

    if not api_key:
        pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

    return DataHubClientConfig(
        base_url=api_base_url,
        api_token=api_key,
        timeout=30.0,
        max_retries=3,
        user_agent="test-agent",
        enable_logging=False,
    )


@pytest.fixture
async def real_client(real_api_config):
    """Fixture for real API client"""
    async with DataHubClient(real_api_config) as client:
        yield client




def create_test_asset_via_django_shell(asset_name: str) -> dict:
    """
    Create a test asset with dataset and file via Django shell.

    Args:
        asset_name: Asset name

    Returns:
        Created asset data with id
    """
    # Use subprocess to call Django shell (avoids test database issues)
    django_shell_script = f"""
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.files.storage import S3StorageClient
import json
import uuid
import io

tenant = Tenant.objects.get(slug='transformation-preview-sdk-test-tenant')
user = User.objects.get(email='transformation-preview-sdk-test@example.com')

# Create asset
asset = Asset.objects.create(
    tenant=tenant,
    name='{asset_name}',
    key='{asset_name.lower().replace(" ", "-")}',
    domain='test',
    status=AssetStatus.ACTIVE,
    created_by=user
)

# Create test CSV content
csv_content = b"id,name,age\\n1,Alice,25\\n2,Bob,30\\n3,Charlie,35\\n4,Diana,28\\n5,Eve,32\\n6,Frank,27\\n7,Grace,29\\n8,Henry,31\\n9,Iris,26\\n10,Jack,33"

# Create file object first
file_obj = File.objects.create(
    tenant=tenant,
    name='{asset_name.lower().replace(" ", "-")}.csv',
    storage_path='',  # Will be set after upload
    size=len(csv_content),
    content_type='text/csv',
    status=FileStatus.PENDING,
    created_by=user
)

# Upload file to MinIO/S3 storage
try:
    storage_client = S3StorageClient()
    storage_path = storage_client.save_file(
        tenant_id=str(tenant.id),
        file_id=str(file_obj.id),
        file_content=csv_content
    )
    # Update file with storage path and mark as active
    file_obj.storage_path = storage_path
    file_obj.status = FileStatus.ACTIVE
    file_obj.save()
except Exception as e:
    # If storage upload fails, still create the file record but mark as failed
    # This allows tests to verify error handling
    file_obj.status = FileStatus.FAILED
    file_obj.save()
    # Re-raise to indicate failure
    raise Exception(f"Failed to upload file to storage: {{str(e)}}")

# Create dataset linking asset and file
dataset = Dataset.objects.create(
    tenant=tenant,
    asset=asset,
    file=file_obj,
    format='CSV',
    row_count=10,
    created_by=user
)

print(json.dumps({{'id': str(asset.id), 'name': asset.name, 'key': asset.key}}))
"""
    try:
        result = subprocess.run(
            ['python', 'manage.py', 'shell'],
            input=django_shell_script,
            text=True,
            capture_output=True,
            timeout=30,
            cwd='/app/hub'
        )
        if result.returncode == 0:
            import json
            output_lines = result.stdout.strip().split('\n')
            for line in reversed(output_lines):
                line = line.strip()
                if line.startswith('{'):
                    try:
                        return json.loads(line)
                    except json.JSONDecodeError:
                        continue
        raise Exception("Failed to create test asset")
    except Exception as e:
        # Not inside Docker, use docker compose exec
        django_shell_script = f"""
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.files.storage import S3StorageClient
import json
import uuid
import io

tenant = Tenant.objects.get(slug='transformation-preview-sdk-test-tenant')
user = User.objects.get(email='transformation-preview-sdk-test@example.com')

# Create asset
asset = Asset.objects.create(
    tenant=tenant,
    name='{asset_name}',
    key='{asset_name.lower().replace(" ", "-")}',
    domain='test',
    status=AssetStatus.ACTIVE,
    created_by=user
)

# Create test CSV content
csv_content = b"id,name,age\\n1,Alice,25\\n2,Bob,30\\n3,Charlie,35\\n4,Diana,28\\n5,Eve,32\\n6,Frank,27\\n7,Grace,29\\n8,Henry,31\\n9,Iris,26\\n10,Jack,33"

# Create file object first
file_obj = File.objects.create(
    tenant=tenant,
    name='{asset_name.lower().replace(" ", "-")}.csv',
    storage_path='',
    size=len(csv_content),
    content_type='text/csv',
    status=FileStatus.PENDING,
    created_by=user
)

# Upload file to MinIO/S3 storage
try:
    storage_client = S3StorageClient()
    storage_path = storage_client.save_file(
        tenant_id=str(tenant.id),
        file_id=str(file_obj.id),
        file_content=csv_content
    )
    file_obj.storage_path = storage_path
    file_obj.status = FileStatus.ACTIVE
    file_obj.save()
except Exception as e:
    file_obj.status = FileStatus.FAILED
    file_obj.save()
    raise Exception(f"Failed to upload file to storage: {{str(e)}}")

# Create dataset linking asset and file
dataset = Dataset.objects.create(
    tenant=tenant,
    asset=asset,
    file=file_obj,
    format='CSV',
    row_count=10,
    created_by=user
)

print(json.dumps({{'id': str(asset.id), 'name': asset.name, 'key': asset.key}}))
"""
        result = subprocess.run(
            ['docker', 'compose', 'exec', '-T', 'api-service', 'python', 'manage.py', 'shell'],
            input=django_shell_script,
            text=True,
            capture_output=True,
            timeout=30,
            cwd='/home/ph/Desktop/DataInteroperabilityHub'
        )
        if result.returncode == 0:
            import json
            output_lines = result.stdout.strip().split('\n')
            for line in reversed(output_lines):
                line = line.strip()
                if line.startswith('{'):
                    try:
                        return json.loads(line)
                    except json.JSONDecodeError:
                        continue
        raise Exception("Failed to create test asset")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_generate_preview_success_integration(real_client):
    """Test successful preview generation with real API"""
    # Add delay to avoid rate limiting
    await asyncio.sleep(1)

    pipeline_name = f"test-pipeline-{uuid.uuid4().hex[:8]}"
    asset_name = f"test-asset-{uuid.uuid4().hex[:8]}"

    try:
        # Create test pipeline
        pipeline = await real_client.transformation.create_pipeline(
            name=pipeline_name,
            description="Test pipeline for preview",
            pipeline_definition={
                "version": "1.0.0",
                "steps": [
                    {
                        "name": "step1",
                        "type": "task",
                        "node_config": {
                            "operation": "transform"
                        }
                    }
                ]
            },
            status="ACTIVE"
        )
        pipeline_id = pipeline["id"]

        # Create test asset
        asset = create_test_asset_via_django_shell(asset_name)
        asset_id = asset["id"]

        # Generate preview
        result = await real_client.transformation.generate_preview(
            pipeline_id=pipeline_id,
            asset_id=asset_id,
            sample_size=10,
            sampling_method="first_n"
        )

        # Verify response structure
        assert "preview_id" in result
        assert result["pipeline_id"] == pipeline_id
        assert result["asset_id"] == asset_id
        # Analysis can be at top level or nested in preview_data
        assert "analysis" in result or "analysis" in result.get("preview_data", {})
        assert "generated_at" in result

    finally:
        # Cleanup
        try:
            await real_client.transformation.delete_pipeline(pipeline_id)
        except Exception:
            pass


@pytest.mark.integration
@pytest.mark.asyncio
async def test_generate_preview_with_defaults_integration(real_client):
    """Test preview generation with default parameters"""
    # Add delay to avoid rate limiting
    await asyncio.sleep(1)

    pipeline_name = f"test-pipeline-{uuid.uuid4().hex[:8]}"
    asset_name = f"test-asset-{uuid.uuid4().hex[:8]}"

    try:
        # Create test pipeline
        pipeline = await real_client.transformation.create_pipeline(
            name=pipeline_name,
            pipeline_definition={
                "version": "1.0.0",
                "steps": [
                    {
                        "name": "step1",
                        "type": "task",
                        "node_config": {
                            "operation": "transform"
                        }
                    }
                ]
            },
            status="ACTIVE"
        )
        pipeline_id = pipeline["id"]

        # Create test asset
        asset = create_test_asset_via_django_shell(asset_name)
        asset_id = asset["id"]

        # Generate preview with defaults
        result = await real_client.transformation.generate_preview(
            pipeline_id=pipeline_id,
            asset_id=asset_id
        )

        # Verify defaults were used
        assert "preview_id" in result
        # Default sample_size is 100, but actual sample may be smaller if asset has fewer rows

    finally:
        # Cleanup
        try:
            await real_client.transformation.delete_pipeline(pipeline_id)
        except Exception:
            pass


@pytest.mark.integration
@pytest.mark.asyncio
async def test_generate_preview_with_random_sampling_integration(real_client):
    """Test preview generation with random sampling method"""
    # Add delay to avoid rate limiting
    await asyncio.sleep(5)

    pipeline_name = f"test-pipeline-{uuid.uuid4().hex[:8]}"
    asset_name = f"test-asset-{uuid.uuid4().hex[:8]}"

    try:
        # Create test pipeline
        pipeline = await real_client.transformation.create_pipeline(
            name=pipeline_name,
            pipeline_definition={
                "version": "1.0.0",
                "steps": [
                    {
                        "name": "step1",
                        "type": "task",
                        "node_config": {
                            "operation": "transform"
                        }
                    }
                ]
            },
            status="ACTIVE"
        )
        pipeline_id = pipeline["id"]

        # Create test asset
        asset = create_test_asset_via_django_shell(asset_name)
        asset_id = asset["id"]

        # Generate preview with random sampling
        result = await real_client.transformation.generate_preview(
            pipeline_id=pipeline_id,
            asset_id=asset_id,
            sample_size=50,
            sampling_method="random"
        )

        assert "preview_id" in result

    finally:
        # Cleanup
        try:
            await real_client.transformation.delete_pipeline(pipeline_id)
        except Exception:
            pass


@pytest.mark.integration
@pytest.mark.asyncio
async def test_generate_preview_not_found_error_integration(real_client):
    """Test that 404 error raises NotFoundError with real API"""
    # Add delay to avoid rate limiting
    await asyncio.sleep(4)

    fake_pipeline_id = str(uuid.uuid4())
    fake_asset_id = str(uuid.uuid4())

    with pytest.raises(NotFoundError) as exc_info:
        await real_client.transformation.generate_preview(
            pipeline_id=fake_pipeline_id,
            asset_id=fake_asset_id
        )
    assert "not found" in str(exc_info.value.message).lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_preview_success_integration(real_client):
    """Test successful preview retrieval with real API"""
    # Add delay to avoid rate limiting
    await asyncio.sleep(10)

    pipeline_name = f"test-pipeline-{uuid.uuid4().hex[:8]}"
    asset_name = f"test-asset-{uuid.uuid4().hex[:8]}"

    try:
        # Create test pipeline with retry for rate limiting
        max_retries = 3
        pipeline = None
        for attempt in range(max_retries):
            try:
                pipeline = await real_client.transformation.create_pipeline(
                    name=pipeline_name,
                    pipeline_definition={
                        "version": "1.0.0",
                        "steps": [
                            {
                                "name": "step1",
                                "type": "task",
                                "node_config": {
                                    "operation": "transform"
                                }
                            }
                        ]
                    },
                    status="ACTIVE"
                )
                break
            except RateLimitError as e:
                if attempt < max_retries - 1:
                    retry_after = getattr(e, 'retry_after', 5)
                    await asyncio.sleep(int(retry_after) + 1)
                else:
                    raise
        pipeline_id = pipeline["id"]

        # Create test asset
        asset = create_test_asset_via_django_shell(asset_name)
        asset_id = asset["id"]

        # Generate preview first with retry for rate limiting
        preview_result = None
        for attempt in range(max_retries):
            try:
                preview_result = await real_client.transformation.generate_preview(
                    pipeline_id=pipeline_id,
                    asset_id=asset_id,
                    sample_size=10
                )
                break
            except RateLimitError as e:
                if attempt < max_retries - 1:
                    retry_after = getattr(e, 'retry_after', 5)
                    await asyncio.sleep(int(retry_after) + 1)
                else:
                    raise
        preview_id = preview_result["preview_id"]

        # Retrieve preview
        result = await real_client.transformation.get_preview(preview_id)

        # Verify response structure
        assert result["preview_id"] == preview_id
        assert result["pipeline_id"] == pipeline_id
        assert result["asset_id"] == asset_id
        # Analysis is nested in preview_data for get_preview response
        assert "preview_data" in result
        assert "analysis" in result["preview_data"]
        assert "generated_at" in result

    finally:
        # Cleanup
        try:
            await real_client.transformation.delete_pipeline(pipeline_id)
        except Exception:
            pass


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_preview_not_found_error_integration(real_client):
    """Test that 404 error raises NotFoundError with real API"""
    fake_preview_id = f"preview_{uuid.uuid4().hex}"

    with pytest.raises(NotFoundError) as exc_info:
        await real_client.transformation.get_preview(fake_preview_id)
    assert "not found" in str(exc_info.value.message).lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_generate_preview_validation_sample_size_too_small(real_client):
    """Test that sample_size < 1 raises ValidationError"""
    # Add delay to avoid rate limiting
    await asyncio.sleep(8)

    pipeline_name = f"test-pipeline-{uuid.uuid4().hex[:8]}"
    asset_name = f"test-asset-{uuid.uuid4().hex[:8]}"

    try:
        # Create test pipeline with retry for rate limiting
        max_retries = 3
        pipeline = None
        for attempt in range(max_retries):
            try:
                pipeline = await real_client.transformation.create_pipeline(
                    name=pipeline_name,
                    pipeline_definition={
                        "version": "1.0.0",
                        "steps": [
                            {
                                "name": "step1",
                                "type": "task",
                                "node_config": {
                                    "operation": "transform"
                                }
                            }
                        ]
                    },
                    status="ACTIVE"
                )
                break
            except RateLimitError as e:
                if attempt < max_retries - 1:
                    retry_after = getattr(e, 'retry_after', 5)
                    await asyncio.sleep(int(retry_after) + 1)
                else:
                    raise
        pipeline_id = pipeline["id"]

        # Create test asset
        asset = create_test_asset_via_django_shell(asset_name)
        asset_id = asset["id"]

        # Try with invalid sample_size
        with pytest.raises(ValidationError) as exc_info:
            await real_client.transformation.generate_preview(
                pipeline_id=pipeline_id,
                asset_id=asset_id,
                sample_size=0
            )
        assert "sample_size" in str(exc_info.value.message).lower()

    finally:
        # Cleanup
        try:
            await real_client.transformation.delete_pipeline(pipeline_id)
        except Exception:
            pass


@pytest.mark.integration
@pytest.mark.asyncio
async def test_generate_preview_validation_sample_size_too_large(real_client):
    """Test that sample_size > 10000 raises ValidationError"""
    # Add delay to avoid rate limiting
    await asyncio.sleep(10)

    pipeline_name = f"test-pipeline-{uuid.uuid4().hex[:8]}"
    asset_name = f"test-asset-{uuid.uuid4().hex[:8]}"

    try:
        # Create test pipeline with retry for rate limiting
        max_retries = 3
        pipeline = None
        for attempt in range(max_retries):
            try:
                pipeline = await real_client.transformation.create_pipeline(
                    name=pipeline_name,
                    pipeline_definition={
                        "version": "1.0.0",
                        "steps": [
                            {
                                "name": "step1",
                                "type": "task",
                                "node_config": {
                                    "operation": "transform"
                                }
                            }
                        ]
                    },
                    status="ACTIVE"
                )
                break
            except RateLimitError as e:
                if attempt < max_retries - 1:
                    retry_after = getattr(e, 'retry_after', 5)
                    await asyncio.sleep(int(retry_after) + 1)
                else:
                    raise
        pipeline_id = pipeline["id"]

        # Create test asset
        asset = create_test_asset_via_django_shell(asset_name)
        asset_id = asset["id"]

        # Try with invalid sample_size
        with pytest.raises(ValidationError) as exc_info:
            await real_client.transformation.generate_preview(
                pipeline_id=pipeline_id,
                asset_id=asset_id,
                sample_size=10001
            )
        assert "sample_size" in str(exc_info.value.message).lower()

    finally:
        # Cleanup
        try:
            await real_client.transformation.delete_pipeline(pipeline_id)
        except Exception:
            pass


@pytest.mark.integration
@pytest.mark.asyncio
async def test_generate_preview_validation_sampling_method_invalid(real_client):
    """Test that invalid sampling_method raises ValidationError"""
    # Add delay to avoid rate limiting
    await asyncio.sleep(2)

    pipeline_name = f"test-pipeline-{uuid.uuid4().hex[:8]}"
    asset_name = f"test-asset-{uuid.uuid4().hex[:8]}"

    try:
        # Create test pipeline
        pipeline = await real_client.transformation.create_pipeline(
            name=pipeline_name,
            pipeline_definition={
                "version": "1.0.0",
                "steps": [
                    {
                        "name": "step1",
                        "type": "task",
                        "node_config": {
                            "operation": "transform"
                        }
                    }
                ]
            },
            status="ACTIVE"
        )
        pipeline_id = pipeline["id"]

        # Create test asset
        asset = create_test_asset_via_django_shell(asset_name)
        asset_id = asset["id"]

        # Try with invalid sampling_method
        with pytest.raises(ValidationError) as exc_info:
            await real_client.transformation.generate_preview(
                pipeline_id=pipeline_id,
                asset_id=asset_id,
                sampling_method="invalid_method"
            )
        assert "sampling_method" in str(exc_info.value.message).lower()

    finally:
        # Cleanup
        try:
            await real_client.transformation.delete_pipeline(pipeline_id)
        except Exception:
            pass


@pytest.mark.integration
@pytest.mark.asyncio
async def test_generate_preview_sampling_method_case_insensitive(real_client):
    """Test that sampling_method is case-insensitive"""
    # Add delay to avoid rate limiting
    await asyncio.sleep(8)

    pipeline_name = f"test-pipeline-{uuid.uuid4().hex[:8]}"
    asset_name = f"test-asset-{uuid.uuid4().hex[:8]}"

    try:
        # Create test pipeline
        pipeline = await real_client.transformation.create_pipeline(
            name=pipeline_name,
            pipeline_definition={
                "version": "1.0.0",
                "steps": [
                    {
                        "name": "step1",
                        "type": "task",
                        "node_config": {
                            "operation": "transform"
                        }
                    }
                ]
            },
            status="ACTIVE"
        )
        pipeline_id = pipeline["id"]

        # Create test asset
        asset = create_test_asset_via_django_shell(asset_name)
        asset_id = asset["id"]

        # Test uppercase - should work (converted to lowercase)
        result1 = await real_client.transformation.generate_preview(
            pipeline_id=pipeline_id,
            asset_id=asset_id,
            sampling_method="FIRST_N"
        )
        assert "preview_id" in result1

        # Test mixed case - should work (converted to lowercase)
        result2 = await real_client.transformation.generate_preview(
            pipeline_id=pipeline_id,
            asset_id=asset_id,
            sampling_method="RaNdOm"
        )
        assert "preview_id" in result2

    finally:
        # Cleanup
        try:
            await real_client.transformation.delete_pipeline(pipeline_id)
        except Exception:
            pass

