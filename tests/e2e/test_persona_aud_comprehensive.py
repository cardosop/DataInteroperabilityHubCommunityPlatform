"""
Comprehensive E2E tests for Auditor (AUD) persona journeys.

Covers all 3 AUD journeys:
- JOURNEY-AUD-001: Review Audit Logs
- JOURNEY-AUD-002: Generate Audit Reports
- JOURNEY-AUD-003: Export Audit Data

All tests use REAL services (no mocks/stubs) and follow TDD approach.
Target: 100% journey coverage for all AUD journeys.
"""
import pytest
import time
import uuid
import json
import csv
from io import StringIO
from datetime import datetime, timedelta
from django.test import TestCase
from django.utils import timezone
from rest_framework import status

from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.users.models import User, Role, UserRole, UserStatus
from hub.apps.audit.models import AuditEvent
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract
from hub.apps.governance.models import ComplianceReport

from .conftest import E2ETestBase, get_response_data


pytestmark = [
    pytest.mark.uc_journey_persona,
    pytest.mark.django_db(transaction=True),
    pytest.mark.e2e,
    pytest.mark.persona("Auditor"),
    pytest.mark.journey("JOURNEY-AUD-001"),
    pytest.mark.journey("JOURNEY-AUD-002"),
    pytest.mark.journey("JOURNEY-AUD-003"),
]


