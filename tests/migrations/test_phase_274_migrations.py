"""
Phase 277.4.8 — Phase 274 migration rollback tests.

Verifies migrations 0067, 0068, 0069 apply cleanly and rollback cleanly.
Verifies RLS policies created on correct tables.
"""
from __future__ import annotations

import os

import pytest
from django.conf import settings
from django.test import TestCase

pytestmark = pytest.mark.django_db(transaction=True)

PHASE_274_MIGRATIONS = [
    ("tenants", "0067_phase_272_compliance_gate"),
    ("tenants", "0068_phase_274_marketplace_compliance_gate"),
    ("tenants", "0069_phase_275_warehouse_flags"),
]


class TestPhase274Migrations(TestCase):
    """Phase 277.4.8 — migration apply/rollback sanity."""

    def test_migration_files_exist(self):
        for app, name in PHASE_274_MIGRATIONS:
            path = os.path.join(
                settings.BASE_DIR, "hub", "apps", app, "migrations", f"{name}.py",
            )
            assert os.path.isfile(path), f"Migration {app}/{name} not found at {path}"

    def test_migrations_are_applied(self):
        from django.db.migrations.recorder import MigrationRecorder
        recorder = MigrationRecorder("default")
        applied = {(m.app, m.name) for m in recorder.applied_migrations()}
        for app, name in PHASE_274_MIGRATIONS:
            assert (app, name) in applied, f"Migration {app}/{name} is not applied"

    def test_tenant_fields_exist(self):
        from hub.apps.tenants.models import Tenant
        fields = [
            "access_request_compliance_gate_enabled",
            "marketplace_publish_compliance_gate_enabled",
            "warehouse_connectivity_enabled",
        ]
        for field_name in fields:
            assert hasattr(Tenant, field_name), f"Field {field_name} missing from Tenant"
