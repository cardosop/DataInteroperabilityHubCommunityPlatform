"""
Phase 270.C.5 — Tenant license validation for compliance regulations.

What this suite pins
====================
(REQ-COMPLIANCE-REG-LICENSE in
``openspec/changes/preprod01/specs/marketplace-tax-compliance-deltas/spec.md``):

1.  **FREE plan tenant requesting PIPL_CN → warning issue** (default
    lenient). The un-licensed regulation surfaces as a
    ``REGULATION_NOT_LICENSED`` entry on
    ``ComplianceRun.metadata_json["license_warnings"]`` and the
    scan proceeds normally. Operators see the warning in the run's
    detail page; downstream alerting can ingest the field.

2.  **strict_license_check=True → 422**. The same un-licensed-regs
    case escalates from warning to outright rejection via
    ``ValidationError(code="REGULATION_NOT_LICENSED")`` which the
    view layer renders as HTTP 422 ``REGULATION_NOT_LICENSED``.

3.  **ENTERPRISE plan with PIPL_CN licensed → no warning**. When
    every requested regulation IS in ``tenant.licensed_regulation_keys``,
    the check is a no-op — no warning, no rejection, run proceeds
    unchanged.

4.  **Empty ``licensed_regulation_keys`` disables the check entirely**
    (backward-compat for pre-Phase-270.C.5 tenants). Existing
    tenants whose ``licensed_regulation_keys`` is the default empty
    list DO NOT suddenly see warnings on every scan post-deploy.

NO MOCKS POLICY
===============
Tests run against the real ``ComplianceService.create_compliance_run``
service-layer entry point, real ``Tenant`` + ``TenantPlan`` rows,
and real ``ComplianceRun`` writes. No HTTP layer involved (the view
is a thin wrapper that surfaces the service layer's exceptions); we
test the service contract directly and assert on the returned
``ComplianceRun`` + the raised exception's ``code`` field.

The compliance-service microservice is NOT invoked in these tests —
the license check runs Hub-side BEFORE the run is dispatched to
the microservice. We assert on the state at the END of
``create_compliance_run`` (before the async dispatch), so no Redis
or external service is required.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.compliance.models import ComplianceRun
from hub.apps.compliance.services import ComplianceService
from hub.apps.core.services.base import ValidationError
from hub.apps.tenants.models import KYCStatus, Tenant, TenantPlan
from hub.apps.testing.billing_support import (
    ensure_tenant_has_active_subscription,
)
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _make_tenant_with_plan(
    *,
    plan_slug: str,
    plan_includes: list,
    tenant_licensed: list,
    strict_license_check: bool = False,
    prefix: str = "t",
):
    """Build a real Tenant + real TenantPlan FK chain. No factories
    so the test is hermetic + the field paths are explicit."""
    sfx = uuid.uuid4().hex[:8]
    plan = TenantPlan.objects.create(
        name=f"Plan {sfx}",
        slug=f"{plan_slug}-{sfx}",
        tier=plan_slug.upper(),
        is_active=True,
        includes_regulations=plan_includes,
    )
    tenant = Tenant.objects.create(
        name=f"T {sfx}",
        slug=f"{prefix}-{sfx}",
        status="ACTIVE",
        kyc_status=KYCStatus.VERIFIED,
        plan=plan,
        licensed_regulation_keys=tenant_licensed,
        strict_license_check=strict_license_check,
    )
    ensure_tenant_has_active_subscription(tenant)
    user = User.objects.create_user(
        email=f"{prefix}-{sfx}@example.com",
        password="testpass",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    asset = Asset.objects.create(
        tenant=tenant,
        key=f"asset-{sfx}",
        name="A",
        status=AssetStatus.ACTIVE,
        created_by=user,
    )
    return tenant, user, asset


# ---------------------------------------------------------------------------
# Tier 1 — lenient mode: out-of-set regulations → warning
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestLicenseLenientWarning(TestCase):
    """The spec's first case: FREE plan tenant requesting PIPL_CN
    → warning issue (default lenient). The scan proceeds; the
    un-licensed reg surfaces as a structured entry on
    ``ComplianceRun.metadata_json["license_warnings"]``."""

    @pytest.mark.integration
    def test_unlicensed_reg_produces_warning_on_metadata(self):
        tenant, user, asset = _make_tenant_with_plan(
            plan_slug="free",
            plan_includes=["GDPR"],
            tenant_licensed=["GDPR"],  # PIPL_CN NOT licensed
            strict_license_check=False,
        )
        service = ComplianceService(tenant_id=str(tenant.id))

        run = service.create_compliance_run(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
            asset_id=str(asset.id),
            scan_mode="internal",
            applicable_regulations=["GDPR", "PIPL_CN"],
            tenant=tenant,
            user=user,
            asset=asset,
        )

        # Run was created (lenient path doesn't block scan).
        assert isinstance(run, ComplianceRun)
        run.refresh_from_db()
        metadata = run.metadata_json or {}
        warnings = metadata.get("license_warnings") or []
        # Exactly one warning entry — for PIPL_CN; GDPR was licensed.
        codes = [w.get("code") for w in warnings]
        assert "REGULATION_NOT_LICENSED" in codes, warnings
        # The warning carries the un-licensed reg list.
        warning = next(w for w in warnings if w["code"] == "REGULATION_NOT_LICENSED")
        assert "PIPL_CN" in warning.get("regulations", [])
        assert "GDPR" not in warning.get("regulations", []), (
            "GDPR was licensed; must NOT appear in the warning"
        )
        # Severity is WARNING (not ERROR) — lenient mode.
        assert warning.get("severity") == "WARNING"

    @pytest.mark.integration
    def test_multiple_unlicensed_regs_in_single_warning(self):
        """The warning entry collects ALL un-licensed regs in
        ONE entry (not one warning per reg) — keeps the surface
        compact for operators."""
        tenant, user, asset = _make_tenant_with_plan(
            plan_slug="free",
            plan_includes=["GDPR"],
            tenant_licensed=["GDPR"],
            strict_license_check=False,
        )
        service = ComplianceService(tenant_id=str(tenant.id))
        run = service.create_compliance_run(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
            asset_id=str(asset.id),
            scan_mode="internal",
            applicable_regulations=["PIPL_CN", "DPDP_IN", "LGPD"],
            tenant=tenant,
            user=user,
            asset=asset,
        )
        run.refresh_from_db()
        warnings = (run.metadata_json or {}).get("license_warnings") or []
        assert len(warnings) == 1
        regs = set(warnings[0].get("regulations", []))
        assert regs == {"PIPL_CN", "DPDP_IN", "LGPD"}


# ---------------------------------------------------------------------------
# Tier 2 — strict mode: out-of-set regulations → 422 rejection
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestLicenseStrictRejection(TestCase):
    """The spec's second case: strict_license_check=True →
    ``ValidationError(code="REGULATION_NOT_LICENSED")`` which the
    view layer renders as HTTP 422. The run is NEVER created — no
    side effects on ComplianceRun / Job tables."""

    @pytest.mark.integration
    def test_strict_unlicensed_reg_raises_validation_error(self):
        tenant, user, asset = _make_tenant_with_plan(
            plan_slug="free",
            plan_includes=["GDPR"],
            tenant_licensed=["GDPR"],
            strict_license_check=True,
        )
        service = ComplianceService(tenant_id=str(tenant.id))

        # Snapshot the ComplianceRun count BEFORE the call — must
        # be unchanged after the rejection.
        before = ComplianceRun.objects.count()

        with pytest.raises(ValidationError) as exc_info:
            service.create_compliance_run(
                tenant_id=str(tenant.id),
                user_id=str(user.id),
                asset_id=str(asset.id),
                scan_mode="internal",
                applicable_regulations=["PIPL_CN"],
                tenant=tenant,
                user=user,
                asset=asset,
            )
        # Spec-mandated code.
        assert exc_info.value.code == "REGULATION_NOT_LICENSED"
        # Phase 270.C.5 audit-fix Gap 1 — the spec MANDATES HTTP
        # 422 on the strict-mode rejection. The view layer's
        # ``handle_service_exception`` reads ``http_status`` off
        # the exception (defaulting to 400 for ValidationError).
        # If this attribute isn't 422, the view returns 400 and
        # the spec contract is silently broken.
        assert exc_info.value.http_status == 422
        # Details carry the un-licensed reg list so the API can
        # render a structured response.
        details = exc_info.value.details or {}
        assert "PIPL_CN" in details.get("unlicensed_regulations", [])

        # No ComplianceRun was created — strict-mode rejection is
        # transactional.
        assert ComplianceRun.objects.count() == before

    @pytest.mark.integration
    def test_strict_all_licensed_succeeds(self):
        """Strict mode + all-licensed regulations → no rejection."""
        tenant, user, asset = _make_tenant_with_plan(
            plan_slug="enterprise",
            plan_includes=["GDPR", "PIPL_CN", "LGPD"],
            tenant_licensed=["GDPR", "PIPL_CN", "LGPD"],
            strict_license_check=True,
        )
        service = ComplianceService(tenant_id=str(tenant.id))
        run = service.create_compliance_run(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
            asset_id=str(asset.id),
            scan_mode="internal",
            applicable_regulations=["GDPR", "PIPL_CN"],
            tenant=tenant,
            user=user,
            asset=asset,
        )
        assert isinstance(run, ComplianceRun)


# ---------------------------------------------------------------------------
# Tier 3 — ENTERPRISE plan with PIPL_CN licensed → no warning
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestLicenseEnterpriseNoWarning(TestCase):
    """The spec's third case: ENTERPRISE plan tenant with PIPL_CN
    in their licensed set → no warning, no rejection. License
    check is a no-op when every requested reg is licensed."""

    @pytest.mark.integration
    def test_enterprise_with_pipl_cn_emits_no_warning(self):
        tenant, user, asset = _make_tenant_with_plan(
            plan_slug="enterprise",
            plan_includes=["GDPR", "UK_GDPR", "LGPD", "PIPL_CN", "DPDP_IN"],
            tenant_licensed=["GDPR", "UK_GDPR", "LGPD", "PIPL_CN", "DPDP_IN"],
            strict_license_check=False,
        )
        service = ComplianceService(tenant_id=str(tenant.id))
        run = service.create_compliance_run(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
            asset_id=str(asset.id),
            scan_mode="internal",
            applicable_regulations=["PIPL_CN"],
            tenant=tenant,
            user=user,
            asset=asset,
        )
        run.refresh_from_db()
        metadata = run.metadata_json or {}
        warnings = metadata.get("license_warnings") or []
        # No license_warnings key OR empty list — both acceptable.
        assert warnings == []


# ---------------------------------------------------------------------------
# Tier 4 — Backward-compat: empty licensed_regulation_keys disables check
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestLicenseCheckBackwardCompat(TestCase):
    """Pre-Phase-270.C.5 tenants have ``licensed_regulation_keys``
    as the empty list (the migration default). The check MUST be
    inactive in this state — otherwise every existing scan would
    surface warnings post-deploy + every strict-mode tenant would
    suddenly 422 on every scan."""

    @pytest.mark.integration
    def test_empty_licensed_set_skips_check_lenient(self):
        tenant, user, asset = _make_tenant_with_plan(
            plan_slug="free",
            plan_includes=[],
            tenant_licensed=[],  # default empty
            strict_license_check=False,
        )
        service = ComplianceService(tenant_id=str(tenant.id))
        run = service.create_compliance_run(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
            asset_id=str(asset.id),
            scan_mode="internal",
            applicable_regulations=["GDPR", "PIPL_CN", "LGPD"],
            tenant=tenant,
            user=user,
            asset=asset,
        )
        run.refresh_from_db()
        warnings = (run.metadata_json or {}).get("license_warnings") or []
        assert warnings == [], (
            "Empty licensed_regulation_keys must DISABLE the check "
            "entirely (backward-compat); got "
            f"{warnings}"
        )

    @pytest.mark.integration
    def test_empty_licensed_set_skips_check_even_with_strict(self):
        """Even when strict_license_check=True, an empty licensed
        set means the check is INACTIVE — strict mode only matters
        when the tenant has a non-empty licensed set to enforce
        against. Otherwise a deploy that flipped strict_license_check
        defensively on every tenant would 422 every scan."""
        tenant, user, asset = _make_tenant_with_plan(
            plan_slug="free",
            plan_includes=[],
            tenant_licensed=[],  # default empty
            strict_license_check=True,
        )
        service = ComplianceService(tenant_id=str(tenant.id))
        # Must NOT raise.
        run = service.create_compliance_run(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
            asset_id=str(asset.id),
            scan_mode="internal",
            applicable_regulations=["GDPR"],
            tenant=tenant,
            user=user,
            asset=asset,
        )
        assert isinstance(run, ComplianceRun)

    @pytest.mark.integration
    def test_no_applicable_regulations_skips_check(self):
        """A run with NO applicable_regulations (None or empty)
        skips the check — there's nothing to validate against."""
        tenant, user, asset = _make_tenant_with_plan(
            plan_slug="free",
            plan_includes=["GDPR"],
            tenant_licensed=["GDPR"],
            strict_license_check=True,
        )
        service = ComplianceService(tenant_id=str(tenant.id))
        run = service.create_compliance_run(
            tenant_id=str(tenant.id),
            user_id=str(user.id),
            asset_id=str(asset.id),
            scan_mode="internal",
            applicable_regulations=None,
            tenant=tenant,
            user=user,
            asset=asset,
        )
        assert isinstance(run, ComplianceRun)


