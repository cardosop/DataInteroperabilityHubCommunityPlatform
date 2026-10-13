"""
Pytest collection hook for security integration tests.

Auto-skips security tests that require a live Meshant API when the
API is unreachable.  Tests that do NOT depend on the API
(test_tls_verification.py, test_dependency_audit.py) are always
collected regardless of API reachability.

Set ``MESHANT_FORCE_INTEGRATION=1`` to bypass the skip and force-run
all tests.

W16 (Phase T.4): the auto-skip is the shared ``tests._env_skip`` policy —
in CI an unreachable API RAISES instead of skipping (the environment failure
announces itself); local runs keep the graceful skip.
"""

from tests._env_skip import auto_skip_unreachable_api

# Files that do not require the live API — never auto-skip these.
_API_INDEPENDENT_FILES = frozenset(
    {
        "test_tls_verification.py",
        "test_dependency_audit.py",
    }
)


def pytest_collection_modifyitems(config, items):
    auto_skip_unreachable_api(
        items,
        suite_label="Security integration tests",
        path_scopes=("/tests/security/",),
        default_port=8001,
        api_independent_files=_API_INDEPENDENT_FILES,
    )
