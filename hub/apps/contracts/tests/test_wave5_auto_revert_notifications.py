"""
Phase 227 Wave 5 — auto-revert notification tests.

Pins two W5 deliverables end-to-end:

* **W5.1** — T+30 final-warning helper + management driver. Every
  TENANT_ADMIN of every tenant whose **currently-active** contracts
  remain structureless 14 days before W5 cutover gets one email; the
  driver is idempotent per tenant; per-recipient failures don't block
  the batch; an all-failed batch leaves no audit row so retries can
  self-heal.
* **W5.3** — per-asset notification when the apply-asset-revert path
  demotes an asset. Each TENANT_ADMIN of the affected tenant gets one
  in-app notification + one email naming the asset, the contract id,
  the previous status, and the restoration playbook. Notification
  dispatch failures do NOT roll back the asset demotion (the demotion
  is the load-bearing operation).

No mocks of internal code paths — real Tenant + User + UserRole +
Asset + Contract rows; real ``send_email_async`` (test container's
backend is a no-op so dispatches succeed without sending); real
``create_user_notification`` (writes a ``UserNotification`` row).
"""
from __future__ import annotations

import datetime as _dt
import json
import uuid
from io import StringIO
from typing import Any
from unittest import mock

import pytest
from django.core.management import CommandError, call_command
from django.test import TestCase
from django.utils import timezone


# ---------------------------------------------------------------------------
# Fixture helpers (mirror W2/W4 driver test conventions)
# ---------------------------------------------------------------------------


def _create_tenant(prefix: str = "W5"):
    from hub.apps.tenants.models import Tenant

    suffix = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"{prefix} Co {suffix}",
        slug=f"{prefix.lower()}-co-{suffix}",
    )


def _create_user(email: str, tenant):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return User.objects.create(email=email, tenant=tenant)


def _grant_tenant_admin_role(user, tenant):
    from hub.apps.users.models import Role, UserRole

    role, _ = Role.objects.get_or_create(tenant=tenant, name="TENANT_ADMIN")
    UserRole.objects.get_or_create(user=user, tenant=tenant, role=role)


def _create_asset(tenant, *, status="ACTIVE"):
    from hub.apps.assets.models import Asset

    suffix = uuid.uuid4().hex[:6]
    return Asset.objects.create(
        tenant=tenant,
        key=f"asset-{suffix}",
        name=f"Asset {suffix}",
        status=status,
    )


def _create_structureless_active_contract(tenant, *, asset=None):
    """Real contract — currently ACTIVE — whose normalised payload
    has no resolvable structure. Mirrors the customer-action cohort
    that Wave 5 demotes."""
    from hub.apps.contracts.models import Contract

    yaml = (
        "kind: DataContract\n"
        "apiVersion: v3.0.2\n"
        "id: bad\n"
        "name: bad\n"
        "version: 1.0.0\n"
        "status: active\n"
        "info:\n"
        "  description: no schema\n"
    )
    return Contract.objects.create(
        tenant=tenant,
        asset=asset,
        version=1,
        original_spec_type="ODCS",
        original_spec_version="3.0.2",
        original_format="YAML",
        original_raw=yaml,
        hub_contract_json={"models": [], "schema": {"fields": []}},
        normalization_status="NORMALIZED_OK",
        validation_status="VALID",
        status="ACTIVE",
    )


# ===========================================================================
# W5.1 — Final-warning email type registration
# ===========================================================================


def test_w5_email_type_registered():
    """``EmailType`` must register the W5 final-warning entry so
    subscribers / business-rules-validation paths recognise it."""
    from hub.apps.notifications.models import EmailType

    assert hasattr(EmailType, "ASSET_AUTO_REVERT_WARNING"), (
        "EmailType must register ASSET_AUTO_REVERT_WARNING for the "
        "W5.1 T+30 final warning email"
    )
    assert (
        EmailType.ASSET_AUTO_REVERT_WARNING.value
        == "ASSET_AUTO_REVERT_WARNING"
    )


