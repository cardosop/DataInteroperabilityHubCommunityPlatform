"""UC grants bridge (openspec add-databricks-uc-write task 2.6).

The D5 flow — PLAN (ABAC policies → intended grants) → DIFF (intended vs
the LIVE UC assignments) → APPLY (REST PATCH; SQL GRANT/REVOKE fallback
for securables without a REST grant endpoint) → VERIFY (re-read) — with
the hard contracts:

- OWNERSHIP is never granted: `OWN`/`OWNERSHIP` in any plan raises
  ``UCGrantBridgeError`` (`DATABRICKS_GRANT_UNSUPPORTED`) — the DPO owns,
  the bridge refuses.
- Model grants use UC's `FUNCTION` securable (the registered-model
  convention).
- Attribute-policy shadows mark the binding OUT_OF_SYNC: a disabled
  policy (or a policy whose securable/principal no longer exists) can
  no longer produce its grant — the operator sees the divergence, the
  bridge never guesses.
- Identity: the CALLER resolves the D12 decision (INTERACTIVE purpose
  ``grant_apply`` — OBO, fail-closed without a binding); the bridge
  itself never selects credentials.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Ownership privileges the bridge NEVER issues (D5 — the DPO owns).
_OWNERSHIP_PRIVILEGES = frozenset({"OWN", "OWNERSHIP"})

# The SQL-fallback leg interpolates privileges into GRANT/REVOKE
# statements — only safe SCREAMING_SNAKE tokens are representable (UC's
# privilege vocabulary); anything else refuses the plan.
_PRIVILEGE_TOKEN = re.compile(r"^[A-Z][A-Z0-9_]*$")

# Binding securable → the UC API's securable path segment. MODEL maps to
# FUNCTION (UC's registered-model grant convention).
_UC_SECURABLE_SEGMENTS = {
    "CATALOG": "catalog",
    "SCHEMA": "schema",
    "TABLE": "table",
    "VIEW": "view",
    "VOLUME": "volume",
    "FUNCTION": "function",
    "MODEL": "function",
}

# Securables with a UC REST grant endpoint (the others ride the SQL
# fallback — UC has no REST grant endpoint for catalog/schema grants).
_REST_GRANT_SECURABLES = frozenset({"TABLE", "VIEW", "VOLUME", "FUNCTION", "MODEL"})


class UCGrantBridgeError(Exception):
    """The bridge's classified refusal (never a workspace error)."""

    def __init__(self, message: str):
        super().__init__(message)
        self.code = "DATABRICKS_GRANT_UNSUPPORTED"


# ── AUDIT (task 2.9) ────────────────────────────────────────────────────────


def _emit_grant_audit(workspace, action: str, *, details: dict) -> None:
    """Best-effort grant audit (resource_type=``DATABRICKS_GRANT``).

    Identifiers only: securable full names, principal names and
    privileges — no credential material exists on this path. An
    audit-DB outage never blocks the bridge (Phase 273 contract).
    """
    try:
        from hub.apps.audit.utils import create_audit_event

        create_audit_event(
            resource_type="DATABRICKS_GRANT",
            action=action,
            tenant=workspace.tenant,
            resource_id=str(workspace.id),
            details=details,
        )
    except Exception:
        logger.warning("databricks_uc_grant_audit_failed", extra={"action": action})


def _emit_apply_audits(workspace, *, securable_type, securable_full_name, changes, method) -> None:
    """APPLIED for the added grants, REVOKED for the removed ones (one
    apply call can carry both legs). The pairs are emitted as OBJECTS —
    the audit pipeline's ``redact_pii`` stringifies non-dict list items,
    so nested pair-lists would arrive as ``str()`` noise."""
    adds = list(changes.get("add") or [])
    removes = list(changes.get("remove") or [])
    if adds:
        _emit_grant_audit(
            workspace,
            "APPLIED",
            details={
                "securable_type": securable_type,
                "securable_full_name": securable_full_name,
                "method": method,
                "add_count": len(adds),
                "added": [
                    {"principal": principal, "privilege": privilege}
                    for principal, privilege in adds
                ],
            },
        )
    if removes:
        _emit_grant_audit(
            workspace,
            "REVOKED",
            details={
                "securable_type": securable_type,
                "securable_full_name": securable_full_name,
                "method": method,
                "remove_count": len(removes),
                "removed": [
                    {"principal": principal, "privilege": privilege}
                    for principal, privilege in removes
                ],
            },
        )


# ── PLAN ─────────────────────────────────────────────────────────────────────


