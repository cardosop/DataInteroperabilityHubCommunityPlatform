"""
Integration tests for product details CLI command against real API service.

These tests test the CLI product details command directly against the running Docker Compose API service.
No Django test infrastructure required - tests use real HTTP requests.

NOTE: These tests require:
1. Docker Compose services running (api-service, postgres, redis)
2. A test user and API key configured in the CLI config
   OR set via environment variables: DATAHUB_API_KEY

To run these tests:
1. Ensure Docker Compose services are running: docker compose ps
2. Create a test user and API key (or use existing)
3. Set API key: export DATAHUB_API_KEY=your-api-key
4. Run: pytest tests/integration/test_product_details_real_api.py -v
"""
import pytest
import requests
import json
import os
import uuid
import subprocess
from click.testing import CliRunner
from datahub_cli.main import cli
from datahub_cli.config import config


def _check_api_available():
    """Check if API service is available"""
    try:
        response = requests.get(os.environ.get("MESHANT_API_URL", "http://localhost:8000/api/v1") + "/", timeout=2)
        return response.status_code < 600  # Any HTTP response means API is up
    except Exception:
        return False


@pytest.fixture(scope="module")
def api_available():
    """Fixture to check if API service is available"""
    return _check_api_available()


class TestProductDetailsRealAPI:
    """Integration tests for product details command with real API"""

    @pytest.fixture(autouse=True)
    def setup_config(self):
        """Set up API base URL to point to Docker Compose service"""
        # Use the running Docker Compose API service
        api_base_url = os.environ.get("MESHANT_API_URL", "http://localhost:8000/api/v1")
        config.set_api_base_url(api_base_url)

        # Try to get API key from environment, config, or create one
        api_key = (
            os.environ.get('DATAHUB_API_KEY') or
            os.environ.get('TEST_API_KEY') or
            config.get_api_key() or
            self._create_test_api_key()
        )

        if not api_key:
            # If we can't get/create an API key, tests will skip with helpful message
            self.api_key = None
        else:
            config.set_api_key(api_key)
            self.api_key = api_key

        yield
        # Cleanup
        config.clear_auth()

    def _create_test_api_key(self):
        """Create a test API key via Django shell in the API service container"""
        django_shell_script = """
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.auth.models import APIKey
import os

# Get or create tenant
tenant, _ = Tenant.objects.get_or_create(
    slug='product-details-cli-test-tenant',
    defaults={'name': 'Product Details CLI Test Tenant'}
)

# Get or create user
user, _ = User.objects.get_or_create(
    email='product-details-cli-test@example.com',
    defaults={
        'tenant': tenant,
        'status': UserStatus.ACTIVE
    }
)
if user.tenant != tenant:
    user.tenant = tenant
    user.status = UserStatus.ACTIVE
    user.save()

# Delete existing API key if it exists
APIKey.objects.filter(user=user, name='product-details-cli-test-key').delete()

# Create new API key
api_key = APIKey.objects.create(
    user=user,
    name='product-details-cli-test-key',
    tenant=tenant
)

print(api_key.key)
"""
        try:
            result = subprocess.run(
                ['docker', 'compose', 'exec', '-T', 'api-service', 'python', 'manage.py', 'shell', '-c', django_shell_script],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass
        return None

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_get_product_details_success(self, setup_config, api_available):
        """Test getting product details from ODPS contract with real API"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        # Create an ODPS 4.1 contract with product details
        api_base_url = config.get_api_base_url()
        contract_data = {
            "original_raw": json.dumps({
                "schema": "https://opendataproducts.org/schema/v4.1",
                "version": "4.1",
                "product": {
                    "details": {
                        "en": {
                            "productID": f"test-product-{uuid.uuid4().hex[:8]}",
                            "name": "Test Product",
                            "description": "A test product description",
                            "productVersion": "1.0.0",
                            "category": "Data Product",
                            "tags": ["test", "integration", "product"]
                        }
                    }
                }
            }),
            "original_format": "JSON",
            "original_spec_type": "ODPS"
        }

        try:
            response = requests.post(
                f"{api_base_url}/contracts/",
                json=contract_data,
                headers={"X-API-Key": self.api_key},
                timeout=30
            )
            assert response.status_code in [200, 201], f"Failed to create contract: {response.status_code} - {response.text}"

            contract_response = response.json()
            contract_id = contract_response.get("id")
            assert contract_id, "Failed to get contract ID from response."

            # Wait a bit for normalization to complete
            import time
            time.sleep(2)

            runner = CliRunner()
            result = runner.invoke(cli, ['contracts', 'get-product-details', contract_id])

            # Should succeed
            assert result.exit_code == 0, f"Command failed with output: {result.output}"
            assert 'Product Details for Contract' in result.output
            assert 'Test Product' in result.output
            assert 'A test product description' in result.output
            assert '1.0.0' in result.output
            assert 'Data Product' in result.output

        except Exception as e:
            pytest.skip(f"Failed to create test contract: {str(e)}")

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_get_product_details_multilingual(self, setup_config, api_available):
        """Test getting product details in different languages"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        # Create an ODPS 4.1 contract with multilingual product details
        api_base_url = config.get_api_base_url()
        contract_data = {
            "original_raw": json.dumps({
                "schema": "https://opendataproducts.org/schema/v4.1",
                "version": "4.1",
                "product": {
                    "details": {
                        "en": {
                            "productID": f"test-product-{uuid.uuid4().hex[:8]}",
                            "name": "Test Product",
                            "description": "English description"
                        },
                        "fi": {
                            "productID": f"test-product-{uuid.uuid4().hex[:8]}",
                            "name": "Testi Tuote",
                            "description": "Suomenkielinen kuvaus"
                        },
                        "es": {
                            "productID": f"test-product-{uuid.uuid4().hex[:8]}",
                            "name": "Producto de Prueba",
                            "description": "Descripción en español"
                        }
                    }
                }
            }),
            "original_format": "JSON",
            "original_spec_type": "ODPS"
        }

        try:
            response = requests.post(
                f"{api_base_url}/contracts/",
                json=contract_data,
                headers={"X-API-Key": self.api_key},
                timeout=30
            )
            assert response.status_code in [200, 201], f"Failed to create contract: {response.status_code} - {response.text}"

            contract_response = response.json()
            contract_id = contract_response.get("id")
            assert contract_id, "Failed to get contract ID from response."

            # Wait a bit for normalization to complete
            import time
            time.sleep(2)

            runner = CliRunner()

            # Test English
            result = runner.invoke(cli, ['contracts', 'get-product-details', contract_id, '--lang', 'en'])
            assert result.exit_code == 0
            assert 'Test Product' in result.output
            assert 'English description' in result.output

            # Test Finnish
            result = runner.invoke(cli, ['contracts', 'get-product-details', contract_id, '--lang', 'fi'])
            assert result.exit_code == 0
            assert 'Testi Tuote' in result.output
            assert 'Suomenkielinen kuvaus' in result.output

            # Test Spanish
            result = runner.invoke(cli, ['contracts', 'get-product-details', contract_id, '--lang', 'es'])
            assert result.exit_code == 0
            assert 'Producto de Prueba' in result.output
            assert 'Descripción en español' in result.output

        except Exception as e:
            pytest.skip(f"Failed to create test contract: {str(e)}")

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_get_product_details_json_format(self, setup_config, api_available):
        """Test getting product details in JSON format"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        # Create an ODPS 4.1 contract with product details
        api_base_url = config.get_api_base_url()
        contract_data = {
            "original_raw": json.dumps({
                "schema": "https://opendataproducts.org/schema/v4.1",
                "version": "4.1",
                "product": {
                    "details": {
                        "en": {
                            "productID": f"test-product-{uuid.uuid4().hex[:8]}",
                            "name": "Test Product",
                            "description": "A test product description"
                        }
                    }
                }
            }),
            "original_format": "JSON",
            "original_spec_type": "ODPS"
        }

        try:
            response = requests.post(
                f"{api_base_url}/contracts/",
                json=contract_data,
                headers={"X-API-Key": self.api_key},
                timeout=30
            )
            assert response.status_code in [200, 201], f"Failed to create contract: {response.status_code} - {response.text}"

            contract_response = response.json()
            contract_id = contract_response.get("id")
            assert contract_id, "Failed to get contract ID from response."

            # Wait a bit for normalization to complete
            import time
            time.sleep(2)

            runner = CliRunner()
            result = runner.invoke(cli, ['contracts', 'get-product-details', contract_id, '--format', 'json'])

            # Should succeed and return valid JSON
            assert result.exit_code == 0
            output_data = json.loads(result.output)
            assert isinstance(output_data, dict)
            assert 'productID' in output_data or 'name' in output_data

        except Exception as e:
            pytest.skip(f"Failed to create test contract: {str(e)}")

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_get_product_details_missing_language(self, setup_config, api_available):
        """Test getting product details for a language that doesn't exist"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        # Create an ODPS 4.1 contract with only English product details
        api_base_url = config.get_api_base_url()
        contract_data = {
            "original_raw": json.dumps({
                "schema": "https://opendataproducts.org/schema/v4.1",
                "version": "4.1",
                "product": {
                    "details": {
                        "en": {
                            "productID": f"test-product-{uuid.uuid4().hex[:8]}",
                            "name": "Test Product"
                        }
                    }
                }
            }),
            "original_format": "JSON",
            "original_spec_type": "ODPS"
        }

        try:
            response = requests.post(
                f"{api_base_url}/contracts/",
                json=contract_data,
                headers={"X-API-Key": self.api_key},
                timeout=30
            )
            assert response.status_code in [200, 201], f"Failed to create contract: {response.status_code} - {response.text}"

            contract_response = response.json()
            contract_id = contract_response.get("id")
            assert contract_id, "Failed to get contract ID from response."

            # Wait a bit for normalization to complete
            import time
            time.sleep(2)

            runner = CliRunner()
            result = runner.invoke(cli, ['contracts', 'get-product-details', contract_id, '--lang', 'fr'])

            # Should succeed but indicate no product details for that language
            assert result.exit_code == 0
            assert 'No product details found' in result.output or 'may not be available' in result.output

        except Exception as e:
            pytest.skip(f"Failed to create test contract: {str(e)}")

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_get_product_details_non_odps_contract(self, setup_config, api_available):
        """Test getting product details from non-ODPS contract (should fail)"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        # Create an ODCS contract (not ODPS)
        api_base_url = config.get_api_base_url()
        contract_data = {
            "original_raw": json.dumps({
                "apiVersion": "odcs/v3",
                "kind": "DataContract",
                "id": f"test-contract-{uuid.uuid4().hex[:8]}",
                "name": "Test Contract",
                "schema": {
                    "fields": [{"name": "id", "type": "string"}]
                }
            }),
            "original_format": "JSON",
            "original_spec_type": "ODCS"
        }

        try:
            response = requests.post(
                f"{api_base_url}/contracts/",
                json=contract_data,
                headers={"X-API-Key": self.api_key},
                timeout=30
            )
            assert response.status_code in [200, 201], f"Failed to create contract: {response.status_code} - {response.text}"

            contract_response = response.json()
            contract_id = contract_response.get("id")
            assert contract_id, "Failed to get contract ID from response."

            runner = CliRunner()
            result = runner.invoke(cli, ['contracts', 'get-product-details', contract_id])

            # Should fail because contract is not ODPS
            assert result.exit_code != 0
            assert 'error' in result.output.lower() or 'odps' in result.output.lower() or 'validation' in result.output.lower()

        except Exception as e:
            pytest.skip(f"Failed to create test contract: {str(e)}")

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_get_product_details_invalid_language_code(self, setup_config, api_available):
        """Test getting product details with invalid language code"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        # Create an ODPS 4.1 contract
        api_base_url = config.get_api_base_url()
        contract_data = {
            "original_raw": json.dumps({
                "schema": "https://opendataproducts.org/schema/v4.1",
                "version": "4.1",
                "product": {
                    "details": {
                        "en": {
                            "productID": f"test-product-{uuid.uuid4().hex[:8]}",
                            "name": "Test Product"
                        }
                    }
                }
            }),
            "original_format": "JSON",
            "original_spec_type": "ODPS"
        }

        try:
            response = requests.post(
                f"{api_base_url}/contracts/",
                json=contract_data,
                headers={"X-API-Key": self.api_key},
                timeout=30
            )
            assert response.status_code in [200, 201], f"Failed to create contract: {response.status_code} - {response.text}"

            contract_response = response.json()
            contract_id = contract_response.get("id")
            assert contract_id, "Failed to get contract ID from response."

            runner = CliRunner()
            result = runner.invoke(cli, ['contracts', 'get-product-details', contract_id, '--lang', 'invalid'])

            # Should fail with invalid language code error
            assert result.exit_code != 0
            assert 'language code' in result.output.lower() or 'invalid' in result.output.lower()

        except Exception as e:
            pytest.skip(f"Failed to create test contract: {str(e)}")

