"""
Pytest fixtures for CLI dimensions tests.

Mirrors ``tests/integration/conftest.py``: auto-skips dimensions tests when
no live Meshant API is reachable. Dimensions tests run a real CLI against a
real backend and have no business failing on dev boxes that don't run docker
compose. Set ``MESHANT_FORCE_INTEGRATION=1`` to bypass.

W16 (Phase T.4): the auto-skip is the shared ``tests._env_skip`` policy —
in CI an unreachable API RAISES instead of skipping (the environment failure
announces itself); local runs keep the graceful skip.
"""

from tests._env_skip import auto_skip_unreachable_api


def pytest_collection_modifyitems(config, items):
    auto_skip_unreachable_api(
        items,
        suite_label="CLI dimensions tests",
        path_scopes=("/tests/dimensions/",),
    )