def plan_uc_grants(workspace) -> list[dict]:
    """Derive the intended grants from the tenant's ABAC policy rows.

    A policy's ``conditions["uc_grant"]`` block carries the grant intent:
    {securable_type, securable_full_name, principal, privileges}. The
    plan REFUSES ownership (fail-closed); bindings whose source policy
    no longer produces them (disabled policy) are marked OUT_OF_SYNC.
    """
    from django.core.exceptions import ValidationError

    from hub.apps.databricks_admin.models import (
        UCGrantBinding,
        UCGrantBindingStatus,
        UCGrantSecurableType,
        UCPPrincipal,
    )
    from hub.apps.governance.models import AccessPolicy

    intended: list[dict] = []
    source_ids: set[str] = set()

    policies = AccessPolicy.objects.filter(tenant=workspace.tenant, effect="ALLOW").select_related(
        "tenant"
    )
    for policy in policies:
        grant = (policy.conditions or {}).get("uc_grant")
        if not isinstance(grant, dict):
            continue
        privileges = grant.get("privileges") or []
        if not privileges:
            continue
        ownership = _OWNERSHIP_PRIVILEGES.intersection(privileges)
        if ownership:
            raise UCGrantBridgeError(
                f"refusing OWNERSHIP grant for {grant.get('securable_full_name')} "
                f"(privilege {sorted(ownership)[0]}) — the DPO owns, the "
                "bridge never issues OWN"
            )
        # 2.6 second review — fail-closed on the securable vocabulary: a
        # securable the bridge cannot map must be SKIPPED (never applied,
        # never crash the ABAC sweep). The SQL-fallback leg interpolates
        # privileges into statements — they must be safe SCREAMING_SNAKE
        # tokens (UC's privilege vocabulary) or the plan refuses.
        securable_type = str(grant.get("securable_type") or "")
        try:
            UCGrantSecurableType(securable_type)
        except ValueError:
            logger.warning(
                "databricks_uc_grant_plan_unmappable_securable",
                extra={
                    "workspace": str(workspace.id),
                    "policy": str(policy.id),
                    "securable_type": securable_type,
                },
            )
            continue
        for privilege in privileges:
            if not _PRIVILEGE_TOKEN.fullmatch(str(privilege)):
                raise UCGrantBridgeError(
                    f"refusing unrepresentable privilege {privilege!r} — UC "
                    "privileges are SCREAMING_SNAKE tokens"
                )
        # The plan needs a UCPPrincipal row to bind against; missing
        # principals are provisioned on first plan (first-login style).
        # The name is checked BEFORE the row is created (no orphan
        # empty-name principals).
        principal_name = str(grant.get("principal") or "").strip()
        if not principal_name:
            raise UCGrantBridgeError("a grant plan must name its principal")
        principal, _created = UCPPrincipal.objects.get_or_create(
            workspace=workspace,
            name=principal_name,
            defaults={"principal_type": "GROUP"},
        )
        securable_full_name = str(grant.get("securable_full_name") or "")
        # A DISABLED policy can no longer produce its grant — its grants
        # NEVER reach the intended plan (the bridge applies nothing); the
        # binding upsert below still runs and shadows the rows.
        if policy.enabled:
            intended.append(
                {
                    "securable_type": securable_type,
                    "securable_full_name": securable_full_name,
                    "principal": principal.name,
                    "privileges": list(privileges),
                }
            )
        # Upsert the bindings at the (principal, securable, privilege)
        # grain; only ENABLED policies produce PLANNED rows.
        for privilege in privileges:
            binding, _created = UCGrantBinding.objects.get_or_create(
                workspace=workspace,
                principal=principal,
                securable_type=UCGrantSecurableType(securable_type),
                securable_full_name=securable_full_name,
                privilege=str(privilege),
                defaults={"source_policy_id": str(policy.id)},
            )
            if not policy.enabled:
                binding.status = UCGrantBindingStatus.OUT_OF_SYNC
                binding.save(update_fields=["status"])
            elif binding.status != UCGrantBindingStatus.APPLIED:
                binding.status = UCGrantBindingStatus.PLANNED
                binding.save(update_fields=["status"])
            source_ids.add(str(binding.id))

    # Policy shadows: every binding whose policy no longer exists (or is
    # disabled) is marked OUT_OF_SYNC — the operator sees the divergence.
    stale = (
        UCGrantBinding.objects.filter(workspace=workspace)
        .exclude(status=UCGrantBindingStatus.OUT_OF_SYNC)
        .select_related("principal")
    )
    for binding in stale:
        policy_id = binding.source_policy_id
        policy = None
        if policy_id:
            try:
                policy = AccessPolicy.objects.filter(id=policy_id, tenant=workspace.tenant).first()
            except (ValueError, ValidationError):  # non-UUID legacy ids fail closed
                policy = None
        if policy is None or not policy.enabled:
            binding.status = UCGrantBindingStatus.OUT_OF_SYNC
            binding.save(update_fields=["status"])
    # 2.9 — the computed plan is audited (identifiers only: the
    # securables and principals involved, never policy conditions).
    _emit_grant_audit(
        workspace,
        "PLAN_COMPUTED",
        details={
            "grant_count": len(intended),
            "securables": sorted({grant["securable_full_name"] for grant in intended}),
            "principals": sorted({grant["principal"] for grant in intended}),
        },
    )
    return intended


# ── DIFF ─────────────────────────────────────────────────────────────────────


def diff_grants(intended: list, live: list) -> dict:
    """(principal, privilege) pairs to add/remove against the live set."""
    intended_pairs = {(pair[0], pair[1]) for pair in intended}
    live_pairs = {(pair[0], pair[1]) for pair in live}
    return {
        "add": sorted(intended_pairs - live_pairs),
        "remove": sorted(live_pairs - intended_pairs),
    }


