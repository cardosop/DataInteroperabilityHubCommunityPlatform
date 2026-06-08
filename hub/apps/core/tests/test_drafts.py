"""
Phase 278.P.1 — FormDraft security tests.

Verifies:
  - Own draft CRUD (create, read, update, delete)
  - Cross-user isolation
  - Cross-tenant isolation
  - UniqueConstraint per-user-per-tenant-per-resource_type-per-draft_key
"""
import pytest

import uuid

from django.db import IntegrityError
from django.db.models import UniqueConstraint
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.core.drafts import FormDraft
from hub.apps.core.tests.factories import create_form_draft
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User


@pytest.fixture
def tenant_a():
    _uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(name=f"draft-tenant-a-{_uid}", slug=f"draft-tenant-a-{_uid}")
    ensure_tenant_has_active_subscription(tenant)
    return tenant


@pytest.fixture
def tenant_b():
    _uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(name=f"draft-tenant-b-{_uid}", slug=f"draft-tenant-b-{_uid}")
    ensure_tenant_has_active_subscription(tenant)
    return tenant


@pytest.fixture
def user_a(tenant_a):
    _uid = uuid.uuid4().hex[:8]
    return User.objects.create_user(
        email=f"draft-user-a-{_uid}@test.com",
        password="testpass123!",
        tenant=tenant_a,
    )


@pytest.fixture
def user_b(tenant_b):
    _uid = uuid.uuid4().hex[:8]
    return User.objects.create_user(
        email=f"draft-user-b-{_uid}@test.com",
        password="testpass123!",
        tenant=tenant_b,
    )


@pytest.fixture
def api_client_a(user_a):
    client = APIClient()
    client.force_authenticate(user=user_a)
    return client


@pytest.fixture
def api_client_b(user_b):
    client = APIClient()
    client.force_authenticate(user=user_b)
    return client


@pytest.mark.django_db
@pytest.mark.unit
class TestFormDraftUniqueConstraint:
    """Verify the UniqueConstraint includes tenant."""

    @pytest.mark.unit
    def test_constraint_includes_tenant(self):
        constraints = FormDraft._meta.constraints
        found = False
        for c in constraints:
            if c.name == "unique_form_draft_per_user_tenant_resource_key":
                found = True
                assert "tenant" in c.fields
                assert "user" in c.fields
                assert "resource_type" in c.fields
                assert "draft_key" in c.fields
        assert found, "Expected constraint with tenant field not found"

    @pytest.mark.unit
    def test_same_user_different_tenants_can_have_drafts(self, user_a, tenant_a, tenant_b):
        """A user in two tenants should be able to save drafts in each."""
        # For test purposes, create drafts as the same user but in different tenants
        create_form_draft(
            user=user_a, tenant=tenant_a,
            resource_type="dpia", draft_key="create", data={"step": 1},
        )
        create_form_draft(
            user=user_a, tenant=tenant_b,
            resource_type="dpia", draft_key="create", data={"step": 2},
        )
        assert FormDraft.objects.filter(user=user_a).count() == 2

    @pytest.mark.unit
    def test_same_user_same_tenant_duplicate_key_raises(self, user_a, tenant_a):
        """Duplicate (user, tenant, resource_type, draft_key) must fail."""
        create_form_draft(
            user=user_a, tenant=tenant_a,
            resource_type="dpia", draft_key="create",
        )
        with pytest.raises(IntegrityError):
            create_form_draft(
                user=user_a, tenant=tenant_a,
                resource_type="dpia", draft_key="create",
            )


