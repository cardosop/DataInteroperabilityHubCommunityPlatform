"""Auth-app test isolation: the DRF throttle history.

The throttle history lives in the default cache (LocMem in tests) and
is keyed per-IP with windows up to an hour — without a reset, the
suite's OWN earlier password-reset/login calls exhaust the windows and
later tests fail with ``RATE_LIMIT_EXCEEDED`` while each passes
standalone (P0-1 battery finding, 2026-10-19: 8 tests failed
in-cluster — password-reset confirm x3, refresh rate-limit, logout
atomic x2, X-Tenant-Id bearer, W102 login mint — all 429s, all green
in isolation). The repo's throttle-aware classes already call
``cache.clear()`` in ``setUp`` (``test_password_reset_rate_limit.py``);
this fixture applies the same reset suite-wide — the standard DRF
throttle-testing recipe.

The fixture runs before each test's ``setUp``, so a test that seeds
the cache in its own ``setUp`` keeps that seed.
"""

import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _clear_auth_throttle_cache():
    cache.clear()