def _live_pairs(assignments) -> list:
    pairs: list = []
    for assignment in assignments or []:
        # 2.6 second review — junk rows in a live answer are ignored
        # (an unparseable assignment can never match; the verify
        # contract is "report the mismatch, never mask, never crash").
        if not isinstance(assignment, dict):
            continue
        principal = assignment.get("principal")
        privileges = assignment.get("privileges")
        if not isinstance(privileges, list):
            continue
        for privilege in privileges:
            if principal:
                pairs.append((principal, privilege))
    return pairs


# ── APPLY ────────────────────────────────────────────────────────────────────


def apply_grant_delta(
    client,
    *,
    workspace,
    securable_type: str,
    securable_full_name: str,
    changes: dict,
    statement_executor=None,
):
    """Apply the diff — REST PATCH where UC has the endpoint, SQL
    GRANT/REVOKE otherwise. Returns the live assignments after apply
    (the REST response envelope), or the statement id for the SQL leg.

    ``workspace`` is REQUIRED (2.9 contract): the bridge emits an audit
    row per successful leg — APPLIED for the added grants, REVOKED for
    the removed ones — and tenant/workspace attribution is part of the
    apply contract, not an option.
    """
    if securable_type in _REST_GRANT_SECURABLES:
        segment = _UC_SECURABLE_SEGMENTS[securable_type]
        patch_changes = []
        for principal, privilege in changes["remove"]:
            patch_changes.append({"principal": principal, "remove": [privilege]})
        for principal, privilege in changes["add"]:
            patch_changes.append({"principal": principal, "add": [privilege]})
        if not patch_changes:
            return None
        response = client.request(
            "PATCH",
            "uc.grants.patch",
            path_params={"securable_type": segment, "full_name": securable_full_name},
            json={"changes": patch_changes},
        )
        payload = response.json()
        _emit_apply_audits(
            workspace,
            securable_type=securable_type,
            securable_full_name=securable_full_name,
            changes=changes,
            method="rest",
        )
        return payload

    result = _apply_sql_grants(
        client,
        securable_type=securable_type,
        securable_full_name=securable_full_name,
        changes=changes,
        statement_executor=statement_executor,
    )
    if result is None:
        return None
    # The SQL leg RAISES on a failed statement (SqlStatementError) — a
    # returned result is a success; APPLIED/REVOKED fire only then.
    _emit_apply_audits(
        workspace,
        securable_type=securable_type,
        securable_full_name=securable_full_name,
        changes=changes,
        method="sql",
    )
    return result


def _apply_sql_grants(client, *, securable_type, securable_full_name, changes, statement_executor):
    from hub.apps.databricks_admin.sql_statements import SqlStatementExecutor
    from hub.apps.databricks_admin.uc_change_executor import _quote

    statements = []
    # The 2.3 _quote discipline: each identifier part is quoted SEPARATELY
    # and backticks are DOUBLED — the plan data is not
    # identifier-validated before this leg, so the escaping is
    # defense-in-depth (a hostile principal/name can never break out).
    target = ".".join(_quote(part) for part in securable_full_name.split("."))
    for principal, privilege in changes["add"]:
        statements.append(f"GRANT {privilege} ON {securable_type} {target} TO {_quote(principal)}")
    for principal, privilege in changes["remove"]:
        statements.append(
            f"REVOKE {privilege} ON {securable_type} {target} FROM {_quote(principal)}"
        )
    if not statements:
        return None
    if statement_executor is None:
        statement_executor = SqlStatementExecutor(client)
    return statement_executor.execute("; ".join(statements))


# ── VERIFY ───────────────────────────────────────────────────────────────────


def verify_grants(
    client,
    *,
    workspace,
    securable_type: str,
    securable_full_name: str,
    expected: list,
) -> bool:
    """Re-read the LIVE assignments and compare against the expected
    (principal, privilege) set — a mismatch is reported, never masked.

    ``workspace`` is REQUIRED (2.9 contract): every verification emits a
    VERIFIED row (matched or mismatch) with tenant attribution.
    """
    segment = _UC_SECURABLE_SEGMENTS.get(securable_type, securable_type.lower())
    response = client.request(
        "GET",
        "uc.permissions.get",
        path_params={"securable_type": segment, "full_name": securable_full_name},
    )
    payload = response.json()
    if not isinstance(payload, dict):
        # The re-read contract: an unparseable answer is a reported
        # mismatch (never masked, never a crash).
        _emit_grant_audit(
            workspace,
            "VERIFIED",
            details={
                "securable_type": securable_type,
                "securable_full_name": securable_full_name,
                "matched": False,
                "expected_count": len(expected),
                "live_count": 0,
            },
        )
        return False
    live = _live_pairs(payload.get("privilege_assignments"))
    matched = set(live) == set(expected)
    _emit_grant_audit(
        workspace,
        "VERIFIED",
        details={
            "securable_type": securable_type,
            "securable_full_name": securable_full_name,
            "matched": matched,
            "expected_count": len(expected),
            "live_count": len(live),
        },
    )
    return matched
