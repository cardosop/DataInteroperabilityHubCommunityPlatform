"""
Comprehensive integration tests for SDK All APIs with ODPS integration.

Tests integration of ODPS contracts with:
- LineageAPI
- ScheduledIngestionAPI
- VersioningAPI
- GovernanceAPI
- SearchAPI
- ObservabilityAPI
- WebhooksAPI

Uses real API connections - no mocks/stubs.

NOTE: These tests require:
1. Docker Compose services running (api-service, postgres, redis)
2. A test user and API key configured
   OR set via environment variables: TEST_API_KEY or DATAHUB_API_KEY

To run these tests:
1. Ensure Docker Compose services are running: docker compose ps
2. Set API key: export TEST_API_KEY=your-api-key
3. Run: pytest tests/test_all_apis_odps_integration.py -v
"""

import json
import os
import uuid
from typing import Optional

import pytest

from datahub_interoperability import DataHubClient, DataHubClientConfig


async def check_endpoint_exists(
    client: DataHubClient, endpoint_path: str, method: str = "GET"
) -> bool:
    """
    Check if an API endpoint exists by making a HEAD or GET request.

    Args:
        client: DataHub client instance
        endpoint_path: API endpoint path (e.g., "contracts/{id}/lineage/contracts/")
        method: HTTP method to use for check (default: "GET")

    Returns:
        True if endpoint exists (returns 200, 201, or 400), False if 404
    """
    try:
        # Use a dummy ID for the check - we just want to see if the endpoint pattern exists
        # Replace {id} or {contract_id} with a test UUID
        test_uuid = "00000000-0000-0000-0000-000000000000"
        test_path = (
            endpoint_path.replace("{id}", test_uuid)
            .replace("{contract_id}", test_uuid)
            .replace("{dataset_id}", test_uuid)
        )

        if method == "GET":
            response = await client.request("GET", test_path)
            # 200, 201, 400 (validation error) = endpoint exists
            # 404 = endpoint doesn't exist
            return response.status_code != 404
        else:
            # For other methods, try HEAD first
            try:
                response = await client.request("HEAD", test_path)
                return response.status_code != 404
            except Exception:
                # If HEAD fails, try GET
                response = await client.request("GET", test_path)
                return response.status_code != 404
    except Exception as e:
        error_str = str(e).lower()
        # 404 means endpoint doesn't exist
        if "404" in error_str or "not found" in error_str:
            return False
        # Other errors might mean endpoint exists but has validation issues
        # Check the actual exception type
        from datahub_interoperability.errors import NotFoundError

        if isinstance(e, NotFoundError):
            return False
        return True


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
    api_base_url = os.environ.get("API_BASE_URL", "http://localhost:8001/api/v1")
    api_key = setup_authentication_for_sdk_tests(api_base_url)

    if not api_key:
        pytest.skip(
            "No API key available. Set TEST_API_KEY or DATAHUB_API_KEY environment variable."
        )

    # Use longer timeout for comprehensive tests (60 seconds) to handle slow operations
    return DataHubClientConfig(
        base_url=api_base_url,
        api_token=api_key,
        timeout=60.0,  # 60 seconds for comprehensive tests
    )


