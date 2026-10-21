"""
W1.20 (oss-release-remediation, D2 / W1.4b) — the pre-tenant
(BYPASSRLS) lookup-alias discriminator, extracted from
``hub/apps/auth/views.py`` so the tenant-scoping middleware and the
auth views share ONE implementation of a subtle contract.

Chooses the connection alias for *pre-auth* / *pre-tenant* identity
lookups — queries that must see identity rows (``api_keys``,
``users``, ``user_tenant_memberships``) BEFORE any tenant GUC exists.

Discriminator: does the ``admin`` alias ACTUALLY map to a different
DB role than ``default``?  That is the only condition under which
routing pre-tenant lookups through ``admin`` buys anything.

* **Production:** ``DATABASES["admin"]["USER"] = "meshant_admin"``
  (BYPASSRLS), ``DATABASES["default"]["USER"] = "meshant_app"``
  (RLS-enforced).  The identity tables carry RLS policies that filter
  by ``current_setting('app.current_tenant_id')`` — under the
  enforced role, before the request tenant is resolved, those lookups
  see zero rows.  The admin alias bypasses RLS and is required for
  login / registration / API-key extraction / membership checks to
  work at all.

* **Test / dev (default):** the ``admin`` alias falls back to the
  same USER as ``default``.  It is still a SEPARATE psycopg
  connection — Django's ``ConnectionHandler`` keys on alias name, not
  on connection params — so routing through it opens a parallel
  session whose MVCC snapshot is taken BEFORE a TestCase's
  atomic-wrapped INSERT.  ``User.objects.using("admin").get(email=...)``
  then raises ``User.DoesNotExist`` for a user the test JUST created.

  ``RLS_USERS_ENABLED`` is NOT a usable discriminator: it defaults to
  ``True``, so testing it would pick ``"admin"`` in test too and trip
  the cross-connection MVCC trap above.

The pytest guard below returns ``"default"`` unconditionally in test
runs — the canonical
``hub.apps.auth.tests.test_rls_middleware_preauth_alias.RLSBypassPreAuthTransactionTest``
(TransactionTestCase + a REAL second BYPASSRLS role on the server)
exercises the production branch by setting
``RLS_ADMIN_ALIAS_IN_TESTS=True`` and overriding ``DATABASES``.
"""

from __future__ import annotations

import os
import sys
from typing import Any

from django.core.exceptions import ImproperlyConfigured


def _alias_differs(databases: dict[str, dict[str, Any]]) -> bool:
    """True when the ``admin`` alias maps to a different DB role than
    ``default`` — the only shape where pre-tenant reads via ``admin``
    change anything."""
    admin_cfg = databases.get("admin")
    default_cfg = databases.get("default", {})
    if not admin_cfg:
        return False
    admin_user = admin_cfg.get("USER")
    default_user = default_cfg.get("USER")
    return bool(admin_user and admin_user != default_user)


def user_lookup_alias() -> str:
    """The connection alias for pre-tenant identity lookups."""
    from django.conf import settings

    try:
        databases = settings.DATABASES
    except (AttributeError, ImproperlyConfigured):  # pragma: no cover — settings always loaded
        return "default"

    # The canonical test escape hatch (see module docstring) — checked
    # BEFORE the pytest guard so the production branch is pinnable.
    if getattr(settings, "RLS_ADMIN_ALIAS_IN_TESTS", False):
        return "admin" if _alias_differs(databases) else "default"

    # In a test run (pytest is in sys.modules or PYTEST_CURRENT_TEST is
    # set) the admin alias uses the same DB USER as default, but Django
    # still routes through a separate psycopg connection whose MVCC
    # snapshot predates the test's atomic-wrapped INSERT.  Force
    # "default" so the pre-tenant lookup runs inside the test's
    # transaction and can see setUp / setUpTestData rows.
    if "pytest" in sys.modules or os.getenv("PYTEST_CURRENT_TEST"):
        return "default"

    return "admin" if _alias_differs(databases) else "default"
