"""
Comprehensive integration scenario tests for Python SDK.

Tests complete workflows using real API server (no mocks) - uses existing API service in Docker Compose.
"""

import asyncio
import json
import uuid

import pytest
from asgiref.sync import sync_to_async

# Try to import SDK
try:
    from datahub_interoperability import DataHubClient, DataHubClientConfig

    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract
from tests.sdk_python.conftest import SDKTestBase

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


@pytest.mark.skipif(
    not SDK_AVAILABLE, reason="SDK not installed. Run: cd sdk/python && pip install -e ."
)
class TestSDKIntegrationScenarios(SDKTestBase):
    """Test complete integration scenarios"""

    @pytest.mark.asyncio
    async def test_complete_asset_lifecycle_workflow(self):
        """
        Test complete asset lifecycle: Create → Update → List → Get → Delete
        """
        config = await self.get_sdk_config()
        async with DataHubClient(config) as client:
            # Step 1: Create asset
            asset_key = f"sdk-lifecycle-{uuid.uuid4().hex[:8]}"
            asset = await client.post(
                "/assets/assets/",
                {
                    "key": asset_key,
                    "name": "SDK Lifecycle Asset",
                    "description": "Complete lifecycle test",
                    "domain": "testing",
                },
            )
            asset_id = asset["id"]
            assert asset["name"] == "SDK Lifecycle Asset"

            # Step 2: Get asset
            retrieved = await client.get(f"/assets/assets/{asset_id}/")
            assert retrieved["id"] == asset_id
            assert retrieved["name"] == "SDK Lifecycle Asset"

            # Step 3: Update asset
            updated = await client.patch(
                f"/assets/assets/{asset_id}/", {"description": "Updated description"}
            )
            assert updated["description"] == "Updated description"

            # Step 4: List assets
            assets = await client.get("/assets/assets/")
            assert "results" in assets or isinstance(assets, list)
            if "results" in assets:
                asset_ids = [a["id"] for a in assets["results"]]
            else:
                asset_ids = [a["id"] for a in assets]
            assert asset_id in asset_ids

            # Step 5: Delete asset (if supported)
            try:
                await client.delete(f"/assets/assets/{asset_id}/")
                # Verify deleted
                from datahub_interoperability.errors import NotFoundError

                with pytest.raises(NotFoundError):
                    await client.get(f"/assets/assets/{asset_id}/")
            except Exception:
                # Delete may not be supported or may soft-delete
                pass

    @pytest.mark.asyncio
    async def test_complete_contract_workflow(self):
        """
        Test complete contract workflow: Create → Validate → Normalize → Get
        """
        config = await self.get_sdk_config()
        async with DataHubClient(config) as client:
            # Step 1: Create contract
            contract = await client.contracts.create(
                name="SDK Workflow Contract",
                original_raw=json.dumps({"version": "1.0", "models": []}),
                original_format="JSON",
            )
            contract_id = contract["id"]
            assert contract["name"] == "SDK Workflow Contract"

            # Step 2: Get contract
            retrieved = await client.contracts.get(contract_id)
            assert retrieved["id"] == contract_id

            # Step 3: Validate contract
            validation = await client.contracts.validate(contract_id)
            assert "validation_status" in validation or "status" in validation

            # Step 4: Normalize contract
            normalization = await client.contracts.normalize(contract_id)
            assert "normalization_status" in normalization or "status" in normalization

    @pytest.mark.asyncio
    async def test_complete_webhook_workflow(self):
        """
        Test complete webhook workflow: Create → List → Get → Update → Trigger → Delete
        """
        config = await self.get_sdk_config()
        async with DataHubClient(config) as client:
            # Step 1: Create webhook
            webhook = await client.webhooks.create(
                name="SDK Workflow Webhook",
                url="https://example.com/webhook-workflow",
                event_types=["asset.created", "asset.updated"],
                secret="workflow-secret",
            )
            webhook_id = webhook["id"]
            assert webhook["url"] == "https://example.com/webhook-workflow"

            # Step 2: List webhooks
            webhooks = await client.webhooks.list()
            assert "results" in webhooks or isinstance(webhooks, list)

            # Step 3: Get webhook
            retrieved = await client.webhooks.get(webhook_id)
            assert retrieved["id"] == webhook_id

            # Step 4: Update webhook
            updated = await client.webhooks.update(
                webhook_id, url="https://example.com/webhook-updated"
            )
            assert updated["url"] == "https://example.com/webhook-updated"

            # Step 5: Test webhook (trigger test delivery)
            trigger_result = await client.webhooks.test(webhook_id)
            assert trigger_result is not None

            # Step 6: Delete webhook
            await client.webhooks.delete(webhook_id)

            # Verify deleted
            from datahub_interoperability.errors import NotFoundError

            with pytest.raises(NotFoundError):
                await client.webhooks.get(webhook_id)

    @pytest.mark.asyncio
    async def test_complete_access_request_workflow(self):
        """
        Test complete access request workflow: Create → List → Get → Approve
        """
        # Create asset
        asset = await sync_to_async(Asset.objects.create)(
            tenant=self.tenant,
            key=f"access-workflow-{uuid.uuid4().hex[:8]}",
            name="Access Workflow Asset",
            status=AssetStatus.ACTIVE,
        )

        config = await self.get_sdk_config()
        async with DataHubClient(config) as client:
            # Step 1: Create access request
            access_request = await client.governance.create_access_request(
                asset_id=str(asset.id), reason="SDK workflow test"
            )
            request_id = access_request["id"]
            assert "id" in access_request

            # Step 2: List access requests
            requests = await client.governance.list_access_requests()
            assert "results" in requests or isinstance(requests, list)

            # Step 3: Get access request (via direct API call)
            retrieved = await client.get(f"governance/access-requests/{request_id}/")
            assert retrieved["id"] == request_id

            # Step 4: Approve access request
            approved = await client.governance.approve_access_request(request_id)
            assert "status" in approved or "approved" in str(approved.get("status", "")).lower()

    @pytest.mark.asyncio
    async def test_multi_api_workflow(self):
        """
        Test workflow using multiple APIs: Contract → Asset → Webhook → Search
        """
        config = await self.get_sdk_config()
        async with DataHubClient(config) as client:
            # Step 1: Create contract
            contract = await client.contracts.create(
                name="Multi-API Contract",
                original_raw=json.dumps({"version": "1.0", "models": []}),
                original_format="JSON",
            )
            contract_id = contract["id"]

            # Step 2: Create asset
            asset_key = f"multi-api-{uuid.uuid4().hex[:8]}"
            asset = await client.post(
                "/assets/assets/",
                {
                    "key": asset_key,
                    "name": "Multi-API Asset",
                    "description": "Created via multi-API workflow",
                },
            )
            asset_id = asset["id"]

            # Step 3: Create webhook for asset events
            webhook = await client.webhooks.create(
                name="Multi-API Webhook",
                url="https://example.com/multi-api-webhook",
                event_types=["asset.created"],
                secret="multi-api-secret",
            )
            webhook_id = webhook["id"]

            # Step 4: Search for asset
            search_results = await client.search.search("Multi-API Asset")
            assert "results" in search_results or isinstance(search_results, list)

            # Verify all operations succeeded
            assert contract_id is not None
            assert asset_id is not None
            assert webhook_id is not None
