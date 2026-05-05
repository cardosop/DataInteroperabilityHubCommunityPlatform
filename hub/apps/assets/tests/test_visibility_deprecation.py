"""
Phase 250.3.B — TDD pin for visibility-as-property deprecation (phase 1).

Per D250.4, ``Asset.visibility`` becomes a ``@property`` derived from
``Asset.status`` (PUBLIC iff status==PUBLIC, else INTERNAL). Phase-1
deprecation:

* Reads of ``asset.visibility`` return the derived value.
* Writes to ``asset.visibility`` are SILENTLY IGNORED but log a
  deprecation warning AND emit ``ASSET_VISIBILITY_WRITE_DEPRECATED``
  audit so dashboards can track caller-side adoption.
* The DB column is nulled by migration ``00NN_visibility_to_property``
  but NOT dropped (column drop ships in phase-2 after 3 release
  cycles of green telemetry per D250.4).
* PATCH endpoint silently ignores ``visibility`` in body for phase 1.
* ``Cache-Control: no-cache`` is set on ``/assets/`` for 7 days
  post-deploy per B2-8 so cached pre-deploy responses don't surface
  stale visibility values to admins.

Tests use real Django ORM rows + real audit-event helper — NO mocks
of business logic. The only mocked surface is ``warnings.warn``
captured via ``warnings.catch_warnings`` (stdlib), which is
fault-injection at a Python-runtime boundary, not a business mock.
"""
from __future__ import annotations

