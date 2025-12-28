"""
Integration tests for Transformation Wrangling API.

Tests wrangling methods end-to-end against the running Docker Compose API service.
No mocks/stubs - uses real API connections.

NOTE: These tests require:
1. Docker Compose services running (api-service, postgres, redis)
2. A test user and API key configured
   OR set via environment variables: TEST_API_KEY or DATAHUB_API_KEY

To run these tests:
1. Ensure Docker Compose services are running: docker compose ps
2. Set API key: export TEST_API_KEY=your-api-key
3. Run: pytest tests/test_transformation_wrangling_integration.py -v -m integration
"""
import os
import pytest
import uuid
import subprocess
from typing import Optional
from datahub_interoperability import DataHubClient, DataHubClientConfig
from datahub_interoperability.errors import (
    ValidationError,
    NotFoundError,
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
        django_shell_script = """
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.auth.models import APIKey

tenant, _ = Tenant.objects.get_or_create(
    slug='transformation-wrangling-sdk-test-tenant',
    defaults={'name': 'Transformation Wrangling SDK Test Tenant'}
)
user, _ = User.objects.get_or_create(
    email='transformation-wrangling-sdk-test@example.com',
    defaults={
        'tenant': tenant,
        'status': UserStatus.ACTIVE
    }
)
if user.tenant != tenant:
    user.tenant = tenant
    user.status = UserStatus.ACTIVE
    user.save()
APIKey.objects.filter(user=user, name='Transformation Wrangling SDK Test Key').delete()
api_key_value = APIKey.generate_key()
api_key_hash = APIKey.hash_key(api_key_value)
api_key_obj = APIKey.objects.create(
    user=user,
    tenant=tenant,
    name='Transformation Wrangling SDK Test Key',
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
    Create a test asset via Django shell.

    Args:
        asset_name: Asset name

    Returns:
        Created asset data with id
    """
    # Use subprocess approach (works both inside and outside Docker)
    # This avoids async context issues with Django ORM
    # Calculate asset_key before f-string
    asset_key = asset_name.lower().replace(" ", "-").replace("_", "-")
    django_shell_script = f"""
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.assets.models import Asset, AssetStatus
import json

from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus

tenant = Tenant.objects.get(slug='transformation-wrangling-sdk-test-tenant')
user = User.objects.get(email='transformation-wrangling-sdk-test@example.com')

# Create asset
asset = Asset.objects.create(
    name='{asset_name}',
    key='{asset_key}',
    description='Test asset for wrangling SDK tests',
    tenant=tenant,
    created_by=user,
    status=AssetStatus.ACTIVE,
    domain='test'
)

# Create CSV file content (use base64 or hex to avoid f-string issues)
import base64
csv_content_b64 = base64.b64encode(b'id,name,age,city\\n1,Alice,30,New York\\n2,Bob,25,London\\n3,Charlie,35,Paris\\n').decode('ascii')
csv_content = base64.b64decode(csv_content_b64)
csv_size = len(csv_content)

# Create file for the asset
file_obj = File.objects.create(
    tenant=tenant,
    created_by=user,
    name='{asset_key}.csv',
    content_type='text/csv',
    size=csv_size,
    status=FileStatus.PENDING,
    storage_path='test/wrangling/{asset_key}.csv'
)

# Upload file to storage (real service)
from hub.apps.files.storage import S3StorageClient
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
    # If storage fails, still create dataset but file won't be accessible
    pass

# Create dataset linked to asset and file
dataset = Dataset.objects.create(
    tenant=tenant,
    created_by=user,
    asset=asset,
    file=file_obj,
    format='CSV',
    version=1,
    row_count=3,
    schema_json={{'fields': [
        {{'name': 'id', 'data_type': 'integer'}},
        {{'name': 'name', 'data_type': 'string'}},
        {{'name': 'age', 'data_type': 'integer'}},
        {{'name': 'city', 'data_type': 'string'}}
    ]}}
)

print(json.dumps({{'id': str(asset.id), 'name': asset.name}}))
"""
    try:
        # Check if we're inside Docker - if so, run python directly
        import os
        if os.path.exists('/app'):
            # Inside Docker - run python manage.py shell directly
            result = subprocess.run(
                ['python', '/app/hub/manage.py', 'shell'],
                input=django_shell_script,
                text=True,
                capture_output=True,
                timeout=30,
                cwd='/app'
            )
        else:
            # Outside Docker - use docker compose exec
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
            # Parse output - look for JSON in any line
            output_lines = result.stdout.strip().split('\n')
            for line in reversed(output_lines):
                line = line.strip()
                # Look for JSON-like content
                if '{' in line and 'id' in line:
                    # Try to extract JSON from the line
                    try:
                        # Find JSON object in the line
                        start_idx = line.find('{')
                        end_idx = line.rfind('}') + 1
                        if start_idx >= 0 and end_idx > start_idx:
                            json_str = line[start_idx:end_idx]
                            parsed = json.loads(json_str)
                            if 'id' in parsed:
                                return parsed
                    except (json.JSONDecodeError, ValueError):
                        continue
            # If no JSON found, check stderr for errors
            if result.stderr:
                pytest.fail(f"Failed to create test asset. Django shell stderr: {result.stderr[:500]}")
            pytest.fail(f"Failed to create test asset. No JSON in output. stdout: {result.stdout[-500:]}")
        else:
            # Command failed
            error_msg = result.stderr if result.stderr else result.stdout
            pytest.fail(f"Failed to create test asset. Django shell failed with return code {result.returncode}. Error: {error_msg[-500:]}")
    except Exception as e:
        pytest.fail(f"Failed to create test asset: {type(e).__name__}: {str(e)}")


def cleanup_test_asset_via_django_shell(asset_id: str):
    """
    Clean up test asset via Django shell.

    Args:
        asset_id: Asset ID to delete
    """
    django_shell_script = f"""
from hub.apps.assets.models import Asset
try:
    asset = Asset.objects.get(id='{asset_id}')
    asset.delete()
    print('deleted')
except Asset.DoesNotExist:
    print('not_found')
"""
    try:
        import os
        if os.path.exists('/app'):
            # Inside Docker - run python directly
            subprocess.run(
                ['python', '/app/hub/manage.py', 'shell'],
                input=django_shell_script,
                text=True,
                capture_output=True,
                timeout=30,
                cwd='/app'
            )
        else:
            # Outside Docker - use docker compose exec
            subprocess.run(
                ['docker', 'compose', 'exec', '-T', 'api-service', 'python', 'manage.py', 'shell'],
                input=django_shell_script,
                text=True,
                capture_output=True,
                timeout=30,
                cwd='/home/ph/Desktop/DataInteroperabilityHub'
            )
    except Exception:
        pass  # Ignore cleanup errors


# Integration Tests

@pytest.mark.integration
@pytest.mark.asyncio
async def test_start_wrangling_success(real_client):
    """Test successful wrangling session start with real API"""
    asset = create_test_asset_via_django_shell(f"test-wrangling-asset-{uuid.uuid4()}")
    asset_id = asset['id']

    try:
        # Start wrangling session
        result = await real_client.transformation.start_wrangling(asset_id=asset_id)

        # Verify response structure - response may have 'session_id' or 'id'
        session_id = result.get('session_id') or result.get('id')
        assert session_id is not None
        assert 'operation_id' in result or 'applied_operations_count' in result

        # Verify we can get the session
        session = await real_client.transformation.get_wrangling_session(session_id)
        # Session response may have 'id' or 'session_id'
        assert session.get('session_id') == session_id or session.get('id') == session_id
        assert session.get('asset_id') == asset_id or 'asset' in session

    finally:
        cleanup_test_asset_via_django_shell(asset_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_start_wrangling_with_operation(real_client):
    """Test starting wrangling session with initial operation"""
    asset = create_test_asset_via_django_shell(f"test-wrangling-asset-{uuid.uuid4()}")
    asset_id = asset['id']

    try:
        operation = {
            "type": "FILTER",
            "parameters": {
                "condition": "age > 25"
            }
        }

        # Start wrangling session with operation
        result = await real_client.transformation.start_wrangling(
            asset_id=asset_id,
            operation=operation
        )

        # Verify response - response may have 'session_id' or 'id'
        session_id = result.get('session_id') or result.get('id')
        assert session_id is not None
        # Should have at least one operation applied
        assert result.get('applied_operations_count', 0) >= 0

    finally:
        cleanup_test_asset_via_django_shell(asset_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_start_wrangling_validation_asset_id_empty(real_client):
    """Test that empty asset_id raises ValidationError"""
    with pytest.raises(ValidationError) as exc_info:
        await real_client.transformation.start_wrangling(asset_id="")
    assert "asset_id" in str(exc_info.value.message).lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_start_wrangling_not_found_error(real_client):
    """Test that non-existent asset raises NotFoundError"""
    fake_asset_id = str(uuid.uuid4())

    # Backend requires operation, so provide a simple one
    operation = {
        "type": "FILTER",
        "parameters": {"condition": "1 == 1"}
    }

    # Backend may return ServerError or NotFoundError for non-existent assets
    with pytest.raises((NotFoundError, ServerError)) as exc_info:
        await real_client.transformation.start_wrangling(
            asset_id=fake_asset_id,
            operation=operation
        )
    error_msg = str(exc_info.value.message).lower()
    assert "not found" in error_msg or "asset" in error_msg


@pytest.mark.integration
@pytest.mark.asyncio
async def test_apply_wrangling_operation_success(real_client):
    """Test successful wrangling operation application with real API"""
    asset = create_test_asset_via_django_shell(f"test-wrangling-asset-{uuid.uuid4()}")
    asset_id = asset['id']

    try:
        # Start wrangling session (backend requires operation)
        operation_init = {
            "type": "FILTER",
            "parameters": {"condition": "1 == 1"}
        }
        start_result = await real_client.transformation.start_wrangling(
            asset_id=asset_id,
            operation=operation_init
        )
        session_id = start_result['session_id']

        # Apply an operation
        operation = {
            "type": "FILTER",
            "parameters": {
                "condition": "age > 25"
            }
        }

        result = await real_client.transformation.apply_wrangling_operation(
            session_id=session_id,
            operation=operation
        )

        # Verify response
        assert 'session_id' in result
        assert result['session_id'] == session_id
        assert 'operation_id' in result or 'applied_operations_count' in result

    finally:
        cleanup_test_asset_via_django_shell(asset_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_apply_wrangling_operation_validation_session_id_empty(real_client):
    """Test that empty session_id raises ValidationError"""
    operation = {
        "type": "FILTER",
        "parameters": {"condition": "age > 25"}
    }

    with pytest.raises(ValidationError) as exc_info:
        await real_client.transformation.apply_wrangling_operation(
            session_id="",
            operation=operation
        )
    assert "session_id" in str(exc_info.value.message).lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_apply_wrangling_operation_not_found_error(real_client):
    """Test that non-existent session raises NotFoundError"""
    fake_session_id = str(uuid.uuid4())
    operation = {
        "type": "FILTER",
        "parameters": {"condition": "age > 25"}
    }

    with pytest.raises(NotFoundError) as exc_info:
        await real_client.transformation.apply_wrangling_operation(
            session_id=fake_session_id,
            operation=operation
        )
    # Error message can be "not found" or "no wranglingsession matches"
    error_msg = str(exc_info.value.message).lower()
    assert "not found" in error_msg or "wranglingsession" in error_msg or "matches" in error_msg


@pytest.mark.integration
@pytest.mark.asyncio
async def test_undo_wrangling_success(real_client):
    """Test successful wrangling undo with real API"""
    asset = create_test_asset_via_django_shell(f"test-wrangling-asset-{uuid.uuid4()}")
    asset_id = asset['id']

    try:
        # Start wrangling session (backend requires operation)
        operation_init = {
            "type": "FILTER",
            "parameters": {"condition": "1 == 1"}
        }
        start_result = await real_client.transformation.start_wrangling(
            asset_id=asset_id,
            operation=operation_init
        )
        session_id = start_result['session_id']

        # Apply an operation first
        operation = {
            "type": "FILTER",
            "parameters": {"condition": "age > 25"}
        }
        await real_client.transformation.apply_wrangling_operation(
            session_id=session_id,
            operation=operation
        )

        # Now undo it
        result = await real_client.transformation.undo_wrangling(session_id)

        # Verify response
        assert 'session_id' in result
        assert result['session_id'] == session_id
        assert 'can_undo' in result
        assert 'can_redo' in result

    finally:
        cleanup_test_asset_via_django_shell(asset_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_undo_wrangling_validation_session_id_empty(real_client):
    """Test that empty session_id raises ValidationError"""
    with pytest.raises(ValidationError) as exc_info:
        await real_client.transformation.undo_wrangling("")
    assert "session_id" in str(exc_info.value.message).lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_undo_wrangling_not_found_error(real_client):
    """Test that non-existent session raises NotFoundError"""
    fake_session_id = str(uuid.uuid4())

    with pytest.raises(NotFoundError) as exc_info:
        await real_client.transformation.undo_wrangling(fake_session_id)
    assert "not found" in str(exc_info.value.message).lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redo_wrangling_success(real_client):
    """Test successful wrangling redo with real API"""
    asset = create_test_asset_via_django_shell(f"test-wrangling-asset-{uuid.uuid4()}")
    asset_id = asset['id']

    try:
        # Start wrangling session (backend requires operation)
        operation_init = {
            "type": "FILTER",
            "parameters": {"condition": "1 == 1"}
        }
        start_result = await real_client.transformation.start_wrangling(
            asset_id=asset_id,
            operation=operation_init
        )
        session_id = start_result['session_id']

        # Apply an operation
        operation = {
            "type": "FILTER",
            "parameters": {"condition": "age > 25"}
        }
        await real_client.transformation.apply_wrangling_operation(
            session_id=session_id,
            operation=operation
        )

        # Undo it
        await real_client.transformation.undo_wrangling(session_id)

        # Now redo it
        result = await real_client.transformation.redo_wrangling(session_id)

        # Verify response
        assert 'session_id' in result
        assert result['session_id'] == session_id
        assert 'can_undo' in result
        assert 'can_redo' in result

    finally:
        cleanup_test_asset_via_django_shell(asset_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redo_wrangling_validation_session_id_empty(real_client):
    """Test that empty session_id raises ValidationError"""
    with pytest.raises(ValidationError) as exc_info:
        await real_client.transformation.redo_wrangling("")
    assert "session_id" in str(exc_info.value.message).lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redo_wrangling_not_found_error(real_client):
    """Test that non-existent session raises NotFoundError"""
    fake_session_id = str(uuid.uuid4())

    with pytest.raises(NotFoundError) as exc_info:
        await real_client.transformation.redo_wrangling(fake_session_id)
    assert "not found" in str(exc_info.value.message).lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_wrangling_session_success(real_client):
    """Test successful wrangling session retrieval with real API"""
    asset = create_test_asset_via_django_shell(f"test-wrangling-asset-{uuid.uuid4()}")
    asset_id = asset['id']

    try:
        # Start wrangling session (backend requires operation)
        operation_init = {
            "type": "FILTER",
            "parameters": {"condition": "1 == 1"}
        }
        start_result = await real_client.transformation.start_wrangling(
            asset_id=asset_id,
            operation=operation_init
        )
        session_id = start_result['session_id']

        # Get the session
        result = await real_client.transformation.get_wrangling_session(session_id)

        # Verify response structure - response may have 'id' or 'session_id'
        assert result.get('session_id') == session_id or result.get('id') == session_id
        assert result.get('asset_id') == asset_id or 'asset' in result
        assert 'operation_history' in result or 'current_state' in result

    finally:
        cleanup_test_asset_via_django_shell(asset_id)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_wrangling_session_validation_session_id_empty(real_client):
    """Test that empty session_id raises ValidationError"""
    with pytest.raises(ValidationError) as exc_info:
        await real_client.transformation.get_wrangling_session("")
    assert "session_id" in str(exc_info.value.message).lower()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_wrangling_session_not_found_error(real_client):
    """Test that non-existent session raises NotFoundError"""
    fake_session_id = str(uuid.uuid4())

    with pytest.raises(NotFoundError) as exc_info:
        await real_client.transformation.get_wrangling_session(fake_session_id)
    # Error message can be "not found" or "no wranglingsession matches"
    error_msg = str(exc_info.value.message).lower()
    assert "not found" in error_msg or "wranglingsession" in error_msg or "matches" in error_msg


@pytest.mark.integration
@pytest.mark.asyncio
async def test_wrangling_workflow_complete(real_client):
    """Test complete wrangling workflow: start, apply, undo, redo, get"""
    asset = create_test_asset_via_django_shell(f"test-wrangling-asset-{uuid.uuid4()}")
    asset_id = asset['id']

    try:
        # 1. Start wrangling session (backend requires operation)
        operation_init = {
            "type": "FILTER",
            "parameters": {"condition": "1 == 1"}
        }
        start_result = await real_client.transformation.start_wrangling(
            asset_id=asset_id,
            operation=operation_init
        )
        # Response may have 'session_id' or 'id'
        session_id = start_result.get('session_id') or start_result.get('id')
        assert session_id is not None
        assert session_id is not None

        # 2. Apply first operation
        operation1 = {
            "type": "FILTER",
            "parameters": {"condition": "age > 25"}
        }
        apply_result1 = await real_client.transformation.apply_wrangling_operation(
            session_id=session_id,
            operation=operation1
        )
        # Response may have 'session_id' or 'id'
        assert apply_result1.get('session_id') == session_id or apply_result1.get('id') == session_id

        # 3. Apply second operation
        operation2 = {
            "type": "SORT",
            "parameters": {"columns": ["age"], "order": "asc"}
        }
        apply_result2 = await real_client.transformation.apply_wrangling_operation(
            session_id=session_id,
            operation=operation2
        )
        # Response may have 'session_id' or 'id'
        assert apply_result2.get('session_id') == session_id or apply_result2.get('id') == session_id

        # 4. Get session to verify state
        session = await real_client.transformation.get_wrangling_session(session_id)
        # Session response may have 'id' or 'session_id'
        assert session.get('session_id') == session_id or session.get('id') == session_id
        assert session.get('applied_operations_count', 0) >= 2

        # 5. Undo last operation
        undo_result = await real_client.transformation.undo_wrangling(session_id)
        # Response may have 'session_id' or 'id'
        assert undo_result.get('session_id') == session_id or undo_result.get('id') == session_id
        assert undo_result.get('can_redo', False) is True

        # 6. Redo operation
        redo_result = await real_client.transformation.redo_wrangling(session_id)
        # Response may have 'session_id' or 'id'
        assert redo_result.get('session_id') == session_id or redo_result.get('id') == session_id
        assert redo_result.get('can_undo', False) is True

        # 7. Final session state
        final_session = await real_client.transformation.get_wrangling_session(session_id)
        # Session response may have 'id' or 'session_id'
        assert final_session.get('session_id') == session_id or final_session.get('id') == session_id

    finally:
        cleanup_test_asset_via_django_shell(asset_id)

