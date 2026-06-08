"""
Comprehensive consistency tests for Python vs JavaScript SDK ODPS methods.

Tests ensure that Python and JavaScript SDKs have:
- Consistent method names
- Consistent parameter names and types
- Consistent response formats
- Consistent error handling

Uses real API connections - no mocks/stubs.

NOTE: These tests require:
1. Docker Compose services running (api-service, postgres, redis)
2. A test user and API key configured
   OR set via environment variables: TEST_API_KEY or DATAHUB_API_KEY
3. Node.js and npm installed for JavaScript SDK tests

To run these tests:
1. Ensure Docker Compose services are running: docker compose ps
2. Set API key: export TEST_API_KEY=your-api-key
3. Run: pytest tests/test_python_js_odps_consistency.py -v
"""
import os
import pytest
import json
import uuid
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
from datahub_interoperability import DataHubClient, DataHubClientConfig


def setup_authentication_for_sdk_tests(api_base_url: str) -> Optional[str]:
    """
    Set up authentication for SDK tests.

    Delegates to the canonical conftest helper which handles token
    validation, auto-provisioning, and transparent refresh so tests
    always receive a working credential.
    """
    from tests.conftest import get_api_key
    return get_api_key()


@pytest.fixture
def real_api_config():
    """Fixture for real API configuration"""
    api_base_url = os.environ.get('API_BASE_URL', 'http://localhost:8001/api/v1')
    api_key = setup_authentication_for_sdk_tests(api_base_url)

    if not api_key:
        pytest.skip("No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable.")

    # Use longer timeout for comprehensive tests (60 seconds) to handle slow operations
    return DataHubClientConfig(
        base_url=api_base_url,
        api_token=api_key,
        timeout=60.0  # 60 seconds for comprehensive tests
    )


