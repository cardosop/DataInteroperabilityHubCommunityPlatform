"""
Tests for Security Incident Detection and Response

Tests verify that:
1. Security incidents are detected from violations
2. Security incidents are stored correctly
3. Security incident API works correctly
4. Security incident resolution works correctly
"""

import uuid
from datetime import datetime, timedelta, timezone

from rest_framework import status

from hub.apps.contracts.models import SecurityAuditLog, SecurityIncident
from hub.apps.contracts.odps_security_logging import (
    SecurityEventType,
    SecurityIncidentDetector,
    SecurityLogger,
    SecuritySeverity,
    SecurityViolationLog,
    get_incident_detector,
    get_security_logger,
)
from hub.apps.contracts.tests.test_base import ContractsAPITestBase, ContractsTestBase
from hub.apps.users.models import User, UserStatus


class SecurityIncidentDetectionTest(ContractsTestBase):
    """Test security incident detection"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.security_logger = get_security_logger()
        self.incident_detector = get_incident_detector()

    def test_detect_rate_limit_abuse(self):
        """Test detection of rate limit abuse pattern"""
        tenant_id = str(self.tenant.id)
        user_id = str(self.user.id)

        # Create 10 rate limit violations (threshold)
        for i in range(10):
            violation_log = SecurityViolationLog(
                event_type=SecurityEventType.RATE_LIMIT_EXCEEDED.value,
                severity=SecuritySeverity.MEDIUM.value,
                timestamp=datetime.now(timezone.utc).isoformat(),
                violation_type="Rate Limit Exceeded",
                description=f"Rate limit exceeded {i}",
                tenant_id=tenant_id,
                user_id=user_id,
                metadata={"level": "global"},
            )
            self.security_logger.log_security_violation(
                event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
                severity=SecuritySeverity.MEDIUM,
                violation_type="Rate Limit Exceeded",
                description=f"Rate limit exceeded {i}",
                tenant_id=tenant_id,
                user_id=user_id,
                metadata={"level": "global"},
            )

        # Check that incident was created
        incidents = SecurityIncident.objects.filter(
            event_type=SecurityEventType.RATE_LIMIT_EXCEEDED.value, tenant=self.tenant
        )
        self.assertEqual(incidents.count(), 1)
        incident = incidents.first()
        self.assertEqual(incident.status, "OPEN")
        self.assertEqual(incident.severity, "HIGH")
        self.assertGreaterEqual(incident.violation_count, 10)

    def test_detect_path_traversal_pattern(self):
        """Test detection of path traversal attack pattern"""
        tenant_id = str(self.tenant.id)
        user_id = str(self.user.id)

        # Create 5 path traversal attempts (threshold)
        for i in range(5):
            self.security_logger.log_security_violation(
                event_type=SecurityEventType.PATH_TRAVERSAL,
                severity=SecuritySeverity.HIGH,
                violation_type="Path Traversal Attempt",
                description=f"Path traversal attempt {i}",
                attempted_path=f"../../../etc/passwd{i}",
                tenant_id=tenant_id,
                user_id=user_id,
            )

        # Check that incident was created
        incidents = SecurityIncident.objects.filter(
            event_type=SecurityEventType.PATH_TRAVERSAL.value, tenant=self.tenant
        )
        self.assertEqual(incidents.count(), 1)
        incident = incidents.first()
        self.assertEqual(incident.status, "OPEN")
        self.assertEqual(incident.severity, "HIGH")
        self.assertGreaterEqual(incident.violation_count, 5)

    def test_detect_url_violation_pattern(self):
        """Test detection of URL violation pattern"""
        tenant_id = str(self.tenant.id)
        user_id = str(self.user.id)

        # Create 3 URL violations (threshold)
        for i in range(3):
            self.security_logger.log_security_violation(
                event_type=SecurityEventType.URL_DENIED,
                severity=SecuritySeverity.HIGH,
                violation_type="URL Denied",
                description=f"URL denied {i}",
                attempted_url=f"https://malicious.com/{i}",
                tenant_id=tenant_id,
                user_id=user_id,
            )

        # Check that incident was created
        incidents = SecurityIncident.objects.filter(
            event_type=SecurityEventType.URL_DENIED.value, tenant=self.tenant
        )
        self.assertEqual(incidents.count(), 1)
        incident = incidents.first()
        self.assertEqual(incident.status, "OPEN")
        self.assertEqual(incident.severity, "HIGH")

    def test_detect_high_severity_violation(self):
        """Test detection of high severity violation pattern"""
        tenant_id = str(self.tenant.id)
        user_id = str(self.user.id)

        # Create 10 high severity violations (threshold)
        for i in range(10):
            self.security_logger.log_security_violation(
                event_type=SecurityEventType.SECURITY_VIOLATION,
                severity=SecuritySeverity.HIGH,
                violation_type="Security Violation",
                description=f"High severity violation {i}",
                tenant_id=tenant_id,
                user_id=user_id,
            )

        # Check that incident was created
        incidents = SecurityIncident.objects.filter(
            severity__in=["HIGH", "CRITICAL"], tenant=self.tenant
        )
        self.assertEqual(incidents.count(), 1)
        incident = incidents.first()
        self.assertEqual(incident.status, "OPEN")
        self.assertEqual(incident.severity, "CRITICAL")

    def test_incident_updates_existing(self):
        """Test that incidents are updated if they already exist"""
        tenant_id = str(self.tenant.id)
        user_id = str(self.user.id)

        # Create initial violations (10 to trigger incident creation)
        for i in range(10):
            self.security_logger.log_security_violation(
                event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
                severity=SecuritySeverity.MEDIUM,
                violation_type="Rate Limit Exceeded",
                description=f"Rate limit exceeded {i}",
                tenant_id=tenant_id,
                user_id=user_id,
                metadata={"level": "global"},
            )

        # Get the incident (should be created after 10 violations)
        incident = SecurityIncident.objects.filter(
            event_type=SecurityEventType.RATE_LIMIT_EXCEEDED.value, tenant=self.tenant
        ).first()
        self.assertIsNotNone(incident, "Incident should be created after 10 violations")
        initial_count = incident.violation_count

        # Create more violations (should update existing incident)
        for i in range(10, 15):
            self.security_logger.log_security_violation(
                event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
                severity=SecuritySeverity.MEDIUM,
                violation_type="Rate Limit Exceeded",
                description=f"Rate limit exceeded {i}",
                tenant_id=tenant_id,
                user_id=user_id,
                metadata={"level": "global"},
            )

        # Check that incident was updated, not duplicated
        incidents = SecurityIncident.objects.filter(
            event_type=SecurityEventType.RATE_LIMIT_EXCEEDED.value, tenant=self.tenant
        )
        self.assertEqual(incidents.count(), 1, "Should have only one incident")
        incident.refresh_from_db()
        self.assertGreater(
            incident.violation_count, initial_count, "Violation count should increase"
        )


class SecurityIncidentModelTest(ContractsTestBase):
    """Test SecurityIncident model"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.user.display_name = "Test User"
        self.user.save()

    def test_create_incident(self):
        """Test creating a security incident"""
        incident = SecurityIncident.objects.create(
            title="Test Incident",
            description="Test description",
            severity="HIGH",
            status="OPEN",
            event_type=SecurityEventType.PATH_TRAVERSAL.value,
            tenant=self.tenant,
            user=self.user,
            violation_count=5,
        )

        self.assertEqual(incident.title, "Test Incident")
        self.assertEqual(incident.severity, "HIGH")
        self.assertEqual(incident.status, "OPEN")
        self.assertEqual(incident.tenant, self.tenant)

    def test_resolve_incident(self):
        """Test resolving a security incident"""
        incident = SecurityIncident.objects.create(
            title="Test Incident",
            description="Test description",
            severity="HIGH",
            status="OPEN",
            event_type=SecurityEventType.PATH_TRAVERSAL.value,
            tenant=self.tenant,
            violation_count=5,
        )

        incident.resolve(resolved_by_user=self.user, resolution_notes="Resolved by test")

        self.assertEqual(incident.status, "RESOLVED")
        self.assertIsNotNone(incident.resolved_at)
        self.assertEqual(incident.resolved_by, self.user)
        self.assertEqual(incident.resolution_notes, "Resolved by test")


