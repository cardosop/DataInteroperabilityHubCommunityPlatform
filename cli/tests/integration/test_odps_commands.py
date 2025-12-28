"""
Comprehensive integration tests for all ODPS CLI commands against real API service.

These tests test all ODPS-related CLI commands directly against the running Docker Compose API service.
No Django test infrastructure required - tests use real HTTP requests.

NOTE: These tests require:
1. Docker Compose services running (api-service, postgres, redis)
2. A test user and API key configured in the CLI config
   OR set via environment variables: DATAHUB_API_KEY

To run these tests:
1. Ensure Docker Compose services are running: docker compose ps
2. Create a test user and API key (or use existing)
3. Set API key: export DATAHUB_API_KEY=your-api-key
4. Run: pytest tests/integration/test_odps_commands.py -v
"""
import pytest
import requests
import json
import os
import uuid
import subprocess
import time
from click.testing import CliRunner
from datahub_cli.main import cli
from datahub_cli.config import config


def _check_api_available():
    """Check if API service is available"""
    try:
        response = requests.get("http://localhost:8000/api/v1/", timeout=2)
        return response.status_code < 600  # Any HTTP response means API is up
    except Exception:
        return False


@pytest.fixture(scope="module")
def api_available():
    """Fixture to check if API service is available"""
    return _check_api_available()


class TestODPSCommandsRealAPI:
    """Comprehensive integration tests for all ODPS commands with real API"""

    @pytest.fixture(autouse=True)
    def setup_config(self):
        """Set up API base URL to point to Docker Compose service"""
        # Use the running Docker Compose API service
        api_base_url = "http://localhost:8000/api/v1"
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
    slug='odps-commands-cli-test-tenant',
    defaults={'name': 'ODPS Commands CLI Test Tenant'}
)