def test_w53_email_type_registered():
    """``EmailType`` must register the W5.3 per-asset post-revert
    notification email type."""
    from hub.apps.notifications.models import EmailType

    assert hasattr(EmailType, "ASSET_AUTO_REVERTED_NOTIFICATION"), (
        "EmailType must register ASSET_AUTO_REVERTED_NOTIFICATION "
        "for the W5.3 post-revert per-asset notification"
    )
    assert (
        EmailType.ASSET_AUTO_REVERTED_NOTIFICATION.value
        == "ASSET_AUTO_REVERTED_NOTIFICATION"
    )


# ===========================================================================
# W5.1 — Final-warning notification helper
# ===========================================================================


@pytest.mark.django_db(transaction=True)
class FinalWarningHelperTests(TestCase):
    """Helper at
    ``hub.apps.contracts.notifications.asset_auto_revert_warning``
    sends one email per TENANT_ADMIN of a given tenant carrying the
    list of structureless ACTIVE contracts + the W5 deadline."""

    def test_dispatches_one_email_per_tenant_admin(self):
        from hub.apps.contracts.notifications.asset_auto_revert_warning import (
            send_final_warning_notification,
        )

        tenant = _create_tenant()
        admin1 = _create_user("a1@example.com", tenant)
        admin2 = _create_user("a2@example.com", tenant)
        plain = _create_user("plain@example.com", tenant)
        _grant_tenant_admin_role(admin1, tenant)
        _grant_tenant_admin_role(admin2, tenant)

        contract = _create_structureless_active_contract(tenant)

        results = send_final_warning_notification(
            tenant=tenant,
            structureless_contracts=[contract],
            deadline=_dt.date(2026, 6, 15),
        )
        recipients = sorted(r["to_email"] for r in results)
        assert recipients == ["a1@example.com", "a2@example.com"]
        assert plain.email not in recipients
        for r in results:
            assert r["success"] is True
            assert r["error"] is None
            assert r["email_type"] == "ASSET_AUTO_REVERT_WARNING"

    def test_per_recipient_failure_does_not_block_remaining_admins(self):
        """A broken email address for admin A must not block dispatch
        to admin B. Same fail-soft contract as W4/W2 helpers."""
        from hub.apps.contracts.notifications import (
            asset_auto_revert_warning as helper,
        )

        tenant = _create_tenant()
        bad = _create_user("bad@example.com", tenant)
        good = _create_user("good@example.com", tenant)
        _grant_tenant_admin_role(bad, tenant)
        _grant_tenant_admin_role(good, tenant)
        _create_structureless_active_contract(tenant)

        original = helper.send_email_async

        def _flaky(*args, **kwargs):
            if kwargs.get("to_email") == "bad@example.com":
                raise RuntimeError("simulated SES outage for one admin")
            return original(*args, **kwargs)

        with mock.patch.object(helper, "send_email_async", side_effect=_flaky):
            results = helper.send_final_warning_notification(
                tenant=tenant,
                structureless_contracts=[],
                deadline=_dt.date(2026, 6, 15),
            )

        emails_seen = {r["to_email"] for r in results}
        assert emails_seen == {"bad@example.com", "good@example.com"}
        outcomes = {r["to_email"]: r["success"] for r in results}
        assert outcomes["bad@example.com"] is False
        assert outcomes["good@example.com"] is True

    def test_no_admins_raises_typed_error(self):
        """Tenant without TENANT_ADMIN raises ``NoTenantAdminsError``
        — re-uses the wave 0 typed exception for caller convenience."""
        from hub.apps.contracts.notifications.asset_auto_revert_warning import (
            NoTenantAdminsError,
            send_final_warning_notification,
        )

        tenant = _create_tenant()
        # No admin role granted.
        with pytest.raises(NoTenantAdminsError):
            send_final_warning_notification(
                tenant=tenant,
                structureless_contracts=[],
                deadline=_dt.date(2026, 6, 15),
            )

    def test_email_template_renders_with_canonical_keys(self):
        """The W5 warning template must render cleanly and surface
        the deadline + tenant + contract list (the keys ops + the
        admins read at-a-glance)."""
        from hub.apps.notifications.templates import render_email_template

        rendered = render_email_template(
            "notifications/emails/asset_auto_revert_warning.html",
            {
                "tenant_name": "Acme Co",
                "app_name": "Meshant",
                "deadline_iso": "2026-06-15",
                "contracts": [
                    {
                        "id": str(uuid.uuid4()),
                        "name": "orders",
                        "spec_type": "ODCS",
                        "schema_editor_url": "https://x/y/edit?tab=schema",
                    },
                ],
            },
        )
        assert "Acme Co" in rendered["html"]
        assert "2026-06-15" in rendered["html"]
        assert "orders" in rendered["html"]
        assert "Meshant" in rendered["html"]


