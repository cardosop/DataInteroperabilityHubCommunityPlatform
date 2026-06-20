"""
Access Certification Models and Service

Periodic access reviews and certification workflows.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

import structlog
from django.conf import settings
from django.db import models
from django.utils import timezone

logger = structlog.get_logger(__name__)


class AccessCertification(models.Model):
    """
    Model for access certifications and periodic reviews.
    """

    CERTIFICATION_STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("IN_PROGRESS", "In Progress"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("EXPIRED", "Expired"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="access_certifications",
        help_text="Tenant this certification belongs to",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="access_certifications",
        help_text="User being certified",
    )
    asset = models.ForeignKey(
        "assets.Asset",
        on_delete=models.CASCADE,
        related_name="access_certifications",
        null=True,
        blank=True,
        help_text="Asset access being certified (nullable for user-level certification)",
    )
    dataset = models.ForeignKey(
        "datasets.Dataset",
        on_delete=models.CASCADE,
        related_name="access_certifications",
        null=True,
        blank=True,
        help_text="Dataset access being certified (nullable)",
    )
    certification_type = models.CharField(
        max_length=50,
        choices=[
            ("USER_LEVEL", "User Level"),
            ("ASSET_LEVEL", "Asset Level"),
            ("DATASET_LEVEL", "Dataset Level"),
        ],
        help_text="Type of certification",
    )
    status = models.CharField(
        max_length=20,
        choices=CERTIFICATION_STATUS_CHOICES,
        default="PENDING",
        help_text="Certification status",
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="reviewed_certifications",
        null=True,
        blank=True,
        help_text="User reviewing this certification",
    )
    review_notes = models.TextField(null=True, blank=True, help_text="Review notes from certifier")
    expires_at = models.DateTimeField(help_text="Certification expiration date")
    certified_at = models.DateTimeField(
        null=True, blank=True, help_text="When certification was approved"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "access_certifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "user", "status"]),
            models.Index(fields=["tenant", "asset", "status"]),
            models.Index(fields=["tenant", "dataset", "status"]),
            models.Index(fields=["tenant", "expires_at"]),
            models.Index(fields=["status", "expires_at"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.certification_type} - {self.status}"

    def is_expired(self) -> bool:
        """Check if certification is expired"""
        return timezone.now() > self.expires_at

    def days_until_expiration(self) -> int:
        """Get days until expiration"""
        if self.is_expired():
            return 0
        delta = self.expires_at - timezone.now()
        return delta.days


class AccessCertificationService:
    """
    Service for access certification workflows.
    """

    DEFAULT_CERTIFICATION_PERIOD_DAYS = 90  # 3 months

    @staticmethod
    def create_certification(
        tenant_id: str,
        user_id: str,
        certification_type: str,
        asset_id: str | None = None,
        dataset_id: str | None = None,
        expires_in_days: int = DEFAULT_CERTIFICATION_PERIOD_DAYS,
    ) -> AccessCertification:
        """
        Create a new access certification.

        Args:
            tenant_id: Tenant UUID
            user_id: User UUID
            certification_type: Type of certification
            asset_id: Optional asset UUID
            dataset_id: Optional dataset UUID
            expires_in_days: Days until expiration (default: 90)

        Returns:
            AccessCertification instance
        """
        from django.contrib.auth import get_user_model

        from hub.apps.tenants.models import Tenant

        User = get_user_model()

        tenant = Tenant.objects.get(id=tenant_id)
        user = User.objects.get(id=user_id)

        expires_at = timezone.now() + timedelta(days=expires_in_days)

        certification = AccessCertification.objects.create(
            tenant=tenant,
            user=user,
            asset_id=asset_id,
            dataset_id=dataset_id,
            certification_type=certification_type,
            status="PENDING",
            expires_at=expires_at,
        )

        return certification

    @staticmethod
    def review_certification(
        certification_id: str, reviewer_id: str, status: str, review_notes: str | None = None
    ) -> AccessCertification:
        """
        Review and approve/reject a certification.

        Args:
            certification_id: Certification UUID
            reviewer_id: Reviewer user UUID
            status: New status ("APPROVED" or "REJECTED")
            review_notes: Optional review notes

        Returns:
            Updated AccessCertification instance
        """
        from django.contrib.auth import get_user_model

        User = get_user_model()

        certification = AccessCertification.objects.get(id=certification_id)
        reviewer = User.objects.get(id=reviewer_id)

        certification.reviewer = reviewer
        certification.status = status
        certification.review_notes = review_notes

        if status == "APPROVED":
            certification.certified_at = timezone.now()

        certification.save()

        return certification

    @staticmethod
    def get_expiring_certifications(
        tenant_id: str | None = None, days_ahead: int = 30
    ) -> list[AccessCertification]:
        """
        Get certifications expiring within specified days.

        Args:
            tenant_id: Optional tenant UUID filter
            days_ahead: Days ahead to check (default: 30)

        Returns:
            List of expiring certifications
        """
        query = AccessCertification.objects.filter(
            status="APPROVED",
            expires_at__lte=timezone.now() + timedelta(days=days_ahead),
            expires_at__gt=timezone.now(),
        )

        if tenant_id:
            query = query.filter(tenant_id=tenant_id)

        return list(query.order_by("expires_at"))

    @staticmethod
    def get_expired_certifications(tenant_id: str | None = None) -> list[AccessCertification]:
        """
        Get expired certifications.

        Args:
            tenant_id: Optional tenant UUID filter

        Returns:
            List of expired certifications
        """
        query = AccessCertification.objects.filter(
            status="APPROVED", expires_at__lte=timezone.now()
        )

        if tenant_id:
            query = query.filter(tenant_id=tenant_id)

        # Update status to EXPIRED
        expired = list(query)
        for cert in expired:
            cert.status = "EXPIRED"
            cert.save(update_fields=["status"])

        return expired

    @staticmethod
    def initiate_periodic_review(
        tenant_id: str, user_id: str, reviewer_id: str
    ) -> AccessCertification:
        """
        Initiate a periodic access review for a user.

        Args:
            tenant_id: Tenant UUID
            user_id: User UUID to review
            reviewer_id: Reviewer user UUID

        Returns:
            Created AccessCertification instance
        """
        # Create user-level certification
        certification = AccessCertificationService.create_certification(
            tenant_id=tenant_id, user_id=user_id, certification_type="USER_LEVEL"
        )

        # Assign reviewer
        certification.reviewer_id = reviewer_id
        certification.status = "IN_PROGRESS"
        certification.save(update_fields=["reviewer_id", "status"])

        return certification

    @staticmethod
    def get_certification_summary(tenant_id: str | None = None) -> dict[str, Any]:
        """
        Get certification summary statistics.

        Args:
            tenant_id: Optional tenant UUID filter

        Returns:
            Dictionary with certification summary
        """
        query = AccessCertification.objects.all()

        if tenant_id:
            query = query.filter(tenant_id=tenant_id)

        total = query.count()
        pending = query.filter(status="PENDING").count()
        in_progress = query.filter(status="IN_PROGRESS").count()
        approved = query.filter(status="APPROVED").count()
        rejected = query.filter(status="REJECTED").count()
        expired = query.filter(status="EXPIRED").count()

        # Get expiring soon (within 30 days)
        expiring_soon = AccessCertificationService.get_expiring_certifications(
            tenant_id=tenant_id, days_ahead=30
        )

        return {
            "total": total,
            "pending": pending,
            "in_progress": in_progress,
            "approved": approved,
            "rejected": rejected,
            "expired": expired,
            "expiring_soon": len(expiring_soon),
        }
