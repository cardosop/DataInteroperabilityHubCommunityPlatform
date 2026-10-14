"""W4.6 (openspec oss-release-remediation, G1) — the unregistered-seam
defaults, pinned OUTSIDE a populated Django app registry.

Under Django the estate app registers every seam at app-ready, so the
"no provider registered" state only exists in a process WITHOUT Django
setup. These pins import the REAL seam modules bare (they import only
stdlib + lazy settings bindings — no ``django.setup()``), and assert the
documented unregistered defaults:

- the m2m token-cache seam resolves None (consumers fall back to the
  best-effort no-cache mode);
- the budget-gate seam resolves None (no budget concept → no gate);
- the staging-volume provisioner refuses classified
  (``DatabricksStagingRefused``) — the refusal fires BEFORE any settings
  or cache access, so a bare import suffices.
"""

from __future__ import annotations


class _BareTenant:
    def __init__(self, tenant_id: str):
        self.id = tenant_id
        self.databricks_staging_volume_name = ""
        self.databricks_s3_external_location_enabled = False


def test_m2m_token_cache_default_is_none_without_django():
    from hub.apps.integrations.m2m_token_cache import default_m2m_token_cache

    assert default_m2m_token_cache() is None


def test_budget_gate_default_is_none_without_django():
    from hub.apps.warehouses.budget_gate import enforce_budget

    assert enforce_budget("any-tenant") is None


def test_staging_provisioner_refuses_without_django():
    import pytest

    from hub.data_movement.staging import (
        DatabricksStagingRefused,
        ensure_staging_volume,
        get_staging_volume_provisioner,
    )

    assert get_staging_volume_provisioner() is None
    with pytest.raises(
        DatabricksStagingRefused, match="no staging-volume provisioner registered"
    ):
        ensure_staging_volume(
            tenant=_BareTenant("t-1"),
            catalog="cat",
            schema="sch",
            client=object(),
            cache=object(),
        )
