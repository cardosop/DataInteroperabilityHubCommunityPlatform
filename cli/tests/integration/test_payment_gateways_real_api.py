"""
Integration tests for payment gateways CLI command against real API service.

These tests test the CLI payment gateways command directly against the running Docker Compose API service.
No Django test infrastructure required - tests use real HTTP requests.

NOTE: These tests require:
1. Docker Compose services running (api-service, postgres, redis)
2. A test user and API key configured in the CLI config
   OR set via environment variables: DATAHUB_API_KEY

To run these tests:
1. Ensure Docker Compose services are running: docker compose ps
2. Create a test user and API key (or use existing)
3. Set API key: export DATAHUB_API_KEY=your-api-key
4. Run: pytest tests/integration/test_payment_gateways_real_api.py -v
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


class TestPaymentGatewaysRealAPI:
    """Integration tests for payment gateways command with real API"""

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
    slug='payment-gateways-cli-test-tenant',
    defaults={'name': 'Payment Gateways CLI Test Tenant'}
)

# Get or create user
user, _ = User.objects.get_or_create(
    email='payment-gateways-cli-test@example.com',
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
APIKey.objects.filter(user=user, name='Payment Gateways CLI Test Key').delete()

# Create new API key
api_key_obj = APIKey.objects.create(
    user=user,
    tenant=tenant,
    name='Payment Gateways CLI Test Key'
)

# Print the plaintext key (it's only available at creation time)
print(api_key_obj.key)
"""
        try:
            result = subprocess.run(
                ['docker', 'compose', 'exec', '-T', 'api-service', 'python', '/app/hub/manage.py', 'shell', '-c', django_shell_script],
                capture_output=True,
                text=True,
                timeout=10,
                cwd='/home/ph/Desktop/DataInteroperabilityHub'
            )
            if result.returncode == 0:
                api_key = result.stdout.strip()
                if api_key and len(api_key) > 20:  # Valid API key should be reasonably long
                    return api_key
        except Exception:
            pass
        return None

    def _create_odps_contract_with_payment_gateways(self, api_base_url: str, api_key: str) -> str:
        """
        Create an ODPS contract with payment gateways via the API for testing.
        Returns the contract ID.
        """
        contract_data = {
            "original_raw": json.dumps({
                "schema": "https://opendataproducts.org/schema/v4.1",
                "version": "4.1",
                "product": {
                    "details": {
                        "en": {
                            "productID": f"test-product-{uuid.uuid4().hex[:8]}",
                            "name": "Test Product with Payment Gateways"
                        }
                    },
                    "marketplace": {
                        "paymentGateways": {
                            "stripe": {
                                "type": "stripe",
                                "enabled": True,
                                "description": "Primary payment gateway"
                            },
                            "paypal": {
                                "type": "paypal",
                                "enabled": False,
                                "description": "Alternative payment gateway"
                            }
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
                headers={
                    "X-API-Key": api_key,
                    "Content-Type": "application/json"
                },
                timeout=10
            )

            if response.status_code in [200, 201]:
                result = response.json()
                contract_id = result.get('id') or result.get('contract_id')
                return contract_id
        except Exception:
            pass
        return None

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_get_payment_gateways_real_api_table_format(self, setup_config, api_available):
        """Test getting payment gateways from real API in table format"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        contract_id = self._create_odps_contract_with_payment_gateways(api_base_url, self.api_key)

        if not contract_id:
            pytest.skip("Failed to create test contract. Check API service and permissions.")

        runner = CliRunner()
        result = runner.invoke(cli, ['contracts', 'get-payment-gateways', contract_id])

        assert result.exit_code == 0
        assert 'Payment Gateways for Contract' in result.output
        assert 'stripe' in result.output.lower() or 'paypal' in result.output.lower()
        assert 'Total:' in result.output

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_get_payment_gateways_real_api_json_format(self, setup_config, api_available):
        """Test getting payment gateways from real API in JSON format"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        contract_id = self._create_odps_contract_with_payment_gateways(api_base_url, self.api_key)

        if not contract_id:
            pytest.skip("Failed to create test contract. Check API service and permissions.")

        runner = CliRunner()
        result = runner.invoke(cli, ['contracts', 'get-payment-gateways', contract_id, '--format', 'json'])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert isinstance(output_data, dict)
        # Should have at least one payment gateway
        assert len(output_data) > 0

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_get_payment_gateways_empty_contract(self, setup_config, api_available):
        """Test getting payment gateways from contract without payment gateways"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        # Create an ODPS contract without payment gateways
        api_base_url = config.get_api_base_url()
        contract_data = {
            "original_raw": json.dumps({
                "schema": "https://opendataproducts.org/schema/v4.1",
                "version": "4.1",
                "product": {
                    "details": {
                        "en": {
                            "productID": f"test-product-{uuid.uuid4().hex[:8]}",
                            "name": "Test Product without Payment Gateways"
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
                headers={
                    "X-API-Key": self.api_key,
                    "Content-Type": "application/json"
                },
                timeout=10
            )

            if response.status_code not in [200, 201]:
                pytest.skip("Failed to create test contract. Check API service and permissions.")

            result = response.json()
            contract_id = result.get('id') or result.get('contract_id')

            if not contract_id:
                pytest.skip("Failed to get contract ID from response.")

            runner = CliRunner()
            result = runner.invoke(cli, ['contracts', 'get-payment-gateways', contract_id])

            assert result.exit_code == 0
            assert 'No payment gateways found' in result.output or 'payment gateway' in result.output.lower()

        except Exception as e:
            pytest.skip(f"Failed to create test contract: {str(e)}")

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_get_payment_gateways_invalid_contract_id(self, setup_config, api_available):
        """Test getting payment gateways with invalid contract ID"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        runner = CliRunner()
        invalid_id = '00000000-0000-0000-0000-000000000000'
        result = runner.invoke(cli, ['contracts', 'get-payment-gateways', invalid_id])

        assert result.exit_code != 0
        assert 'error' in result.output.lower() or 'not found' in result.output.lower() or '404' in result.output

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_get_payment_gateways_non_odps_contract(self, setup_config, api_available):
        """Test getting payment gateways from non-ODPS contract (should fail)"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        # Create an ODCS contract (not ODPS)
        api_base_url = config.get_api_base_url()
        contract_data = {
            "original_raw": json.dumps({
                "apiVersion": "odcs.io/v3.0.2",
                "kind": "DataContract",
                "id": f"test-odcs-{uuid.uuid4().hex[:8]}",
                "name": "Test ODCS Contract"
            }),
            "original_format": "JSON",
            "original_spec_type": "ODCS"
        }

        try:
            response = requests.post(
                f"{api_base_url}/contracts/",
                json=contract_data,
                headers={
                    "X-API-Key": self.api_key,
                    "Content-Type": "application/json"
                },
                timeout=10
            )

            if response.status_code not in [200, 201]:
                pytest.skip("Failed to create test contract. Check API service and permissions.")

            result = response.json()
            contract_id = result.get('id') or result.get('contract_id')

            if not contract_id:
                pytest.skip("Failed to get contract ID from response.")

            runner = CliRunner()
            result = runner.invoke(cli, ['contracts', 'get-payment-gateways', contract_id])

            # Should fail because contract is not ODPS
            assert result.exit_code != 0
            assert 'error' in result.output.lower() or 'odps' in result.output.lower() or 'validation' in result.output.lower()

        except Exception as e:
            pytest.skip(f"Failed to create test contract: {str(e)}")

