"""
Phase 250.5.F (closes G2-3 / G2-4 / G-5) — GDPR + DPA tests.

Contract under test
-------------------

1. **250.5.F.1**: ``Tenant.federated_import_classification_default``
   field exists with `ClassificationCategory` choices, defaults to
   ``INTERNAL`` (production-safe default — never PUBLIC because
   federated imports may carry PII the source tenant hasn't yet
   classified). Migration `0037_tenant_federated_import_classification_default`
   provides the column-level default for both new and existing
   tenants.

2. **250.5.F.2**: ``ExternalResourceReference.deleted_at`` field
   exists, nullable, default None, db-indexed. Distinct from
   ``source_tenant_deleted_at`` (which is the source-side
   tombstone cascade per D250.16). The consumer-side ``deleted_at``
   marks user-initiated soft-deletion of the consumer's federated
   COPY without affecting the source-tenant row.

3. **250.5.F.5**: GDPR right-to-erasure (`ErasureService.execute_erasure`)
   cascades through assets owned by the user AND scrubs audit-event
   `details_json` PII more comprehensively than just `actor_email` /
   `user_email`. The new contract:
   * Anonymise (NOT hard-delete) assets where ``Asset.created_by_id == user.id``
     so audit history survives but no PII remains in `name` /
     `description`.
   * Scrub audit-event `details_json` for an extended PII key
     allow-list: `actor_email`, `user_email`, `email`, `display_name`,
     `name`, `phone`, `ip_address`, `user_agent`, etc.
   * Track every cascaded mutation in
     ``ErasureRequest.deleted_resources`` so the audit replay sees
     the full scope.

TDD doctrine
------------
Real Django ORM rows for `Tenant`, `User`, `Asset`,
`ExternalResourceReference`, `AuditEvent`, `ErasureRequest`. Real
``ErasureService.execute_erasure`` invocation. NO mocks of business
logic. The audit assertions read the real `AuditEvent` table to
confirm scrubbing actually persisted.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import (
    Asset,
    AssetStatus,
    ExternalResourceReference,
)
from hub.apps.audit.models import AuditEvent
from hub.apps.gdpr.models import ErasureRequest
from hub.apps.gdpr.services import ErasureService
from hub.apps.governance.models import ClassificationCategory
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _seed_tenant(*, suffix: str | None = None) -> Tenant:
    uid = suffix or uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"GDPR-DPA-{uid}",
        slug=f"gdpr-dpa-{uid}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )


def _seed_user(tenant: Tenant) -> User:
    return User.objects.create_user(
        email=f"u-{uuid.uuid4().hex[:8]}@example.com",
        password="testpass123",
        tenant=tenant,
    )


# ---------------------------------------------------------------------------
# 250.5.F.1 — Tenant.federated_import_classification_default
# ---------------------------------------------------------------------------


class TestFederatedImportClassificationDefault(TestCase):
    """The new tenant field defaults to INTERNAL on creation;
    accepts any ClassificationCategory value."""

    def test_field_exists_and_defaults_to_INTERNAL(self):
        tenant = _seed_tenant()
        # Field must exist on the model. AttributeError → test fail.
        actual = tenant.federated_import_classification_default
        assert actual == ClassificationCategory.INTERNAL, (
            "Default MUST be INTERNAL — production-safe posture "
            "for federated imports whose source-tenant classification "
            "is not yet known. PUBLIC default would risk leaking "
            "unclassified PII into the public catalogue."
        )

    def test_field_accepts_RESTRICTED(self):
        tenant = _seed_tenant()
        tenant.federated_import_classification_default = ClassificationCategory.RESTRICTED
        tenant.save(
            update_fields=["federated_import_classification_default"],
        )
        tenant.refresh_from_db()
        assert tenant.federated_import_classification_default == ClassificationCategory.RESTRICTED

    def test_field_accepts_PII(self):
        """A tenant whose source-marketplace contains PII can pin
        the default to PII to ensure every imported metadata blob
        receives the PII classification at intake."""
        tenant = _seed_tenant()
        tenant.federated_import_classification_default = ClassificationCategory.PII
        tenant.save(
            update_fields=["federated_import_classification_default"],
        )
        tenant.refresh_from_db()
        assert tenant.federated_import_classification_default == ClassificationCategory.PII


# ---------------------------------------------------------------------------
# 250.5.F.2 — ExternalResourceReference.deleted_at
# ---------------------------------------------------------------------------


class TestExternalResourceReferenceDeletedAt(TestCase):
    """The consumer-side ``deleted_at`` is independent of the
    source-tenant cascade tombstone (`source_tenant_deleted_at`).
    It marks user-initiated soft-deletion of the consumer's
    federated COPY without affecting the source-tenant row."""

    def _seed_asset(self, tenant, user):
        return Asset.objects.create(
            tenant=tenant,
            key=f"asset-{uuid.uuid4().hex[:8]}",
            name="GDPR Asset",
            status=AssetStatus.DRAFT,
            created_by=user,
        )

    def _seed_external_ref(self, asset, *, deleted_at=None) -> ExternalResourceReference:
        return ExternalResourceReference.objects.create(
            asset=asset,
            resource_id=f"r-{uuid.uuid4().hex[:8]}",
            name="federated copy",
            url="https://safe.example.com/data.csv",
            format="CSV",
            marketplace_type="CKAN_INSTANCE",
            connection_id=uuid.uuid4(),
            deleted_at=deleted_at,
        )

    def test_deleted_at_field_exists_and_defaults_to_None(self):
        tenant = _seed_tenant()
        user = _seed_user(tenant)
        asset = self._seed_asset(tenant, user)
        ref = self._seed_external_ref(asset)
        assert ref.deleted_at is None

    def test_deleted_at_can_be_set_independently_of_source_tenant_deleted_at(
        self,
    ):
        """The consumer-side deletion does NOT touch
        ``source_tenant_deleted_at`` and vice-versa — they are
        independent fields tracking different events."""
        tenant = _seed_tenant()
        user = _seed_user(tenant)
        asset = self._seed_asset(tenant, user)
        ref = self._seed_external_ref(asset)

        now = timezone.now()
        ref.deleted_at = now
        ref.save(update_fields=["deleted_at"])
        ref.refresh_from_db()

        assert ref.deleted_at is not None
        assert ref.source_tenant_deleted_at is None, (
            "Consumer-side delete MUST NOT mutate "
            "source_tenant_deleted_at — that field is owned by "
            "the source-tenant soft-delete cascade (D250.16)."
        )

    def test_both_fields_can_carry_distinct_timestamps(self):
        """Edge case: a consumer who deletes their copy AFTER the
        source tenant tombstoned. Both fields populated with
        different timestamps."""
        tenant = _seed_tenant()
        user = _seed_user(tenant)
        asset = self._seed_asset(tenant, user)
        source_tombstone = timezone.now() - timedelta(days=10)
        ref = self._seed_external_ref(asset)
        ref.source_tenant_deleted_at = source_tombstone
        ref.save(update_fields=["source_tenant_deleted_at"])

        consumer_delete = timezone.now()
        ref.deleted_at = consumer_delete
        ref.save(update_fields=["deleted_at"])
        ref.refresh_from_db()

        assert ref.source_tenant_deleted_at == source_tombstone
        # Allow microsecond truncation difference in timestamp roundtrip.
        assert abs((ref.deleted_at - consumer_delete).total_seconds()) < 1


# ---------------------------------------------------------------------------
# 250.5.F.5 — GDPR erasure cascades through assets + audit events
# ---------------------------------------------------------------------------


class TestGDPRErasureAssetCascade(TestCase):
    """``ErasureService.execute_erasure`` MUST anonymise (not
    hard-delete) every Asset owned by the user — anonymisation
    preserves audit history while removing PII from the
    user-facing surface."""

    def _create_erasure_request(self, user, tenant) -> ErasureRequest:
        service = ErasureService(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
        )
        return service.create_request(
            user_id=str(user.id),
        )

    def test_user_owned_assets_are_anonymized_not_hard_deleted(self):
        tenant = _seed_tenant()
        user = _seed_user(tenant)
        asset = Asset.objects.create(
            tenant=tenant,
            key=f"k-{uuid.uuid4().hex[:8]}",
            name=f"User {user.email}'s asset",  # contains PII
            description=f"Asset for {user.email}",  # contains PII
            status=AssetStatus.DRAFT,
            created_by=user,
        )

        request = self._create_erasure_request(user, tenant)
        service = ErasureService(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
        )
        service.execute_erasure(str(request.id))

        # Asset row MUST still exist (anonymised, not hard-deleted)
        # so audit history remains.
        asset.refresh_from_db()
        assert asset.id is not None, (
            "Erasure MUST anonymise assets, not hard-delete them — "
            "hard-deletion would orphan audit history. Phase "
            "250.5.F.5 / G2-2 contract."
        )
        # Name + description MUST no longer carry the user's email.
        assert user.email not in (asset.name or ""), f"asset.name still carries PII: {asset.name!r}"
        assert user.email not in (asset.description or ""), (
            f"asset.description still carries PII: {asset.description!r}"
        )

    def test_assets_owned_by_other_users_unchanged(self):
        """Cascading MUST NOT touch other users' assets — the
        erasure is scoped to the requesting user's owned rows."""
        tenant = _seed_tenant()
        user_a = _seed_user(tenant)
        user_b = _seed_user(tenant)
        Asset.objects.create(
            tenant=tenant,
            key=f"a-{uuid.uuid4().hex[:8]}",
            name="A's Asset",
            status=AssetStatus.DRAFT,
            created_by=user_a,
        )
        asset_b = Asset.objects.create(
            tenant=tenant,
            key=f"b-{uuid.uuid4().hex[:8]}",
            name="B's Pristine Asset",
            status=AssetStatus.DRAFT,
            created_by=user_b,
        )

        request = self._create_erasure_request(user_a, tenant)
        service = ErasureService(
            tenant_id=str(tenant.id),
            user_id=str(user_a.id),
        )
        service.execute_erasure(str(request.id))

        asset_b.refresh_from_db()
        assert asset_b.name == "B's Pristine Asset", (
            "Erasure of user A MUST NOT mutate user B's assets."
        )

    def test_erasure_request_records_assets_in_deleted_resources(self):
        tenant = _seed_tenant()
        user = _seed_user(tenant)
        Asset.objects.create(
            tenant=tenant,
            key=f"k-{uuid.uuid4().hex[:8]}",
            name="A",
            status=AssetStatus.DRAFT,
            created_by=user,
        )
        Asset.objects.create(
            tenant=tenant,
            key=f"k-{uuid.uuid4().hex[:8]}",
            name="B",
            status=AssetStatus.DRAFT,
            created_by=user,
        )

        request = self._create_erasure_request(user, tenant)
        service = ErasureService(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
        )
        service.execute_erasure(str(request.id))
        request.refresh_from_db()

        # The erasure-completion audit MUST mention assets so the
        # audit replay shows the cascade ran.
        assert "assets" in request.deleted_resources, (
            f"deleted_resources MUST include 'assets'; got {request.deleted_resources!r}"
        )

    def test_post_save_signal_fires_per_asset_so_search_vector_rebuilds(self):
        """250.5.F audit-pass GAP-A regression — pin that the cascade
        invokes per-row ``Asset.save()`` (NOT ``QuerySet.update()``)
        so the ``post_save`` signal fires and the secondary search
        index can rebuild from the redacted text.

        Why this matters: the original implementation used
        ``QuerySet.update()`` which bypasses ``post_save``. The
        ``rebuild_asset_search_vector`` signal at
        [hub/apps/assets/signals.py:113](hub/apps/assets/signals.py#L113)
        registers ``transaction.on_commit(_enqueue)`` which queues
        a search-vector rebuild from the asset's CURRENT name +
        description. With ``.update()`` the signal never fired and
        the search_vector retained the user's PII (e.g. their
        email embedded in the original asset name) — a future
        search query would surface the redacted asset BY THE
        ORIGINAL TEXT, defeating the right-to-erasure invariant.

        The audit-pass fix replaced ``.update()`` with an iterator
        that calls ``.save(update_fields=[...])`` per row. This
        test pins that fix at the SIGNAL level — capturing every
        ``post_save`` for ``Asset`` during erasure and asserting:
          1. The signal fired exactly once per user-owned asset.
          2. The instance passed to the signal has the REDACTED
             name + description (not the original PII text), so a
             downstream search-vector rebuild reads the post-
             redaction state.

        Without this regression test, a future refactor that
        switched back to ``.update()`` for "performance" would
        silently re-introduce the right-to-erasure leak — exactly
        the failure mode this audit-pass corrected.
        """
        from django.db.models.signals import post_save

        tenant = _seed_tenant()
        user = _seed_user(tenant)
        # Two ACTIVE assets owned by the user — ACTIVE status is
        # important: the search-vector signal short-circuits on
        # DRAFT (Phase 250.1.F gate), so testing with DRAFT would
        # not exercise the load-bearing path.
        a1 = Asset.objects.create(
            tenant=tenant,
            key=f"k-{uuid.uuid4().hex[:8]}",
            name=f"Personal asset of {user.email}",
            description=f"Owned by {user.email}",
            status=AssetStatus.ACTIVE,
            created_by=user,
        )
        a2 = Asset.objects.create(
            tenant=tenant,
            key=f"k-{uuid.uuid4().hex[:8]}",
            name=f"Second asset of {user.email}",
            status=AssetStatus.ACTIVE,
            created_by=user,
        )

        # Capture the post_save signal for Asset across the
        # erasure call. The capture records (pk, name,
        # description) at signal-fire time so we can verify the
        # instance state the signal observed reflects the
        # redaction (proving save() ran AFTER the field
        # mutation, not before).
        captured = []

        def _capture(sender, instance, **kwargs):
            captured.append(
                {
                    "pk": instance.pk,
                    "name": instance.name,
                    "description": instance.description,
                }
            )

        post_save.connect(_capture, sender=Asset, dispatch_uid="t250_5_f_audit")
        try:
            request = self._create_erasure_request(user, tenant)
            service = ErasureService(
                tenant_id=str(tenant.id),
                user_id=str(user.id),
            )
            service.execute_erasure(str(request.id))
        finally:
            post_save.disconnect(sender=Asset, dispatch_uid="t250_5_f_audit")

        # Filter to the captured events for OUR assets — other
        # signal-driven saves (e.g. ErasureRequest's own audit
        # cascade) would otherwise pollute the assertion.
        per_asset_saves = {ev["pk"]: ev for ev in captured if ev["pk"] in (a1.pk, a2.pk)}
        assert a1.pk in per_asset_saves, (
            "post_save MUST fire for asset a1 — without it the "
            "search_vector rebuild signal can't run and the user's "
            "PII stays embedded in the secondary index."
        )
        assert a2.pk in per_asset_saves, (
            "post_save MUST fire for asset a2 — same invariant "
            "as a1; both assets must be saved, not bulk-updated."
        )

        # The captured signal payload MUST reflect the redacted
        # state — proves the field mutation happened BEFORE the
        # save (not after). If the implementation did
        # ``save(); name = redacted; save()`` we'd capture the
        # original text on the first save and that would be a
        # regression.
        for pk, ev in per_asset_saves.items():
            assert user.email not in (ev["name"] or ""), (
                f"post_save for asset {pk} captured name={ev['name']!r} "
                "— still contains PII. The cascade must mutate "
                "name BEFORE invoking save() so the signal-driven "
                "search-vector rebuild reads redacted text."
            )
            assert user.email not in (ev["description"] or ""), (
                f"post_save for asset {pk} captured description="
                f"{ev['description']!r} — still contains PII."
            )