import uuid
import warnings

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus, AssetVisibility
from hub.apps.audit import event_types as audit_event_types
from hub.apps.audit.models import AuditEvent
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _seed():
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"Tenant {uid}",
        slug=f"tenant-{uid}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )
    ensure_tenant_has_active_subscription(tenant)
    user = User.objects.create_user(
        email=f"user-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    return tenant, user


# ---------------------------------------------------------------------------
# 250.3.B.1 — visibility is a property derived from status
# ---------------------------------------------------------------------------


class VisibilityDerivedFromStatusTest(TestCase):
    """``Asset.visibility`` returns the derived value, not a stored
    column value. The mapping is:

    * ``status == PUBLIC`` → ``visibility == PUBLIC``
    * any other status → ``visibility == INTERNAL``
    """

    def test_draft_asset_derives_internal(self):
        tenant, user = _seed()
        asset = Asset.objects.create(
            tenant=tenant, key=f"a-{uuid.uuid4().hex[:6]}", name="A",
            status=AssetStatus.DRAFT,
        )
        assert asset.visibility == AssetVisibility.INTERNAL

    def test_active_asset_derives_internal(self):
        tenant, user = _seed()
        asset = Asset.objects.create(
            tenant=tenant, key=f"a-{uuid.uuid4().hex[:6]}", name="A",
            status=AssetStatus.ACTIVE,
        )
        assert asset.visibility == AssetVisibility.INTERNAL

    def test_public_asset_derives_public(self):
        tenant, user = _seed()
        asset = Asset.objects.create(
            tenant=tenant, key=f"a-{uuid.uuid4().hex[:6]}", name="A",
            status=AssetStatus.PUBLIC,
        )
        assert asset.visibility == AssetVisibility.PUBLIC

    def test_retired_asset_derives_internal(self):
        tenant, user = _seed()
        asset = Asset.objects.create(
            tenant=tenant, key=f"a-{uuid.uuid4().hex[:6]}", name="A",
            status=AssetStatus.RETIRED,
        )
        assert asset.visibility == AssetVisibility.INTERNAL

    def test_status_change_flips_derived_visibility(self):
        tenant, user = _seed()
        asset = Asset.objects.create(
            tenant=tenant, key=f"a-{uuid.uuid4().hex[:6]}", name="A",
            status=AssetStatus.ACTIVE,
        )
        assert asset.visibility == AssetVisibility.INTERNAL
        asset.status = AssetStatus.PUBLIC
        # No save needed — property reads ``self.status`` directly.
        assert asset.visibility == AssetVisibility.PUBLIC


# ---------------------------------------------------------------------------
# 250.3.B.3 — writes log warn + emit ASSET_VISIBILITY_WRITE_DEPRECATED
# ---------------------------------------------------------------------------


class VisibilityWriteIsDeprecationOnlyTest(TestCase):
    """Setting ``asset.visibility = X`` is a no-op for the derived
    state but emits the deprecation signal:

    1. Python ``DeprecationWarning`` (so ``-W error::DeprecationWarning``
       in CI catches stragglers).
    2. ``ASSET_VISIBILITY_WRITE_DEPRECATED`` audit row carrying the
       attempted value, the asset_id, and the actor (when available).
    """

    def test_write_emits_deprecation_warning_and_audit(self):
        tenant, user = _seed()
        asset = Asset.objects.create(
            tenant=tenant, key=f"a-{uuid.uuid4().hex[:6]}", name="A",
            status=AssetStatus.ACTIVE,
        )
        before = AuditEvent.objects.filter(
            action=audit_event_types.ASSET_VISIBILITY_WRITE_DEPRECATED,
            tenant=tenant,
        ).count()

        # Capture the deprecation warning emitted by the setter.
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always", DeprecationWarning)
            asset.visibility = AssetVisibility.PUBLIC

        deprecation_warnings = [
            w for w in captured if issubclass(w.category, DeprecationWarning)
        ]
        assert deprecation_warnings, "expected a DeprecationWarning on visibility write"
        assert "Asset.visibility" in str(deprecation_warnings[0].message)

        # Audit row emitted with attempted value + asset_id.
        after = AuditEvent.objects.filter(
            action=audit_event_types.ASSET_VISIBILITY_WRITE_DEPRECATED,
            tenant=tenant,
        ).order_by("-created_at")
        assert after.count() - before == 1
        ev = after.first()
        assert ev.details_json["attempted_value"] == "PUBLIC"
        assert ev.details_json["asset_id"] == str(asset.id)
        # Best-effort: the property setter may not always know the
        # actor (no request context); the audit row's actor_user can
        # be None.

    def test_write_is_silently_ignored_for_derived_value(self):
        tenant, user = _seed()
        asset = Asset.objects.create(
            tenant=tenant, key=f"a-{uuid.uuid4().hex[:6]}", name="A",
            status=AssetStatus.ACTIVE,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            asset.visibility = AssetVisibility.PUBLIC  # attempted write
        # Status didn't change, so derived visibility stays INTERNAL.
        assert asset.status == AssetStatus.ACTIVE
        assert asset.visibility == AssetVisibility.INTERNAL

    def test_construction_with_visibility_kwarg_is_silently_ignored(self):
        """``Asset(visibility="PUBLIC", ...)`` MUST NOT crash for
        backwards compat with pre-phase-1 callers. The kwarg is
        absorbed, the deprecation signals fire, and the asset is
        created with the status-derived visibility."""
        tenant, user = _seed()
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always", DeprecationWarning)
            asset = Asset.objects.create(
                tenant=tenant,
                key=f"a-{uuid.uuid4().hex[:6]}",
                name="A",
                status=AssetStatus.ACTIVE,
                visibility=AssetVisibility.PUBLIC,  # legacy kwarg
            )
        # Asset persisted (no crash).
        assert Asset.objects.filter(id=asset.id).exists()
        # Derived visibility ignored the kwarg.
        assert asset.visibility == AssetVisibility.INTERNAL
        # Deprecation signal fired.
        deprecation_warnings = [
            w for w in captured if issubclass(w.category, DeprecationWarning)
        ]
        assert deprecation_warnings


# ---------------------------------------------------------------------------
# 250.3.B.4 — PATCH /assets/{id}/ silently ignores visibility in body
# ---------------------------------------------------------------------------


class PatchEndpointIgnoresVisibilityTest(TestCase):
    """A PATCH body containing ``visibility=PUBLIC`` returns 200 +
    the existing derived value. The asset's status (and therefore
    derived visibility) is NOT mutated by the visibility key in the
    body. Existing PATCH semantics for other fields (``name``,
    ``description``, etc.) keep working unchanged."""

    def setUp(self):
        self.tenant, self.user = _seed()
        # Promote to a role allowed to PATCH assets.
        self.user.roles = ["TENANT_ADMIN", "DATA_PROVIDER"]
        self.user.save(update_fields=["roles"])
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"a-{uuid.uuid4().hex[:6]}",
            name="OriginalName",
            status=AssetStatus.ACTIVE,
        )

    def test_patch_with_only_visibility_returns_200_and_doesnt_mutate_status(self):
        url = f"/api/v1/assets/{self.asset.id}/"
        before_status = self.asset.status
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            resp = self.client.patch(
                url,
                data={"visibility": "PUBLIC", "version": self.asset.version},
                format="json",
            )
        # PATCH succeeded (the visibility was silently ignored, no error).
        assert resp.status_code in (200, 202), resp.content
        self.asset.refresh_from_db()
        assert self.asset.status == before_status
        # Response carries the derived visibility, not the body value.
        body = resp.json()
        assert body.get("visibility") in ("INTERNAL", "PUBLIC")
        assert body["visibility"] == (
            "PUBLIC" if before_status == AssetStatus.PUBLIC else "INTERNAL"
        )

    def test_patch_with_visibility_AND_other_fields_only_changes_others(self):
        url = f"/api/v1/assets/{self.asset.id}/"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            resp = self.client.patch(
                url,
                data={
                    "name": "UpdatedName",
                    "visibility": "PUBLIC",  # ignored
                    "version": self.asset.version,
                },
                format="json",
            )
        assert resp.status_code in (200, 202), resp.content
        self.asset.refresh_from_db()
        assert self.asset.name == "UpdatedName"
        assert self.asset.status == AssetStatus.ACTIVE


# ---------------------------------------------------------------------------
# 250.3.B.7 — POST /assets/ phase-1 backwards compat
# ---------------------------------------------------------------------------


class PostEndpointAcceptsVisibilityForBackcompatTest(TestCase):
    """A pre-phase-1 client posting ``visibility=PUBLIC`` STILL
    creates the asset (no 400). The visibility kwarg is absorbed,
    a deprecation warning is logged, an audit event fires, and the
    asset is created with status=DRAFT (and therefore derived
    visibility=INTERNAL)."""

    def setUp(self):
        self.tenant, self.user = _seed()
        self.user.roles = ["TENANT_ADMIN", "DATA_PROVIDER"]
        self.user.save(update_fields=["roles"])
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_post_with_visibility_succeeds_with_derived_internal(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            resp = self.client.post(
                "/api/v1/assets/",
                data={
                    "key": f"a-{uuid.uuid4().hex[:6]}",
                    "name": "Backcompat",
                    "visibility": "PUBLIC",  # legacy
                },
                format="json",
            )
        assert resp.status_code == 201, resp.content
        body = resp.json()
        # New asset is DRAFT by default → derived visibility INTERNAL.
        assert body["status"] == AssetStatus.DRAFT
        assert body["visibility"] == AssetVisibility.INTERNAL


# ---------------------------------------------------------------------------
# 250.3.B.8 — Cache-Control: no-cache window on /assets/
# ---------------------------------------------------------------------------


class AssetEndpointDeprecationHeadersTest(TestCase):
    """Phase-1 deploy MUST emit:

    * ``Deprecation: true`` so RFC-8594 clients (the FE interceptor)
      can detect the deprecation window without parsing the body.
    * ``Sunset: <RFC-7231 date>`` pointing at the phase-2 column-drop
      target.
    * ``Cache-Control: no-cache, no-store, must-revalidate`` for the
      first 7 days post-deploy so cached pre-deploy responses (which
      carried the stored ``visibility`` column) don't surface stale
      values to admins.
    """

    def setUp(self):
        self.tenant, self.user = _seed()
        self.user.roles = ["TENANT_ADMIN"]
        self.user.save(update_fields=["roles"])
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_assets_list_carries_deprecation_and_sunset_headers(self):
        resp = self.client.get("/api/v1/assets/")
        # Don't assert status (may be 200 or 401 depending on test
        # setup); the HEADER contract is what we're pinning.
        assert "Deprecation" in resp, list(resp.headers.keys())
        assert resp["Deprecation"] == "true"
        assert "Sunset" in resp
        # RFC-7231 date format: e.g. "Wed, 21 Oct 2026 07:28:00 GMT"
        assert "GMT" in resp["Sunset"]

    def test_assets_list_carries_no_cache_during_window(self):
        from django.test import override_settings
        from datetime import datetime, timezone, timedelta

        # The window-end is far in the future for this test so the
        # no-cache header is guaranteed active regardless of when
        # the suite runs.
        future = datetime.now(timezone.utc) + timedelta(days=30)
        with override_settings(
            ASSET_VISIBILITY_DEPRECATION_NO_CACHE_UNTIL=future
        ):
            resp = self.client.get("/api/v1/assets/")
        assert "Cache-Control" in resp
        cc = resp["Cache-Control"]
        assert "no-cache" in cc
        assert "no-store" in cc
