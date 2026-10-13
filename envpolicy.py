"""envpolicy — W16 (Phase T.4): environment failure must announce itself.

ONE policy for every "service unavailable / not authenticated / dependency
missing" branch in the Python test trees. When ``CI=true`` the branch RAISES
instead of skipping, so a broken environment fails the run loudly; local runs
keep the graceful skip so developers are not blocked by their own machine
state.

This module retires:
  * the per-file ``_check_api_available()`` helpers (today true for any
    ``status_code < 600`` — a 500 counted as "up" and the suite ran green
    against a broken backend);
  * the ``if service down: return/skip`` family scattered through conftests.

Call-site contract
------------------
* Collection hooks / fixtures: ``skip_or_fail("<what is missing>")`` replaces
  ``pytest.skip(...)`` at every environment-dependent site.
* Reachability probes: ``api_available()`` replaces ``_check_api_available()``
  — in ``@pytest.mark.skipif(not api_available(), ...)`` a down API raises at
  collection in CI (the run fails loudly) and skips locally.
* Custom branches: call ``environment_guard("<detail>")`` BEFORE the local
  skip/fallback.

Pure stdlib + pytest; no Django import, so it is importable at conftest
collection time from both the ``cli/tests`` and the project-root ``tests``
trees (the project root is on ``sys.path`` in both pytest contexts).

The frontend twin is ``frontend/e2e/fixtures/envPolicy.cjs`` — same policy,
same CI predicate, one per language.
"""

from __future__ import annotations

import os
import urllib.error
import urllib.request

import pytest


class EnvironmentFailureError(RuntimeError):
    """Raised in CI when an environment-dependent branch is taken.

    The whole point of W16: this error fails the run loudly instead of the
    branch skipping silently. Never catch it to convert it back into a skip.
    """


def is_ci() -> bool:
    """True when the run is a CI run (GitHub Actions sets CI=true)."""
    value = os.environ.get("CI", "")
    return value in ("true", "1")


def environment_guard(detail: str) -> None:
    """Call at every environment-dependent branch BEFORE the local skip/fallback.

    CI: raises EnvironmentFailureError (the environment failure announces
    itself). Local: no-op — the caller proceeds to its graceful skip.
    """
    if is_ci():
        raise EnvironmentFailureError(
            "[W16] environment-dependent condition in CI — failing loudly "
            f"instead of skipping silently: {detail}. Local runs keep the "
            "graceful skip; CI runs must have a working environment."
        )


def skip_or_fail(detail: str) -> None:
    """The policy applied to a skip site: raise in CI, pytest.skip locally."""
    environment_guard(detail)
    pytest.skip(detail)


def probe_service(url: str, timeout: float = 2.0) -> bool:
    """True iff the service answers the HTTP probe.

    Any 1xx-4xx response proves the service is up (even 404); a 5xx and a
    connection failure mean the service is broken/down — the retired per-file
    helpers' ``status_code < 600`` counted 5xx as up. stdlib urllib only, so
    the probe has no dependency on requests being installed.
    """
    try:
        with urllib.request.urlopen(url, timeout=timeout) as _response:
            return True
    except urllib.error.HTTPError as exc:
        # A real HTTP response reached us — 5xx is a broken service, 4xx
        # still proves the service answers.
        return exc.code < 500
    except (urllib.error.URLError, OSError, ValueError):
        # Connection refused / DNS failure / timeout / malformed URL.
        return False


def api_available(url: str | None = None, timeout: float = 2.0) -> bool:
    """The retired ``_check_api_available()``, policy-applied.

    True when the API answers. When it does not: CI raises
    EnvironmentFailureError (the run fails loudly at collection/local branch);
    local returns False (the caller's skipif/skip proceeds to skip).

    Default URL: ``MESHANT_API_URL``, else ``http://localhost:<API_TEST_PORT
    or 8000>/api/v1`` — the same default the retired per-file helpers used.
    """
    if url is None:
        url = os.environ.get(
            "MESHANT_API_URL",
            f"http://localhost:{os.environ.get('API_TEST_PORT', '8000')}/api/v1",
        )
    if probe_service(url, timeout=timeout):
        return True
    environment_guard(f"Meshant API not reachable at {url}")
    return False