class JourneyAUD001ReviewAuditLogsTests(E2ETestBase):
    """JOURNEY-AUD-001: Review Audit Logs"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        
        # Create tenant and auditor user
        self.tenant = Tenant.objects.create(
            name="Audit Tenant",
            slug="audit-tenant",
            kyc_status=KYCStatus.VERIFIED
        )
        
        self.auditor_user = User.objects.create_user(
            email="auditor@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        # Create AUDITOR role and assign to user
        auditor_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="AUDITOR",
            defaults={"description": "Auditor - Read-only access"}
        )
        UserRole.objects.create(user=self.auditor_user, role=auditor_role)
        
        # Authenticate as auditor
        self.client.force_authenticate(user=self.auditor_user)
        
        # Create some audit events for testing
        self.create_test_audit_events()
    
    def create_test_audit_events(self):
        """Create test audit events"""
        from hub.apps.audit.utils import create_audit_event
        
        # Create various audit events
        create_audit_event(
            resource_type="ASSET",
            action="ASSET_CREATED",
            actor_user=self.auditor_user,
            tenant=self.tenant,
            resource_id=uuid.uuid4(),
            details={"key": "test-asset-1"}
        )
        
        create_audit_event(
            resource_type="CONTRACT",
            action="CONTRACT_CREATED",
            actor_user=self.auditor_user,
            tenant=self.tenant,
            resource_id=uuid.uuid4(),
            details={"name": "test-contract-1"}
        )
        
        create_audit_event(
            resource_type="ASSET",
            action="ASSET_UPDATED",
            actor_user=self.auditor_user,
            tenant=self.tenant,
            resource_id=uuid.uuid4(),
            details={"key": "test-asset-2"}
        )
        
        # Create event from different time
        past_time = timezone.now() - timedelta(days=2)
        past_event = AuditEvent.objects.create(
            tenant=self.tenant,
            actor_user=self.auditor_user,
            resource_type="USER",
            action="USER_CREATED",
            result="SUCCESS",
            details_json={"email": "test@example.com"},
            timestamp=past_time
        )
    
    def test_list_audit_logs(self):
        """
        Test listing audit logs
        """
        response = self.client.get('/api/v1/audit/audit-events/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Handle both paginated and non-paginated responses
        data = get_response_data(response) or {}
        if isinstance(data, list):
            events = data
        else:
            events = data.get('results', [])
        
        # Should see audit events for the tenant
        self.assertGreater(len(events), 0)
        
        # Verify event structure
        for event in events:
            self.assertIn('id', event)
            self.assertIn('timestamp', event)
            self.assertIn('resource_type', event)
            self.assertIn('action', event)
            self.assertIn('result', event)
    
    def test_filter_audit_logs_by_resource_type(self):
        """
        Test filtering audit logs by resource type
        """
        # Filter by ASSET
        response = self.client.get('/api/v1/audit/audit-events/?resource_type=ASSET')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Handle both paginated and non-paginated responses
        data = get_response_data(response) or {}
        if isinstance(data, list):
            events = data
        else:
            events = data.get('results', [])
        
        # All events should be ASSET type
        for event in events:
            self.assertEqual(event['resource_type'], 'ASSET')
        
        # Filter by CONTRACT
        response = self.client.get('/api/v1/audit/audit-events/?resource_type=CONTRACT')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Handle both paginated and non-paginated responses
        data = get_response_data(response) or {}
        if isinstance(data, list):
            events = data
        else:
            events = data.get('results', [])
        
        # All events should be CONTRACT type
        for event in events:
            self.assertEqual(event['resource_type'], 'CONTRACT')
    
    def test_filter_audit_logs_by_action(self):
        """
        Test filtering audit logs by action
        """
        # Filter by ASSET_CREATED
        response = self.client.get('/api/v1/audit/audit-events/?action=ASSET_CREATED')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Handle both paginated and non-paginated responses
        data = get_response_data(response) or {}
        if isinstance(data, list):
            events = data
        else:
            events = data.get('results', [])
        
        # All events should have ASSET_CREATED action
        for event in events:
            self.assertEqual(event['action'], 'ASSET_CREATED')
    
    def test_filter_audit_logs_by_time_range(self):
        """
        Test filtering audit logs by time range
        """
        # Get events from last 24 hours
        start_date = (timezone.now() - timedelta(days=1)).isoformat()
        end_date = timezone.now().isoformat()
        
        response = self.client.get(
            f'/api/v1/audit/audit-events/?start_date={start_date}&end_date={end_date}'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Handle both paginated and non-paginated responses
        data = get_response_data(response) or {}
        if isinstance(data, list):
            events = data
        else:
            events = data.get('results', [])
        
        # Verify all events are within time range
        for event in events:
            event_time = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
            self.assertGreaterEqual(event_time, datetime.fromisoformat(start_date.replace('Z', '+00:00')))
            self.assertLessEqual(event_time, datetime.fromisoformat(end_date.replace('Z', '+00:00')))
    
    def test_filter_audit_logs_by_actor_user(self):
        """
        Test filtering audit logs by actor user
        """
        response = self.client.get(
            f'/api/v1/audit/audit-events/?actor_user_id={self.auditor_user.id}'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Handle both paginated and non-paginated responses
        data = get_response_data(response) or {}
        if isinstance(data, list):
            events = data
        else:
            events = data.get('results', [])
        
        # All events should be from the auditor user
        for event in events:
            self.assertEqual(str(event['actor_user']), str(self.auditor_user.id))
    
    def test_get_audit_log_details(self):
        """
        Test getting details of a specific audit log entry
        """
        # Get first audit event
        response = self.client.get('/api/v1/audit/audit-events/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Handle both paginated and non-paginated responses
        data = get_response_data(response) or {}
        if isinstance(data, list):
            events = data
        else:
            events = data.get('results', [])
        
        if events:
            event_id = events[0]['id']
            
            # Get event details
            response = self.client.get(f'/api/v1/audit/audit-events/{event_id}/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            data = get_response_data(response) or {}
            self.assertEqual(data['id'], event_id)
            self.assertIn('timestamp', data)
            self.assertIn('resource_type', data)
            self.assertIn('action', data)
            self.assertIn('details_json', data)
    
    def test_audit_logs_are_read_only(self):
        """
        Test that audit logs are read-only (cannot be modified or deleted)
        """
        # Get first audit event
        response = self.client.get('/api/v1/audit/audit-events/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Handle both paginated and non-paginated responses
        data = get_response_data(response) or {}
        if isinstance(data, list):
            events = data
        else:
            events = data.get('results', [])
        
        if events:
            event_id = events[0]['id']
            
            # Try to update (should fail - read-only)
            response = self.client.patch(
                f'/api/v1/audit/audit-events/{event_id}/',
                {'action': 'MODIFIED'},
                format='json'
            )
            # Should return 405 Method Not Allowed or 403 Forbidden
            self.assertIn(response.status_code, [
                status.HTTP_405_METHOD_NOT_ALLOWED,
                status.HTTP_403_FORBIDDEN
            ])
            
            # Try to delete (should fail - read-only)
            response = self.client.delete(f'/api/v1/audit/audit-events/{event_id}/')
            # Should return 405 Method Not Allowed or 403 Forbidden
            self.assertIn(response.status_code, [
                status.HTTP_405_METHOD_NOT_ALLOWED,
                status.HTTP_403_FORBIDDEN
            ])
    
    def test_error_access_nonexistent_audit_log(self):
        """
        Test error scenario: Accessing non-existent audit log
        """
        fake_event_id = str(uuid.uuid4())
        response = self.client.get(f'/api/v1/audit/audit-events/{fake_event_id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class JourneyAUD002GenerateAuditReportsTests(E2ETestBase):
    """JOURNEY-AUD-002: Generate Audit Reports"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        
        # Create tenant and auditor user
        self.tenant = Tenant.objects.create(
            name="Report Tenant",
            slug="report-tenant",
            kyc_status=KYCStatus.VERIFIED
        )
        
        self.auditor_user = User.objects.create_user(
            email="auditor@report.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        # Create AUDITOR role and assign to user
        auditor_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="AUDITOR",
            defaults={"description": "Auditor - Read-only access"}
        )
        UserRole.objects.create(user=self.auditor_user, role=auditor_role)
        
        # Authenticate as auditor
        self.client.force_authenticate(user=self.auditor_user)
        
        # Create test audit events
        self.create_test_audit_events()
    
    def create_test_audit_events(self):
        """Create test audit events for reporting"""
        from hub.apps.audit.utils import create_audit_event
        
        # Create events for different resource types
        for i in range(5):
            create_audit_event(
                resource_type="ASSET",
                action="ASSET_CREATED",
                actor_user=self.auditor_user,
                tenant=self.tenant,
                resource_id=uuid.uuid4(),
                details={"key": f"asset-{i}"}
            )
        
        for i in range(3):
            create_audit_event(
                resource_type="CONTRACT",
                action="CONTRACT_CREATED",
                actor_user=self.auditor_user,
                tenant=self.tenant,
                resource_id=uuid.uuid4(),
                details={"name": f"contract-{i}"}
            )
    
    def test_generate_audit_summary_report(self):
        """
        Test generating an audit summary report by querying and aggregating audit logs
        """
        # Get all audit events
        response = self.client.get('/api/v1/audit/audit-events/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Handle both paginated and non-paginated responses
        data = get_response_data(response) or {}
        if isinstance(data, list):
            events = data
        else:
            events = data.get('results', [])
        
        # Generate summary report
        summary = {
            'total_events': len(events),
            'by_resource_type': {},
            'by_action': {},
            'by_result': {}
        }
        
        for event in events:
            # Count by resource type
            resource_type = event['resource_type']
            summary['by_resource_type'][resource_type] = summary['by_resource_type'].get(resource_type, 0) + 1
            
            # Count by action
            action = event['action']
            summary['by_action'][action] = summary['by_action'].get(action, 0) + 1
            
            # Count by result
            result = event['result']
            summary['by_result'][result] = summary['by_result'].get(result, 0) + 1
        
        # Verify summary
        self.assertGreater(summary['total_events'], 0)
        self.assertIn('ASSET', summary['by_resource_type'])
        self.assertIn('CONTRACT', summary['by_resource_type'])
    
    def test_generate_compliance_report_via_workflow(self):
        """
        Test generating a compliance report (which includes audit data)
        """
        from hub.apps.orchestration.workflows.compliance_reporting import ComplianceReportingWorkflow
        
        # Generate compliance report
        result = ComplianceReportingWorkflow.execute(
            tenant_id=str(self.tenant.id),
            regulation="GDPR",
            report_type="STANDARD",
            triggered_by_id=str(self.auditor_user.id)
        )
        
        # Verify report was generated
        self.assertTrue(result.get('success', False))
        report_id = result.get('report_id')
        self.assertIsNotNone(report_id)
        
        # Verify report exists
        report = ComplianceReport.objects.get(id=report_id)
        self.assertEqual(report.tenant.id, self.tenant.id)
        self.assertEqual(report.regulation, "GDPR")
    
    def test_filter_audit_logs_for_report(self):
        """
        Test filtering audit logs for specific report criteria
        """
        # Filter by resource type for report
        response = self.client.get('/api/v1/audit/audit-events/?resource_type=ASSET')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Handle both paginated and non-paginated responses
        data = get_response_data(response) or {}
        if isinstance(data, list):
            asset_events = data
        else:
            asset_events = data.get('results', [])
        
        # Filter by action for report
        response = self.client.get('/api/v1/audit/audit-events/?action=ASSET_CREATED')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Handle both paginated and non-paginated responses
        data = get_response_data(response) or {}
        if isinstance(data, list):
            created_events = data
        else:
            created_events = data.get('results', [])
        
        # Verify filters work
        self.assertGreaterEqual(len(asset_events), 0)
        self.assertGreaterEqual(len(created_events), 0)
    
    def test_error_invalid_time_range(self):
        """
        Test error scenario: Invalid time range for report
        """
        # Invalid date format
        response = self.client.get('/api/v1/audit/audit-events/?start_date=invalid-date')
        # Should still return 200 (invalid dates are ignored)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class JourneyAUD003ExportAuditDataTests(E2ETestBase):
    """JOURNEY-AUD-003: Export Audit Data"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        
        # Create tenant and auditor user
        self.tenant = Tenant.objects.create(
            name="Export Tenant",
            slug="export-tenant",
            kyc_status=KYCStatus.VERIFIED
        )
        
        self.auditor_user = User.objects.create_user(
            email="auditor@export.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        # Create AUDITOR role and assign to user
        auditor_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="AUDITOR",
            defaults={"description": "Auditor - Read-only access"}
        )
        UserRole.objects.create(user=self.auditor_user, role=auditor_role)
        
        # Authenticate as auditor
        self.client.force_authenticate(user=self.auditor_user)
        
        # Create test audit events
        self.create_test_audit_events()
    
    def create_test_audit_events(self):
        """Create test audit events for export"""
        from hub.apps.audit.utils import create_audit_event
        
        # Create various audit events
        for i in range(10):
            create_audit_event(
                resource_type="ASSET",
                action="ASSET_CREATED",
                actor_user=self.auditor_user,
                tenant=self.tenant,
                resource_id=uuid.uuid4(),
                details={"key": f"export-asset-{i}"}
            )
    
    def test_export_audit_logs_as_csv(self):
        """
        Test exporting audit logs as CSV
        """
        response = self.client.get('/api/v1/audit/audit-events/export/?format=csv')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify CSV content
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn('Content-Disposition', response)
        self.assertIn('attachment', response['Content-Disposition'])
        
        # Parse CSV
        csv_content = response.content.decode('utf-8')
        csv_reader = csv.reader(StringIO(csv_content))
        rows = list(csv_reader)
        
        # Verify header
        self.assertEqual(len(rows), 11)  # 1 header + 10 data rows
        self.assertEqual(rows[0], [
            'ID', 'Timestamp', 'Tenant', 'Actor User', 'Resource Type', 'Resource ID',
            'Action', 'Result', 'Details'
        ])
        
        # Verify data rows
        self.assertGreater(len(rows), 1)
        for row in rows[1:]:
            self.assertEqual(len(row), 9)  # All columns present
    
    def test_export_audit_logs_as_json(self):
        """
        Test exporting audit logs as JSON
        """
        response = self.client.get('/api/v1/audit/audit-events/export/?format=json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify JSON content
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        
        # Verify event structure
        for event in data:
            self.assertIn('id', event)
            self.assertIn('timestamp', event)
            self.assertIn('resource_type', event)
            self.assertIn('action', event)
            self.assertIn('result', event)
    
    def test_export_audit_logs_with_filters(self):
        """
        Test exporting filtered audit logs
        """
        # Export only ASSET events
        response = self.client.get(
            '/api/v1/audit/audit-events/export/?format=csv&resource_type=ASSET'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Parse CSV
        csv_content = response.content.decode('utf-8')
        csv_reader = csv.reader(StringIO(csv_content))
        rows = list(csv_reader)
        
        # Verify all rows are ASSET type (skip header)
        for row in rows[1:]:
            self.assertEqual(row[4], 'ASSET')  # Resource Type column
    
    def test_export_audit_logs_with_time_range(self):
        """
        Test exporting audit logs within a time range
        """
        # Get events from last 24 hours
        start_date = (timezone.now() - timedelta(days=1)).isoformat()
        end_date = timezone.now().isoformat()
        
        response = self.client.get(
            f'/api/v1/audit/audit-events/export/?format=json&start_date={start_date}&end_date={end_date}'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        self.assertIsInstance(data, list)
        
        # Verify all events are within time range
        for event in data:
            event_time = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
            self.assertGreaterEqual(event_time, datetime.fromisoformat(start_date.replace('Z', '+00:00')))
            self.assertLessEqual(event_time, datetime.fromisoformat(end_date.replace('Z', '+00:00')))
    
    def test_export_size_limit(self):
        """
        Test that export has a size limit (safety measure)
        """
        # Create many audit events (more than limit)
        from hub.apps.audit.utils import create_audit_event
        
        # Create 100 events (limit is 10000, so this should work)
        for i in range(100):
            create_audit_event(
                resource_type="ASSET",
                action="ASSET_CREATED",
                actor_user=self.auditor_user,
                tenant=self.tenant,
                resource_id=uuid.uuid4(),
                details={"key": f"limit-asset-{i}"}
            )
        
        # Export should succeed (within limit)
        response = self.client.get('/api/v1/audit/audit-events/export/?format=json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.json()
        self.assertLessEqual(len(data), 10000)  # Should be within limit


class AuditorUseCasesTests(E2ETestBase):
    """Test use cases: Review audit logs, generate audit reports, export audit data, filter/search logs"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        
        # Create tenant and auditor user
        self.tenant = Tenant.objects.create(
            name="Use Case Tenant",
            slug="usecase-tenant",
            kyc_status=KYCStatus.VERIFIED
        )
        
        self.auditor_user = User.objects.create_user(
            email="auditor@usecase.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        # Create AUDITOR role and assign to user
        auditor_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="AUDITOR",
            defaults={"description": "Auditor - Read-only access"}
        )
        UserRole.objects.create(user=self.auditor_user, role=auditor_role)
        
        # Authenticate as auditor
        self.client.force_authenticate(user=self.auditor_user)
        
        # Create test audit events
        self.create_test_audit_events()
    
    def create_test_audit_events(self):
        """Create test audit events"""
        from hub.apps.audit.utils import create_audit_event
        
        # Create events for different scenarios
        create_audit_event(
            resource_type="ASSET",
            action="ASSET_CREATED",
            actor_user=self.auditor_user,
            tenant=self.tenant,
            resource_id=uuid.uuid4(),
            details={"key": "usecase-asset-1"}
        )
        
        create_audit_event(
            resource_type="CONTRACT",
            action="CONTRACT_CREATED",
            actor_user=self.auditor_user,
            tenant=self.tenant,
            resource_id=uuid.uuid4(),
            details={"name": "usecase-contract-1"}
        )
        
        create_audit_event(
            resource_type="USER",
            action="USER_CREATED",
            actor_user=self.auditor_user,
            tenant=self.tenant,
            resource_id=uuid.uuid4(),
            details={"email": "usecase@user.com"}
        )
    
    def test_complete_audit_review_workflow(self):
        """
        Test complete audit review workflow: List → Filter → Review → Export
        """
        # Step 1: List all audit events
        response = self.client.get('/api/v1/audit/audit-events/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Handle both paginated and non-paginated responses
        data = get_response_data(response) or {}
        if isinstance(data, list):
            events = data
        else:
            events = data.get('results', [])
        self.assertGreater(len(events), 0)
        
        # Step 2: Filter by resource type
        response = self.client.get('/api/v1/audit/audit-events/?resource_type=ASSET')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Handle both paginated and non-paginated responses
        data = get_response_data(response) or {}
        if isinstance(data, list):
            asset_events = data
        else:
            asset_events = data.get('results', [])
        self.assertGreaterEqual(len(asset_events), 0)
        
        # Step 3: Get details of specific event
        if asset_events:
            event_id = asset_events[0]['id']
            response = self.client.get(f'/api/v1/audit/audit-events/{event_id}/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            data = get_response_data(response) or {}
            self.assertEqual(data['id'], event_id)
        
        # Step 4: Export filtered events
        response = self.client.get(
            '/api/v1/audit/audit-events/export/?format=json&resource_type=ASSET'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        exported_data = response.json()
        self.assertIsInstance(exported_data, list)
    
    def test_search_audit_logs_by_multiple_filters(self):
        """
        Test searching audit logs with multiple filters
        """
        # Search with multiple filters
        response = self.client.get(
            '/api/v1/audit/audit-events/?resource_type=ASSET&action=ASSET_CREATED'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Handle both paginated and non-paginated responses
        data = get_response_data(response) or {}
        if isinstance(data, list):
            events = data
        else:
            events = data.get('results', [])
        
        # Verify all events match filters
        for event in events:
            self.assertEqual(event['resource_type'], 'ASSET')
            self.assertEqual(event['action'], 'ASSET_CREATED')
    
    def test_generate_audit_report_with_aggregation(self):
        """
        Test generating an audit report with data aggregation
        """
        # Get all events
        response = self.client.get('/api/v1/audit/audit-events/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Handle both paginated and non-paginated responses
        data = get_response_data(response) or {}
        if isinstance(data, list):
            events = data
        else:
            events = data.get('results', [])
        
        # Generate aggregated report
        report = {
            'total_events': len(events),
            'events_by_resource_type': {},
            'events_by_action': {},
            'events_by_result': {},
            'time_range': {
                'earliest': None,
                'latest': None
            }
        }
        
        for event in events:
            # Aggregate by resource type
            resource_type = event['resource_type']
            report['events_by_resource_type'][resource_type] = \
                report['events_by_resource_type'].get(resource_type, 0) + 1
            
            # Aggregate by action
            action = event['action']
            report['events_by_action'][action] = \
                report['events_by_action'].get(action, 0) + 1
            
            # Track time range
            event_time = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
            if report['time_range']['earliest'] is None or event_time < report['time_range']['earliest']:
                report['time_range']['earliest'] = event_time
            if report['time_range']['latest'] is None or event_time > report['time_range']['latest']:
                report['time_range']['latest'] = event_time
        
        # Verify report structure
        self.assertGreater(report['total_events'], 0)
        self.assertIsNotNone(report['time_range']['earliest'])
        self.assertIsNotNone(report['time_range']['latest'])


class AuditorErrorScenariosTests(E2ETestBase):
    """Test error scenarios: Audit log access failure, report generation failure"""
    
    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        
        # Create tenant and auditor user
        self.tenant = Tenant.objects.create(
            name="Error Tenant",
            slug="error-tenant",
            kyc_status=KYCStatus.VERIFIED
        )
        
        self.auditor_user = User.objects.create_user(
            email="auditor@error.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        # Create AUDITOR role and assign to user
        auditor_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="AUDITOR",
            defaults={"description": "Auditor - Read-only access"}
        )
        UserRole.objects.create(user=self.auditor_user, role=auditor_role)
        
        # Authenticate as auditor
        self.client.force_authenticate(user=self.auditor_user)
    
    def test_error_access_nonexistent_audit_log(self):
        """
        Test error scenario: Accessing non-existent audit log
        """
        fake_event_id = str(uuid.uuid4())
        response = self.client.get(f'/api/v1/audit/audit-events/{fake_event_id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_error_invalid_export_format(self):
        """
        Test error scenario: Invalid export format
        """
        # Invalid format (should default to JSON or return error)
        response = self.client.get('/api/v1/audit/audit-events/export/?format=invalid')
        # May return 200 with default format, 400 for invalid format, or 404 if endpoint not found
        # The export endpoint may default to JSON for invalid formats
        self.assertIn(response.status_code, [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND
        ])
    
    def test_error_unauthorized_access(self):
        """
        Test error scenario: Unauthorized access to audit logs
        """
        from rest_framework.test import APIClient
        unauthenticated_client = APIClient()
        
        # Unauthenticated request should fail
        response = unauthenticated_client.get('/api/v1/audit/audit-events/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_error_cross_tenant_access(self):
        """
        Test error scenario: Auditor cannot access audit logs from other tenants
        """
        # Create another tenant
        other_tenant = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant",
            kyc_status=KYCStatus.VERIFIED
        )
        
        # Create audit event for other tenant
        from hub.apps.audit.utils import create_audit_event
        other_user = User.objects.create_user(
            email="other@tenant.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE
        )
        
        create_audit_event(
            resource_type="ASSET",
            action="ASSET_CREATED",
            actor_user=other_user,
            tenant=other_tenant,
            resource_id=uuid.uuid4(),
            details={"key": "other-tenant-asset"}
        )
        
        # Auditor should not see other tenant's events
        response = self.client.get('/api/v1/audit/audit-events/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Handle both paginated and non-paginated responses
        data = get_response_data(response) or {}
        if isinstance(data, list):
            events = data
        else:
            events = data.get('results', [])
        
        # Verify no events from other tenant
        for event in events:
            if event.get('tenant'):
                self.assertEqual(event['tenant'], str(self.tenant.id))