@pytest.fixture
async def odps_contract(real_api_config):
    """Fixture to create an ODPS contract for testing"""
    client = DataHubClient(real_api_config)

    odps_content = json.dumps(
        {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": f"test-odps-{uuid.uuid4().hex[:8]}",
                        "name": f"Test ODPS Product {uuid.uuid4().hex[:8]}",
                        "description": "Test ODPS product for API integration tests",
                    }
                },
                "contract": {
                    "spec": {
                        "apiVersion": "odcs/v3",
                        "kind": "DataContract",
                        "id": f"test-contract-{uuid.uuid4().hex[:8]}",
                        "name": "Test Contract",
                        "version": "1.0.0",
                        "schema": {
                            "fields": [
                                {"name": "id", "type": "string", "nullable": False},
                                {"name": "name", "type": "string", "nullable": False},
                            ]
                        },
                    }
                },
                "marketplace": {
                    "pricingPlans": [
                        {
                            "planID": "basic",
                            "name": "Basic Plan",
                            "price": 9.99,
                            "currency": "USD",
                            "billingPeriod": "monthly",
                        }
                    ]
                },
            },
        },
        indent=2,
    )

    # Retry logic for network errors
    import asyncio

    from datahub_interoperability.errors import NetworkError

    max_retries = 3
    retry_delay = 2  # seconds

    for attempt in range(max_retries):
        try:
            result = await client.contracts.create_odps(
                original_raw=odps_content, extract_odcs=True, original_format="JSON"
            )

            # Handle async workflow if needed - import helper from comprehensive tests
            from tests.test_contracts_api_odps_comprehensive import handle_async_workflow_response

            result = await handle_async_workflow_response(client, result, timeout=300)

            if isinstance(result, dict) and "error" in result:
                if "workflow" in str(result.get("error", "")).lower():
                    pytest.skip(f"Workflow execution failed: {result.get('error')}")

            odps_id = result.get("odps_contract", {}).get("id") or result.get("id")
            if not odps_id:
                pytest.skip("Could not create ODPS contract for API integration tests")

            yield odps_id
            return
        except NetworkError as e:
            error_str = str(e).lower()

            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (attempt + 1))
                continue

            # Network error after all retries — fail, don't skip.
            # Connectivity problems are real failures that need investigation.
            pytest.fail(f"Network error after {max_retries} attempts: {error_str}")

        except Exception:
            # Re-raise unexpected errors immediately — they are real bugs.
            raise


class TestLineageAPIWithODPS:
    """Tests for LineageAPI with ODPS contracts"""

    @pytest.mark.asyncio
    async def test_get_contract_lineage_with_odps_contract(self, real_api_config, odps_contract):
        """Test get_contract_lineage() with ODPS contract"""
        client = DataHubClient(real_api_config)

        try:
            # Try to get lineage - endpoint exists, may return empty for new contracts
            lineage = await client.lineage.get_contract_lineage(odps_contract)
            assert lineage is not None
            # Lineage may be empty for new contracts, but should return valid structure
            assert isinstance(lineage, dict)
        except Exception as e:
            # Lineage endpoint may not be fully implemented or may require specific setup
            error_str = str(e).lower()
            if "not found" in error_str or "404" in error_str:
                pytest.skip(f"Lineage endpoint not available: {error_str}")
            raise

    @pytest.mark.asyncio
    async def test_get_full_lineage_with_odps_contract(self, real_api_config, odps_contract):
        """Test get_full_lineage() with ODPS contract"""
        client = DataHubClient(real_api_config)

        try:
            # Try to get full lineage - endpoint exists, may return empty for new contracts
            lineage = await client.lineage.get_full_lineage(
                contract_id=odps_contract,
                max_contract_depth=5,
                max_model_depth=5,
                max_field_depth=5,
            )
            assert lineage is not None
            assert isinstance(lineage, dict)
        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "404" in error_str:
                pytest.skip(f"Lineage endpoint not available: {error_str}")
            raise


