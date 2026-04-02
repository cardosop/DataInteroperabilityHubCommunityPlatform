"""Phase 87: Tests for JWT scope bypass prevention."""
from unittest.mock import MagicMock
from django.test import TestCase, override_settings
from hub.apps.auth.permissions import (
    HasScope, HasAnyScope, ROLE_SCOPE_MAP,
)


def _make_request(roles=None, api_key_scopes=None, is_platform_admin=False):
    """Build a mock request with the given roles/scopes."""
    request = MagicMock()
    user = MagicMock()
    user.is_authenticated = True
    user.is_platform_admin = is_platform_admin
    user.id = 1

    # Build role objects
    if roles:
        role_mocks = []
        for r in roles:
            ur = MagicMock()
            ur.role.name = r
            role_mocks.append(ur)
        user.user_roles.all.return_value = role_mocks
    else:
        user.user_roles.all.return_value = []

    request.user = user
    # Store roles on request so _get_user_scopes can resolve without DB
    request._roles = roles or []

    if api_key_scopes is not None:
        request.api_key_scopes = api_key_scopes
    else:
        # Ensure hasattr(request, 'api_key_scopes') is False
        del request.api_key_scopes

    return request


class TestScopeBypassPrevention(TestCase):
    """Verify that JWT users are subject to role-scope enforcement."""

    @override_settings(ENFORCE_JWT_SCOPES=True)
    def test_data_viewer_denied_assets_write_when_enforced(self):
        """DATA_VIEWER should NOT have assets:write."""
        request = _make_request(roles=["DATA_VIEWER"])
        perm = HasScope("assets:write")
        self.assertFalse(perm.has_permission(request, view=None))

    @override_settings(ENFORCE_JWT_SCOPES=True)
    def test_tenant_admin_allowed_any_scope_when_enforced(self):
        """TENANT_ADMIN should have assets:write."""
        request = _make_request(roles=["TENANT_ADMIN"])
        perm = HasScope("assets:write")
        self.assertTrue(perm.has_permission(request, view=None))

    @override_settings(ENFORCE_JWT_SCOPES=True)
    def test_data_viewer_allowed_assets_read_when_enforced(self):
        """DATA_VIEWER should have assets:read."""
        request = _make_request(roles=["DATA_VIEWER"])
        perm = HasScope("assets:read")
        self.assertTrue(perm.has_permission(request, view=None))

    @override_settings(ENFORCE_JWT_SCOPES=False)
    def test_jwt_user_allowed_without_enforcement(self):
        """Legacy mode: DATA_VIEWER can access assets:write when flag is off."""
        request = _make_request(roles=["DATA_VIEWER"])
        perm = HasScope("assets:write")
        self.assertTrue(perm.has_permission(request, view=None))

    def test_api_key_with_explicit_scope_works(self):
        """API key with assets:read should pass HasScope('assets:read')."""
        request = _make_request(api_key_scopes=["assets:read"])
        perm = HasScope("assets:read")
        self.assertTrue(perm.has_permission(request, view=None))

    def test_api_key_without_scope_denied(self):
        """API key with only assets:read should fail HasScope('assets:write')."""
        request = _make_request(api_key_scopes=["assets:read"])
        perm = HasScope("assets:write")
        self.assertFalse(perm.has_permission(request, view=None))

    def test_platform_admin_bypasses_all(self):
        """Platform admin should bypass all scope checks."""
        request = _make_request(is_platform_admin=True)
        perm = HasScope("assets:write")
        self.assertTrue(perm.has_permission(request, view=None))

    @override_settings(ENFORCE_JWT_SCOPES=True)
    def test_has_any_scope_data_consumer(self):
        """DATA_CONSUMER has assets:read, so HasAnyScope(['assets:read', 'assets:write']) should pass."""
        request = _make_request(roles=["DATA_CONSUMER"])
        perm = HasAnyScope(["assets:read", "assets:write"])
        self.assertTrue(perm.has_permission(request, view=None))

    @override_settings(ENFORCE_JWT_SCOPES=True)
    def test_has_any_scope_data_viewer_denied(self):
        """DATA_VIEWER lacks both assets:write and datasets:write."""
        request = _make_request(roles=["DATA_VIEWER"])
        perm = HasAnyScope(["assets:write", "datasets:write"])
        self.assertFalse(perm.has_permission(request, view=None))

    def test_unauthenticated_denied(self):
        """Unauthenticated user should be denied."""
        request = MagicMock()
        request.user = MagicMock()
        request.user.is_authenticated = False
        perm = HasScope("assets:read")
        self.assertFalse(perm.has_permission(request, view=None))

    @override_settings(ENFORCE_JWT_SCOPES=True)
    def test_auditor_allowed_audit_read(self):
        """AUDITOR should have audit:read scope."""
        request = _make_request(roles=["AUDITOR"])
        perm = HasScope("audit:read")
        self.assertTrue(perm.has_permission(request, view=None))

    @override_settings(ENFORCE_JWT_SCOPES=True)
    def test_auditor_denied_assets_write(self):
        """AUDITOR must NOT have write scopes."""
        request = _make_request(roles=["AUDITOR"])
        perm = HasScope("assets:write")
        self.assertFalse(perm.has_permission(request, view=None))

    @override_settings(ENFORCE_JWT_SCOPES=True)
    def test_compliance_officer_allowed_compliance_write(self):
        """COMPLIANCE_OFFICER should have compliance:write."""
        request = _make_request(roles=["COMPLIANCE_OFFICER"])
        perm = HasScope("compliance:write")
        self.assertTrue(perm.has_permission(request, view=None))

    @override_settings(ENFORCE_JWT_SCOPES=True)
    def test_authenticated_no_roles_denied(self):
        """Authenticated user with zero roles must fail scope check."""
        request = _make_request(roles=[])
        perm = HasScope("assets:read")
        self.assertFalse(perm.has_permission(request, view=None))


class TestRoleScopeMapConsistency(TestCase):
    """Sanity checks on the ROLE_SCOPE_MAP itself."""

    def test_platform_admin_has_wildcard(self):
        self.assertIn("*", ROLE_SCOPE_MAP["PLATFORM_ADMIN"])

    def test_data_viewer_is_read_only(self):
        scopes = ROLE_SCOPE_MAP["DATA_VIEWER"]
        for scope in scopes:
            self.assertTrue(
                scope.endswith(":read"),
                f"DATA_VIEWER has non-read scope: {scope}",
            )

    def test_data_consumer_has_no_write(self):
        scopes = ROLE_SCOPE_MAP["DATA_CONSUMER"]
        for scope in scopes:
            self.assertFalse(
                scope.endswith(":write"),
                f"DATA_CONSUMER has write scope: {scope}",
            )

    def test_tenant_admin_superset_of_data_provider(self):
        ta = ROLE_SCOPE_MAP["TENANT_ADMIN"]
        dp = ROLE_SCOPE_MAP["DATA_PROVIDER"]
        self.assertTrue(
            dp.issubset(ta),
            f"DATA_PROVIDER scopes not a subset of TENANT_ADMIN: {dp - ta}",
        )
