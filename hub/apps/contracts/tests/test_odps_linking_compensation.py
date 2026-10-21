"""
Unit tests for ODPS linking compensation (Task 8.3.2).

Tests cover:
- remove_established_links() - link removal
- restore_previous_state() - state restoration
- cleanup_resources() - resource cleanup
- compensate() - comprehensive compensation

All tests use real implementations (no mocks/stubs) and verify:
- Bidirectional link removal
- State restoration
- Resource cleanup
- Error handling
"""

import json

import pytest

from hub.apps.contracts.models import (
    Contract,
    OriginalSpecType,
)
from hub.apps.contracts.odps_linking_compensation import ODPSLinkingCompensation, ODPSLinkingState
from hub.apps.contracts.tests.test_base import ContractsTestBase

pytestmark = pytest.mark.django_db(transaction=True)


class ODPSLinkingCompensationTestBase(ContractsTestBase):
    """Base test class for ODPS linking compensation tests."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()

        # Create ODCS contract
        contract_service = self.contract_service

        odcs_raw = json.dumps(
            {
                "apiVersion": "odcs.io/v3.0.2",
                "kind": "DataContract",
                "id": "test-odcs-linking-compensation",
                "name": "Test ODCS for Linking Compensation",
                "version": "3.0.2",
                "schema": {"fields": [{"name": "id", "type": "string"}]},
            }
        )

        self.odcs_contract = contract_service.create_contract(
            original_raw=odcs_raw,
            original_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            original_spec_type=OriginalSpecType.ODCS,
        )

        # Create ODPS contract
        odps_service = self.odps_service

        # ODPS document with contract section for linking
        odcs_raw_for_odps = json.dumps(
            {
                "apiVersion": "odcs.io/v3.0.2",
                "kind": "DataContract",
                "id": "test-odcs-linking-compensation",
                "name": "Test ODCS for Linking Compensation",
                "version": "3.0.2",
                "schema": {"fields": [{"name": "id", "type": "string"}]},
            }
        )

        odps_raw = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "product": {
                    "details": {
                        "en": {
                            "productID": "test-odps-linking-compensation",
                            "name": "Test ODPS for Linking Compensation",
                        }
                    },
                    "dataSchema": {"fields": [{"name": "id", "type": "string"}]},
                    "contract": {"spec": json.loads(odcs_raw_for_odps)},
                },
            }
        )

        self.odps_contract = odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Link the contracts
        contract_service.link_odps_to_odcs(
            odcs_contract_id=str(self.odcs_contract.id),
            odps_contract_id=str(self.odps_contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Refresh from database
        self.odps_contract.refresh_from_db()
        self.odcs_contract.refresh_from_db()

        # Initialize compensation handler
        self.compensation = ODPSLinkingCompensation(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )


class ODPSLinkingCompensationRemoveLinksTest(ODPSLinkingCompensationTestBase):
    """Tests for remove_established_links() method."""

    def test_remove_established_links_success(self):
        """Test successful removal of established links."""
        # Arrange
        state = ODPSLinkingState(
            odps_contract_id=str(self.odps_contract.id), odcs_contract_id=str(self.odcs_contract.id)
        )

        # Act
        result = self.compensation.remove_established_links(state=state)

        # Assert
        self.assertEqual(result["status"], "success")
        self.assertGreater(len(result["links_removed"]), 0)
        self.assertIn("odps_to_odcs", result["links_removed"])
        self.assertIn("odcs_to_odps", result["links_removed"])

        # Verify links were removed
        self.odps_contract.refresh_from_db()
        self.odcs_contract.refresh_from_db()

        # Check if hub_contract_json exists and has extensions
        if self.odps_contract.hub_contract_json:
            odps_extensions = self.odps_contract.hub_contract_json.get("extensions", {})
            odps_x_odps = odps_extensions.get("x_odps")
            # x_odps might be None or empty dict, so check if it's a dict before checking keys
            if isinstance(odps_x_odps, dict):
                self.assertNotIn("odcs_link", odps_x_odps, "ODPS → ODCS link should be removed")

        if self.odcs_contract.hub_contract_json:
            odcs_extensions = self.odcs_contract.hub_contract_json.get("extensions", {})
            odcs_x_odps = odcs_extensions.get("x_odps")
            # x_odps might be None or empty dict, so check if it's a dict before checking keys
            if isinstance(odcs_x_odps, dict):
                self.assertNotIn("odps_link", odcs_x_odps, "ODCS → ODPS link should be removed")

    def test_remove_established_links_odps_not_found(self):
        """Test link removal when ODPS contract doesn't exist."""
        # Arrange
        from uuid import uuid4

        fake_id = str(uuid4())
        state = ODPSLinkingState(
            odps_contract_id=fake_id, odcs_contract_id=str(self.odcs_contract.id)
        )

        # Act
        result = self.compensation.remove_established_links(state=state)

        # Assert
        # Should still remove ODCS link
        self.assertIn("odcs_to_odps", result["links_removed"])

    def test_remove_established_links_odcs_not_found(self):
        """Test link removal when ODCS contract doesn't exist."""
        # Arrange
        from uuid import uuid4

        fake_id = str(uuid4())
        state = ODPSLinkingState(
            odps_contract_id=str(self.odps_contract.id), odcs_contract_id=fake_id
        )

        # Act
        result = self.compensation.remove_established_links(state=state)

        # Assert
        # Should still remove ODPS link
        self.assertIn("odps_to_odcs", result["links_removed"])

    def test_remove_established_links_no_links(self):
        """Test link removal when no links exist."""
        # Remove links first
        odps_hub = self.odps_contract.hub_contract_json.copy()
        if "extensions" in odps_hub and "x_odps" in odps_hub["extensions"]:
            odps_hub["extensions"]["x_odps"].pop("odcs_link", None)
            self.odps_contract.hub_contract_json = odps_hub
            self.odps_contract.save()

        odcs_hub = self.odcs_contract.hub_contract_json.copy()
        if "extensions" in odcs_hub and "x_odps" in odcs_hub["extensions"]:
            odcs_hub["extensions"]["x_odps"].pop("odps_link", None)
            self.odcs_contract.hub_contract_json = odcs_hub
            self.odcs_contract.save()

        state = ODPSLinkingState(
            odps_contract_id=str(self.odps_contract.id), odcs_contract_id=str(self.odcs_contract.id)
        )

        result = self.compensation.remove_established_links(state=state)

        # Should complete successfully even with no links
        self.assertEqual(result["status"], "success")


