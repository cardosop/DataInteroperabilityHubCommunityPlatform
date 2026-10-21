"""
W1.20 (oss-release-remediation, D2 / W1.4b) — settings ↔ deployed-
policy GUC inventory sync pins.

Every ``app.rls_<table>_enabled`` GUC referenced by a DEPLOYED RLS
policy must have a paired ``RLS_<TABLE>_ENABLED`` settings kill
switch (default True), and every such settings entry must map back to
a real policy GUC.  The middleware derives the per-request GUC set
from the settings names — a drift in either direction silently changes
what the request path arms, so the inventory is pinned bidirectionally.

The database is the source of truth: the policy expressions are read
from ``pg_policies`` (``pg_get_expr``), which catches every policy
shape — including the f-string-constructed ones (e.g.
``api_keys``/``refresh_tokens`` in auth migration 0015, whose GUC
names never appear as literals in any migration file, so a source
scan would miss them).

``RLS_REQUEST_PATH_ENABLED`` is the MASTER kill switch for the whole
arming path — it is deliberately NOT a table flag and must never be
treated as one.
"""

import re

import pytest
from django.conf import settings
from django.db import connection

from hub.apps.auth.rls_gucs import RLS_TENANT_GUC, iter_rls_enabled_settings

pytestmark = pytest.mark.django_db(transaction=True)

GUC_RE = re.compile(r"app\.rls_[a-z0-9_]+_enabled")
SETTING_NAME_RE = re.compile(r"^RLS_[A-Z0-9_]+_ENABLED$")


def _deployed_policy_gucs() -> set[str]:
    """The GUC names actually referenced by live RLS policies."""
    gucs: set[str] = set()
    with connection.cursor() as cursor:
        # pg_policies renders qual / with_check as TEXT in this
        # PostgreSQL major — pg_get_expr on a re-cast pg_node_tree is
        # rejected server-side ("cannot accept a value of type
        # pg_node_tree"), so the expressions are read as text.
        cursor.execute(
            "SELECT schemaname, tablename, qual, with_check FROM pg_policies"
        )
        for _schemaname, _tablename, qual, with_check in cursor.fetchall():
            for expression in (qual, with_check):
                if expression:
                    gucs.update(GUC_RE.findall(expression))
    return gucs


def _setting_names() -> list[str]:
    return sorted(name for name in dir(settings) if SETTING_NAME_RE.match(name))


def _settings_derived_gucs() -> set[str]:
    # Derive through the production registry (iter_rls_enabled_settings)
    # so the master switch exclusion is part of what's pinned.
    return {guc for _, guc, _ in iter_rls_enabled_settings(settings)}


class TestRLSGucSettingsSync:
    """The inventory has no drift in either direction."""

    @pytest.mark.integration
    def test_every_deployed_policy_guc_has_a_paired_settings_kill_switch(self):
        policy_gucs = _deployed_policy_gucs()
        settings_gucs = _settings_derived_gucs()
        missing = sorted(policy_gucs - settings_gucs)
        assert not missing, (
            "deployed RLS policy GUCs without a paired RLS_*_ENABLED settings "
            "kill switch: " + ", ".join(missing)
        )

    @pytest.mark.integration
    def test_every_rls_enabled_setting_maps_to_a_real_policy_guc(self):
        policy_gucs = _deployed_policy_gucs()
        settings_gucs = _settings_derived_gucs()
        orphan = sorted(settings_gucs - policy_gucs)
        assert not orphan, (
            "RLS_*_ENABLED settings with no matching GUC in any deployed policy: "
            + ", ".join(orphan)
        )

    @pytest.mark.integration
    def test_master_switch_is_not_treated_as_a_table_flag(self):
        # RLS_REQUEST_PATH_ENABLED matches the setting-name shape but is
        # the arming kill switch, not a table flag — the registry must
        # exclude it or the middleware would set a phantom GUC.
        registered = {name: guc for name, guc, _ in iter_rls_enabled_settings(settings)}
        assert "RLS_REQUEST_PATH_ENABLED" not in registered
        assert "app.rls_request_path_enabled" not in registered.values()

    @pytest.mark.integration
    def test_tenant_guc_name_matches_the_policy_convention(self):
        assert RLS_TENANT_GUC == "app.current_tenant_id"
