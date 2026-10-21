"""
Phase 277.2.5 (P0-3) — UserBusinessRules tests.

Validates ``UserBusinessRules.validate_user_creation()`` across
valid inputs, duplicate email, missing tenant, invalid status,
weak password, role tenant mismatch, and invitation expiry.
"""

from __future__ import annotations

import uuid

import pytest
from django.test import TestCase

from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.business_rules import UserBusinessRules
from hub.apps.users.models import Role, User


@pytest.mark.django_db(transaction=True)
@pytest.mark.integration
class TestUserBusinessRules(TestCase):
    """UserBusinessRules.validate_user_creation() contract tests."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"UBR-{uid}",
            slug=f"ubr-{uid}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )
        # Disable OTel metrics/tracing so the instance is picklable
        # (setUpTestData deepcopies class attributes, and OTel meter
        # objects hold _thread.RLock instances that can't be pickled).
        self.rules = UserBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=None,
            enable_metrics=False,
            enable_tracing=False,
        )
        self.valid_email = f"valid-{uid}@example.com"
        self.valid_password = "securepass123"

    # ── Happy path ─────────────────────────────────────────────────

    @pytest.mark.integration
    def test_valid_inputs_pass(self):
        result = self.rules.validate_user_creation(
            email=self.valid_email,
            tenant_id=str(self.tenant.id),
            password=self.valid_password,
        )
        assert result.is_valid is True
        assert len(result.errors) == 0

    @pytest.mark.integration
    def test_minimal_inputs_pass(self):
        """Only email is required; tenant/password/status/roles are optional."""
        result = self.rules.validate_user_creation(
            email=f"minimal-{uuid.uuid4().hex[:8]}@example.com",
        )
        assert result.is_valid is True

    # ── Duplicate email ────────────────────────────────────────────

    @pytest.mark.integration
    def test_duplicate_email_rejected(self):
        email = f"dup-{uuid.uuid4().hex[:8]}@example.com"
        User.objects.create_user(
            email=email,
            password="testpass123",
            tenant=self.tenant,
        )
        result = self.rules.validate_user_creation(
            email=email,
            tenant_id=str(self.tenant.id),
        )
        assert result.is_valid is False
        assert result.details["code"] == "EMAIL_EXISTS"

    # ── Missing tenant ─────────────────────────────────────────────

    @pytest.mark.integration
    def test_empty_tenant_rejected(self):
        result = self.rules.validate_user_creation(
            email=self.valid_email,
            tenant_id="",
        )
        assert result.is_valid is False
        assert result.details["code"] == "TENANT_REQUIRED"

    # ── Invalid status ─────────────────────────────────────────────

    @pytest.mark.integration
    def test_invalid_status_rejected(self):
        result = self.rules.validate_user_creation(
            email=self.valid_email,
            tenant_id=str(self.tenant.id),
            status="NONEXISTENT",
        )
        assert result.is_valid is False
        assert result.details["code"] == "INVALID_STATUS"

    @pytest.mark.integration
    def test_valid_status_accepted(self):
        for s in ("ACTIVE", "INVITED", "DISABLED", "SUSPENDED"):
            result = self.rules.validate_user_creation(
                email=f"status-{s}-{uuid.uuid4().hex[:6]}@example.com",
                tenant_id=str(self.tenant.id),
                status=s,
            )
            assert result.is_valid is True, f"Status {s} should be valid"

    # ── Weak password ──────────────────────────────────────────────

    @pytest.mark.integration
    def test_short_password_rejected(self):
        result = self.rules.validate_user_creation(
            email=self.valid_email,
            tenant_id=str(self.tenant.id),
            password="short",
        )
        assert result.is_valid is False
        assert result.details["code"] == "WEAK_PASSWORD"

    @pytest.mark.integration
    def test_minimum_length_password_accepted(self):
        result = self.rules.validate_user_creation(
            email=self.valid_email,
            tenant_id=str(self.tenant.id),
            password="0123456789",  # exactly 10 — the current minimum
        )
        assert result.is_valid is True

    # ── Role assignment ────────────────────────────────────────────

    @pytest.mark.integration
    def test_role_tenant_mismatch_rejected(self):
        other_tenant = Tenant.objects.create(
            name=f"UBR-other-{uuid.uuid4().hex[:8]}",
            slug=f"ubr-other-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )
        role = Role.objects.create(
            tenant=other_tenant,
            name="TENANT_ADMIN",
            description="Belongs to other tenant",
        )
        result = self.rules.validate_user_creation(
            email=self.valid_email,
            tenant_id=str(self.tenant.id),
            role_ids=[str(role.id)],
        )
        assert result.is_valid is False
        assert result.details["code"] == "ROLE_TENANT_MISMATCH"

    @pytest.mark.integration
    def test_role_same_tenant_accepted(self):
        role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Same tenant"},
        )
        result = self.rules.validate_user_creation(
            email=f"role-ok-{uuid.uuid4().hex[:6]}@example.com",
            tenant_id=str(self.tenant.id),
            role_ids=[str(role.id)],
        )
        assert result.is_valid is True

    # ── Invitation expiry ──────────────────────────────────────────

    @pytest.mark.integration
    def test_expired_invitation_token_rejected(self):
        from datetime import timedelta

        from django.utils import timezone

        User.objects.create_user(
            email=f"expired-inv-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            invitation_token="expired-token-hash",
            invitation_token_expires_at=timezone.now() - timedelta(hours=1),
        )
        result = self.rules.validate_user_creation(
            email=self.valid_email,
            tenant_id=str(self.tenant.id),
            invitation_token="expired-token-hash",
        )
        assert result.is_valid is False
        assert result.details["code"] == "INVITATION_EXPIRED"