# ===========================================================================
# W5.1 — Management driver (wave5_send_final_warning_notifications)
# ===========================================================================


def _run_w51(*flags, **kwargs):
    out = StringIO()
    err = StringIO()
    args = ["wave5_send_final_warning_notifications", *flags]
    call_command(*args, stdout=out, stderr=err, **kwargs)
    return out.getvalue(), err.getvalue()


@pytest.mark.django_db(transaction=True)
class FinalWarningDriverScopeTests(TestCase):
    """Driver scope: by default targets ONLY tenants whose ACTIVE
    contracts are still structureless. Clean tenants are skipped so
    the W5 email doesn't reach customers who have already remediated."""

    def test_default_scope_excludes_clean_tenants(self):
        """Tenant with only well-formed (non-structureless) contracts
        is excluded from the default scope."""
        from hub.apps.audit.models import AuditEvent
        from hub.apps.contracts.models import Contract

        clean_tenant = _create_tenant("CLEAN")
        admin = _create_user("clean@example.com", clean_tenant)
        _grant_tenant_admin_role(admin, clean_tenant)
        # NOT structureless — populated models[]:
        Contract.objects.create(
            tenant=clean_tenant,
            version=1,
            original_spec_type="ODCS",
            original_spec_version="3.0.2",
            original_format="YAML",
            original_raw="kind: DataContract\nid: c\nname: c\nversion: 1.0.0\nstatus: active\n",
            hub_contract_json={"models": [{"name": "m", "fields": [{"name": "id", "type": "string"}]}]},
            normalization_status="NORMALIZED_OK",
            validation_status="VALID",
            status="ACTIVE",
        )

        deadline = (_dt.date.today() + _dt.timedelta(days=14)).isoformat()
        out, _ = _run_w51(f"--deadline={deadline}")

        # No NOTIFIED audit row written for the clean tenant.
        rows = AuditEvent.objects.filter(
            tenant=clean_tenant,
            action="ASSET_AUTO_REVERT_WARNING_NOTIFIED",
        )
        assert rows.count() == 0
        assert "sent=0" in out

    def test_default_scope_targets_structureless_active_tenants(self):
        from hub.apps.audit.models import AuditEvent

        residue_tenant = _create_tenant("RESID")
        admin = _create_user("resid@example.com", residue_tenant)
        _grant_tenant_admin_role(admin, residue_tenant)
        asset = _create_asset(residue_tenant, status="ACTIVE")
        _create_structureless_active_contract(residue_tenant, asset=asset)

        deadline = (_dt.date.today() + _dt.timedelta(days=14)).isoformat()
        out, _ = _run_w51(f"--deadline={deadline}")

        # Tenant got the warning and an audit row was written.
        rows = AuditEvent.objects.filter(
            tenant=residue_tenant,
            action="ASSET_AUTO_REVERT_WARNING_NOTIFIED",
        )
        assert rows.count() == 1
        assert "sent=1" in out

    def test_tenant_id_flag_targets_single_tenant(self):
        from hub.apps.audit.models import AuditEvent

        t1 = _create_tenant("TONE")
        t2 = _create_tenant("TTWO")
        for t in (t1, t2):
            admin = _create_user(f"{t.slug}@example.com", t)
            _grant_tenant_admin_role(admin, t)
            _create_structureless_active_contract(t)

        deadline = (_dt.date.today() + _dt.timedelta(days=14)).isoformat()
        _run_w51(f"--deadline={deadline}", f"--tenant-id={t1.id}")

        # Only t1 was notified.
        assert AuditEvent.objects.filter(
            tenant=t1, action="ASSET_AUTO_REVERT_WARNING_NOTIFIED"
        ).count() == 1
        assert AuditEvent.objects.filter(
            tenant=t2, action="ASSET_AUTO_REVERT_WARNING_NOTIFIED"
        ).count() == 0


