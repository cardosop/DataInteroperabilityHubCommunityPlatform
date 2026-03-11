"""
Security tests: Search service (401 unauthenticated, tenant isolation).

Per tasks 29.6.3. Search API must return 401 when unauthenticated and enforce
tenant isolation for search results. Real APIClient; no mocks.
"""

import uuid

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.search.models import SearchIndex

pytestmark = pytest.mark.django_db(transaction=True)


def test_search_returns_401_when_unauthenticated():
    """GET /api/v1/search/search/ without auth must return 401."""
    client = APIClient()
    response = client.get("/api/v1/search/search/", {"q": "test"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_search_suggestions_returns_401_when_unauthenticated():
    """GET /api/v1/search/suggestions/ without auth must return 401."""
    client = APIClient()
    response = client.get("/api/v1/search/suggestions/", {"q": "test"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_search_tenant_isolation_user_sees_only_own_tenant_results():
    """User from tenant A must not see tenant B's search results."""
    from django.contrib.postgres.search import SearchVector

    from .base_idor import IDORTestBase

    t = IDORTestBase()
    t.setUp()
    uid = uuid.uuid4().hex[:8]
    term_a = f"tenant-a-unique-{uid}"
    term_b = f"tenant-b-unique-{uid}"
    # Create SearchIndex for tenant A with search_vector for full-text search
    idx_a = SearchIndex.objects.create(
        tenant=t.tenant_a,
        resource_type="ASSET",
        resource_id=uuid.uuid4(),
        title=term_a,
        description="Asset in tenant A",
    )
    idx_a.search_vector = (
        SearchVector("title", weight="A", config="english")
        + SearchVector("description", weight="B", config="english")
    )
    idx_a.save()
    # Create SearchIndex for tenant B
    idx_b = SearchIndex.objects.create(
        tenant=t.tenant_b,
        resource_type="ASSET",
        resource_id=uuid.uuid4(),
        title=term_b,
        description="Asset in tenant B",
    )
    idx_b.search_vector = (
        SearchVector("title", weight="A", config="english")
        + SearchVector("description", weight="B", config="english")
    )
    idx_b.save()
    # User A searches for tenant B's term - must get 0 results (tenant isolation)
    t.client.force_authenticate(user=t.user_a)
    response = t.client.get(
        "/api/v1/search/search/",
        {"q": term_b},
    )
    assert response.status_code == status.HTTP_200_OK
    total = response.data.get("total", 0)
    assert total == 0, "User from tenant A must not see tenant B's search results"

    # User A searches for own tenant's term - should get results
    response_a = t.client.get(
        "/api/v1/search/search/",
        {"q": term_a},
    )
    assert response_a.status_code == status.HTTP_200_OK
    assert response_a.data.get("total", 0) >= 1