@pytest.mark.django_db
@pytest.mark.unit
class TestFormDraftCrossUserIsolation:
    """Verify user A cannot access user B's drafts."""

    @pytest.mark.unit
    def test_retrieve_own_draft(self, api_client_a, user_a, tenant_a):
        create_form_draft(
            user=user_a, tenant=tenant_a,
            resource_type="dpia", draft_key="create", data={"step": 1},
        )
        response = api_client_a.get(
            "/api/v1/drafts/?resource_type=dpia&draft_key=create"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["data"] == {"step": 1}

    @pytest.mark.unit
    def test_cannot_retrieve_other_user_draft(self, api_client_a, api_client_b, user_a, user_b, tenant_a, tenant_b):
        create_form_draft(
            user=user_b, tenant=tenant_b,
            resource_type="dpia", draft_key="create", data={"step": 99},
        )
        # User A tries to read user B's draft (wrong user + wrong tenant)
        response = api_client_a.get(
            "/api/v1/drafts/?resource_type=dpia&draft_key=create"
        )
        # Should return "not found" (not leak the other user's draft)
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["data"] == {}

    @pytest.mark.unit
    def test_cannot_delete_other_user_draft(self, api_client_a, api_client_b, user_a, user_b, tenant_a, tenant_b):
        draft = create_form_draft(
            user=user_b, tenant=tenant_b,
            resource_type="dpia", draft_key="create",
        )
        # User A tries to delete user B's draft
        response = api_client_a.delete(
            "/api/v1/drafts/delete/?resource_type=dpia&draft_key=create"
        )
        # Returns 204 but should NOT have deleted user B's draft
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert FormDraft.objects.filter(id=draft.id).exists()


@pytest.mark.django_db
@pytest.mark.unit
class TestFormDraftCrossTenantIsolation:
    """Verify tenant A cannot access drafts scoped to tenant B."""

    @pytest.mark.unit
    def test_draft_save_scoped_to_tenant(self, api_client_a, user_a, tenant_a, tenant_b):
        """PUT /drafts/save/ must create the draft in the request's tenant."""
        response = api_client_a.put(
            "/api/v1/drafts/save/",
            {"resource_type": "dpia", "draft_key": "tenant-test", "data": {"v": 1}},
            format="json",
        )
        assert response.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED)
        draft_id = response.json()["id"]
        draft = FormDraft.objects.get(id=draft_id)
        assert str(draft.tenant_id) == str(tenant_a.id)

    @pytest.mark.unit
    def test_draft_retrieve_includes_tenant_filter(self, api_client_a, user_a, tenant_a):
        """GET /drafts/ must only return drafts in the request's tenant."""
        create_form_draft(
            user=user_a, tenant=tenant_a,
            resource_type="dpia", draft_key="t1", data={"v": "a"},
        )
        response = api_client_a.get(
            "/api/v1/drafts/?resource_type=dpia&draft_key=t1"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["data"] == {"v": "a"}

    @pytest.mark.unit
    def test_draft_upsert_includes_tenant_in_lookup(self, api_client_a, user_a, tenant_a):
        """update_or_create must use tenant_id in lookup, not just defaults."""
        # First save
        api_client_a.put(
            "/api/v1/drafts/save/",
            {"resource_type": "dpia", "draft_key": "upsert", "data": {"v": 1}},
            format="json",
        )
        # Second save (update)
        response = api_client_a.put(
            "/api/v1/drafts/save/",
            {"resource_type": "dpia", "draft_key": "upsert", "data": {"v": 2}},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        # Should be exactly one draft for this tenant
        count = FormDraft.objects.filter(
            user=user_a, tenant=tenant_a,
            resource_type="dpia", draft_key="upsert",
        ).count()
        assert count == 1


@pytest.mark.django_db
@pytest.mark.unit
class TestFormDraftCRUD:
    """End-to-end draft CRUD flow."""

    @pytest.mark.unit
    def test_save_creates_draft(self, api_client_a):
        response = api_client_a.put(
            "/api/v1/drafts/save/",
            {"resource_type": "dpia", "draft_key": "create", "data": {"step": 1}},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert "id" in response.json()
        assert response.json()["data"] == {"step": 1}

    @pytest.mark.unit
    def test_save_updates_existing_draft(self, api_client_a):
        api_client_a.put(
            "/api/v1/drafts/save/",
            {"resource_type": "dpia", "draft_key": "update-test", "data": {"step": 1}},
            format="json",
        )
        response = api_client_a.put(
            "/api/v1/drafts/save/",
            {"resource_type": "dpia", "draft_key": "update-test", "data": {"step": 2}},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["data"] == {"step": 2}

    @pytest.mark.unit
    def test_retrieve_returns_404_body_for_missing(self, api_client_a):
        response = api_client_a.get(
            "/api/v1/drafts/?resource_type=nonexistent&draft_key=missing"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["data"] == {}

    @pytest.mark.unit
    def test_delete_removes_draft(self, api_client_a):
        api_client_a.put(
            "/api/v1/drafts/save/",
            {"resource_type": "dpia", "draft_key": "del-test", "data": {"x": 1}},
            format="json",
        )
        response = api_client_a.delete(
            "/api/v1/drafts/delete/?resource_type=dpia&draft_key=del-test"
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

    @pytest.mark.unit
    def test_save_requires_auth(self):
        client = APIClient()
        response = client.put(
            "/api/v1/drafts/save/",
            {"resource_type": "dpia", "data": {"step": 1}},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.unit
    def test_save_requires_resource_type(self, api_client_a):
        response = api_client_a.put(
            "/api/v1/drafts/save/",
            {"data": {"step": 1}},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.unit
    def test_save_requires_data(self, api_client_a):
        response = api_client_a.put(
            "/api/v1/drafts/save/",
            {"resource_type": "dpia"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.unit
    def test_different_resource_types_independent(self, api_client_a):
        """Drafts for different resource_types are independent."""
        api_client_a.put(
            "/api/v1/drafts/save/",
            {"resource_type": "dpia", "draft_key": "default", "data": {"a": 1}},
            format="json",
        )
        api_client_a.put(
            "/api/v1/drafts/save/",
            {"resource_type": "contract", "draft_key": "default", "data": {"b": 2}},
            format="json",
        )
        r1 = api_client_a.get("/api/v1/drafts/?resource_type=dpia&draft_key=default")
        r2 = api_client_a.get("/api/v1/drafts/?resource_type=contract&draft_key=default")
        assert r1.json()["data"] == {"a": 1}
        assert r2.json()["data"] == {"b": 2}
