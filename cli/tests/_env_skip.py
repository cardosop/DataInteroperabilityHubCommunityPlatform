"""Shared collection-time auto-skip for the CLI conftest family (W16 / Phase T.4).

One implementation for the five previously duplicated
``pytest_collection_modifyitems`` bodies in
``cli/tests/{integration,e2e,security,dimensions,use_cases}/conftest.py``.

W16 policy (see project-root ``envpolicy.py``):
  * ``MESHANT_FORCE_INTEGRATION=1`` — operator override, never touched.
  * API reachable — no markers.
  * API unreachable + CI — raises ``EnvironmentFailureError``: the broken
    environment announces itself instead of skipping the whole suite.
  * API unreachable + local — adds a skip marker to items under the suite's
    path scopes, never to API-independent files (the security suite's
    TLS/dependency-audit files run without a backend).

Pure ``pytest`` + ``envpolicy``; no Django import, so importing this module
never opens a database connection (the Django-backed conftests keep their
own ``ensure_django()`` bootstrap).
"""

from __future__ import annotations

import os

import pytest

from envpolicy import environment_guard, probe_service


def auto_skip_unreachable_api(
    items,
    *,
    suite_label: str,
    path_scopes: tuple[str, ...],
    default_port: int = 8000,
    api_independent_files: frozenset[str] = frozenset(),
) -> None:
    """Auto-skip the suite when no live Meshant API is reachable (see module docstring).

    ``items`` are the ``pytest_collection_modifyitems`` items; ``path_scopes``
    the fspath fragments that gate which items receive the local skip marker;
    ``api_independent_files`` filenames that must never be marked locally.
    """
    if os.environ.get("MESHANT_FORCE_INTEGRATION") == "1":
        return
    api_url = os.environ.get(
        "MESHANT_API_URL",
        f"http://localhost:{default_port}/api/v1",
    )
    # Probe the API root once per session (the /api/v1 prefix itself 404s on
    # some configurations — the root is the reliable up/down signal).
    api_root = api_url.rsplit("/api/v1", 1)[0] or api_url
    if probe_service(api_root):
        return
    environment_guard(
        f"Meshant API not reachable at {api_root} — {suite_label} require a live backend."
    )
    skip_marker = pytest.mark.skip(
        reason=(
            f"Meshant API not reachable at {api_root}. {suite_label} "
            "require a live backend; start docker compose or set "
            "MESHANT_FORCE_INTEGRATION=1 to override."
        )
    )
    for item in items:
        fspath = str(item.fspath)
        filename = os.path.basename(fspath)
        if filename in api_independent_files:
            continue
        if any(scope in fspath for scope in path_scopes):
            item.add_marker(skip_marker)