@pytest.mark.django_db(transaction=True)
class FinalWarningDriverIdempotencyTests(TestCase):
    """Idempotency: a recent NOTIFIED audit row blocks re-send unless
    ``--force`` is set; an all-failed batch does NOT write the audit
    row so a retry can self-heal."""

    def test_recent_audit_row_blocks_resend(self):
        from hub.apps.audit.models import AuditEvent
        from hub.apps.audit.utils import create_audit_event

        tenant = _create_tenant("IDEM")
        admin = _create_user("idem@example.com", tenant)
        _grant_tenant_admin_role(admin, tenant)
        _create_structureless_active_contract(tenant)
        # Pre-existing NOTIFIED audit row.
        create_audit_event(
            tenant=tenant,
            resource_type="TENANT",
            action="ASSET_AUTO_REVERT_WARNING_NOTIFIED",
            resource_id=str(tenant.id),
            details={"phase": "227.W5.1"},
        )
        before = AuditEvent.objects.filter(
            tenant=tenant, action="ASSET_AUTO_REVERT_WARNING_NOTIFIED"
        ).count()

        deadline = (_dt.date.today() + _dt.timedelta(days=14)).isoformat()
        out, _ = _run_w51(f"--deadline={deadline}")

        after = AuditEvent.objects.filter(
            tenant=tenant, action="ASSET_AUTO_REVERT_WARNING_NOTIFIED"
        ).count()
        assert after == before, "second send should not write a new audit row"
        assert "skipped-idempotent" in out

    def test_force_bypasses_idempotency(self):
        from hub.apps.audit.models import AuditEvent
        from hub.apps.audit.utils import create_audit_event

        tenant = _create_tenant("FORCE")
        admin = _create_user("force@example.com", tenant)
        _grant_tenant_admin_role(admin, tenant)
        _create_structureless_active_contract(tenant)
        create_audit_event(
            tenant=tenant,
            resource_type="TENANT",
            action="ASSET_AUTO_REVERT_WARNING_NOTIFIED",
            resource_id=str(tenant.id),
            details={"phase": "227.W5.1"},
        )
        before = AuditEvent.objects.filter(
            tenant=tenant, action="ASSET_AUTO_REVERT_WARNING_NOTIFIED"
        ).count()

        deadline = (_dt.date.today() + _dt.timedelta(days=14)).isoformat()
        _run_w51(f"--deadline={deadline}", "--force")

        after = AuditEvent.objects.filter(
            tenant=tenant, action="ASSET_AUTO_REVERT_WARNING_NOTIFIED"
        ).count()
        assert after == before + 1, (
            "force should re-send AND record a fresh audit row capturing the intent"
        )

    def test_all_failed_batch_does_not_write_audit_row(self):
        """Critical retry-correctness invariant: if every dispatch in
        the batch failed (e.g. transient SES outage), the NOTIFIED
        row must NOT be written so the next run retries the tenant."""
        from hub.apps.audit.models import AuditEvent
        from hub.apps.contracts.notifications import (
            asset_auto_revert_warning as helper,
        )

        tenant = _create_tenant("ALLFAIL")
        admin = _create_user("af@example.com", tenant)
        _grant_tenant_admin_role(admin, tenant)
        _create_structureless_active_contract(tenant)

        with mock.patch.object(
            helper,
            "send_email_async",
            side_effect=RuntimeError("SES totally down"),
        ):
            deadline = (_dt.date.today() + _dt.timedelta(days=14)).isoformat()
            _run_w51(f"--deadline={deadline}")

        rows = AuditEvent.objects.filter(
            tenant=tenant, action="ASSET_AUTO_REVERT_WARNING_NOTIFIED"
        )
        assert rows.count() == 0, (
            "all-failed batch must NOT record the NOTIFIED row so retry "
            "can self-heal"
        )