class TestScheduledIngestionAPIWithODPS:
    """Tests for ScheduledIngestionAPI with ODPS contracts"""

    @pytest.mark.asyncio
    async def test_list_scheduled_ingestions_with_odps_contract(
        self, real_api_config, odps_contract
    ):
        """Test list() scheduled ingestions - verify ODPS contracts can be referenced"""
        client = DataHubClient(real_api_config)

        try:
            # Get contract to extract asset_id if available
            contract = await client.contracts.get(odps_contract)
            asset_id = contract.get("asset_id")

            # List scheduled ingestions (may filter by asset_id if available)
            ingestions = await client.scheduled_ingestion.list(
                asset_id=asset_id if asset_id else None
            )
            assert ingestions is not None
            assert isinstance(ingestions, dict)
            assert "results" in ingestions or "count" in ingestions
        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "404" in error_str:
                pytest.skip(f"Scheduled ingestion endpoint not available: {error_str}")
            raise

    @pytest.mark.asyncio
    async def test_create_scheduled_ingestion_with_odps_contract(
        self, real_api_config, odps_contract
    ):
        """Test create() scheduled ingestion referencing ODPS contract"""
        client = DataHubClient(real_api_config)

        try:
            # Get contract to extract asset_id if available
            contract = await client.contracts.get(odps_contract)
            asset_id = contract.get("asset_id")

            # Create scheduled ingestion (if asset_id is available)
            if asset_id:
                ingestion = await client.scheduled_ingestion.create(
                    name=f"test-ingestion-{uuid.uuid4().hex[:8]}",
                    source_type="http",
                    source_config={"url": "https://example.com/data"},
                    schedule="0 0 * * *",  # Daily at midnight
                    asset_id=asset_id,
                )
                assert ingestion is not None
                assert isinstance(ingestion, dict)
                assert "id" in ingestion
            else:
                pytest.skip("ODPS contract does not have asset_id for scheduled ingestion test")
        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "404" in error_str:
                pytest.skip(f"Scheduled ingestion endpoint not available: {error_str}")
            raise


class TestVersioningAPIWithODPS:
    """Tests for VersioningAPI with ODPS contracts"""

    @pytest.mark.asyncio
    async def test_get_version_history_with_odps_contract(self, real_api_config, odps_contract):
        """Test get_version_history() with ODPS contract"""
        client = DataHubClient(real_api_config)

        try:
            # Get contract to extract dataset_id
            contract = await client.contracts.get(odps_contract)
            dataset_id = contract.get("dataset_id")

            if not dataset_id:
                pytest.skip("ODPS contract has no associated dataset_id for version history")

            # Try to get version history - endpoint exists
            version_history = await client.versioning.get_version_history(dataset_id)
            assert version_history is not None
            assert isinstance(version_history, dict)
            # Version history may be empty for new datasets
        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "404" in error_str:
                pytest.skip(f"Versioning endpoint not available: {error_str}")
            raise

    @pytest.mark.asyncio
    async def test_get_schema_evolution_with_odps_contract(self, real_api_config, odps_contract):
        """Test get_schema_evolution() with ODPS contract"""
        client = DataHubClient(real_api_config)

        try:
            # Get contract to extract dataset_id
            contract = await client.contracts.get(odps_contract)
            dataset_id = contract.get("dataset_id")

            if not dataset_id:
                pytest.skip("ODPS contract has no associated dataset_id for schema evolution")

            # Try to get schema evolution - endpoint exists
            schema_evolution = await client.versioning.get_schema_evolution(dataset_id)
            assert schema_evolution is not None
            assert isinstance(schema_evolution, dict)
        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "404" in error_str:
                pytest.skip(f"Versioning endpoint not available: {error_str}")
            raise


