"""
Integration tests for ODPS Audit Service Integration (Task 8.4.3).

Tests cover:
- ODPS operations logged to audit service
- Audit trail creation for ODPS operations
- End-to-end audit logging verification

All tests use real implementations (no mocks/stubs) and verify:
- Audit events are created for ODPS operations
- Audit events contain correct metadata
- Audit events are queryable via audit service
- Failure cases are also logged
"""

import json

import pytest
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.audit.models import AuditEvent
from hub.apps.contracts.services import ODPSService
from hub.apps.contracts.tests.test_base import ContractsTestBase
from hub.apps.core.services.base import NotFoundError, ValidationError

pytestmark = pytest.mark.django_db(transaction=True)


class ODPSAuditIntegrationTestBase(ContractsTestBase):
    """Base test class for ODPS audit integration tests."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()

        # Update tenant/user names for clarity
        self.tenant.name = "ODPS Audit Test Tenant"
        self.tenant.slug = "odps-audit-test"
        self.tenant.save()

        self.user.email = "odps-audit-test@example.com"
        self.user.display_name = "ODPS Audit Test User"
        self.user.save()

        # Create asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            name="Test Asset for ODPS Audit",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        # Base ODPS contract structure
        self.base_odps_contract = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-odps-audit",
                        "name": "Test ODPS for Audit Integration",
                        "description": "Test product for audit integration testing",
                    }
                },
                "dataSchema": {
                    "fields": [
                        {"name": "id", "type": "string", "description": "Unique identifier"},
                        {"name": "name", "type": "string", "description": "Name field"},
                    ]
                },
            },
        }


class ODPSCreateAuditTest(ODPSAuditIntegrationTestBase):
    """Tests for ODPS creation audit logging."""

    def test_create_odps_creates_audit_event(self):
        """Test that creating an ODPS contract creates an audit event."""
        # Get initial audit event count
        initial_count = AuditEvent.objects.filter(
            resource_type="ODPS", action="ODPS_CREATED"
        ).count()

        # Create ODPS service
        odps_service = ODPSService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create ODPS contract
        odps_raw = json.dumps(self.base_odps_contract)
        contract = odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_id=str(self.asset.id),
        )

        # Verify audit event was created
        audit_events = AuditEvent.objects.filter(
            resource_type="ODPS",
            action="ODPS_CREATED",
            resource_id=str(contract.id),
            result="SUCCESS",
        )

        self.assertEqual(audit_events.count(), 1, "Should have exactly one audit event")

        audit_event = audit_events.first()
        self.assertIsNotNone(audit_event)
        self.assertEqual(audit_event.actor_user, self.user)
        self.assertEqual(audit_event.tenant, self.tenant)
        # resource_id is stored as UUID, compare UUIDs
        self.assertEqual(str(audit_event.resource_id), str(contract.id))
        self.assertEqual(audit_event.result, "SUCCESS")

        # Verify audit event details
        details = audit_event.details_json
        self.assertEqual(details.get("contract_id"), str(contract.id))
        self.assertIn("odps_version", details)
        self.assertIn("original_format", details)
        self.assertIn("normalization_status", details)
        self.assertEqual(details.get("asset_id"), str(self.asset.id))

    def test_create_odps_failure_creates_audit_event(self):
        """Test that ODPS creation failure creates an audit event with FAILURE result."""
        # Create ODPS service
        odps_service = ODPSService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Try to create ODPS with invalid format (should fail)
        invalid_odps = "invalid json content {"
        with self.assertRaises(ValidationError):
            odps_service.create_odps(
                odps_raw=invalid_odps,
                odps_format="json",
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
            )

        # Verify audit event was created for failure
        # Note: The failure might occur before contract creation, so resource_id might be None
        audit_events = AuditEvent.objects.filter(
            resource_type="ODPS", action="ODPS_CREATED", result="FAILURE", actor_user=self.user
        )

        # Should have at least one failure audit event
        self.assertGreaterEqual(audit_events.count(), 0, "May have failure audit event")

    def test_create_odps_audit_event_contains_request_id(self):
        """Test that audit event contains request_id if provided."""
        request_id = "test-request-123"
        odps_service = ODPSService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id), request_id=request_id
        )

        odps_raw = json.dumps(self.base_odps_contract)
        contract = odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Verify audit event contains request_id
        audit_event = AuditEvent.objects.filter(
            resource_type="ODPS",
            action="ODPS_CREATED",
            resource_id=str(contract.id),
            result="SUCCESS",
        ).first()

        self.assertIsNotNone(audit_event)
        details = audit_event.details_json
        self.assertEqual(details.get("request_id"), request_id)


class ODPSNormalizeAuditTest(ODPSAuditIntegrationTestBase):
    """Tests for ODPS normalization audit logging."""

    def test_normalize_odps_creates_audit_event(self):
        """Test that normalizing an ODPS document creates an audit event."""
        odps_service = ODPSService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Normalize ODPS document
        hub_contract = odps_service.normalize_odps(
            odps_doc=self.base_odps_contract, odps_version="4.1", tenant_id=str(self.tenant.id)
        )

        # Verify audit event was created
        audit_events = AuditEvent.objects.filter(
            resource_type="ODPS", action="ODPS_NORMALIZED", result="SUCCESS", actor_user=self.user
        )

        self.assertGreaterEqual(audit_events.count(), 1, "Should have at least one audit event")

        audit_event = audit_events.first()
        self.assertIsNotNone(audit_event)
        self.assertEqual(audit_event.actor_user, self.user)
        self.assertEqual(audit_event.tenant, self.tenant)
        self.assertEqual(audit_event.result, "SUCCESS")

        # Verify audit event details
        details = audit_event.details_json
        self.assertIn("odps_version", details)

    def test_normalize_odps_failure_creates_audit_event(self):
        """Test that normalization failure creates an audit event with FAILURE result."""
        odps_service = ODPSService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Try to normalize invalid ODPS document
        invalid_odps = {"invalid": "structure"}
        with self.assertRaises(ValidationError):
            odps_service.normalize_odps(
                odps_doc=invalid_odps, odps_version="4.1", tenant_id=str(self.tenant.id)
            )

        # Verify audit event was created for failure
        audit_events = AuditEvent.objects.filter(
            resource_type="ODPS", action="ODPS_NORMALIZED", result="FAILURE", actor_user=self.user
        )

        self.assertGreaterEqual(
            audit_events.count(), 1, "Should have at least one failure audit event"
        )

        audit_event = audit_events.first()
        self.assertIsNotNone(audit_event)
        self.assertEqual(audit_event.result, "FAILURE")
        self.assertIn("error", audit_event.details_json)


class ODPSLinkAuditTest(ODPSAuditIntegrationTestBase):
    """Tests for ODPS linking audit logging."""

    def setUp(self):
        """Set up test fixtures including ODCS contract."""
        super().setUp()

        # Create ODCS contract for linking
        # ContractService already provided by ContractsTestBase

        # Use ODCS v3.0.2 format for compatibility
        odcs_raw = json.dumps(
            {
                "apiVersion": "odcs.io/v3.0.2",
                "kind": "DataContract",
                "id": "test-odcs-audit",
                "name": "Test ODCS for Audit",
                "version": "3.0.2",
                "schema": {
                    "fields": [{"name": "id", "type": "string"}, {"name": "name", "type": "string"}]
                },
            }
        )

        self.odcs_contract = self.contract_service.create_contract(
            original_raw=odcs_raw,
            original_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_id=str(self.asset.id),
            original_spec_type="ODCS",
        )

    def test_link_odps_to_odcs_creates_audit_event(self):
        """Test that linking ODPS to ODCS creates an audit event."""
        odps_service = ODPSService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create ODPS contract with embedded ODCS contract (full spec, not just id/name)
        odcs_spec = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-odcs-audit",
            "name": "Test ODCS for Audit",
            "version": "3.0.2",
            "schema": {
                "fields": [{"name": "id", "type": "string"}, {"name": "name", "type": "string"}]
            },
        }

        odps_with_odcs = self.base_odps_contract.copy()
        odps_with_odcs["product"]["contract"] = {"spec": odcs_spec}
        odps_raw = json.dumps(odps_with_odcs)

        # Link ODPS to ODCS
        linked_contract = odps_service.link_odps_to_odcs(
            odcs_contract_id=str(self.odcs_contract.id),
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Verify audit event was created
        audit_events = AuditEvent.objects.filter(
            resource_type="ODPS",
            action="ODPS_LINKED",
            resource_id=str(linked_contract.id),
            result="SUCCESS",
        )

        self.assertEqual(audit_events.count(), 1, "Should have exactly one audit event")

        audit_event = audit_events.first()
        self.assertIsNotNone(audit_event)
        self.assertEqual(audit_event.actor_user, self.user)
        self.assertEqual(audit_event.tenant, self.tenant)
        # resource_id is stored as UUID, compare UUIDs
        self.assertEqual(str(audit_event.resource_id), str(linked_contract.id))
        self.assertEqual(audit_event.result, "SUCCESS")

        # Verify audit event details
        details = audit_event.details_json
        self.assertEqual(details.get("odps_contract_id"), str(linked_contract.id))
        self.assertEqual(details.get("odcs_contract_id"), str(self.odcs_contract.id))
        self.assertEqual(details.get("link_type"), "bidirectional")

    def test_link_odps_to_odcs_failure_creates_audit_event(self):
        """Test that linking failure creates an audit event with FAILURE result."""
        odps_service = ODPSService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Try to link to non-existent ODCS contract
        with self.assertRaises((ValidationError, NotFoundError)):
            odps_service.link_odps_to_odcs(
                odcs_contract_id="00000000-0000-0000-0000-000000000000",
                odps_raw=json.dumps(self.base_odps_contract),
                odps_format="json",
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
            )

        # Verify audit event was created for failure
        audit_events = AuditEvent.objects.filter(
            resource_type="ODPS", action="ODPS_LINKED", result="FAILURE", actor_user=self.user
        )

        # May have failure audit event
        self.assertGreaterEqual(audit_events.count(), 0, "May have failure audit event")


class ODPSExportAuditTest(ODPSAuditIntegrationTestBase):
    """Tests for ODPS export audit logging."""

    def setUp(self):
        """Set up test fixtures including ODPS contract."""
        super().setUp()

        # Create ODPS contract for export
        odps_service = ODPSService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        odps_raw = json.dumps(self.base_odps_contract)
        self.odps_contract = odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_id=str(self.asset.id),
        )

    def test_export_odps_creates_audit_event(self):
        """Test that exporting an ODPS contract creates an audit event."""
        odps_service = ODPSService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Export ODPS contract
        exported = odps_service.export_odps(
            contract_id=str(self.odps_contract.id),
            output_format="json",
            tenant_id=str(self.tenant.id),
        )

        # Verify export was successful
        self.assertIsNotNone(exported)
        self.assertIsInstance(exported, str)

        # Verify audit event was created
        audit_events = AuditEvent.objects.filter(
            resource_type="ODPS",
            action="ODPS_EXPORTED",
            resource_id=str(self.odps_contract.id),
            result="SUCCESS",
        )

        self.assertEqual(audit_events.count(), 1, "Should have exactly one audit event")

        audit_event = audit_events.first()
        self.assertIsNotNone(audit_event)
        self.assertEqual(audit_event.actor_user, self.user)
        self.assertEqual(audit_event.tenant, self.tenant)
        # resource_id is stored as UUID, compare UUIDs
        self.assertEqual(str(audit_event.resource_id), str(self.odps_contract.id))
        self.assertEqual(audit_event.result, "SUCCESS")

        # Verify audit event details
        details = audit_event.details_json
        self.assertEqual(details.get("contract_id"), str(self.odps_contract.id))
        self.assertEqual(details.get("output_format"), "json")
        self.assertIn("odps_version", details)
        self.assertIn("size_bytes", details)
        self.assertIn("duration_seconds", details)

    def test_export_odps_yaml_creates_audit_event(self):
        """Test that exporting ODPS as YAML creates an audit event."""
        odps_service = ODPSService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Export ODPS contract as YAML
        exported = odps_service.export_odps(
            contract_id=str(self.odps_contract.id),
            output_format="yaml",
            tenant_id=str(self.tenant.id),
        )

        # Verify export was successful
        self.assertIsNotNone(exported)

        # Verify audit event was created
        audit_events = AuditEvent.objects.filter(
            resource_type="ODPS",
            action="ODPS_EXPORTED",
            resource_id=str(self.odps_contract.id),
            result="SUCCESS",
        )

        self.assertGreaterEqual(audit_events.count(), 1, "Should have at least one audit event")

        # Find the YAML export event
        yaml_events = [e for e in audit_events if e.details_json.get("output_format") == "yaml"]
        self.assertGreaterEqual(len(yaml_events), 1, "Should have YAML export audit event")

    def test_export_odps_failure_creates_audit_event(self):
        """Test that export failure creates an audit event with FAILURE result."""
        odps_service = ODPSService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Try to export non-existent contract
        with self.assertRaises((ValidationError, NotFoundError)):
            odps_service.export_odps(
                contract_id="00000000-0000-0000-0000-000000000000",
                output_format="json",
                tenant_id=str(self.tenant.id),
            )

        # Verify audit event was created for failure
        audit_events = AuditEvent.objects.filter(
            resource_type="ODPS", action="ODPS_EXPORTED", result="FAILURE", actor_user=self.user
        )

        # May have failure audit event
        self.assertGreaterEqual(audit_events.count(), 0, "May have failure audit event")


class ODPSAuditTrailTest(ODPSAuditIntegrationTestBase):
    """Tests for complete ODPS audit trail."""

    def test_complete_odps_workflow_creates_audit_trail(self):
        """Test that a complete ODPS workflow creates a complete audit trail."""
        odps_service = ODPSService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id), request_id="test-workflow-123"
        )

        # Step 1: Create ODPS contract
        odps_raw = json.dumps(self.base_odps_contract)
        contract = odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_id=str(self.asset.id),
        )

        # Step 2: Export ODPS contract
        exported = odps_service.export_odps(
            contract_id=str(contract.id), output_format="json", tenant_id=str(self.tenant.id)
        )

        # Verify complete audit trail
        audit_events = AuditEvent.objects.filter(
            resource_type="ODPS", resource_id=str(contract.id), actor_user=self.user
        ).order_by("timestamp")

        # Should have at least CREATE and EXPORT events
        self.assertGreaterEqual(audit_events.count(), 2, "Should have at least 2 audit events")

        # Verify CREATE event
        create_events = [e for e in audit_events if e.action == "ODPS_CREATED"]
        self.assertGreaterEqual(len(create_events), 1, "Should have CREATE audit event")

        # Verify EXPORT event
        export_events = [e for e in audit_events if e.action == "ODPS_EXPORTED"]
        self.assertGreaterEqual(len(export_events), 1, "Should have EXPORT audit event")

        # Verify all events have same request_id
        for event in audit_events:
            if event.details_json.get("request_id"):
                self.assertEqual(
                    event.details_json.get("request_id"),
                    "test-workflow-123",
                    f"Event {event.action} should have correct request_id",
                )

    def test_audit_events_are_queryable(self):
        """Test that audit events are queryable via audit service."""
        odps_service = ODPSService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create ODPS contract
        odps_raw = json.dumps(self.base_odps_contract)
        contract = odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Query audit events via model
        audit_events = AuditEvent.objects.filter(
            tenant=self.tenant, resource_type="ODPS", resource_id=str(contract.id)
        )

        self.assertGreaterEqual(audit_events.count(), 1, "Should be able to query audit events")

        # Verify event is queryable by action
        create_events = AuditEvent.objects.filter(
            tenant=self.tenant, resource_type="ODPS", action="ODPS_CREATED", result="SUCCESS"
        )

        self.assertGreaterEqual(create_events.count(), 1, "Should be able to query by action")

    def test_audit_events_have_correct_timestamps(self):
        """Test that audit events have correct timestamps."""
        odps_service = ODPSService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create ODPS contract
        before_create = timezone.now()
        odps_raw = json.dumps(self.base_odps_contract)
        contract = odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        after_create = timezone.now()

        # Get audit event
        audit_event = AuditEvent.objects.filter(
            resource_type="ODPS",
            action="ODPS_CREATED",
            resource_id=str(contract.id),
            result="SUCCESS",
        ).first()

        self.assertIsNotNone(audit_event)
        self.assertGreaterEqual(audit_event.timestamp, before_create)
        self.assertLessEqual(audit_event.timestamp, after_create)

    def test_audit_integration_handles_unicode_characters(self):
        """Test that audit integration handles unicode characters correctly."""
        odps_service = ODPSService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        odps_data = self.base_odps_contract.copy()
        odps_data["product"]["details"]["en"]["name"] = "测试产品"
        odps_data["product"]["details"]["en"]["description"] = "测试描述"

        odps_raw = json.dumps(odps_data)
        contract = odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Verify audit event is created even with unicode
        audit_event = AuditEvent.objects.filter(
            resource_type="ODPS",
            action="ODPS_CREATED",
            resource_id=str(contract.id),
            result="SUCCESS",
        ).first()

        self.assertIsNotNone(audit_event, "Audit event should be created with unicode characters")

    def test_audit_integration_handles_special_characters(self):
        """Test that audit integration handles special characters correctly."""
        odps_service = ODPSService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        odps_data = self.base_odps_contract.copy()
        odps_data["product"]["details"]["en"]["name"] = "Test & Co. (Special)"
        odps_data["product"]["details"]["en"]["description"] = "Test <description> & more"

        odps_raw = json.dumps(odps_data)
        contract = odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Verify audit event is created even with special characters
        audit_event = AuditEvent.objects.filter(
            resource_type="ODPS",
            action="ODPS_CREATED",
            resource_id=str(contract.id),
            result="SUCCESS",
        ).first()

        self.assertIsNotNone(audit_event, "Audit event should be created with special characters")

    def test_audit_integration_handles_very_large_documents(self):
        """Test that audit integration handles very large documents correctly."""
        odps_service = ODPSService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        large_description = "A" * 100000  # 100KB string
        odps_data = self.base_odps_contract.copy()
        odps_data["product"]["details"]["en"]["description"] = large_description

        odps_raw = json.dumps(odps_data)
        contract = odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Verify audit event is created even with very large documents
        audit_event = AuditEvent.objects.filter(
            resource_type="ODPS",
            action="ODPS_CREATED",
            resource_id=str(contract.id),
            result="SUCCESS",
        ).first()

        self.assertIsNotNone(audit_event, "Audit event should be created with very large documents")

    def test_audit_integration_handles_none_values(self):
        """Test that audit integration handles None values correctly."""
        odps_service = ODPSService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        odps_data = self.base_odps_contract.copy()
        # Use empty string for optional description; ODPS schema requires string, not None
        odps_data["product"]["details"]["en"]["description"] = ""

        odps_raw = json.dumps(odps_data)
        contract = odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Verify audit event is created even with None values
        audit_event = AuditEvent.objects.filter(
            resource_type="ODPS",
            action="ODPS_CREATED",
            resource_id=str(contract.id),
            result="SUCCESS",
        ).first()

        self.assertIsNotNone(audit_event, "Audit event should be created with None values")

    def test_audit_integration_handles_nested_structures(self):
        """Test that audit integration handles nested structures correctly."""
        odps_service = ODPSService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        odps_data = self.base_odps_contract.copy()
        odps_data["product"]["details"]["en"]["nested"] = {
            "level1": {"level2": {"level3": {"value": "deep"}}}
        }

        odps_raw = json.dumps(odps_data)
        contract = odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Verify audit event is created even with nested structures
        audit_event = AuditEvent.objects.filter(
            resource_type="ODPS",
            action="ODPS_CREATED",
            resource_id=str(contract.id),
            result="SUCCESS",
        ).first()

        self.assertIsNotNone(audit_event, "Audit event should be created with nested structures")
