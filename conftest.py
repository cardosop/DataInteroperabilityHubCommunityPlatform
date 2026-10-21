"""
Root conftest — core-only collection gate for paid-context test modules.

In the PUBLIC repository the paid apps' directories (and every test module
that imports them) do not exist, so the core CI job simply never collects
them. The PRIVATE repository keeps those files for the full-mode suite;
when ``HUB_CORE_ONLY=1`` the paid apps are not in INSTALLED_APPS and any
module-level ``from hub.apps.<paid>... import ...`` raises
``RuntimeError`` at model-class definition, turning collection into an
error instead of a skip.

``pytest_ignore_collect`` mirrors the public tree's behavior: under
``HUB_CORE_ONLY=1``, test modules that import paid apps at module level
are ignored. Full-mode runs return ``None`` for everything and are
completely unaffected.
"""

from __future__ import annotations

import os
import re

# Initialize Django BEFORE any per-directory conftest loads: some
# conftests import app modules at module level (e.g. the orchestration
# workflows tests conftest chain reaches hub.apps.audit.models →
# get_user_model), which requires the app registry to be populated.
# pytest-django's own setup runs later (pytest_configure); this is
# idempotent with it.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")
try:
    import django

    django.setup()
except Exception:
    pass

# Manifest-owned paid modules — keep in sync with
# ``_PAID_MODULES`` in hub/apps/manifest.py.
#
# W7.1: the pattern matches COLUMN-0 imports only.  Guarded imports
# (try/except (RuntimeError, ModuleNotFoundError), is_core_only()
# branches) are INDENTED — those modules now collect in core mode and
# their guards degrade or skip at run time, so the public CI actually
# exercises them.  The ``^\s*`` prefix this replaced ignored guarded
# modules too (a guard is indistinguishable from no guard to a regex),
# which is what made the W7.1 guard work necessary.
_PAID_MODULE_IMPORT_RE = re.compile(
    r"^(?:from|import)\s+hub\.apps\.(?:semantic|marketplace|billing|baas"
    r"|rate_limiting|ai|ml|social|graphql|graphql_ld|graphql_graphene"
    r"|databricks_admin)\b",
    flags=re.MULTILINE,
)

_TEST_MODULE_RE = re.compile(r"^(test_.*|.*_tests)\.py$")

_SOURCE_CACHE: dict[str, bool] = {}


def pytest_ignore_collect(collection_path, config):
    """Ignore paid-context test modules in core-only mode (None otherwise)."""
    if os.environ.get("HUB_CORE_ONLY") != "1":
        return None
    if not collection_path.is_file():
        return None
    if not _TEST_MODULE_RE.match(collection_path.name):
        return None
    path_str = str(collection_path)
    cached = _SOURCE_CACHE.get(path_str)
    if cached is not None:
        return cached
    try:
        source = collection_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        _SOURCE_CACHE[path_str] = None
        return None
    ignored = bool(_PAID_MODULE_IMPORT_RE.search(source))
    _SOURCE_CACHE[path_str] = ignored
    return ignored