@pytest.mark.django_db(transaction=True)
class FinalWarningDriverSafetyTests(TestCase):
    """Guard rails: dry-run, deadline validation, no-admin handling,
    audit-output JSONL trail."""

    def test_dry_run_writes_nothing(self):
        from hub.apps.audit.models import AuditEvent
        from hub.apps.notifications.models import EmailDelivery

        tenant = _create_tenant("DRY")
        admin = _create_user("dry@example.com", tenant)
        _grant_tenant_admin_role(admin, tenant)
        _create_structureless_active_contract(tenant)

        deadline = (_dt.date.today() + _dt.timedelta(days=14)).isoformat()
        out, _ = _run_w51(f"--deadline={deadline}", "--dry-run")

        assert "[dry-run]" in out
        assert AuditEvent.objects.filter(
            tenant=tenant, action="ASSET_AUTO_REVERT_WARNING_NOTIFIED"
        ).count() == 0
        # No EmailDelivery rows for this tenant.
        assert EmailDelivery.objects.filter(
            tenant_id=str(tenant.id),
            email_type="ASSET_AUTO_REVERT_WARNING",
        ).count() == 0

    def test_no_admin_tenant_skipped_not_crashed(self):
        """Tenant with structureless contracts but no admin produces
        ``[skipped-no-admin]`` not a stack trace."""
        from hub.apps.audit.models import AuditEvent

        tenant = _create_tenant("NOADM")
        # No admin role granted; just a plain user.
        _create_user("plain@example.com", tenant)
        _create_structureless_active_contract(tenant)

        deadline = (_dt.date.today() + _dt.timedelta(days=14)).isoformat()
        out, _ = _run_w51(f"--deadline={deadline}")

        assert "[skipped-no-admin]" in out
        assert AuditEvent.objects.filter(
            tenant=tenant, action="ASSET_AUTO_REVERT_WARNING_NOTIFIED"
        ).count() == 0

    def test_past_deadline_raises_command_error(self):
        from hub.apps.audit.models import AuditEvent

        # CommandError is raised during argument parsing, not after.
        with pytest.raises(CommandError):
            _run_w51("--deadline=2020-01-01")

    def test_audit_output_writes_jsonl_artefact(self, tmp_path=None):
        """``--audit-output`` writes a per-dispatch JSONL audit trail
        for cross-checking against ``EmailDelivery`` rows."""
        import tempfile

        tenant = _create_tenant("JSONL")
        admin = _create_user("jsonl@example.com", tenant)
        _grant_tenant_admin_role(admin, tenant)
        _create_structureless_active_contract(tenant)

        with tempfile.NamedTemporaryFile(
            mode="r", suffix=".jsonl", delete=False
        ) as fp:
            audit_path = fp.name

        deadline = (_dt.date.today() + _dt.timedelta(days=14)).isoformat()
        _run_w51(
            f"--deadline={deadline}",
            f"--audit-output={audit_path}",
        )

        with open(audit_path, "r") as fp:
            lines = [json.loads(ln) for ln in fp if ln.strip()]
        assert len(lines) >= 1
        rec = lines[0]
        # Canonical keys for ops cross-check.
        for key in ("tenant_id", "to_email", "email_type", "success", "deadline"):
            assert key in rec, f"audit JSONL missing {key!r}"


# ===========================================================================
# W5.3 — Per-asset notification on auto-revert
# ===========================================================================


def _run_apply_revert(*, tenant):
    out = StringIO()
    call_command(
        "renormalize_contracts",
        "--spec-version=3.1.0",
        "--filter=structureless",
        "--apply",
        "--apply-asset-revert",
        f"--tenant-id={tenant.id}",
        stdout=out,
    )
    return out.getvalue()


