"""TDD pins for hybrid identity enforcement — D12 (task 0b.6).

No mocks: real Postgres rows (workspace, credential, binding, approval
request) and REAL audit rows. The pins cover the enforcement contract:

- INTERACTIVE purposes (live_query, catalog_browse, ddl_execution,
  job_run_now) REQUIRE an OBO provider — without one the resolution
  FAILS CLOSED (``DATABRICKS_OBO_REFRESH_FAILED``) even when an M2M
  credential is available; a credential passed alongside is ignored.
- BACKGROUND purposes (uc_sync, cost_sync, scheduled_export,
  deferred_ddl) resolve the workspace M2M credential WITH approver-chain
  audit linkage — the emitted audit row carries the approval-request id
  and the chain snapshot; a missing credential or a missing linkage
  violates the contract.
- Unknown purposes default-deny.
"""

import uuid

import pytest

from hub.apps.databricks_admin.tests._fixtures import REAL_HOST, require_dns
from hub.apps.databricks_admin.tests.test_views import (
    _activate_billing,
    _make_user,
)
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


def _setup():
    require_dns()
    from hub.apps.databricks_admin.models import (
        DatabricksCloud,
        DatabricksCredential,
        DatabricksCredentialAuthMode,
        DatabricksUserBinding,
        DatabricksWorkspace,
    )

    tenant = TenantFactory.create_tenant()
    _activate_billing(tenant)
    user = _make_user(tenant, f"ident-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN")
    workspace = DatabricksWorkspace.objects.create(
        tenant=tenant,
        name=f"ws-{uuid.uuid4().hex[:8]}",
        host=REAL_HOST,
        cloud=DatabricksCloud.AWS,
        region="us-east-1",
        status="ACTIVE",
    )
    binding = DatabricksUserBinding.objects.create(
        tenant=tenant,
        user=user,
        workspace=workspace,
        databricks_sub=f"sub-{uuid.uuid4().hex[:8]}",
        databricks_email=user.email,
    )
    m2m = DatabricksCredential.objects.create(
        workspace=workspace,
        auth_mode=DatabricksCredentialAuthMode.OAUTH_M2M,
        config={"client_id": "cid-1", "client_secret": "sec-1"},
    )
    return tenant, user, workspace, binding, m2m


def _obo_provider(binding):
    from hub.apps.databricks_admin.obo_tokens import OBOTokenProvider

    return OBOTokenProvider(
        binding=binding,
        oidc_client_id="client-abc",
        oidc_base_url=f"https://{REAL_HOST}",
    )


def _approval_request(tenant, user, workflow=("DATA_OWNER", "CDO")):
    from hub.apps.governance.models import AccessRequest, AccessRequestStatus
    from tests.factories import AssetFactory

    asset = AssetFactory.create(tenant=tenant)
    return AccessRequest.objects.create(
        tenant=tenant,
        requested_by=user,
        asset=asset,
        reason="Databricks workspace service-identity approval",
        requested_access_type="READ",
        status=AccessRequestStatus.APPROVED,
        approval_workflow=list(workflow),
        approvers=list(workflow),
    )


class TestInteractiveEnforcement:
    def test_interactive_requires_obo_and_ignores_m2m(self):
        from hub.apps.databricks_admin.identity import (
            INTERACTIVE_PURPOSES,
            resolve_execution_identity,
        )

        _tenant, _user, workspace, binding, m2m = _setup()
        for purpose in INTERACTIVE_PURPOSES:
            identity = resolve_execution_identity(
                purpose=purpose,
                workspace=workspace,
                obo_provider=_obo_provider(binding),
                credential=m2m,  # MUST be ignored on interactive paths
            )
            assert identity.kind == "obo"
            assert identity.obo_provider is not None
            assert identity.credential is None

    def test_interactive_without_obo_fails_closed_even_with_m2m_available(self):
        from hub.apps.databricks_admin.client import DatabricksOBOError
        from hub.apps.databricks_admin.identity import resolve_execution_identity

        _tenant, _user, workspace, _binding, m2m = _setup()
        with pytest.raises(DatabricksOBOError) as excinfo:
            resolve_execution_identity(
                purpose="live_query",
                workspace=workspace,
                obo_provider=None,
                credential=m2m,
            )
        assert excinfo.value.code == "DATABRICKS_OBO_REFRESH_FAILED"


