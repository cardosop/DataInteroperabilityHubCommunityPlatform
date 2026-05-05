"""
Tests for ``manage.py create_asset`` management command.

Task 250.7.C requires:
- the command must reuse ``AssetService.create_asset(...)``
- required args: tenant, key, name, actor-email
- optional args: description, domain
- ``--dry-run`` must not persist rows
- command-created row must match POST /api/v1/assets semantics
"""

from __future__ import annotations

import io
import json
import uuid
from typing import Any, cast

import pytest
from django.core.management import call_command
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from hub.apps.assets.models import (
    Asset,
    AssetStatus,
    AssetVisibility,
    ComplianceStatus,
    DQStatus,
)
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.role_support import ensure_user_has_data_provider_role
from hub.apps.users.models import User, UserStatus


pytestmark = pytest.mark.django_db(transaction=True)


class CreateAssetCommandTest(TestCase):
    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Create Asset Command Tenant {uid}",
            slug=f"create-asset-command-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        user_manager = cast(Any, User.objects)
        self.user = user_manager.create_user(
            email=f"create-asset-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        ensure_user_has_data_provider_role(self.user)
        self.api_client = APIClient()
        self.api_client.force_authenticate(user=self.user)

    def test_create_asset_command_produces_same_asset_shape_as_post(self):
        base_payload = {
            "name": "Command/API Parity Asset",
            "description": "Created for parity test",
            "domain": "finance",
        }

        api_payload = {
            "key": f"api-{uuid.uuid4().hex[:8]}",
            **base_payload,
        }
        api_response = cast(
            Any,
            self.api_client.post(
            "/api/v1/assets/",
            data=json.dumps(api_payload),
            content_type="application/json",
            ),
        )
        self.assertEqual(api_response.status_code, status.HTTP_201_CREATED)
        api_response_json = json.loads(api_response.content)
        api_asset = Asset.objects.get(id=api_response_json["id"])

        command_key = f"cmd-{uuid.uuid4().hex[:8]}"
        call_command(
            "create_asset",
            f"--tenant={self.tenant.id}",
            f"--key={command_key}",
            f"--name={base_payload['name']}",
            f"--description={base_payload['description']}",
            f"--domain={base_payload['domain']}",
            f"--actor-email={self.user.email}",
            stdout=io.StringIO(),
        )
        cmd_asset = Asset.objects.get(tenant=self.tenant, key=command_key)

        self.assertEqual(cmd_asset.name, api_asset.name)
        self.assertEqual(cmd_asset.description, api_asset.description)
        self.assertEqual(cmd_asset.domain, api_asset.domain)
        self.assertEqual(cmd_asset.status, api_asset.status)
        self.assertEqual(cmd_asset.status, AssetStatus.DRAFT)
        self.assertEqual(cmd_asset.version, api_asset.version)
        self.assertEqual(cmd_asset.version, 1)
        self.assertEqual(cmd_asset.dq_status, api_asset.dq_status)
        self.assertEqual(cmd_asset.dq_status, DQStatus.UNKNOWN)
        self.assertEqual(cmd_asset.compliance_status, api_asset.compliance_status)
        self.assertEqual(cmd_asset.compliance_status, ComplianceStatus.UNKNOWN)
        self.assertEqual(cmd_asset.visibility, api_asset.visibility)
        self.assertEqual(cmd_asset.visibility, AssetVisibility.INTERNAL)
        self.assertEqual(cmd_asset.created_by, api_asset.created_by)

    def test_create_asset_command_dry_run_does_not_persist(self):
        key = f"dry-{uuid.uuid4().hex[:8]}"
        call_command(
            "create_asset",
            f"--tenant={self.tenant.id}",
            f"--key={key}",
            "--name=Dry Run Asset",
            "--description=No persistence expected",
            "--domain=ops",
            f"--actor-email={self.user.email}",
            "--dry-run",
            stdout=io.StringIO(),
        )
        self.assertFalse(Asset.objects.filter(tenant=self.tenant, key=key).exists())