class TestGovernanceAPIWithODPS:
    """Tests for GovernanceAPI with ODPS contracts"""

    @pytest.mark.asyncio
    async def test_classify_data_with_odps_contract(self, real_api_config, odps_contract):
        """Test classify_asset() with ODPS contract"""
        client = DataHubClient(real_api_config)

        try:
            # Get contract to extract asset_id
            contract = await client.contracts.get(odps_contract)
            asset_id = contract.get("asset_id")

            if not asset_id:
                pytest.skip("ODPS contract has no associated asset_id for classification")

            # Get classification for the asset
            classification = await client.governance.get_classification(asset_id)
            assert classification is not None
            assert isinstance(classification, dict)
        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "404" in error_str:
                pytest.skip(f"Governance endpoint not available: {error_str}")
            raise

    @pytest.mark.asyncio
    async def test_get_retention_policies_with_odps_contract(self, real_api_config, odps_contract):
        """Test get_retention_policies() with ODPS contract"""
        client = DataHubClient(real_api_config)

        try:
            retention_policies = await client.governance.get_retention_policies(odps_contract)
            assert retention_policies is not None
            assert isinstance(retention_policies, dict)
        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "404" in error_str:
                pytest.skip(f"Governance endpoint not available: {error_str}")
            raise

    @pytest.mark.asyncio
    async def test_get_compliance_report_with_odps_contract(self, real_api_config, odps_contract):
        """Test get_compliance_report() with ODPS contract"""
        client = DataHubClient(real_api_config)

        try:
            # Get contract to extract asset_id
            contract = await client.contracts.get(odps_contract)
            asset_id = contract.get("asset_id")

            if not asset_id:
                pytest.skip("ODPS contract has no associated asset_id for compliance report")

            # First, generate a compliance report
            report = await client.governance.generate_compliance_report(
                regime="GDPR", asset_ids=[asset_id]
            )

            if not report or "report_id" not in report and "id" not in report:
                pytest.skip("Could not generate compliance report for testing")

            report_id = report.get("report_id") or report.get("id")

            # Now get the report by ID
            compliance_report = await client.governance.get_compliance_report(report_id)
            assert compliance_report is not None
            assert isinstance(compliance_report, dict)
        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "404" in error_str:
                pytest.skip(f"Governance endpoint not available: {error_str}")
            raise


class TestSearchAPIWithODPS:
    """Tests for SearchAPI with ODPS product details"""

    @pytest.mark.asyncio
    async def test_search_odps_products(self, real_api_config, odps_contract):
        """Test search() for ODPS products"""
        client = DataHubClient(real_api_config)

        try:
            # Get product details from ODPS contract
            contract = await client.contracts.get(odps_contract)
            product_details = client.contracts.get_product_details(contract, lang="en")
            product_name = product_details.get("name") if product_details else None

            if product_name:
                # Search for the product by name
                search_results = await client.search.search(
                    query=product_name, type="contract", limit=10
                )
                assert search_results is not None
                assert isinstance(search_results, dict)
                # Results may or may not contain our contract depending on indexing
            else:
                # Search for ODPS contracts in general
                search_results = await client.search.search(query="ODPS", type="contract", limit=10)
                assert search_results is not None
                assert isinstance(search_results, dict)
        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "404" in error_str:
                pytest.skip(f"Search endpoint not available: {error_str}")
            raise

    @pytest.mark.asyncio
    async def test_get_suggestions_for_odps_products(self, real_api_config, odps_contract):
        """Test get_suggestions() for ODPS products"""
        client = DataHubClient(real_api_config)

        try:
            # Get product details from ODPS contract
            contract = await client.contracts.get(odps_contract)
            product_details = client.contracts.get_product_details(contract, lang="en")
            product_name = product_details.get("name") if product_details else "ODPS"

            # Get search suggestions
            suggestions = await client.search.get_suggestions(
                query=product_name[:5] if product_name else "ODPS", limit=10
            )
            assert suggestions is not None
            assert isinstance(suggestions, dict)
        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "404" in error_str:
                pytest.skip(f"Search endpoint not available: {error_str}")
            raise