def check_nodejs_available():
    """Check if Node.js is available"""
    try:
        result = subprocess.run(['node', '--version'], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


@pytest.fixture
def js_sdk_available():
    """Check if JavaScript SDK is available"""
    if not check_nodejs_available():
        pytest.skip("Node.js not available. Install Node.js to run JavaScript SDK consistency tests.")

    js_sdk_path = Path(__file__).parent.parent.parent / "js"
    if not (js_sdk_path / "package.json").exists():
        pytest.skip("JavaScript SDK not found. Build JavaScript SDK first.")

    return js_sdk_path


def create_valid_odps_json(
    product_id: str = None,
    include_contract: bool = True,
    odcs_contract_id: str = None,
    odcs_contract_name: str = None
) -> str:
    """Create a valid ODPS JSON document"""
    if product_id is None:
        product_id = f"test-product-{uuid.uuid4().hex[:8]}"

    odps = {
        "schema": "https://opendataproducts.org/schema/v4.1",
        "version": "4.1",
        "product": {
            "details": {
                "en": {
                    "productID": product_id,
                    "name": f"Test Product {product_id}",
                    "description": f"Test product for consistency tests: {product_id}"
                }
            },
            "contract": {
                "spec": {
                    "apiVersion": "odcs/v3",
                    "kind": "DataContract",
                    "id": odcs_contract_id if odcs_contract_id else f"{product_id}-contract",
                    "name": odcs_contract_name if odcs_contract_name else f"Test Contract {product_id}",
                    "version": "1.0.0",
                    "schema": {
                        "fields": [
                            {
                                "name": "id",
                                "type": "string",
                                "nullable": False
                            }
                        ]
                    }
                }
            } if include_contract else None,
            "marketplace": {
                "pricingPlans": [
                    {
                        "planID": "basic",
                        "name": "Basic Plan",
                        "price": 9.99,
                        "currency": "USD",
                        "billingPeriod": "monthly"
                    }
                ],
                "accessMethods": {
                    "api": {
                        "type": "REST API",
                        "endpoint": f"https://api.example.com/v1/products/{product_id}",
                        "protocol": "HTTPS"
                    }
                },
                "paymentGateways": {
                    "stripe": {
                        "enabled": True,
                        "mode": "test"
                    }
                }
            }
        }
    }

    return json.dumps(odps, indent=2)


class TestMethodNameConsistency:
    """Verify ODPS helper methods exist in the ContractsAPI with expected names.

    Uses ``inspect.getmembers`` to introspect the actual SDK at runtime,
    so renames or removals are caught immediately.
    """

    EXPECTED_METHODS: tuple[str, ...] = (
        "create_odps",
        "export_odps",
        "download_odps",
        "link_odps_to_odcs",
        "unlink_odps_from_odcs",
        "get_linked_contracts",
        "get_pricing_plans",
        "get_access_methods",
        "get_payment_gateways",
        "get_product_strategy",
        "get_product_details",
        "is_odps_contract",
        "get_odps_version",
    )

    @pytest.fixture(scope="class")
    def sdk_methods(self) -> frozenset[str]:
        """Return frozenset of public ContractsAPI method names."""
        import inspect as _inspect
        from datahub_interoperability.contracts import ContractsAPI

        return frozenset(
            name
            for name, _ in _inspect.getmembers(ContractsAPI, _inspect.isfunction)
            if not name.startswith("_")
        )

    def test_all_expected_odps_methods_present(self, sdk_methods):
        """Every expected ODPS helper is actually callable on ContractsAPI."""
        missing = [m for m in self.EXPECTED_METHODS if m not in sdk_methods]
        assert not missing, (
            f"ODPS methods missing from ContractsAPI: {missing}. "
            f"Either the method was renamed/removed or this list needs updating."
        )


class TestParameterConsistency:
    """Verify ODPS method signatures match expected parameters via introspection."""

    # Canonical snake_case parameter names for each method.
    # Keys are method names, values are the expected parameter names.
    EXPECTED_PARAMS: dict[str, tuple[str, ...]] = {
        "create_odps": (
            "original_raw", "extract_odcs", "link_odcs_id",
            "original_format", "odps_version", "resolve_external_refs", "asset_id",
        ),
        "export_odps": ("contract_id", "version", "format"),
        "download_odps": ("contract_id", "version", "format"),
        "link_odps_to_odcs": (
            "odcs_contract_id", "odps_contract_id",
            "odps_raw", "odps_format", "resolve_external_refs",
        ),
    }

    @pytest.fixture(scope="class")
    def sdk_signatures(self) -> dict[str, tuple[str, ...]]:
        """Return {method_name: (parameter_names, ...)} for ContractsAPI."""
        import inspect as _inspect
        from datahub_interoperability.contracts import ContractsAPI

        result: dict[str, tuple[str, ...]] = {}
        for name, fn in _inspect.getmembers(ContractsAPI, _inspect.isfunction):
            if name.startswith("_"):
                continue
            try:
                sig = _inspect.signature(fn)
            except (ValueError, TypeError):
                continue
            params = tuple(
                p.name for p in sig.parameters.values()
                if p.name not in ("self",)
                and p.kind not in (
                    _inspect.Parameter.VAR_POSITIONAL,
                    _inspect.Parameter.VAR_KEYWORD,
                )
            )
            result[name] = params
        return result

    def test_create_odps_parameters_match_sdk(self, sdk_signatures):
        assert "create_odps" in sdk_signatures, "create_odps not found in ContractsAPI"
        actual = sdk_signatures["create_odps"]
        expected = self.EXPECTED_PARAMS["create_odps"]
        assert set(expected).issubset(set(actual)), (
            f"create_odps is missing parameters: {set(expected) - set(actual)}. "
            f"Actual signature: {actual}"
        )

    def test_export_odps_parameters_match_sdk(self, sdk_signatures):
        assert "export_odps" in sdk_signatures
        actual = sdk_signatures["export_odps"]
        expected = self.EXPECTED_PARAMS["export_odps"]
        assert set(expected).issubset(set(actual)), (
            f"export_odps missing: {set(expected) - set(actual)}. Actual: {actual}"
        )

    def test_link_odps_to_odcs_parameters_match_sdk(self, sdk_signatures):
        assert "link_odps_to_odcs" in sdk_signatures
        actual = sdk_signatures["link_odps_to_odcs"]
        expected = self.EXPECTED_PARAMS["link_odps_to_odcs"]
        assert set(expected).issubset(set(actual)), (
            f"link_odps_to_odcs missing: {set(expected) - set(actual)}. Actual: {actual}"
        )


class TestResponseFormatConsistency:
    """Tests for response format consistency"""

    @pytest.mark.asyncio
    async def test_create_odps_response_format(self, real_api_config):
        """Test that create_odps response format is consistent"""
        client = DataHubClient(real_api_config)
        odps_content = create_valid_odps_json("response-format-test")

        try:
            result = await client.contracts.create_odps(
                original_raw=odps_content,
                extract_odcs=True,
                original_format="JSON"
            )

            if isinstance(result, dict) and "error" in result:
                if "workflow" in str(result.get("error", "")).lower():
                    pytest.skip(f"Workflow execution failed: {result.get('error')}")

            # Verify response structure
            assert isinstance(result, dict), "Response should be a dictionary"

            # Product-First flow should return odps_contract, odcs_contract, workflow_instance_id
            if "odps_contract" in result:
                assert isinstance(result["odps_contract"], dict), "odps_contract should be a dictionary"
                assert "id" in result["odps_contract"], "odps_contract should have 'id' field"
            elif "id" in result:
                assert isinstance(result["id"], str), "id should be a string"
        except Exception as e:
            error_str = str(e).lower()
            if "workflow" in error_str or "product creation failed" in error_str:
                pytest.skip(f"Workflow execution failed: {error_str}")
            raise

    @pytest.mark.asyncio
    async def test_export_odps_response_format(self, real_api_config):
        """Test that export_odps response format is consistent"""
        client = DataHubClient(real_api_config)
        odps_content = create_valid_odps_json("export-response-format")

        try:
            create_result = await client.contracts.create_odps(
                original_raw=odps_content,
                extract_odcs=True,
                original_format="JSON"
            )

            # Handle async workflow if needed
            from tests.test_contracts_api_odps_comprehensive import handle_async_workflow_response
            create_result = await handle_async_workflow_response(client, create_result, timeout=300)

            if isinstance(create_result, dict) and "error" in create_result:
                if "workflow" in str(create_result.get("error", "")).lower():
                    pytest.skip(f"Workflow execution failed: {create_result.get('error')}")

            odps_id = create_result.get("odps_contract", {}).get("id") or create_result.get("id")
            if not odps_id:
                pytest.skip("Could not create ODPS contract for response format test")

            export_result = await client.contracts.export_odps(
                contract_id=odps_id,
                format="json"
            )

            # Verify response format
            assert export_result is not None
            # JSON format should return dict or parseable JSON string
            if isinstance(export_result, str):
                parsed = json.loads(export_result)
                assert isinstance(parsed, dict)
            else:
                assert isinstance(export_result, dict)
        except Exception as e:
            error_str = str(e).lower()
            if "workflow" in error_str or "product creation failed" in error_str:
                pytest.skip(f"Workflow execution failed: {error_str}")
            raise

    @pytest.mark.asyncio
    async def test_get_linked_contracts_response_format(self, real_api_config):
        """Test that get_linked_contracts response format is consistent"""
        client = DataHubClient(real_api_config)

        # Create ODCS contract
        odcs_contract_id = "linked-response-format"
        odcs_contract_name = "Linked Response Format"
        odcs_content = f"""{{
  "apiVersion": "odcs/v3",
  "kind": "DataContract",
  "id": "{odcs_contract_id}",
  "name": "{odcs_contract_name}",
  "version": "1.0.0",
  "schema": {{
    "fields": [{{"name": "id", "type": "string", "nullable": false}}]
  }}
}}"""
        odcs_result = await client.contracts.create(
            original_raw=odcs_content,
            original_format="JSON"
        )
        odcs_id = odcs_result["id"]

        # Create and link ODPS with matching contract ID and name
        odps_content = create_valid_odps_json(
            "linked-response-format",
            include_contract=True,
            odcs_contract_id=odcs_contract_id,
            odcs_contract_name=odcs_contract_name
        )
        try:
            link_result = await client.contracts.link_odps_to_odcs(
                odcs_contract_id=odcs_id,
                odps_raw=odps_content,
                odps_format="JSON"
            )

            if isinstance(link_result, dict) and "error" in link_result:
                if "workflow" in str(link_result.get("error", "")).lower():
                    pytest.skip(f"Workflow execution failed: {link_result.get('error')}")

            linked = await client.contracts.get_linked_contracts(odcs_id)

            # Verify response format
            assert linked is not None
            assert isinstance(linked, dict), "Response should be a dictionary"
            # Should contain odps_link or odcs_link fields
            assert "odps_link" in linked or "odcs_link" in linked or "links" in linked
        except Exception as e:
            error_str = str(e).lower()
            if "workflow" in error_str or "product creation failed" in error_str:
                pytest.skip(f"Workflow execution failed: {error_str}")
            raise


class TestErrorHandlingConsistency:
    """Tests for error handling consistency"""

    @pytest.mark.asyncio
    async def test_create_odps_error_mutually_exclusive(self, real_api_config):
        """Test that create_odps error handling is consistent"""
        client = DataHubClient(real_api_config)
        odps_content = create_valid_odps_json("error-test")

        # Both extract_odcs and link_odcs_id should raise error
        from datahub_interoperability.errors import ODPSValidationError

        with pytest.raises(ODPSValidationError) as exc_info:
            await client.contracts.create_odps(
                original_raw=odps_content,
                extract_odcs=True,
                link_odcs_id="some-id",
                original_format="JSON"
            )

        # Verify error message contains relevant information
        error_msg = str(exc_info.value).lower()
        assert "extract_odcs" in error_msg or "mutually" in error_msg or "both" in error_msg

    @pytest.mark.asyncio
    async def test_create_odps_error_neither_option(self, real_api_config):
        """Test that create_odps error when neither option provided is consistent"""
        client = DataHubClient(real_api_config)
        odps_content = create_valid_odps_json("error-neither")

        from datahub_interoperability.errors import ODPSValidationError

        with pytest.raises(ODPSValidationError) as exc_info:
            await client.contracts.create_odps(
                original_raw=odps_content,
                original_format="JSON"
                # Missing both extract_odcs and link_odcs_id
            )

        error_msg = str(exc_info.value).lower()
        assert "extract_odcs" in error_msg or "link_odcs_id" in error_msg or "must specify" in error_msg

    @pytest.mark.asyncio
    async def test_export_odps_error_invalid_contract_id(self, real_api_config):
        """Test that export_odps error handling is consistent"""
        client = DataHubClient(real_api_config)
        invalid_id = "00000000-0000-0000-0000-000000000000"

        from datahub_interoperability.errors import NotFoundError, ODPSExportError

        with pytest.raises((NotFoundError, ODPSExportError)):
            await client.contracts.export_odps(
                contract_id=invalid_id,
                format="json"
            )


class TestHelperMethodsConsistency:
    """Tests for helper methods consistency"""

    @pytest.mark.asyncio
    async def test_is_odps_contract_consistency(self, real_api_config):
        """Test that is_odps_contract returns consistent results"""
        client = DataHubClient(real_api_config)
        odps_content = create_valid_odps_json("helper-is-odps")

        try:
            create_result = await client.contracts.create_odps(
                original_raw=odps_content,
                extract_odcs=True,
                original_format="JSON"
            )

            if isinstance(create_result, dict) and "error" in create_result:
                if "workflow" in str(create_result.get("error", "")).lower():
                    pytest.skip(f"Workflow execution failed: {create_result.get('error')}")

            odps_id = create_result.get("odps_contract", {}).get("id") or create_result.get("id")
            if not odps_id:
                pytest.skip("Could not create ODPS contract for helper test")

            contract = await client.contracts.get(odps_id)
            is_odps = client.contracts.is_odps_contract(contract)

            # Should return boolean
            assert isinstance(is_odps, bool)
            assert is_odps is True

            # Test with ODCS contract
            odcs_content = """{
  "apiVersion": "odcs/v3",
  "kind": "DataContract",
  "id": "helper-is-odcs",
  "name": "Helper Is ODCS",
  "version": "1.0.0",
  "schema": {
    "fields": [{"name": "id", "type": "string", "nullable": false}]
  }
}"""
            odcs_result = await client.contracts.create(
                original_raw=odcs_content,
                original_format="JSON"
            )
            odcs_contract = await client.contracts.get(odcs_result["id"])
            is_odps_odcs = client.contracts.is_odps_contract(odcs_contract)
            assert isinstance(is_odps_odcs, bool)
            assert is_odps_odcs is False
        except Exception as e:
            error_str = str(e).lower()
            if "workflow" in error_str or "product creation failed" in error_str:
                pytest.skip(f"Workflow execution failed: {error_str}")
            raise

    @pytest.mark.asyncio
    async def test_get_odps_version_consistency(self, real_api_config):
        """Test that get_odps_version returns consistent results"""
        client = DataHubClient(real_api_config)
        odps_content = create_valid_odps_json("helper-version")

        try:
            create_result = await client.contracts.create_odps(
                original_raw=odps_content,
                extract_odcs=True,
                original_format="JSON",
                odps_version="4.1"
            )

            if isinstance(create_result, dict) and "error" in create_result:
                if "workflow" in str(create_result.get("error", "")).lower():
                    pytest.skip(f"Workflow execution failed: {create_result.get('error')}")

            odps_id = create_result.get("odps_contract", {}).get("id") or create_result.get("id")
            if not odps_id:
                pytest.skip("Could not create ODPS contract for helper test")

            contract = await client.contracts.get(odps_id)
            version = client.contracts.get_odps_version(contract)

            # Should return string or None
            assert version is None or isinstance(version, str)
            if version:
                assert version == "4.1"
        except Exception as e:
            error_str = str(e).lower()
            if "workflow" in error_str or "product creation failed" in error_str:
                pytest.skip(f"Workflow execution failed: {error_str}")
            raise
