"""
Phase 250.3.C.2 (closes C2-2) — PATCH endpoint rejects ``visibility``
field with ``400 FIELD_REMOVED`` once the deprecation phase 2 gate
clears.

Contract under test
-------------------

The ``Asset.visibility`` field is being removed in a multi-phase
deprecation:

* **Phase 0** (current): ``visibility`` is a real CharField column;
  PATCH /assets/{id}/ accepts and persists writes.
* **Phase 1** (250.3.B, not yet shipped): ``visibility`` becomes a
  ``@property`` derived from ``status``; the column is nulled by
  migration; PATCH silently ignores ``visibility`` in body but
  emits a deprecation log + audit row.
* **Phase 2** (this 250.3.C): after **three full release cycles**
  of phase-1 green telemetry, the gate flips and PATCH **rejects**
  ``visibility`` writes with structured error
  ``code="FIELD_REMOVED"``, ``http_status=400``,
  ``details={"field": "visibility", "phase": "phase_2",
  "reason": "...", "alternative": "..."}``.
* **Phase 2 follow-up**: the column-drop migration runs after at
  least one cycle of rejection telemetry confirms zero callers
  still attempt the write.

This phase implements the **rejection** behind a feature flag
(``settings.ASSET_VISIBILITY_PHASE_2_REJECT_ENABLED``, default
False). The flag default-False posture means the rejection ships
inert — the existing phase-0 / phase-1 contract is preserved
until ops flips the flag after the 3-cycle gate clears. This
test suite pins both states (flag-OFF preserves existing
behaviour, flag-ON activates the rejection) so the rejection
contract is reviewable + provably testable in CI without waiting
for the gate to clear in production.

TDD doctrine
------------
Real Django ORM rows + real DRF APIClient + real AssetUpdateSerializer
+ real AssetService. NO mocks of business logic. The settings flag is
toggled via ``django.test.override_settings`` — a Django-supplied
mechanism, NOT a mock of the application's settings reader.
"""
from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus, AssetVisibility
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.role_support import ensure_user_has_data_provider_role
from hub.apps.users.models import UserStatus


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _seed_tenant_user_asset() -> tuple[Tenant, "User", Asset]:
    """Create a tenant + DATA_PROVIDER user + DRAFT asset for PATCH
    tests. Tenant is given an active subscription so the
    middleware allows writes."""
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"VisPhase2-{uid}",
        slug=f"vis-phase-2-{uid}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )
    ensure_tenant_has_active_subscription(tenant)
    user = User.objects.create_user(
        email=f"u-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    ensure_user_has_data_provider_role(user)
    asset = Asset.objects.create(
        tenant=tenant,
        key=f"asset-{uid}",
        name="VisPhase2 Asset",
        status=AssetStatus.DRAFT,
        visibility=AssetVisibility.INTERNAL,
        created_by=user,
    )
    return tenant, user, asset


def _patch_visibility(
    client: APIClient, asset: Asset, *, visibility: str, version: int = 1
):
    """PATCH /assets/{id}/ with visibility in the body. Returns the
    HTTP response so the caller can assert status code + body."""
    return client.patch(
        f"/api/v1/assets/{asset.id}/",
        {"visibility": visibility, "version": version},
        format="json",
    )


def _patch_name(
    client: APIClient, asset: Asset, *, name: str, version: int = 1
):
    """PATCH /assets/{id}/ with name (no visibility). Used to assert
    that non-visibility fields are unaffected by the rejection."""
    return client.patch(
        f"/api/v1/assets/{asset.id}/",
        {"name": name, "version": version},
        format="json",
    )


# ---------------------------------------------------------------------------
# 250.3.C.2 — flag OFF preserves the phase-0 / phase-1 contract
# ---------------------------------------------------------------------------


@override_settings(ASSET_VISIBILITY_PHASE_2_REJECT_ENABLED=False)
class TestPhase2RejectionFlagOff(TestCase):
    """When the phase-2 gate has NOT cleared
    (``settings.ASSET_VISIBILITY_PHASE_2_REJECT_ENABLED=False``),
    the PATCH endpoint MUST preserve the existing behaviour
    (phase-0: accept; phase-1 once it lands: silently ignore)
    so the rejection contract ships inert and only activates
    after ops explicitly opens the gate."""

    def setUp(self):
        self.client = APIClient()
        self.tenant, self.user, self.asset = _seed_tenant_user_asset()
        self.client.force_authenticate(user=self.user)

    def test_visibility_in_body_does_not_return_400_FIELD_REMOVED(self):
        response = _patch_visibility(
            self.client, self.asset, visibility=AssetVisibility.PUBLIC,
        )
        # Whatever the response — 200 (current phase-0 accept) or
        # 200-with-deprecation-log (phase-1 silent ignore once
        # 250.3.B lands) — it MUST NOT be the 400 FIELD_REMOVED
        # rejection. The audit-pin: with the flag OFF, the
        # phase-2 rejection branch is unreachable.
        if response.status_code == 400:
            body = response.json() if response.content else {}
            assert body.get("code") != "FIELD_REMOVED", (
                "Phase-2 rejection MUST NOT fire when "
                "ASSET_VISIBILITY_PHASE_2_REJECT_ENABLED is False; "
                f"got 400 with code={body.get('code')!r}"
            )


# ---------------------------------------------------------------------------
# 250.3.C.2 — flag ON activates the FIELD_REMOVED rejection
# ---------------------------------------------------------------------------


@override_settings(ASSET_VISIBILITY_PHASE_2_REJECT_ENABLED=True)
class TestPhase2RejectionFlagOn(TestCase):
    """Once the gate clears (``settings.ASSET_VISIBILITY_PHASE_2_REJECT_ENABLED=True``),
    PATCH /assets/{id}/ MUST reject any body that contains
    ``visibility`` with the structured error contract from C2-2."""

    def setUp(self):
        self.client = APIClient()
        self.tenant, self.user, self.asset = _seed_tenant_user_asset()
        self.client.force_authenticate(user=self.user)

    def test_visibility_in_body_returns_400_FIELD_REMOVED(self):
        response = _patch_visibility(
            self.client, self.asset, visibility=AssetVisibility.PUBLIC,
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, (
            f"Expected 400, got {response.status_code}: "
            f"{response.content!r}"
        )
        body = response.json()
        assert body.get("code") == "FIELD_REMOVED", (
            f"Expected code=FIELD_REMOVED, got {body.get('code')!r}; "
            "the phase-2 rejection contract is the load-bearing "
            "deliverable of 250.3.C.2."
        )

    def test_rejection_carries_structured_details(self):
        response = _patch_visibility(
            self.client, self.asset, visibility=AssetVisibility.PUBLIC,
        )
        body = response.json()
        details = body.get("details") or {}
        # The structured error must carry enough context that the
        # API consumer can adapt without reading docs:
        # - field: which field was rejected
        # - phase: which deprecation phase rejected it (so a
        #   future phase-3 rejection has a different value)
        # - reason: human-readable explanation
        # - alternative: the canonical replacement field/property
        assert details.get("field") == "visibility"
        assert details.get("phase") == "phase_2"
        assert "reason" in details, (
            f"details MUST include 'reason'; got {details!r}"
        )
        assert "alternative" in details, (
            "details MUST include 'alternative' pointing the "
            "consumer to the canonical replacement (Asset.status "
            "per D250.4 — visibility is now a derived @property)."
        )

    def test_rejection_does_not_persist_visibility_change(self):
        original_visibility = self.asset.visibility
        _patch_visibility(
            self.client, self.asset, visibility=AssetVisibility.PUBLIC,
        )
        # Refresh from DB; the value must be unchanged because the
        # rejection fired BEFORE any DB write.
        self.asset.refresh_from_db()
        assert self.asset.visibility == original_visibility, (
            "Phase-2 rejection MUST NOT persist any change — the "
            "rejection fires at the view boundary before the "
            "service / serializer / save layer runs."
        )

    def test_payload_without_visibility_succeeds(self):
        """Other PATCHable fields (e.g. ``name``) MUST continue
        to work — the rejection is targeted to the visibility
        field only."""
        response = _patch_name(self.client, self.asset, name="Renamed")
        assert response.status_code == status.HTTP_200_OK, (
            f"PATCH without visibility MUST succeed; got "
            f"{response.status_code}: {response.content!r}"
        )
        self.asset.refresh_from_db()
        assert self.asset.name == "Renamed"

    def test_visibility_alongside_other_fields_still_rejected(self):
        """If the body contains BOTH visibility AND other valid
        fields, the rejection MUST fire — partial acceptance
        would let consumers bypass the gate by bundling the
        deprecated field with valid fields. The fail-closed
        posture: any visibility in body → reject everything,
        atomic."""
        response = self.client.patch(
            f"/api/v1/assets/{self.asset.id}/",
            {
                "visibility": AssetVisibility.PUBLIC,
                "name": "Renamed",
                "version": 1,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        body = response.json()
        assert body.get("code") == "FIELD_REMOVED"
        # Confirm name was NOT updated despite being in the body
        # — the rejection is atomic.
        self.asset.refresh_from_db()
        assert self.asset.name != "Renamed", (
            "Atomic rejection: NO field is persisted when "
            "visibility is present in the body."
        )

    def test_explicit_null_visibility_also_rejected(self):
        """``visibility: null`` is also a write attempt against
        the deprecated field; the gate must reject it
        identically — preventing consumers from claiming "I'm
        only setting it to null, not really a write" as a
        bypass."""
        response = self.client.patch(
            f"/api/v1/assets/{self.asset.id}/",
            {"visibility": None, "version": 1},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json().get("code") == "FIELD_REMOVED"

    def test_rejection_fires_before_get_object_db_query(self):
        """Audit-pass GAP-A pin: the rejection fires BEFORE
        ``self.get_object()`` and therefore BEFORE any DB I/O.

        Verification path: PATCH a non-existent asset id with
        visibility in the body. If the rejection fired BEFORE
        ``self.get_object()``, the response is 400 FIELD_REMOVED
        (no DB lookup performed). If the rejection fired AFTER
        ``self.get_object()``, the response would be 404
        (asset not found).

        The 400-not-404 contract is the operator-facing
        invariant: the deprecation rejection is the dominant
        signal, regardless of whether the asset exists. This
        also closes a subtle inefficiency in the original
        implementation where the rejection path performed one
        avoidable DB query."""
        bogus_id = uuid.uuid4()
        response = self.client.patch(
            f"/api/v1/assets/{bogus_id}/",
            {"visibility": AssetVisibility.PUBLIC, "version": 1},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, (
            f"Rejection MUST fire before get_object (DB I/O); "
            f"got {response.status_code} which suggests "
            f"get_object ran first. Audit-pass GAP-A regression."
        )
        assert response.json().get("code") == "FIELD_REMOVED"


# ---------------------------------------------------------------------------
# 250.3.C.1 staging — migration template existence
# ---------------------------------------------------------------------------


class TestMigrationTemplateExists(TestCase):
    """Phase 250.3.C.1 stages the column-drop migration as a
    documented template at ``docs/migrations/staged/`` rather
    than a live Django migration in ``hub/apps/assets/migrations/``.
    Reason: the live migration cannot be authored until phase-1
    (250.3.B.2) lands and gets its migration number; pre-baking
    the dependency to a name that doesn't yet exist would block
    Django's makemigrations / migrate. The template lives in
    docs/ as a reviewable, copy-pasteable artefact that ops
    promotes to a real migration when both gates clear:

      1. Phase 1 (250.3.B) has shipped.
      2. Three full release cycles of phase-1 green telemetry.
      3. At least one cycle of phase-2 rejection telemetry
         (this audit's 250.3.C.2) confirms zero callers still
         attempt visibility writes.

    This test pins the template's existence so a future
    refactor can't accidentally remove the staged artefact."""

    def test_migration_template_file_exists(self):
        from pathlib import Path

        template = (
            Path(__file__).resolve().parents[4]
            / "docs"
            / "migrations"
            / "staged"
            / "drop_visibility_column.py.template"
        )
        assert template.exists(), (
            f"Phase 250.3.C.1 migration template MUST live at "
            f"{template} — staged for promotion when the "
            f"3-cycle gate clears. Removing this file is a "
            f"phase-2 deliverable regression."
        )

    def test_migration_template_documents_gate(self):
        """The template MUST self-document the deferral gate so
        a future operator promoting it to a live migration can't
        miss the prerequisite checks."""
        from pathlib import Path

        template = (
            Path(__file__).resolve().parents[4]
            / "docs"
            / "migrations"
            / "staged"
            / "drop_visibility_column.py.template"
        )
        content = template.read_text()
        content_lower = content.lower()
        # Self-document the gate via specific keywords every
        # operator playbook reader would search for. The "full"
        # qualifier is part of the phrase so a substring search
        # for "three release cycles" would miss "three full
        # release cycles" — assert "three" + "release cycles"
        # separately to allow that idiomatic phrasing.
        assert "three" in content_lower
        assert "release cycles" in content_lower, (
            "Template MUST reference the release-cycle gate."
        )
        assert "phase 1" in content_lower, (
            "Template MUST reference phase 1 prerequisite."
        )
        # Phase-1 (250.3.B) already removed the field from Django
        # state via SeparateDatabaseAndState; phase-2's actual
        # operation is a database-only ``DROP COLUMN`` raw SQL,
        # NOT Django's ``RemoveField`` (which would no-op or fail
        # because state already has no field). Pin the correct
        # operation so a future operator doesn't reach for the
        # state-level RemoveField that would silently no-op
        # without dropping the underlying column.
        assert "DROP COLUMN" in content, (
            "Template MUST include the database-side DROP COLUMN "
            "raw SQL — phase-2 is a DB-only operation because "
            "phase-1 already removed the field from Django state "
            "via SeparateDatabaseAndState."
        )
        assert "0013_visibility_to_property" in content, (
            "Template MUST reference the phase-1 migration name "
            "(0013_visibility_to_property) — phase 1 has shipped "
            "in the live codebase, so the dependency is now known."
        )