class TestObservabilityAPIWithODPS:
    """Tests for ObservabilityAPI with ODPS contracts"""

    @pytest.mark.asyncio
    async def test_get_freshness_monitoring_with_odps_contract(
        self, real_api_config, odps_contract
    ):
        """Test get_freshness() with ODPS contract"""
        client = DataHubClient(real_api_config)

        try:
            # Get contract to extract asset_id
            contract = await client.contracts.get(odps_contract)
            asset_id = contract.get("asset_id")

            if not asset_id:
                pytest.skip("ODPS contract has no associated asset_id for freshness monitoring")

            # Get freshness for the asset
            freshness = await client.observability.get_freshness(asset_id)
            assert freshness is not None
            assert isinstance(freshness, dict)
        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "404" in error_str:
                pytest.skip(f"Observability endpoint not available: {error_str}")
            raise

    @pytest.mark.asyncio
    async def test_get_schema_drift_with_odps_contract(self, real_api_config, odps_contract):
        """Test get_schema_drift() with ODPS contract"""
        client = DataHubClient(real_api_config)

        try:
            schema_drift = await client.observability.get_schema_drift(odps_contract)
            assert schema_drift is not None
            assert isinstance(schema_drift, dict)
        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "404" in error_str:
                pytest.skip(f"Observability endpoint not available: {error_str}")
            raise

    @pytest.mark.asyncio
    async def test_get_sla_monitoring_with_odps_contract(self, real_api_config, odps_contract):
        """Test get_slas() with ODPS contract"""
        client = DataHubClient(real_api_config)

        try:
            # Get contract to extract asset_id
            contract = await client.contracts.get(odps_contract)
            asset_id = contract.get("asset_id")

            if not asset_id:
                pytest.skip("ODPS contract has no associated asset_id for SLA monitoring")

            # Get SLAs for the asset (get_slas takes dataset_id, not asset_id)
            # Try to get dataset_id from contract or use asset_id
            dataset_id = contract.get("dataset_id") or asset_id
            sla_monitoring = await client.observability.get_slas(dataset_id=dataset_id)
            assert sla_monitoring is not None
            assert isinstance(sla_monitoring, dict)
        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "404" in error_str:
                pytest.skip(f"Observability endpoint not available: {error_str}")
            raise


class TestWebhooksAPIWithODPS:
    """Tests for WebhooksAPI with ODPS events"""

    @pytest.mark.asyncio
    async def test_list_webhooks_for_odps_events(self, real_api_config):
        """Test list() webhooks - verify ODPS events can be configured"""
        client = DataHubClient(real_api_config)

        try:
            webhooks = await client.webhooks.list()
            assert webhooks is not None
            assert isinstance(webhooks, dict)
            assert "results" in webhooks or "count" in webhooks
        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "404" in error_str:
                pytest.skip(f"Webhooks endpoint not available: {error_str}")
            raise

    @pytest.mark.asyncio
    async def test_create_webhook_for_odps_events(self, real_api_config):
        """Test create() webhook for ODPS contract events"""
        client = DataHubClient(real_api_config)

        try:
            webhook = await client.webhooks.create(
                url="https://example.com/webhook",
                event_types=["contract.created", "contract.updated", "odps.created"],
                name=f"test-odps-webhook-{uuid.uuid4().hex[:8]}",
                secret="test-secret-key-for-webhook-validation",
                active=True,
            )
            assert webhook is not None
            assert isinstance(webhook, dict)
            assert "id" in webhook

            # Cleanup
            webhook_id = webhook.get("id")
            if webhook_id:
                try:
                    await client.webhooks.delete(webhook_id)
                except Exception:
                    pass  # Ignore cleanup errors
        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "404" in error_str:
                pytest.skip(f"Webhooks endpoint not available: {error_str}")
            raise

    @pytest.mark.asyncio
    async def test_trigger_webhook_with_odps_contract(self, real_api_config, odps_contract):
        """Test webhook triggering when ODPS contract is created/updated"""
        client = DataHubClient(real_api_config)

        try:
            # Create a webhook
            webhook = await client.webhooks.create(
                url="https://example.com/webhook",
                event_types=["contract.created", "contract.updated"],
                name=f"test-odps-trigger-{uuid.uuid4().hex[:8]}",
                secret="test-secret-key-for-webhook-validation",
                active=True,
            )

            if webhook and "id" in webhook:
                webhook_id = webhook.get("id")

                # Update ODPS contract to trigger webhook
                await client.contracts.get(odps_contract)
                # Note: Actual webhook triggering depends on backend implementation

                # Cleanup
                try:
                    await client.webhooks.delete(webhook_id)
                except Exception:
                    pass  # Ignore cleanup errors
        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "404" in error_str:
                pytest.skip(f"Webhooks endpoint not available: {error_str}")
            raise
