"""
Pytest fixtures for CLI e2e tests.

Mirrors ``tests/integration/conftest.py``: auto-skips e2e tests when no live
Meshant API is reachable. e2e tests run a real CLI against a real backend
and have no business failing on dev boxes that don't run docker compose.
Set ``MESHANT_FORCE_INTEGRATION=1`` to bypass.

W16 (Phase T.4): the auto-skip is the shared ``tests._env_skip`` policy —
in CI an unreachable API RAISES instead of skipping (the environment failure
announces itself); local runs keep the graceful skip.
"""

# Django-backed modules in this directory import ``hub``/Django models at
# module scope, so settings must be configured before collection.  Kept
# here (not in the suite-root conftest) so unit batches never import
# ``hub.settings`` — that import opens a real PostgreSQL connection.
from tests._django_bootstrap import ensure_django

ensure_django()

from tests._env_skip import auto_skip_unreachable_api


def pytest_collection_modifyitems(config, items):
    auto_skip_unreachable_api(
        items,
        suite_label="CLI e2e tests",
        path_scopes=("/tests/e2e/",),
    )