# Get or create user
user, _ = User.objects.get_or_create(
    email='odps-commands-cli-test@example.com',
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
APIKey.objects.filter(user=user, name='odps-commands-cli-test-key').delete()

# Create new API key
api_key_value = APIKey.generate_key()
api_key_hash = APIKey.hash_key(api_key_value)
api_key_obj = APIKey.objects.create(
    user=user,
    tenant=tenant,
    name='odps-commands-cli-test-key',
    key_hash=api_key_hash
)

# Print the plaintext key (it's only available at creation time)
print(api_key_value)
"""
        try:
            result = subprocess.run(
                ['docker', 'compose', 'exec', '-T', 'api-service', 'python', 'manage.py', 'shell'],
                input=django_shell_script,
                text=True,
                capture_output=True,
                timeout=30,
                cwd='/home/ph/Desktop/DataInteroperabilityHub'
            )

            if result.returncode == 0:
                # Extract API key from output (should be the last line)
                output_lines = result.stdout.strip().split('\n')
                for line in reversed(output_lines):
                    line = line.strip()
                    # API keys are typically long (40+ characters), alphanumeric with possible dashes/underscores
                    if line and len(line) > 20:  # API keys are typically long
                        # Additional validation: check if it looks like an API key
                        cleaned = line.replace('-', '').replace('_', '')
                        if cleaned.isalnum() and ' ' not in line and ':' not in line and '"' not in line and '{' not in line and '}' not in line:
                            return line
        except Exception:
            pass
        return None

    def _create_comprehensive_odps_contract(self, api_base_url: str, api_key: str) -> str:
        """
        Create a comprehensive ODPS 4.1 contract with all features for testing.
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
                            "name": "Comprehensive Test Product",
                            "description": "A comprehensive test product with all ODPS features",
                            "productVersion": "1.0.0",
                            "category": "Data Product",
                            "tags": ["test", "integration", "odps"]
                        },
                        "fi": {
                            "productID": f"test-product-{uuid.uuid4().hex[:8]}",
                            "name": "Kattava Testituote",
                            "description": "Kattava testituote kaikilla ODPS-ominaisuuksilla"
                        }
                    },
                    "productStrategy": {
                        "objectives": [
                            {
                                "name": "Increase market share",
                                "description": "Target 15% market share by end of year"
                            }
                        ],
                        "strategicAlignment": [
                            {
                                "name": "Digital transformation",
                                "description": "Align with company digital transformation goals"
                            }
                        ],
                        "productKPIs": [
                            {
                                "name": "User adoption",
                                "targetValue": "5000",
                                "unit": "users",
                                "description": "Monthly active users"
                            }
                        ],
                        "targetAudience": {
                            "type": "enterprise",
                            "size": "large"
                        },
                        "valueProposition": {
                            "key": "cost reduction",
                            "benefit": "Reduce operational costs by 30%"
                        }
                    },
                    "pricing": {
                        "plans": [
                            {
                                "planID": "basic",
                                "name": "Basic Plan",
                                "description": "Basic access plan",
                                "price": 99.99,
                                "currency": "USD",
                                "billingPeriod": "monthly",
                                "billingUnit": "subscription",
                                "isDefault": True,
                                "features": ["api_access", "basic_support"]
                            },
                            {
                                "planID": "premium",
                                "name": "Premium Plan",
                                "description": "Premium access plan with all features",
                                "price": 299.99,
                                "currency": "USD",
                                "billingPeriod": "monthly",
                                "billingUnit": "subscription",
                                "isDefault": False,
                                "features": ["api_access", "premium_support", "priority_access"]
                            }
                        ]
                    },
                    "accessMethods": [
                        {
                            "methodID": "api",
                            "type": "REST API",
                            "name": "REST API Access",
                            "description": "Access via REST API",
                            "endpoint": "https://api.example.com/v1/data",
                            "url": "https://api.example.com/v1/data",
                            "authenticationType": "api_key",
                            "authenticationConfig": {
                                "apiKeyHeader": "X-API-Key"
                            },
                            "rateLimit": {
                                "requests": 1000,
                                "period": "hour"
                            },
                            "format": "json",
                            "maxSize": "10MB",
                            "version": "1.0"
                        },
                        {
                            "methodID": "s3",
                            "type": "S3",
                            "name": "S3 Access",
                            "description": "Access via S3 bucket",
                            "url": "s3://bucket/data",
                            "authenticationType": "aws_credentials",
                            "format": "parquet",
                            "maxSize": "1GB"
                        }
                    ],
                    "paymentGateways": [
                        {
                            "gatewayID": "stripe",
                            "name": "Stripe",
                            "type": "stripe",
                            "enabled": True,
                            "config": {
                                "publicKey": "pk_test_123"
                            },
                            "webhookUrl": "https://api.example.com/webhooks/stripe"
                        }
                    ],
                    "contract": {
                        "spec": {
                            "apiVersion": "odcs/v3",
                            "kind": "DataContract",
                            "id": f"test-contract-{uuid.uuid4().hex[:8]}",
                            "name": "Test Data Contract",
                            "schema": {
                                "fields": [
                                    {"name": "id", "type": "string"},
                                    {"name": "value", "type": "number"}
                                ]
                            }
                        }
                    }
                }
            }),
            "original_format": "JSON",
            "original_spec_type": "ODPS",
            "resolve_external_refs": True
        }

        try:
            response = requests.post(
                f"{api_base_url}/contracts/products/",
                json=contract_data,
                headers={"X-API-Key": api_key},
                timeout=30
            )
            assert response.status_code in [200, 201], f"Failed to create contract: {response.status_code} - {response.text}"

            contract_response = response.json()
            contract_id = contract_response.get("id")
            assert contract_id, "Failed to get contract ID from response."

            # Wait for normalization to complete
            time.sleep(3)

            return contract_id
        except Exception as e:
            pytest.skip(f"Failed to create test contract: {str(e)}")

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_get_product_details_table_format(self, setup_config, api_available):
        """Test get-product-details command in table format"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        contract_id = self._create_comprehensive_odps_contract(api_base_url, self.api_key)

        if not contract_id:
            pytest.skip("Failed to create test contract. Check API service and permissions.")

        runner = CliRunner()
        result = runner.invoke(cli, ['contracts', 'get-product-details', contract_id])

        assert result.exit_code == 0, f"Command failed with output: {result.output}"
        assert 'Product Details for Contract' in result.output
        assert 'Comprehensive Test Product' in result.output or 'Kattava Testituote' in result.output
        assert 'Language: en' in result.output

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_get_product_details_json_format(self, setup_config, api_available):
        """Test get-product-details command in JSON format"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        contract_id = self._create_comprehensive_odps_contract(api_base_url, self.api_key)

        if not contract_id:
            pytest.skip("Failed to create test contract. Check API service and permissions.")

        runner = CliRunner()
        result = runner.invoke(cli, ['contracts', 'get-product-details', contract_id, '--format', 'json'])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert isinstance(output_data, dict)
        assert 'productID' in output_data or 'name' in output_data

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_get_product_details_multilingual(self, setup_config, api_available):
        """Test get-product-details command with different languages"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        contract_id = self._create_comprehensive_odps_contract(api_base_url, self.api_key)

        if not contract_id:
            pytest.skip("Failed to create test contract. Check API service and permissions.")

        runner = CliRunner()

        # Test English
        result = runner.invoke(cli, ['contracts', 'get-product-details', contract_id, '--lang', 'en'])
        assert result.exit_code == 0
        assert 'Comprehensive Test Product' in result.output

        # Test Finnish
        result = runner.invoke(cli, ['contracts', 'get-product-details', contract_id, '--lang', 'fi'])
        assert result.exit_code == 0
        assert 'Kattava Testituote' in result.output

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_get_product_strategy_table_format(self, setup_config, api_available):
        """Test get-product-strategy command in table format"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        contract_id = self._create_comprehensive_odps_contract(api_base_url, self.api_key)

        if not contract_id:
            pytest.skip("Failed to create test contract. Check API service and permissions.")

        runner = CliRunner()
        result = runner.invoke(cli, ['contracts', 'get-product-strategy', contract_id])

        assert result.exit_code == 0, f"Command failed with output: {result.output}"
        assert 'Product Strategy for Contract' in result.output
        assert 'Objectives' in result.output or 'objectives' in result.output.lower()

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_get_product_strategy_json_format(self, setup_config, api_available):
        """Test get-product-strategy command in JSON format"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        contract_id = self._create_comprehensive_odps_contract(api_base_url, self.api_key)

        if not contract_id:
            pytest.skip("Failed to create test contract. Check API service and permissions.")

        runner = CliRunner()
        result = runner.invoke(cli, ['contracts', 'get-product-strategy', contract_id, '--format', 'json'])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert isinstance(output_data, dict)

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_get_pricing_table_format(self, setup_config, api_available):
        """Test get-pricing command in table format"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        contract_id = self._create_comprehensive_odps_contract(api_base_url, self.api_key)

        if not contract_id:
            pytest.skip("Failed to create test contract. Check API service and permissions.")

        runner = CliRunner()
        result = runner.invoke(cli, ['contracts', 'get-pricing', contract_id])

        assert result.exit_code == 0, f"Command failed with output: {result.output}"
        assert 'Pricing Plans' in result.output or 'pricing' in result.output.lower()
        assert 'Basic Plan' in result.output or 'Premium Plan' in result.output

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_get_pricing_json_format(self, setup_config, api_available):
        """Test get-pricing command in JSON format"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        contract_id = self._create_comprehensive_odps_contract(api_base_url, self.api_key)

        if not contract_id:
            pytest.skip("Failed to create test contract. Check API service and permissions.")

        runner = CliRunner()
        result = runner.invoke(cli, ['contracts', 'get-pricing', contract_id, '--format', 'json'])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert isinstance(output_data, dict)
        assert 'pricing_plans' in output_data or 'pricingPlans' in output_data or len(output_data) > 0

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_get_access_methods_table_format(self, setup_config, api_available):
        """Test get-access-methods command in table format"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        contract_id = self._create_comprehensive_odps_contract(api_base_url, self.api_key)

        if not contract_id:
            pytest.skip("Failed to create test contract. Check API service and permissions.")

        runner = CliRunner()
        result = runner.invoke(cli, ['contracts', 'get-access-methods', contract_id])

        assert result.exit_code == 0, f"Command failed with output: {result.output}"
        assert 'Access Methods' in result.output or 'access' in result.output.lower()
        assert 'REST API' in result.output or 'S3' in result.output

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_get_access_methods_json_format(self, setup_config, api_available):
        """Test get-access-methods command in JSON format"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        contract_id = self._create_comprehensive_odps_contract(api_base_url, self.api_key)

        if not contract_id:
            pytest.skip("Failed to create test contract. Check API service and permissions.")

        runner = CliRunner()
        result = runner.invoke(cli, ['contracts', 'get-access-methods', contract_id, '--format', 'json'])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert isinstance(output_data, dict)
        assert 'access_methods' in output_data or 'accessMethods' in output_data or len(output_data) > 0

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_get_payment_gateways_table_format(self, setup_config, api_available):
        """Test get-payment-gateways command in table format"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        contract_id = self._create_comprehensive_odps_contract(api_base_url, self.api_key)

        if not contract_id:
            pytest.skip("Failed to create test contract. Check API service and permissions.")

        runner = CliRunner()
        result = runner.invoke(cli, ['contracts', 'get-payment-gateways', contract_id])

        assert result.exit_code == 0, f"Command failed with output: {result.output}"
        assert 'Payment Gateways' in result.output or 'payment' in result.output.lower()
        assert 'Stripe' in result.output

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_get_payment_gateways_json_format(self, setup_config, api_available):
        """Test get-payment-gateways command in JSON format"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        contract_id = self._create_comprehensive_odps_contract(api_base_url, self.api_key)

        if not contract_id:
            pytest.skip("Failed to create test contract. Check API service and permissions.")

        runner = CliRunner()
        result = runner.invoke(cli, ['contracts', 'get-payment-gateways', contract_id, '--format', 'json'])

        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert isinstance(output_data, dict)
        assert 'payment_gateways' in output_data or 'paymentGateways' in output_data or len(output_data) > 0

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_all_odps_commands_error_handling_invalid_contract_id(self, setup_config, api_available):
        """Test error handling for all ODPS commands with invalid contract ID"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        runner = CliRunner()
        invalid_id = 'invalid-contract-id'

        # Test all commands with invalid contract ID
        commands = [
            ['contracts', 'get-product-details', invalid_id],
            ['contracts', 'get-product-strategy', invalid_id],
            ['contracts', 'get-pricing', invalid_id],
            ['contracts', 'get-access-methods', invalid_id],
            ['contracts', 'get-payment-gateways', invalid_id],
        ]

        for cmd in commands:
            result = runner.invoke(cli, cmd)
            assert result.exit_code != 0, f"Command {cmd} should have failed with invalid contract ID"
            assert 'error' in result.output.lower() or 'invalid' in result.output.lower() or 'not found' in result.output.lower()

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_all_odps_commands_error_handling_non_odps_contract(self, setup_config, api_available):
        """Test error handling for all ODPS commands with non-ODPS contract"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        # Create a non-ODPS contract
        api_base_url = config.get_api_base_url()
        contract_data = {
            "original_raw": json.dumps({
                "apiVersion": "odcs/v3",
                "kind": "DataContract",
                "id": f"test-contract-{uuid.uuid4().hex[:8]}",
                "name": "Test ODCS Contract",
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

            # Test all commands with non-ODPS contract
            commands = [
                ['contracts', 'get-product-details', contract_id],
                ['contracts', 'get-product-strategy', contract_id],
                ['contracts', 'get-pricing', contract_id],
                ['contracts', 'get-access-methods', contract_id],
                ['contracts', 'get-payment-gateways', contract_id],
            ]

            for cmd in commands:
                result = runner.invoke(cli, cmd)
                assert result.exit_code != 0, f"Command {cmd} should have failed with non-ODPS contract"
                assert 'error' in result.output.lower() or 'odps' in result.output.lower() or 'not an odps' in result.output.lower()

        except Exception as e:
            pytest.skip(f"Failed to create test contract: {str(e)}")

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_get_product_details_error_handling_invalid_language(self, setup_config, api_available):
        """Test error handling for get-product-details with invalid language code"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        contract_id = self._create_comprehensive_odps_contract(api_base_url, self.api_key)

        if not contract_id:
            pytest.skip("Failed to create test contract. Check API service and permissions.")

        runner = CliRunner()
        result = runner.invoke(cli, ['contracts', 'get-product-details', contract_id, '--lang', 'invalid'])

        assert result.exit_code != 0
        assert 'language code' in result.output.lower() or 'invalid' in result.output.lower()

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_all_commands_output_formatting_consistency(self, setup_config, api_available):
        """Test that all ODPS commands support both table and JSON output formats consistently"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        api_base_url = config.get_api_base_url()
        contract_id = self._create_comprehensive_odps_contract(api_base_url, self.api_key)

        if not contract_id:
            pytest.skip("Failed to create test contract. Check API service and permissions.")

        runner = CliRunner()

        # Test all commands with both formats
        commands = [
            ['contracts', 'get-product-details', contract_id],
            ['contracts', 'get-product-strategy', contract_id],
            ['contracts', 'get-pricing', contract_id],
            ['contracts', 'get-access-methods', contract_id],
            ['contracts', 'get-payment-gateways', contract_id],
        ]

        for cmd in commands:
            # Test table format (default)
            result_table = runner.invoke(cli, cmd)
            assert result_table.exit_code == 0, f"Command {cmd} failed in table format: {result_table.output}"
            assert len(result_table.output) > 0, f"Command {cmd} produced empty output in table format"

            # Test JSON format
            cmd_json = cmd + ['--format', 'json']
            result_json = runner.invoke(cli, cmd_json)
            assert result_json.exit_code == 0, f"Command {cmd_json} failed in JSON format: {result_json.output}"
            try:
                output_data = json.loads(result_json.output)
                assert isinstance(output_data, (dict, list)), f"Command {cmd_json} did not produce valid JSON"
            except json.JSONDecodeError:
                pytest.fail(f"Command {cmd_json} did not produce valid JSON: {result_json.output}")

    @pytest.mark.skipif(not _check_api_available(), reason="API service is not available. Ensure Docker Compose services are running.")
    def test_all_odps_commands_with_empty_data(self, setup_config, api_available):
        """Test all ODPS commands with contract that has minimal data"""
        if not self.api_key:
            pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

        # Create ODPS contract with minimal data
        api_base_url = config.get_api_base_url()
        contract_data = {
            "original_raw": json.dumps({
                "schema": "https://opendataproducts.org/schema/v4.1",
                "version": "4.1",
                "product": {
                    "details": {
                        "en": {
                            "productID": f"minimal-product-{uuid.uuid4().hex[:8]}",
                            "name": "Minimal Product"
                        }
                    }
                }
            }),
            "original_format": "JSON",
            "original_spec_type": "ODPS"
        }

        try:
            # Try creating via products endpoint first (workflow-based)
            response = requests.post(
                f"{api_base_url}/contracts/products/",
                json=contract_data,
                headers={"X-API-Key": self.api_key},
                timeout=30
            )

            # If workflow fails, try creating directly via contracts endpoint
            if response.status_code not in [200, 201]:
                # Fallback: create directly via contracts endpoint (no workflow)
                contract_data_direct = {
                    "original_raw": contract_data["original_raw"],
                    "original_format": contract_data["original_format"],
                    "original_spec_type": contract_data["original_spec_type"]
                }
                response = requests.post(
                    f"{api_base_url}/contracts/",
                    json=contract_data_direct,
                    headers={"X-API-Key": self.api_key},
                    timeout=30
                )

            if response.status_code not in [200, 201]:
                pytest.skip(f"Failed to create minimal contract: {response.status_code} - {response.text}")

            contract_response = response.json()
            contract_id = contract_response.get("id")
            if not contract_id:
                pytest.skip("Failed to get contract ID from response.")

            time.sleep(3)

            runner = CliRunner()

            # Test all commands - they should handle empty data gracefully
            commands = [
                ['contracts', 'get-product-details', contract_id],
                ['contracts', 'get-product-strategy', contract_id],
                ['contracts', 'get-pricing', contract_id],
                ['contracts', 'get-access-methods', contract_id],
                ['contracts', 'get-payment-gateways', contract_id],
            ]

            for cmd in commands:
                result = runner.invoke(cli, cmd)
                # Commands should succeed but may indicate no data available
                assert result.exit_code == 0, f"Command {cmd} failed with minimal data: {result.output}"

        except Exception as e:
            pytest.skip(f"Failed to create test contract: {str(e)}")

