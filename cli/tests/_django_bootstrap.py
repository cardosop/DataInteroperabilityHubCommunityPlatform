"""Opt-in Django bootstrap for the CLI test directories that need it.

The CLI suite is designed to run standalone — ``cli/pytest.ini`` sets
``-p no:django`` — but three directories (``integration/``, ``e2e/``,
``use_cases/``) import Django/``hub`` to verify cross-package contracts,
and those modules expect settings to be configured for them.

This used to run at ``cli/tests/conftest.py`` import time, i.e. for every
CLI test session.  Importing ``hub.settings`` opens a real PostgreSQL
connection (``hub/settings.py`` probes the DB and retries for ~60s before
raising), so on a host with no database the *entire* CLI suite — including
the pure-mock unit batches and the meta/guard batch, none of which touch
Django — died with a conftest ImportError.

pytest imports a directory's ``conftest.py`` only when it collects from
that directory, so calling ``ensure_django()`` from the three conftests
that need it gives us the laziness for free: unit batches never pay the
cost, and the directories that do need Django still fail loudly when
settings are genuinely misconfigured.
"""

from __future__ import annotations

import functools
import os
import pathlib


def _public_tree_missing_paid_apps() -> bool:
    """True when the paid app directories are absent (the PUBLIC tree).

    With ``HUB_CORE_ONLY`` unset, ``hub.settings`` installs the paid apps;
    in the public tree those directories do not exist, so the FIRST
    ``django.setup()`` dies with ``No module named 'hub.apps.<paid>'``.
    Django's app registry is not reentrant — a failed populate() cannot
    be retried with different settings — so the core-mode decision must be
    made BEFORE the first setup.  The probe is filesystem-only (no Django
    imports): the paid-app membership lives in ``hub/apps/manifest.py``,
    which the published tree filters (publish_paths_exclude.txt), so
    absence of the directories is the public-tree signal.

    Private-tree runs (full or core-only) have the directories present
    and return False.
    """
    hub_dir = pathlib.Path(__file__).resolve().parents[2] / "hub" / "apps"
    if not hub_dir.is_dir():
        # No hub at all — not even core — treat like the public tree.
        return True
    paid_modules = (
        "billing",
        "semantic",
        "marketplace",
        "graphql",
        "graphql_ld",
        "rate_limiting",
        "ai",
        "ml",
        "social",
        "baas",
        "graphql_graphene",
    )
    return not any((hub_dir / m).is_dir() for m in paid_modules)


@functools.cache
def ensure_django() -> None:
    """Configure Django settings for this process, once.

    ``functools.cache`` makes repeat calls free — several sibling
    conftests call this — while still retrying if a call raises, since a
    raising call is not cached.

    Distinguishes three outcomes:

    1. Django not installed        -> no-op (standalone CLI mode).
    2. Already configured          -> no-op (e.g. pytest-django got there
       first, or a sibling conftest already called us).
    3. Installed but ``setup()`` fails -> the exception propagates.  A
       failure here is a real configuration or environment problem for a
       directory that genuinely requires Django, and callers need to see
       it rather than collect a silently Django-less session.
    """

    try:
        import django
    except ImportError:
        return

    from django.conf import settings

    if settings.configured:
        return

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")
    if _public_tree_missing_paid_apps():
        # Public tree: force core-mode settings BEFORE the first setup —
        # a failed populate() cannot be retried (app registry not
        # reentrant).
        os.environ["HUB_CORE_ONLY"] = "1"
    try:
        django.setup()
    except RuntimeError as exc:
        # Django raises RuntimeError when setup() runs twice; that is
        # safe.  Anything else is a real configuration error.
        if "populate()" not in str(exc):
            raise
