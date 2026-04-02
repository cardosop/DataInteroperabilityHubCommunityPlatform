"""
E2E workflow tests for ODPS linking via SDK.

Tests complete end-to-end workflows:
- Complete linking workflow: create ODCS, create ODPS, link, verify, unlink
- Multiple linking scenarios
- Error recovery workflows

Uses REAL API server (no mocks) - uses existing API service in Docker Compose.
"""

import json
import uuid

import pytest

pytestmark = pytest.mark.slow
from asgiref.sync import sync_to_async

# Try to import SDK
try:
    from datahub_interoperability import DataHubClient, DataHubClientConfig
    from datahub_interoperability.errors import (
        NotFoundError,
        ValidationError,
    )

    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False

from hub.apps.contracts.models import Contract, OriginalSpecType
from tests.sdk_python.conftest import SDKTestBase

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


@pytest.mark.skipif(
    not SDK_AVAILABLE, reason="SDK not installed. Run: cd sdk/python && pip install -e ."
)
class TestODPSLinkingWorkflowE2E(SDKTestBase):
    """E2E workflow tests for ODPS linking"""

    @pytest.mark.asyncio
    async def test_complete_linking_workflow(self):
        """Test complete workflow: create ODCS, create ODPS, link, verify, unlink"""
        config = await self.get_sdk_config()
        client = DataHubClient(config)
        contracts_api = client.contracts

        # Step 1: Create ODCS contract
        odcs_id = f"odcs-{uuid.uuid4().hex[:8]}"
        odcs_content = json.dumps({
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": odcs_id,
            "name": "E2E Test ODCS Contract",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "nullable": False},
                    {"name": "name", "type": "string", "nullable": True},
                    {"name": "value", "type": "number", "nullable": True}
                ]
            }
        })

        odcs_contract = await contracts_api.create(
            original_raw=odcs_content,
            original_format="JSON"
        )
        odcs_contract_id = odcs_contract["id"]
        assert odcs_contract["original_spec_type"] == OriginalSpecType.ODCS

        # Step 2: Create ODPS contract using link_odcs_id (creates and links)
        odcs_contract_data = json.loads(odcs_content)
        odps_content = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": f"e2e-product-{uuid.uuid4().hex[:8]}",
                        "name": "E2E Test Product",
                        "description": "Product for E2E linking workflow test"
                    }
                },
                "contract": {
                    "spec": odcs_contract_data  # Full ODCS contract in spec
                }
            }
        })

        # Create ODPS using link_odcs_id (creates and links in one step)
        odps_result = await contracts_api.create_odps(
            original_raw=odps_content,
            link_odcs_id=odcs_contract_id,
            original_format="JSON"
        )

        # Extract ODPS contract ID
        odps_contract_id = odps_result["id"]
        assert odps_result["original_spec_type"] == OriginalSpecType.ODPS

        # Step 3: Unlink to test linking existing ODPS
        await contracts_api.unlink_odps_from_odcs(odcs_contract_id)

        # Verify unlinked
        links = await contracts_api.get_linked_contracts(odcs_contract_id)
        assert links["odps_link"] is None

        # Step 4: Link existing ODPS to our ODCS contract
        linked_odps = await contracts_api.link_odps_to_odcs(
            odcs_contract_id=odcs_contract_id,
            odps_contract_id=odps_contract_id
        )

        # Verify linking succeeded
        assert linked_odps["id"] == odps_contract_id
        assert linked_odps["original_spec_type"] == OriginalSpecType.ODPS

        # Step 5: Verify bidirectional links
        links_odcs = await contracts_api.get_linked_contracts(odcs_contract_id)
        assert links_odcs["odps_link"] is not None
        assert links_odcs["odps_link"]["id"] == odps_contract_id

        links_odps = await contracts_api.get_linked_contracts(odps_contract_id)
        assert links_odps["odcs_link"] is not None
        assert links_odps["odcs_link"]["id"] == odcs_contract_id

        # Step 6: Verify contracts are accessible
        odcs_retrieved = await contracts_api.get(odcs_contract_id)
        assert odcs_retrieved["id"] == odcs_contract_id

        odps_retrieved = await contracts_api.get(odps_contract_id)
        assert odps_retrieved["id"] == odps_contract_id

        # Step 7: Unlink
        await contracts_api.unlink_odps_from_odcs(odcs_contract_id)

        # Step 8: Verify links are removed
        links_odcs_after = await contracts_api.get_linked_contracts(odcs_contract_id)
        assert links_odcs_after["odps_link"] is None

        links_odps_after = await contracts_api.get_linked_contracts(odps_contract_id)
        assert links_odps_after["odcs_link"] is None

        # Step 9: Verify contracts still exist (unlinking doesn't delete them)
        odcs_retrieved_after = await contracts_api.get(odcs_contract_id)
        assert odcs_retrieved_after["id"] == odcs_contract_id

        odps_retrieved_after = await contracts_api.get(odps_contract_id)
        assert odps_retrieved_after["id"] == odps_contract_id

    @pytest.mark.asyncio
    async def test_linking_workflow_create_and_link_new_odps(self):
        """Test workflow: create ODCS, then create and link new ODPS in one step"""
        config = await self.get_sdk_config()
        client = DataHubClient(config)
        contracts_api = client.contracts

        # Step 1: Create ODCS contract
        odcs_id = f"odcs-{uuid.uuid4().hex[:8]}"
        odcs_content = json.dumps({
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": odcs_id,
            "name": "E2E Test ODCS for New ODPS",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "nullable": False}
                ]
            }
        })

        odcs_contract = await contracts_api.create(
            original_raw=odcs_content,
            original_format="JSON"
        )
        odcs_contract_id = odcs_contract["id"]

        # Step 2: Create and link new ODPS in one step
        odcs_contract_data = json.loads(odcs_content)
        odps_content = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": f"e2e-product-new-{uuid.uuid4().hex[:8]}",
                        "name": "E2E Test Product New",
                        "description": "Product created and linked in one step"
                    }
                },
                "contract": {
                    "spec": odcs_contract_data  # Full ODCS contract in spec
                }
            }
        })

        linked_odps = await contracts_api.link_odps_to_odcs(
            odcs_contract_id=odcs_contract_id,
            odps_raw=odps_content,
            odps_format="JSON",
            resolve_external_refs=True
        )

        # Verify ODPS was created and linked
        assert linked_odps["id"] is not None
        assert linked_odps["original_spec_type"] == OriginalSpecType.ODPS
        odps_contract_id = linked_odps["id"]

        # Verify bidirectional links
        links_odcs = await contracts_api.get_linked_contracts(odcs_contract_id)
        assert links_odcs["odps_link"] is not None
        assert links_odcs["odps_link"]["id"] == odps_contract_id

        links_odps = await contracts_api.get_linked_contracts(odps_contract_id)
        assert links_odps["odcs_link"] is not None
        assert links_odps["odcs_link"]["id"] == odcs_contract_id

    @pytest.mark.asyncio
    async def test_linking_workflow_multiple_operations(self):
        """Test workflow with multiple link/unlink operations"""
        config = await self.get_sdk_config()
        client = DataHubClient(config)
        contracts_api = client.contracts

        # Step 1: Create ODCS contract
        odcs_id = f"odcs-{uuid.uuid4().hex[:8]}"
        odcs_content = json.dumps({
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": odcs_id,
            "name": "E2E Test ODCS for Multiple Ops",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "nullable": False}
                ]
            }
        })

        odcs_contract = await contracts_api.create(
            original_raw=odcs_content,
            original_format="JSON"
        )
        odcs_contract_id = odcs_contract["id"]

        # Step 2: Create first ODPS and link
        odcs_contract_data = json.loads(odcs_content)
        odps_content_1 = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": f"e2e-product-1-{uuid.uuid4().hex[:8]}",
                        "name": "E2E Test Product 1"
                    }
                },
                "contract": {
                    "spec": odcs_contract_data  # Full ODCS contract in spec
                }
            }
        })

        linked_odps_1 = await contracts_api.link_odps_to_odcs(
            odcs_contract_id=odcs_contract_id,
            odps_raw=odps_content_1,
            odps_format="JSON"
        )
        odps_contract_id_1 = linked_odps_1["id"]

        # Verify link exists
        links = await contracts_api.get_linked_contracts(odcs_contract_id)
        assert links["odps_link"]["id"] == odps_contract_id_1

        # Step 3: Unlink
        await contracts_api.unlink_odps_from_odcs(odcs_contract_id)

        # Verify link removed
        links = await contracts_api.get_linked_contracts(odcs_contract_id)
        assert links["odps_link"] is None

        # Step 4: Create and link second ODPS
        odps_content_2 = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": f"e2e-product-2-{uuid.uuid4().hex[:8]}",
                        "name": "E2E Test Product 2"
                    }
                },
                "contract": {
                    "spec": odcs_contract_data  # Full ODCS contract in spec
                }
            }
        })

        linked_odps_2 = await contracts_api.link_odps_to_odcs(
            odcs_contract_id=odcs_contract_id,
            odps_raw=odps_content_2,
            odps_format="JSON"
        )
        odps_contract_id_2 = linked_odps_2["id"]

        # Verify new link exists
        links = await contracts_api.get_linked_contracts(odcs_contract_id)
        assert links["odps_link"]["id"] == odps_contract_id_2
        assert links["odps_link"]["id"] != odps_contract_id_1  # Different ODPS

        # Step 5: Verify both ODPS contracts still exist
        odps_1 = await contracts_api.get(odps_contract_id_1)
        assert odps_1["id"] == odps_contract_id_1

        odps_2 = await contracts_api.get(odps_contract_id_2)
        assert odps_2["id"] == odps_contract_id_2

        # Step 6: Verify only the second one is linked
        links_odps_1 = await contracts_api.get_linked_contracts(odps_contract_id_1)
        assert links_odps_1["odcs_link"] is None

        links_odps_2 = await contracts_api.get_linked_contracts(odps_contract_id_2)
        assert links_odps_2["odcs_link"] is not None
        assert links_odps_2["odcs_link"]["id"] == odcs_contract_id

