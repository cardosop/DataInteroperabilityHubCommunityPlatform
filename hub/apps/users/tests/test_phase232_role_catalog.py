"""Phase 232.0 — canonical role catalog (D232.13)."""

import pytest
import importlib

from django.test import SimpleTestCase

from hub.apps.users.role_catalog import (
    STANDARD_TENANT_ROLE_NAMES,
    STANDARD_TENANT_ROLE_DEFINITIONS,
)


class Phase232RoleCatalogTests(SimpleTestCase):
    @pytest.mark.unit
    def test_privacy_roles_declared(self):
        for name in ("DPO", "LEGAL_ADMIN", "SECURITY_ADMIN", "PII_VIEWER"):
            self.assertIn(name, STANDARD_TENANT_ROLE_NAMES)

    @pytest.mark.unit
    def test_definition_count_matches_names(self):
        self.assertEqual(len(STANDARD_TENANT_ROLE_DEFINITIONS), len(STANDARD_TENANT_ROLE_NAMES))

    @pytest.mark.unit
    def test_users_0019_backfill_rows_match_catalog_roles(self):
        """Each row in the Phase-232 migration remains identical to the catalog tuple."""
        mod = importlib.import_module(
            "hub.apps.users.migrations.0019_phase232_privacy_roles_backfill",
        )
        migration_rows = tuple(tuple(r) for r in mod._ROLE_ROWS)
        catalog_by_name = dict(STANDARD_TENANT_ROLE_DEFINITIONS)
        for name, desc in migration_rows:
            self.assertEqual(catalog_by_name[name], desc)

    @pytest.mark.unit
    def test_users_0020_adds_pii_viewer_matching_catalog(self):
        mod = importlib.import_module(
            "hub.apps.users.migrations.0020_phase260_pii_viewer_role_backfill",
        )
        catalog_by_name = dict(STANDARD_TENANT_ROLE_DEFINITIONS)
        self.assertEqual(mod._ROLE_NAME, "PII_VIEWER")
        self.assertEqual(catalog_by_name["PII_VIEWER"], mod._ROLE_DESCRIPTION)