class TestBackgroundEnforcement:
    def test_background_resolves_m2m_with_approval_linkage(self):
        from hub.apps.audit.models import AuditEvent
        from hub.apps.databricks_admin.identity import (
            BACKGROUND_PURPOSES,
            resolve_execution_identity,
        )

        tenant, user, workspace, _binding, m2m = _setup()
        approval = _approval_request(tenant, user)
        for purpose in BACKGROUND_PURPOSES:
            identity = resolve_execution_identity(
                purpose=purpose,
                workspace=workspace,
                credential=m2m,
                approval_request=approval,
            )
            assert identity.kind == "m2m"
            assert identity.credential_id == m2m.id
            assert identity.approval_linkage["approval_request_id"] == str(approval.id)
            assert identity.approval_linkage["approver_chain"] == ["DATA_OWNER", "CDO"]

        # The resolution itself is audited with the linkage.
        event = AuditEvent.objects.filter(action="RESOLVED").order_by("-timestamp").first()
        assert event is not None
        assert event.resource_type == "DATABRICKS_EXECUTION_IDENTITY"
        details = event.details_json or {}
        assert details.get("purpose") in BACKGROUND_PURPOSES
        assert details.get("kind") == "m2m"
        assert details.get("approval_request_id") == str(approval.id)

    def test_background_without_m2m_credential_violates(self):
        from hub.apps.databricks_admin.identity import (
            HybridIdentityError,
            resolve_execution_identity,
        )

        tenant, user, workspace, _binding, _m2m = _setup()
        approval = _approval_request(tenant, user)
        with pytest.raises(HybridIdentityError) as excinfo:
            resolve_execution_identity(
                purpose="uc_sync",
                workspace=workspace,
                credential=None,
                approval_request=approval,
            )
        assert excinfo.value.code == "DATABRICKS_HYBRID_IDENTITY_VIOLATION"

    def test_background_without_approval_linkage_violates(self):
        from hub.apps.databricks_admin.identity import (
            HybridIdentityError,
            resolve_execution_identity,
        )

        _tenant, _user, workspace, _binding, m2m = _setup()
        with pytest.raises(HybridIdentityError) as excinfo:
            resolve_execution_identity(
                purpose="cost_sync",
                workspace=workspace,
                credential=m2m,
                approval_request=None,
            )
        assert excinfo.value.code == "DATABRICKS_HYBRID_IDENTITY_VIOLATION"

    def test_background_rejects_a_foreign_workspace_credential(self):
        from hub.apps.databricks_admin.identity import (
            HybridIdentityError,
            resolve_execution_identity,
        )

        tenant, user, workspace, _binding, _m2m = _setup()
        from hub.apps.databricks_admin.models import DatabricksCloud, DatabricksWorkspace

        other_workspace = DatabricksWorkspace.objects.create(
            tenant=tenant,
            name=f"ws-other-{uuid.uuid4().hex[:8]}",
            host=REAL_HOST,
            cloud=DatabricksCloud.AWS,
            region="us-east-1",
        )
        from hub.apps.databricks_admin.models import (
            DatabricksCredential,
            DatabricksCredentialAuthMode,
        )

        foreign_m2m = DatabricksCredential.objects.create(
            workspace=other_workspace,
            auth_mode=DatabricksCredentialAuthMode.OAUTH_M2M,
            config={"client_id": "cid-x", "client_secret": "sec-x"},
        )
        with pytest.raises(HybridIdentityError):
            resolve_execution_identity(
                purpose="uc_sync",
                workspace=workspace,
                credential=foreign_m2m,
                approval_request=_approval_request(tenant, user),
            )

    def test_background_rejects_a_pat_credential(self):
        from hub.apps.databricks_admin.identity import (
            HybridIdentityError,
            resolve_execution_identity,
        )

        tenant, user, workspace, _binding, _m2m = _setup()
        from hub.apps.databricks_admin.models import (
            DatabricksCredential,
            DatabricksCredentialAuthMode,
        )

        pat = DatabricksCredential.objects.create(
            workspace=workspace,
            auth_mode=DatabricksCredentialAuthMode.PAT,
            config={"token": "dapi-pat"},
        )
        with pytest.raises(HybridIdentityError):
            resolve_execution_identity(
                purpose="uc_sync",
                workspace=workspace,
                credential=pat,
                approval_request=_approval_request(tenant, user),
            )