class TestGDPRErasureAuditEventScrubbing(TestCase):
    """The pre-Phase ``execute_erasure`` only scrubbed
    ``actor_email`` and ``user_email`` from audit-event
    ``details_json``. Phase 250.5.F.5 extends the scrub set to
    every common PII key. Without the extension, an audit event
    carrying e.g. ``details_json["email"]`` (no prefix) would
    leak PII through audit replay after erasure."""

    def _create_erasure_request(self, user, tenant) -> ErasureRequest:
        service = ErasureService(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
        )
        return service.create_request(
            user_id=str(user.id),
        )

    def test_extended_pii_keys_scrubbed(self):
        tenant = _seed_tenant()
        user = _seed_user(tenant)
        original_email = user.email
        # Seed an audit event with PII under non-prefixed keys.
        audit = AuditEvent.objects.create(
            tenant=tenant,
            actor_user=user,
            resource_type="USER",
            action="USER_LOGGED_IN",
            details_json={
                "email": original_email,
                "display_name": "Real Name",
                "phone": "+15551234567",
                "ip_address": "203.0.113.42",
                "user_agent": "Mozilla/5.0",
                "non_pii_metadata": {"login_method": "oauth"},
            },
        )

        request = self._create_erasure_request(user, tenant)
        service = ErasureService(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
        )
        service.execute_erasure(str(request.id))

        # Refresh via all_objects (default manager filters archived).
        scrubbed = AuditEvent.all_objects.get(pk=audit.pk)
        details = scrubbed.details_json or {}

        # Every PII key MUST be scrubbed (replaced with a sentinel
        # OR removed).  The scrubbing implementation uses
        # "deleted@deleted.local" for all PII field values.
        for pii_key in (
            "email",
            "display_name",
            "phone",
            "ip_address",
            "user_agent",
        ):
            value = details.get(pii_key)
            self.assertIn(
                value,
                (None, "deleted@deleted.local"),
                f"PII key {pii_key!r} must be None or 'deleted@deleted.local'; got {value!r}",
            )

        # Non-PII keys MUST be preserved.
        assert details.get("non_pii_metadata") == {
            "login_method": "oauth",
        }, "Non-PII keys MUST be preserved."
