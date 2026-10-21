"""
Pytest configuration for the performance suite.

The perf tree sits OUTSIDE ``hub/``, so ``hub/conftest.py`` (session plan
seed + post-flush auto-seed patch) does not apply here. The shared reused DB
is periodically flushed by TransactionTestCase tests, which deletes the
``tenant_plans`` rows that ``PlanLimitService`` needs — surfaced as
``NotFoundError: No FREE plan found`` in marketplace/registration perf tests.

Two defenses, mirroring ``hub/conftest.py``:

1. Session-scoped seed: run ``seed_default_plans`` once per session.
2. Defensive ``TenantPlan.objects.get`` auto-seed: after a TRUNCATE CASCADE
   flush, the next ``.get(slug=...)`` for a known plan re-seeds and retries
   once — self-healing regardless of fixture/flush ordering.
"""

import contextlib

import pytest

_KNOWN_PLAN_SLUGS = {
    "free",
    "pro",
    "enterprise",
    "ml-starter",
    "ml-professional",
    "ml-enterprise",
}


def _seed_plans() -> None:
    """Seed default tenant plans via the idempotent management command."""
    from django.core.management import call_command

    call_command("seed_default_plans")


@pytest.fixture(scope="session", autouse=True)
def _perf_seed_default_plans(django_db_setup, django_db_blocker):
    """Seed default plans once per session (after DB setup)."""
    with django_db_blocker.unblock():
        _seed_plans()


def pytest_configure(config):
    """Apply two defenses, mirroring ``hub/conftest.py``:

    1. Defensive ``TenantPlan.objects.get`` auto-seed (covers direct .get).
    2. Post-flush re-seed: TransactionTestCase._fixture_teardown TRUNCATEs
       all tables (Django 6) — re-seed immediately so the NEXT test finds
       free/pro/enterprise plans. This is the path that matters for
       PlanLimitService, which looks plans up via .filter(...).first().
    """
    try:
        from hub.apps.tenants.models import TenantPlan

        _manager = type(TenantPlan.objects)
        if not getattr(_manager, "_hub_autoseed_get", False):
            _orig_get = _manager.get

            def _autoseed_get(self, *args, **kwargs):
                try:
                    return _orig_get(self, *args, **kwargs)
                except self.model.DoesNotExist:
                    # Guard: only auto-seed for TenantPlan, not other models
                    # sharing the Manager class.
                    if self.model is not TenantPlan:
                        raise
                    # Only auto-seed for known plan slugs.
                    slug_val = kwargs.get("slug")
                    if slug_val and slug_val in _KNOWN_PLAN_SLUGS:
                        _seed_plans()
                        return _orig_get(self, *args, **kwargs)
                    raise

            _manager.get = _autoseed_get
            _manager._hub_autoseed_get = True
    except Exception:
        pass

    try:
        from django.test import TransactionTestCase

        if not getattr(TransactionTestCase, "_perf_reseed_hooked", False):
            _orig_teardown = TransactionTestCase._fixture_teardown

            def _teardown_with_reseed(self, *args, **kwargs):
                _orig_teardown(self, *args, **kwargs)
                # TRUNCATE CASCADE already completed and released locks —
                # re-seed plans so the next test (any class) finds them.
                with contextlib.suppress(Exception):
                    _seed_plans()

            TransactionTestCase._fixture_teardown = _teardown_with_reseed
            TransactionTestCase._perf_reseed_hooked = True
    except Exception:
        pass