# ---------------------------------------------------------------------------
# Tier 5 — ValidationError.code routes to HTTP 422 at view layer
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestValidationErrorCodeContract(TestCase):
    """The view layer relies on ``ValidationError.code`` to shape
    the HTTP response. This test pins the contract — if the code
    field is renamed/reshaped, the API consumer (frontend, CLI,
    SDK) breaks."""

    @pytest.mark.integration
    def test_validation_error_has_regulation_not_licensed_code(self):
        tenant, user, asset = _make_tenant_with_plan(
            plan_slug="free",
            plan_includes=["GDPR"],
            tenant_licensed=["GDPR"],
            strict_license_check=True,
        )
        service = ComplianceService(tenant_id=str(tenant.id))
        with pytest.raises(ValidationError) as exc_info:
            service.create_compliance_run(
                tenant_id=str(tenant.id),
                user_id=str(user.id),
                asset_id=str(asset.id),
                scan_mode="internal",
                applicable_regulations=["PIPL_CN"],
                tenant=tenant,
                user=user,
                asset=asset,
            )
        # Exactly this code — pinned to prevent drift.
        assert exc_info.value.code == "REGULATION_NOT_LICENSED"
        # Phase 270.C.5 audit-fix Gap 1 — pin the http_status so a
        # future refactor that drops the explicit
        # ``http_status=422`` kwarg can't silently regress the
        # spec'd 422 contract back to ValidationError's 400 default.
        assert exc_info.value.http_status == 422
        # Details carry the diagnostic info the API renders.
        details = exc_info.value.details or {}
        assert "unlicensed_regulations" in details
        assert "licensed_regulation_keys" in details
        assert "PIPL_CN" in details["unlicensed_regulations"]

    @pytest.mark.integration
    def test_view_layer_renders_422_end_to_end(self):
        """Pin the FULL exception → HTTP response pipeline. Pre-
        audit, even setting ``code="REGULATION_NOT_LICENSED"`` was
        not enough because the view's
        ``handle_service_exception(exc)`` reads
        ``getattr(exc, "http_status", 400)`` and returns the
        default 400 if the service didn't set
        ``http_status=422``. This test invokes the SAME mapping
        function the view layer uses, with the SAME exception the
        service raises, and asserts the rendered DRF Response
        carries 422.
        """
        from hub.apps.core.responses import handle_service_exception

        tenant, user, asset = _make_tenant_with_plan(
            plan_slug="free",
            plan_includes=["GDPR"],
            tenant_licensed=["GDPR"],
            strict_license_check=True,
        )
        service = ComplianceService(tenant_id=str(tenant.id))
        try:
            service.create_compliance_run(
                tenant_id=str(tenant.id),
                user_id=str(user.id),
                asset_id=str(asset.id),
                scan_mode="internal",
                applicable_regulations=["PIPL_CN"],
                tenant=tenant,
                user=user,
                asset=asset,
            )
            raise AssertionError("expected ValidationError")
        except ValidationError as exc:
            response = handle_service_exception(exc)

        assert response.status_code == 422, response.data
        # Response body shape: ``{code, message, details}`` per
        # ``api_error_response`` (see hub/apps/core/responses.py).
        # The structured payload survives the view layer.
        assert response.data.get("code") == "REGULATION_NOT_LICENSED"
        details = response.data.get("details") or {}
        assert "PIPL_CN" in details.get("unlicensed_regulations", [])