@pytest.mark.django_db(transaction=True)
class AssetAutoRevertNotificationTests(TestCase):
    """When the apply-asset-revert path demotes an asset, every
    TENANT_ADMIN of the asset's tenant gets one email + one in-app
    UserNotification carrying the asset name, the contract id, the
    previous status, and a restoration deep-link."""

    def test_email_sent_to_each_tenant_admin(self):
        from hub.apps.notifications.models import EmailDelivery

        tenant = _create_tenant("REV")
        admin1 = _create_user("rev1@example.com", tenant)
        admin2 = _create_user("rev2@example.com", tenant)
        plain = _create_user("plain@example.com", tenant)
        _grant_tenant_admin_role(admin1, tenant)
        _grant_tenant_admin_role(admin2, tenant)
        asset = _create_asset(tenant, status="ACTIVE")
        _create_structureless_active_contract(tenant, asset=asset)

        before = EmailDelivery.objects.filter(
            email_type="ASSET_AUTO_REVERTED_NOTIFICATION",
            tenant_id=str(tenant.id),
        ).count()
        _run_apply_revert(tenant=tenant)
        after = EmailDelivery.objects.filter(
            email_type="ASSET_AUTO_REVERTED_NOTIFICATION",
            tenant_id=str(tenant.id),
        ).count()

        # One email per tenant admin (2 admins → 2 emails).
        assert after - before == 2, (
            f"Expected 2 ASSET_AUTO_REVERTED_NOTIFICATION emails (one per "
            f"admin); got {after - before}"
        )
        recipients = set(
            EmailDelivery.objects.filter(
                email_type="ASSET_AUTO_REVERTED_NOTIFICATION",
                tenant_id=str(tenant.id),
            ).values_list("to_email", flat=True)
        )
        assert recipients == {"rev1@example.com", "rev2@example.com"}
        assert "plain@example.com" not in recipients

    def test_in_app_notification_created_per_admin(self):
        from hub.apps.notifications.models import UserNotification

        tenant = _create_tenant("INAPP")
        admin = _create_user("inapp@example.com", tenant)
        _grant_tenant_admin_role(admin, tenant)
        asset = _create_asset(tenant, status="ACTIVE")
        _create_structureless_active_contract(tenant, asset=asset)

        _run_apply_revert(tenant=tenant)

        rows = UserNotification.objects.filter(
            user=admin,
            tenant=tenant,
            resource_type="ASSET",
            resource_id=asset.id,
        )
        assert rows.count() == 1, (
            f"Expected exactly one in-app UserNotification for the admin; "
            f"got {rows.count()}"
        )
        n = rows.first()
        assert "DRAFT" in n.message or "structureless" in n.message.lower(), (
            f"in-app message should mention the demotion / structureless "
            f"reason; got {n.message!r}"
        )

    def test_revert_does_not_emit_notification_when_no_revert(self):
        """If the asset was already DRAFT (so no revert applied), the
        notification helper must not be called — there's nothing to
        notify about."""
        from hub.apps.notifications.models import EmailDelivery, UserNotification

        tenant = _create_tenant("NOREV")
        admin = _create_user("norev@example.com", tenant)
        _grant_tenant_admin_role(admin, tenant)
        asset = _create_asset(tenant, status="DRAFT")  # already DRAFT
        _create_structureless_active_contract(tenant, asset=asset)

        _run_apply_revert(tenant=tenant)

        assert EmailDelivery.objects.filter(
            email_type="ASSET_AUTO_REVERTED_NOTIFICATION",
            tenant_id=str(tenant.id),
        ).count() == 0
        assert UserNotification.objects.filter(
            tenant=tenant, resource_type="ASSET", resource_id=asset.id,
        ).count() == 0

    def test_notification_failure_does_not_roll_back_revert(self):
        """A simulated SES outage during revert notification must NOT
        roll back the asset demotion — the demotion is the load-
        bearing operation; notifications are best-effort."""
        from hub.apps.assets.models import AssetStatus
        from hub.apps.contracts.notifications import asset_auto_revert_warning  # noqa: F401 — ensures module loadable

        tenant = _create_tenant("FAIL")
        admin = _create_user("fail@example.com", tenant)
        _grant_tenant_admin_role(admin, tenant)
        asset = _create_asset(tenant, status="ACTIVE")
        _create_structureless_active_contract(tenant, asset=asset)

        # Patch the per-asset notification helper to raise.
        with mock.patch(
            "hub.apps.contracts.notifications.asset_auto_reverted."
            "send_asset_auto_reverted_notification",
            side_effect=Exception("simulated notification backend outage"),
        ):
            _run_apply_revert(tenant=tenant)

        asset.refresh_from_db()
        assert asset.status == AssetStatus.DRAFT, (
            "Asset demotion is the load-bearing op; a notification "
            "failure must NOT roll it back"
        )
