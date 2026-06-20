"""Shared pytest fixtures for integration tests.

Auto-enables feature flags on every Tenant created during integration
tests so endpoints return proper responses instead of 403 X_DISABLED.

Uses a ``pre_save`` signal receiver that injects ``_TEST_FEATURE_FLAGS``
into any new ``Tenant`` record before it is saved.  The signal is
connected at session start and disconnected at session end via the
``pytest_sessionstart`` / ``pytest_sessionfinish`` hooks, ensuring it
only runs during the integration test session.
"""

from __future__ import annotations

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
    """Auto-enable feature flags on every new Tenant before save.

    Connected during ``pytest_sessionstart`` and disconnected during
    ``pytest_sessionfinish`` so it only affects the integration test session.
    """
    if instance._state.adding:  # Only for new (unsaved) instances
        for flag, value in _INTEGRATION_FEATURE_FLAGS.items():
            if not getattr(instance, flag, False):
                setattr(instance, flag, value)


def pytest_sessionstart(session):
    """Register the feature-flag pre_save signal for the test session."""
    from django.db.models.signals import pre_save

    # Deferred import so this module is importable before Django is ready.
    try:
        from hub.apps.tenants.models import Tenant
    except Exception:
        return  # Django not configured — skip (e.g., collection-only runs)

    pre_save.connect(_tenant_pre_save_receiver, sender=Tenant)


def pytest_sessionfinish(session, exitstatus):
    """Disconnect the feature-flag pre_save signal."""
    from django.db.models.signals import pre_save

    try:
        from hub.apps.tenants.models import Tenant
    except Exception:
        return

    pre_save.disconnect(_tenant_pre_save_receiver, sender=Tenant)
