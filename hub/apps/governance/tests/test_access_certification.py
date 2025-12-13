"""
Unit tests for Access Certification

Tests for periodic access reviews and certification workflows.
"""
import pytest
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from hub.apps.governance.access_certification import (
    AccessCertificationService,
    AccessCertification
)
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


pytestmark = pytest.mark.django_db(transaction=True)


class AccessCertificationServiceTest(TestCase):
    """Test AccessCertificationService"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="UNVERIFIED"
        )
        
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        self.reviewer = User.objects.create_user(
            email="reviewer@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
    
    def test_create_certification(self):
        """Test certification creation"""
        certification = AccessCertificationService.create_certification(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            certification_type="USER_LEVEL",
            expires_in_days=90
        )
        
        self.assertIsNotNone(certification)
        self.assertEqual(certification.status, "PENDING")
        self.assertIsNotNone(certification.expires_at)
    
    def test_review_certification(self):
        """Test certification review"""
        certification = AccessCertificationService.create_certification(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            certification_type="USER_LEVEL"
        )
        
        updated = AccessCertificationService.review_certification(
            certification_id=str(certification.id),
            reviewer_id=str(self.reviewer.id),
            status="APPROVED",
            review_notes="User access approved"
        )
        
        self.assertEqual(updated.status, "APPROVED")
        self.assertIsNotNone(updated.certified_at)
        self.assertEqual(updated.review_notes, "User access approved")
    
    def test_get_expiring_certifications(self):
        """Test expiring certifications retrieval"""
        # Create certification expiring soon
        certification = AccessCertificationService.create_certification(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            certification_type="USER_LEVEL",
            expires_in_days=20
        )
        
        # Approve it
        AccessCertificationService.review_certification(
            certification_id=str(certification.id),
            reviewer_id=str(self.reviewer.id),
            status="APPROVED"
        )
        
        expiring = AccessCertificationService.get_expiring_certifications(
            tenant_id=str(self.tenant.id),
            days_ahead=30
        )
        
        self.assertGreater(len(expiring), 0)
        self.assertEqual(expiring[0].id, certification.id)
    
    def test_get_expired_certifications(self):
        """Test expired certifications retrieval"""
        # Create expired certification
        certification = AccessCertification.objects.create(
            tenant=self.tenant,
            user=self.user,
            certification_type="USER_LEVEL",
            status="APPROVED",
            expires_at=timezone.now() - timedelta(days=1)
        )
        
        expired = AccessCertificationService.get_expired_certifications(
            tenant_id=str(self.tenant.id)
        )
        
        self.assertGreater(len(expired), 0)
        # Status should be updated to EXPIRED
        certification.refresh_from_db()
        self.assertEqual(certification.status, "EXPIRED")
    
    def test_initiate_periodic_review(self):
        """Test periodic review initiation"""
        certification = AccessCertificationService.initiate_periodic_review(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            reviewer_id=str(self.reviewer.id)
        )
        
        self.assertIsNotNone(certification)
        self.assertEqual(certification.status, "IN_PROGRESS")
        self.assertEqual(certification.reviewer.id, self.reviewer.id)
    
    def test_get_certification_summary(self):
        """Test certification summary"""
        # Create some certifications
        for i in range(3):
            AccessCertificationService.create_certification(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                certification_type="USER_LEVEL"
            )
        
        summary = AccessCertificationService.get_certification_summary(
            tenant_id=str(self.tenant.id)
        )
        
        self.assertIn("total", summary)
        self.assertIn("pending", summary)
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["pending"], 3)

