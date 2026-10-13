"""Shared pytest fixtures for integration tests.

Auto-enables feature flags on every Tenant created during integration
tests so endpoints return proper responses instead of 403 X_DISABLED.

Uses a ``pre_save`` signal receiver that injects ``_TEST_FEATURE_FLAGS``
into any new ``Tenant`` record before it is saved.  The receiver is
connected by an autouse per-test fixture, so it only affects tests under
``tests/integration/``.  (The previous session-wide connection leaked
into every other test tree running in the same pytest session — e.g. it
flipped ``developer_enabled`` on the developer-gate tests'
``no-dev-tenant`` and turned an expected 403 into a 200.)
"""

from __future__ import annotations

import pytest

# All feature flags that integration tests need enabled by default.
# Mirrors tests/fixtures/test_data_factories.py:TenantFactory._TEST_FEATURE_FLAGS.
_INTEGRATION_FEATURE_FLAGS = {
    "marketplace_integrations_enabled": True,
    "baas_enabled": True,
    "ml_enabled": True,
    "transformation_enabled": True,
    "data_movement_enabled": True,
    "data_mesh_enabled": True,
    "virtualization_enabled": True,
    "developer_enabled": True,
    "pipeline_dependency_enabled": True,
}


def _tenant_pre_save_receiver(sender, instance, **kwargs):
    """Auto-enable feature flags on every new Tenant before save."""
    if instance._state.adding:  # Only for new (unsaved) instances
        for flag, value in _INTEGRATION_FEATURE_FLAGS.items():
            if not getattr(instance, flag, False):
                setattr(instance, flag, value)


@pytest.fixture(autouse=True)
def _auto_enable_feature_flags():
    """Connect the flag-injecting receiver for THIS test only.

    Autouse + conftest-scoped: applies to every test under
    ``tests/integration/`` and to nothing else in the session.
    """
    from django.db.models.signals import pre_save

    from hub.apps.tenants.models import Tenant

    pre_save.connect(_tenant_pre_save_receiver, sender=Tenant)
    try:
        yield
    finally:
        pre_save.disconnect(_tenant_pre_save_receiver, sender=Tenant)
