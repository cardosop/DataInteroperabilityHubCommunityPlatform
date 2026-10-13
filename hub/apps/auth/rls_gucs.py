"""
W1.20 (oss-release-remediation, D2 / W1.4b) — the RLS request-path
GUC registry.

The TenantScopingMiddleware arms PostgreSQL Row-Level Security on the
HTTP path by setting, transaction-locally, one GUC per RLS policy plus
the tenant GUC itself::

    app.current_tenant_id            — the resolved request tenant
                                       (NULL for anonymous requests —
                                       the fail-closed direction)
    app.rls_<table>_enabled          — derived from the paired
                                       RLS_<TABLE>_ENABLED settings
                                       kill switch (default True =
                                       enforced; False = the table's
                                       USING clause opens for reads —
                                       the forensic-inspection mode)

The settings names are the single source of truth; the mapping is the
deterministic transform ``RLS_<TABLE>_ENABLED → app.rls_<table>_enabled``.
``RLS_REQUEST_PATH_ENABLED`` — the MASTER kill switch that disables
the whole arming path — is explicitly NOT a table flag and is excluded
here.  The inventory is pinned bidirectionally against the actual RLS
policy migrations by
``hub.apps.auth.tests.test_rls_guc_settings_sync`` — a drift in either
direction fails the suite.

Why transaction-local: staging and production route through PgBouncer
in transaction pooling, where a session-level ``SET`` leaks onto the
next client that reuses the pooled server connection.  ``SET LOCAL``
inside the request transaction evaporates at COMMIT/ROLLBACK — a
pooled connection can never carry one tenant's scope into another
request (pinned by ``test_rls_middleware_guc`` /
``test_rls_request_path_arming``).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable

RLS_TENANT_GUC = "app.current_tenant_id"

# The master arming kill switch — matches the RLS_*_ENABLED shape but
# gates the whole middleware path, not a single table policy.
RLS_REQUEST_PATH_SWITCH = "RLS_REQUEST_PATH_ENABLED"

_SETTING_NAME_RE = re.compile(r"^RLS_(?P<table>[A-Z0-9_]+)_ENABLED$")


def guc_name_for_setting(setting_name: str) -> str:
    """Map ``RLS_ASSETS_ENABLED`` → ``app.rls_assets_enabled``."""
    match = _SETTING_NAME_RE.match(setting_name)
    if not match:
        raise ValueError(
            f"{setting_name!r} is not a RLS_<TABLE>_ENABLED kill-switch setting"
        )
    return f"app.rls_{match.group('table').lower()}_enabled"


def iter_rls_enabled_settings(
    settings_module: Any | None = None,
) -> Iterable[tuple[str, str, bool]]:
    """Yield ``(setting_name, guc_name, enabled)`` for every registered
    table kill switch, sorted by setting name for determinism.

    The master switch ``RLS_REQUEST_PATH_ENABLED`` is excluded — it is
    not a table flag (setting it as a GUC would create a phantom GUC
    no policy reads).
    """
    from django.conf import settings as django_settings

    settings_module = settings_module or django_settings
    entries: list[tuple[str, str, bool]] = []
    for name in dir(settings_module):
        if name == RLS_REQUEST_PATH_SWITCH or not _SETTING_NAME_RE.match(name):
            continue
        entries.append((name, guc_name_for_setting(name), bool(getattr(settings_module, name))))
    return sorted(entries, key=lambda entry: entry[0])


def build_arm_sql(tenant_id: str | None, settings_module: Any | None = None):
    """Build the single batched ``SET LOCAL`` statement for a request.

    One round trip sets every GUC: the tenant (or NULL — the
    fail-closed anonymous direction) plus every per-table kill switch,
    each transaction-scoped via ``set_config(..., is_local=true)``.
    """
    from django.conf import settings as django_settings

    settings_module = settings_module or django_settings
    calls = ["set_config(%s, %s, true)"]
    params: list = [RLS_TENANT_GUC, str(tenant_id) if tenant_id else None]
    for _setting_name, guc_name, enabled in iter_rls_enabled_settings(settings_module):
        calls.append("set_config(%s, %s, true)")
        params.extend([guc_name, "true" if enabled else "false"])
    return "SELECT " + ", ".join(calls), params
