"""
Security tests: Files service (path traversal, upload validation, tenant isolation).

Per tasks 29.6.2. File API must reject path traversal in filenames, validate uploads,
and enforce tenant isolation. Real APIClient; no mocks.
"""

import uuid

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

User = __import__("django.contrib.auth", fromlist=["get_user_model"]).get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


def test_files_list_returns_401_when_unauthenticated():
    """GET /api/v1/files/ without auth must return 401."""
    client = APIClient()
    response = client.get("/api/v1/files/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_file_init_rejects_path_traversal_in_filename():
    """POST /api/v1/files/init/ with path traversal in name must return 400."""
    uid = str(uuid.uuid4())[:8]
    tenant = Tenant.objects.create(name=f"Files {uid}", slug=f"files-{uid}")
    ensure_tenant_has_active_subscription(tenant)
    user = User.objects.create_user(
        email=f"files-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(
        "/api/v1/files/init/",
        {
            "name": "../../../etc/passwd",
            "content_type": "text/plain",
            "size": 100,
        },
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_file_init_rejects_alternative_path_traversal():
    """POST /api/v1/files/init/ with ..\\ in name must return 400."""
    uid = str(uuid.uuid4())[:8]
    tenant = Tenant.objects.create(name=f"Files {uid}", slug=f"files-{uid}")
    ensure_tenant_has_active_subscription(tenant)
    user = User.objects.create_user(
        email=f"files-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(
        "/api/v1/files/init/",
        {
            "name": "..\\..\\windows\\system32\\config\\sam",
            "content_type": "text/plain",
            "size": 100,
        },
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_file_init_rejects_disallowed_file_type():
    """POST /api/v1/files/init/ with disallowed extension must return 400."""
    uid = str(uuid.uuid4())[:8]
    tenant = Tenant.objects.create(name=f"Files {uid}", slug=f"files-{uid}")
    ensure_tenant_has_active_subscription(tenant)
    user = User.objects.create_user(
        email=f"files-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    # .exe is not in default ALLOWED_FILE_TYPES (csv, json, parquet, txt, xlsx, xls)
    response = client.post(
        "/api/v1/files/init/",
        {
            "name": "malicious.exe",
            "content_type": "application/x-msdownload",
            "size": 1024,
        },
        format="json",
    )
    assert response.status_code in (
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_422_UNPROCESSABLE_ENTITY,
    ), f"Disallowed file type must be rejected, got {response.status_code}"


def test_file_init_rejects_filename_without_extension():
    """POST /api/v1/files/init/ with no file extension must return 400."""
    uid = str(uuid.uuid4())[:8]
    tenant = Tenant.objects.create(name=f"Files {uid}", slug=f"files-{uid}")
    ensure_tenant_has_active_subscription(tenant)
    user = User.objects.create_user(
        email=f"files-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(
        "/api/v1/files/init/",
        {
            "name": "noextension",
            "content_type": "application/octet-stream",
            "size": 1024,
        },
        format="json",
    )
    assert response.status_code in (
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_422_UNPROCESSABLE_ENTITY,
    ), f"Filename without extension must be rejected, got {response.status_code}"


def test_files_tenant_isolation_cross_tenant_returns_403_or_404():
    """User from tenant A must not access tenant B's file."""
    from .base_idor import IDORTestBase

    t = IDORTestBase()
    t.setUp()
    file_b = File.objects.create(
        tenant=t.tenant_b,
        name="file-b.csv",
        content_type="text/csv",
        size=100,
        status=FileStatus.ACTIVE,
        storage_path=f"tenant-b/{uuid.uuid4().hex}/file-b.csv",
        created_by=t.user_b,
    )
    t.client.force_authenticate(user=t.user_a)
    response = t.client.get(f"/api/v1/files/{file_b.id}/")
    assert response.status_code in (
        status.HTTP_403_FORBIDDEN,
        status.HTTP_404_NOT_FOUND,
    )