class TestUnknownPurpose:
    def test_unknown_purpose_defaults_to_deny(self):
        from hub.apps.databricks_admin.identity import (
            HybridIdentityError,
            resolve_execution_identity,
        )

        _tenant, _user, workspace, binding, m2m = _setup()
        with pytest.raises(HybridIdentityError):
            resolve_execution_identity(
                purpose="something_new",
                workspace=workspace,
                obo_provider=_obo_provider(binding),
                credential=m2m,
            )


class TestGCPFallback:
    """0b.8 — U2M is unsupported on GCP: interactive purposes fall back to
    the workspace PAT/M2M credential instead of requiring OBO (fail-closed
    when no credential exists)."""

    def _gcp_setup(self):
        from hub.apps.databricks_admin.models import DatabricksCloud

        tenant, user, workspace, binding, m2m = _setup()
        workspace.cloud = DatabricksCloud.GCP
        workspace.save(update_fields=["cloud"])
        return tenant, user, workspace, binding, m2m

    def test_gcp_interactive_rejects_a_foreign_workspace_credential(self):
        from hub.apps.databricks_admin.identity import (
            HybridIdentityError,
            resolve_execution_identity,
        )

        tenant, _user, workspace, _binding, _m2m = self._gcp_setup()
        from hub.apps.databricks_admin.models import DatabricksCloud, DatabricksWorkspace

        other_workspace = DatabricksWorkspace.objects.create(
            tenant=tenant,
            name=f"ws-other-{uuid.uuid4().hex[:8]}",
            host=REAL_HOST,
            cloud=DatabricksCloud.AWS,
            region="us-east-1",
        )
        from hub.apps.databricks_admin.models import (
            DatabricksCredential,
            DatabricksCredentialAuthMode,
        )

        foreign_pat = DatabricksCredential.objects.create(
            workspace=other_workspace,
            auth_mode=DatabricksCredentialAuthMode.PAT,
            config={"token": "dapi-foreign"},
        )
        with pytest.raises(HybridIdentityError):
            resolve_execution_identity(
                purpose="live_query",
                workspace=workspace,
                credential=foreign_pat,
            )

    def test_gcp_interactive_accepts_own_pat(self):
        from hub.apps.databricks_admin.identity import resolve_execution_identity

        _tenant, _user, workspace, _binding, _m2m = self._gcp_setup()
        from hub.apps.databricks_admin.models import (
            DatabricksCredential,
            DatabricksCredentialAuthMode,
        )

        own_pat = DatabricksCredential.objects.create(
            workspace=workspace,
            auth_mode=DatabricksCredentialAuthMode.PAT,
            config={"token": "dapi-own-pat"},
        )
        identity = resolve_execution_identity(
            purpose="live_query",
            workspace=workspace,
            credential=own_pat,
        )
        assert identity.kind == "m2m"
        assert identity.credential_id == own_pat.id
        assert identity.approval_linkage == {"gcp_fallback": True}

    def test_gcp_interactive_falls_back_to_credential(self):
        from hub.apps.databricks_admin.identity import (
            INTERACTIVE_PURPOSES,
            resolve_execution_identity,
        )

        _tenant, _user, workspace, _binding, m2m = self._gcp_setup()
        for purpose in INTERACTIVE_PURPOSES:
            identity = resolve_execution_identity(
                purpose=purpose,
                workspace=workspace,
                obo_provider=None,  # no OBO — GCP fallback is expected
                credential=m2m,
            )
            assert identity.kind == "m2m"
            assert identity.credential_id == m2m.id

    def test_gcp_interactive_without_credential_fails_closed(self):
        from hub.apps.databricks_admin.identity import (
            HybridIdentityError,
            resolve_execution_identity,
        )

        _tenant, _user, workspace, _binding, _m2m = self._gcp_setup()
        with pytest.raises(HybridIdentityError) as excinfo:
            resolve_execution_identity(
                purpose="live_query",
                workspace=workspace,
                obo_provider=None,
                credential=None,
            )
        assert excinfo.value.code == "DATABRICKS_HYBRID_IDENTITY_VIOLATION"