class SecurityIncidentAPITest(ContractsAPITestBase):
    """Test security incident API endpoints"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        self.user.display_name = "Test User"
        self.user.save()
        self.admin_user = User.objects.create_user(
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
            password="adminpass123",
            tenant=None,  # Platform admins may not have tenant
            status=UserStatus.ACTIVE,
            display_name="Admin User",
            is_platform_admin=True,
        )

        # Create test incidents
        self.incident1 = SecurityIncident.objects.create(
            title="Test Incident 1",
            description="Test description 1",
            severity="HIGH",
            status="OPEN",
            event_type=SecurityEventType.PATH_TRAVERSAL.value,
            tenant=self.tenant,
            violation_count=5,
        )
        self.incident2 = SecurityIncident.objects.create(
            title="Test Incident 2",
            description="Test description 2",
            severity="CRITICAL",
            status="OPEN",
            event_type=SecurityEventType.RATE_LIMIT_EXCEEDED.value,
            tenant=self.tenant,
            violation_count=10,
        )

    def test_list_incidents_authenticated(self):
        """Test listing incidents as authenticated user"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/v1/security/incidents/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data["results"]), 2)

    def test_list_incidents_filter_by_severity(self):
        """Test filtering incidents by severity"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/v1/security/incidents/?severity=HIGH")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for result in response.data["results"]:
            self.assertEqual(result["severity"], "HIGH")

    def test_list_incidents_filter_by_status(self):
        """Test filtering incidents by status"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/v1/security/incidents/?status=OPEN")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for result in response.data["results"]:
            self.assertEqual(result["status"], "OPEN")

    def test_list_incidents_filter_by_event_type(self):
        """Test filtering incidents by event type"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            f"/api/v1/security/incidents/?event_type={SecurityEventType.PATH_TRAVERSAL.value}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for result in response.data["results"]:
            self.assertEqual(result["event_type"], SecurityEventType.PATH_TRAVERSAL.value)

    def test_retrieve_incident(self):
        """Test retrieving a specific incident"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(f"/api/v1/security/incidents/{self.incident1.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.incident1.id))
        self.assertEqual(response.data["title"], "Test Incident 1")

    def test_resolve_incident_admin(self):
        """Test resolving an incident as admin"""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            f"/api/v1/security/incidents/{self.incident1.id}/resolve/",
            {"resolution_notes": "Resolved by admin"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "RESOLVED")
        self.assertIsNotNone(response.data["resolved_at"])
        self.assertEqual(response.data["resolution_notes"], "Resolved by admin")

        # Verify in database
        self.incident1.refresh_from_db()
        self.assertEqual(self.incident1.status, "RESOLVED")

    def test_resolve_incident_non_admin_forbidden(self):
        """Test that non-admin users cannot resolve incidents"""
        # Create a non-admin user (self.user is platform_admin from setUp)
        non_admin_user = User.objects.create_user(
            email=f"nonadmin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
            display_name="Non Admin",
            is_platform_admin=False,
        )
        self.client.force_authenticate(user=non_admin_user)
        response = self.client.post(
            f"/api/v1/security/incidents/{self.incident1.id}/resolve/",
            {"resolution_notes": "Attempted resolution"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_resolve_incident_unauthenticated(self):
        """Test that unauthenticated users cannot access incidents"""
        # Clear authentication (setUp authenticates self.user)
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/v1/security/incidents/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