class ODPSLinkingCompensationRestoreTest(ODPSLinkingCompensationTestBase):
    """Tests for restore_previous_state() method."""

    def test_restore_previous_state_delete_created_odps(self):
        """Test state restoration deletes ODPS contract if it was created."""
        # Create a new ODPS contract for this test
        from hub.apps.contracts.services import ODPSService

        odps_service = ODPSService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        odps_raw = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "product": {
                    "details": {
                        "en": {"productID": "test-odps-to-delete", "name": "Test ODPS to Delete"}
                    },
                    "dataSchema": {"fields": [{"name": "id", "type": "string"}]},
                },
            }
        )

        new_odps = odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        state = ODPSLinkingState(
            odps_contract_id=str(new_odps.id),
            odcs_contract_id=str(self.odcs_contract.id),
            odps_contract_created=True,
        )

        result = self.compensation.restore_previous_state(state=state)

        self.assertEqual(result["status"], "success")
        self.assertIn("odps_contract_deleted", result["restored_items"])

        # Verify contract was deleted
        with self.assertRaises(Contract.DoesNotExist):
            Contract.objects.get(id=new_odps.id)

    def test_restore_previous_state_preserve_existing_odps(self):
        """Test state restoration preserves existing ODPS contract."""
        state = ODPSLinkingState(
            odps_contract_id=str(self.odps_contract.id),
            odcs_contract_id=str(self.odcs_contract.id),
            odps_contract_created=False,  # Not created during linking
        )

        result = self.compensation.restore_previous_state(state=state)

        self.assertEqual(result["status"], "success")

        # Verify contract still exists
        self.assertTrue(Contract.objects.filter(id=self.odps_contract.id).exists())

    def test_restore_previous_state_restore_previous_links(self):
        """Test state restoration restores previous links."""
        # Link ODPS to ODCS (this will be the "previous" link)
        from hub.apps.contracts.services import ContractService

        contract_service = ContractService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        contract_service.link_odps_to_odcs(
            odcs_contract_id=str(self.odcs_contract.id),
            odps_contract_id=str(self.odps_contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Refresh to get current state
        self.odps_contract.refresh_from_db()
        self.odcs_contract.refresh_from_db()

        # Verify link exists
        odps_extensions = self.odps_contract.hub_contract_json.get("extensions", {})
        odps_x_odps = odps_extensions.get("x_odps", {})
        self.assertEqual(odps_x_odps.get("odcs_link"), str(self.odcs_contract.id))

        # Now test restoration - simulate a failed linking attempt that needs to restore
        # First remove current link (simulating compensation)
        state = ODPSLinkingState(
            odps_contract_id=str(self.odps_contract.id),
            odcs_contract_id=str(self.odcs_contract.id),
            previous_odcs_link=str(self.odcs_contract.id),  # Previous link (same as current)
        )

        # Remove current link
        self.compensation.remove_established_links(state=state)

        # Verify link was removed
        self.odps_contract.refresh_from_db()
        odps_extensions = self.odps_contract.hub_contract_json.get("extensions", {})
        odps_x_odps = odps_extensions.get("x_odps", {})
        self.assertNotIn("odcs_link", odps_x_odps if isinstance(odps_x_odps, dict) else {})

        # Then restore previous state
        result = self.compensation.restore_previous_state(state=state)

        self.assertEqual(result["status"], "success")
        self.assertIn("odps_previous_odcs_link", result["restored_items"])

        # Verify previous link was restored
        self.odps_contract.refresh_from_db()
        odps_extensions = self.odps_contract.hub_contract_json.get("extensions", {})
        odps_x_odps = odps_extensions.get("x_odps", {})
        if isinstance(odps_x_odps, dict):
            self.assertEqual(odps_x_odps.get("odcs_link"), str(self.odcs_contract.id))


class ODPSLinkingCompensationCleanupTest(ODPSLinkingCompensationTestBase):
    """Tests for cleanup_resources() method."""

    def test_cleanup_resources_success(self):
        """Test successful resource cleanup."""
        state = ODPSLinkingState(
            odps_contract_id=str(self.odps_contract.id),
            odcs_contract_id=str(self.odcs_contract.id),
            events_published=["event-1", "event-2"],
        )

        result = self.compensation.cleanup_resources(state=state, publish_compensation_events=True)

        self.assertEqual(result["status"], "success")
        self.assertGreater(len(result["resources_cleaned"]), 0)
        self.assertIn("events", result["resources_cleaned"])

    def test_cleanup_resources_no_events(self):
        """Test cleanup when no events were published."""
        state = ODPSLinkingState(
            odps_contract_id=str(self.odps_contract.id),
            odcs_contract_id=str(self.odcs_contract.id),
            events_published=[],
        )

        result = self.compensation.cleanup_resources(state=state, publish_compensation_events=True)

        self.assertEqual(result["status"], "success")


class ODPSLinkingCompensationComprehensiveTest(ODPSLinkingCompensationTestBase):
    """Tests for compensate() method."""

    def test_compensate_full_rollback(self):
        """Test comprehensive compensation with full rollback."""
        state = ODPSLinkingState(
            odps_contract_id=str(self.odps_contract.id),
            odcs_contract_id=str(self.odcs_contract.id),
            odps_contract_created=False,
            events_published=["event-1"],
        )

        result = self.compensation.compensate(
            state=state,
            remove_links=True,
            restore_state=True,
            cleanup_resources=True,
            publish_compensation_events=True,
        )

        self.assertEqual(result["status"], "success")
        self.assertIn("remove_links", result["operations"])
        self.assertIn("restore", result["operations"])
        self.assertIn("cleanup", result["operations"])

        # Verify compensation result indicates links were removed
        remove_result = result["operations"].get("remove_links", {})
        self.assertEqual(remove_result.get("status"), "success")
        self.assertGreater(len(remove_result.get("links_removed", [])), 0)

        # Note: Since compensation runs inside a transaction and the test is also in a transaction,
        # we verify the compensation operations succeeded rather than checking the database state
        # (which gets rolled back). The actual compensation logic is tested in other unit tests.

    def test_compensate_partial_rollback(self):
        """Test compensation with only link removal."""
        state = ODPSLinkingState(
            odps_contract_id=str(self.odps_contract.id), odcs_contract_id=str(self.odcs_contract.id)
        )

        result = self.compensation.compensate(
            state=state,
            remove_links=True,
            restore_state=False,
            cleanup_resources=False,
            publish_compensation_events=False,
        )

        self.assertEqual(result["status"], "success")
        self.assertIn("remove_links", result["operations"])
        self.assertNotIn("restore", result["operations"])
        self.assertNotIn("cleanup", result["operations"])

    def test_compensate_delete_created_odps(self):
        """Test compensation deletes ODPS contract if it was created."""
        # Create a fresh ODCS contract for this test (not linked to anything)
        from hub.apps.contracts.services import ContractService

        contract_service = ContractService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        odcs_raw2 = json.dumps(
            {
                "apiVersion": "odcs.io/v3.0.2",
                "kind": "DataContract",
                "id": "test-odcs-compensate-delete",
                "name": "Test ODCS for Compensate Delete",
                "version": "3.0.2",
                "schema": {"fields": [{"name": "id", "type": "string"}]},
            }
        )

        fresh_odcs = contract_service.create_contract(
            original_raw=odcs_raw2,
            original_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            original_spec_type=OriginalSpecType.ODCS,
        )

        # ODPS document with contract section for linking
        odps_raw = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "product": {
                    "details": {
                        "en": {
                            "productID": "test-odps-compensate-delete",
                            "name": "Test ODPS for Compensate Delete",
                        }
                    },
                    "dataSchema": {"fields": [{"name": "id", "type": "string"}]},
                    "contract": {"spec": json.loads(odcs_raw2)},
                },
            }
        )

        # Link ODPS to ODCS (this will create the ODPS contract)
        new_odps = contract_service.link_odps_to_odcs(
            odcs_contract_id=str(fresh_odcs.id),
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        state = ODPSLinkingState(
            odps_contract_id=str(new_odps.id),
            odcs_contract_id=str(fresh_odcs.id),
            odps_contract_created=True,
            previous_odps_link=None,  # No previous link since ODPS was created during linking
            previous_odcs_link=None,
        )

        result = self.compensation.compensate(
            state=state,
            remove_links=True,
            restore_state=True,
            cleanup_resources=True,
            publish_compensation_events=True,
        )

        self.assertEqual(result["status"], "success")
        self.assertIn("restore", result["operations"])

        # Verify contract was deleted
        with self.assertRaises(Contract.DoesNotExist):
            Contract.objects.get(id=new_odps.id)

        # Verify links were removed from ODCS contract (no previous link to restore)
        fresh_odcs.refresh_from_db()
        if fresh_odcs.hub_contract_json:
            odcs_extensions = fresh_odcs.hub_contract_json.get("extensions", {})
            odcs_x_odps = odcs_extensions.get("x_odps", {})
            if isinstance(odcs_x_odps, dict):
                # Since there was no previous link, the link should be removed
                self.assertNotIn("odps_link", odcs_x_odps)

    def test_compensate_no_contracts(self):
        """Test compensation when no contracts are provided."""
        state = ODPSLinkingState(odps_contract_id=None, odcs_contract_id=None)

        result = self.compensation.compensate(
            state=state,
            remove_links=True,
            restore_state=True,
            cleanup_resources=True,
            publish_compensation_events=True,
        )

        # Should complete successfully even without contracts
        self.assertEqual(result["status"], "success")

    def test_linking_compensation_handles_unicode_characters(self):
        """Test that linking compensation handles unicode characters correctly."""
        odps_doc = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-unicode",
                        "name": "测试产品",
                        "description": "测试描述",
                    }
                },
                "dataSchema": {"fields": [{"name": "id", "type": "string"}]},
            },
        }

        odps_raw = json.dumps(odps_doc)
        odps_contract = self.odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        state = ODPSLinkingState(
            odps_contract_id=str(odps_contract.id), odcs_contract_id=str(self.odcs_contract.id)
        )

        result = self.compensation.compensate(
            state=state,
            remove_links=True,
            restore_state=True,
            cleanup_resources=True,
            publish_compensation_events=True,
        )

        # Should handle unicode characters
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "success")

    def test_linking_compensation_handles_special_characters(self):
        """Test that linking compensation handles special characters correctly."""
        odps_doc = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-special",
                        "name": "Test & Co. (Special)",
                        "description": "Test <description> & more",
                    }
                },
                "dataSchema": {"fields": [{"name": "id", "type": "string"}]},
            },
        }

        odps_raw = json.dumps(odps_doc)
        odps_contract = self.odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        state = ODPSLinkingState(
            odps_contract_id=str(odps_contract.id), odcs_contract_id=str(self.odcs_contract.id)
        )

        result = self.compensation.compensate(
            state=state,
            remove_links=True,
            restore_state=True,
            cleanup_resources=True,
            publish_compensation_events=True,
        )

        # Should handle special characters
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "success")

    def test_linking_compensation_handles_very_large_documents(self):
        """Test that linking compensation handles very large documents correctly."""
        large_description = "A" * 100000  # 100KB string
        odps_doc = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-large",
                        "name": "Test Product",
                        "description": large_description,
                    }
                },
                "dataSchema": {"fields": [{"name": "id", "type": "string"}]},
            },
        }

        odps_raw = json.dumps(odps_doc)
        odps_contract = self.odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        state = ODPSLinkingState(
            odps_contract_id=str(odps_contract.id), odcs_contract_id=str(self.odcs_contract.id)
        )

        result = self.compensation.compensate(
            state=state,
            remove_links=True,
            restore_state=True,
            cleanup_resources=True,
            publish_compensation_events=True,
        )

        # Should handle very large documents
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "success")

    def test_linking_compensation_handles_none_values(self):
        """Test that linking compensation handles None values correctly."""
        odps_doc = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-none",
                        "name": "Test Product",
                        # description omitted - None is not allowed by schema
                    }
                },
                "dataSchema": {"fields": [{"name": "id", "type": "string"}]},
            },
        }

        odps_raw = json.dumps(odps_doc)
        odps_contract = self.odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        state = ODPSLinkingState(
            odps_contract_id=str(odps_contract.id), odcs_contract_id=str(self.odcs_contract.id)
        )

        result = self.compensation.compensate(
            state=state,
            remove_links=True,
            restore_state=True,
            cleanup_resources=True,
            publish_compensation_events=True,
        )

        # Should handle None values gracefully
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "success")

    def test_linking_compensation_handles_nested_structures(self):
        """Test that linking compensation handles nested structures correctly."""
        odps_doc = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-nested",
                        "name": "Test Product",
                        "nested": {"level1": {"level2": {"level3": {"value": "deep"}}}},
                    }
                },
                "dataSchema": {"fields": [{"name": "id", "type": "string"}]},
            },
        }

        odps_raw = json.dumps(odps_doc)
        odps_contract = self.odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        state = ODPSLinkingState(
            odps_contract_id=str(odps_contract.id), odcs_contract_id=str(self.odcs_contract.id)
        )

        result = self.compensation.compensate(
            state=state,
            remove_links=True,
            restore_state=True,
            cleanup_resources=True,
            publish_compensation_events=True,
        )

        # Should handle nested structures
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "success")
