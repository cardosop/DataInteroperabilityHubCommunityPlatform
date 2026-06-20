"""Phase D (TR.D.8-D.9) — Consent: HMAC proofs + key rotation."""

import uuid

import pytest
from django.test import TestCase, override_settings

from hub.apps.consent.models import ConsentPurpose, ConsentRecordStatus
from hub.apps.consent.services import ConsentService
from hub.apps.consent.signing import (
    build_canonical_bytes,
    compute_proof_hmac,
    get_signing_key_ring_for_tenant,
    verify_proof_hmac,
)
from hub.apps.tenants.models import Tenant, TenantStatus
from hub.apps.users.models import User

pytestmark = pytest.mark.django_db(transaction=True)


def _consent_signing_keys() -> dict:
    """3-key ring for rotation tests."""
    return {
        "__default__": [
            "b" * 64,  # key[0] = newest
            "a" * 64,  # key[1]
            "c" * 64,  # key[2] = oldest
        ]
    }


class ConsentHmacTests(TestCase):
    """TR.D.8 — HMAC proof verification."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"cn-hmac-{uid}",
            slug=f"cn-hmac-{uid}",
            status=TenantStatus.ACTIVE,
            compliance_consent_enabled=True,
        )
        self.user = User.objects.create_user(
            email=f"cn-hmac-{uid}@test.local",
            password="Pass1234!",
            tenant=self.tenant,
        )
        self.purpose = ConsentPurpose.objects.create(
            tenant=self.tenant,
            key=f"hmac.test.{uid}",
            name="HMAC Test Purpose",
            is_active=True,
        )

    @override_settings(CONSENT_SIGNING_KEYS_JSON=_consent_signing_keys())
    def test_valid_proof_verifies(self):
        """A consent record signed with key[0] verifies correctly."""
        service = ConsentService()
        record = service.grant(
            tenant=self.tenant,
            user=self.user,
            purpose=self.purpose,
            payload={"source": "test"},
        )
        assert record.status == ConsentRecordStatus.GRANTED
        # Verify the stored proof matches a fresh computation
        build_canonical_bytes(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            purpose_id=str(self.purpose.id),
            payload={"source": "test"},
        )
        key_ring = get_signing_key_ring_for_tenant(str(self.tenant.id))
        recomputed = compute_proof_hmac(
            key=key_ring[0],
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            purpose_id=str(self.purpose.id),
            payload={"source": "test"},
        )
        assert record.proof_hmac == recomputed
        assert record.proof_hmac is not None

    @override_settings(CONSENT_SIGNING_KEYS_JSON=_consent_signing_keys())
    def test_tampered_record_detection(self):
        """A tampered consent record fails HMAC verification."""
        service = ConsentService()
        record = service.grant(
            tenant=self.tenant,
            user=self.user,
            purpose=self.purpose,
            payload={"source": "test"},
        )
        # Tamper with the payload but keep the same proof
        tampered_payload = {"source": "tampered"}
        is_valid, _ = verify_proof_hmac(
            proof_hex=record.proof_hmac,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            purpose_id=str(self.purpose.id),
            payload=tampered_payload,
            key_ring=get_signing_key_ring_for_tenant(str(self.tenant.id)),
        )
        assert not is_valid, "Tampered payload must fail HMAC verification"

    @override_settings(CONSENT_SIGNING_KEYS_JSON=_consent_signing_keys())
    def test_idempotent_grant(self):
        """Granting consent twice with same payload is idempotent."""
        service = ConsentService()
        record1 = service.grant(
            tenant=self.tenant,
            user=self.user,
            purpose=self.purpose,
            payload={"source": "test"},
        )
        record2 = service.grant(
            tenant=self.tenant,
            user=self.user,
            purpose=self.purpose,
            payload={"source": "test"},
        )
        # Same record ID, same proof
        assert record1.id == record2.id
        assert record1.proof_hmac == record2.proof_hmac


class ConsentKeyRotationTests(TestCase):
    """TR.D.9 — Rolling key rotation (3-key window)."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"cn-rot-{uid}",
            slug=f"cn-rot-{uid}",
            status=TenantStatus.ACTIVE,
            compliance_consent_enabled=True,
        )
        self.user = User.objects.create_user(
            email=f"cn-rot-{uid}@test.local",
            password="Pass1234!",
            tenant=self.tenant,
        )
        self.purpose = ConsentPurpose.objects.create(
            tenant=self.tenant,
            key=f"rot.test.{uid}",
            name="Rotation Test Purpose",
            is_active=True,
        )

    @override_settings(CONSENT_SIGNING_KEYS_JSON=_consent_signing_keys())
    def test_v3_key_verifies_after_v5_rotation(self):
        """A record signed with an older key still verifies after rotation."""
        ConsentService()
        key_ring = get_signing_key_ring_for_tenant(str(self.tenant.id))
        # Sign with key[2] (oldest)
        proof = compute_proof_hmac(
            key=key_ring[2],
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            purpose_id=str(self.purpose.id),
            payload={"source": "rotation-test"},
        )
        # Verification against full key ring should succeed
        is_valid, matched_idx = verify_proof_hmac(
            proof_hex=proof,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            purpose_id=str(self.purpose.id),
            payload={"source": "rotation-test"},
            key_ring=key_ring,
        )
        assert is_valid, "Record signed with old key must verify after rotation"
        assert matched_idx == 2, "Should match the oldest key in the ring"

    @override_settings(CONSENT_SIGNING_KEYS_JSON=_consent_signing_keys())
    def test_rolling_window_3_keys(self):
        """All 3 keys in the ring can independently sign and verify."""
        key_ring = get_signing_key_ring_for_tenant(str(self.tenant.id))
        assert len(key_ring) == 3, "Key ring must have exactly 3 keys"

        payload = {"source": "rolling-window"}
        for idx, key in enumerate(key_ring):
            proof = compute_proof_hmac(
                key=key,
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                purpose_id=str(self.purpose.id),
                payload=payload,
            )
            is_valid, matched_idx = verify_proof_hmac(
                proof_hex=proof,
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                purpose_id=str(self.purpose.id),
                payload=payload,
                key_ring=key_ring,
            )
            assert is_valid, f"Key at index {idx} must sign and verify"
            assert matched_idx == idx, f"Must match key index {idx}"
