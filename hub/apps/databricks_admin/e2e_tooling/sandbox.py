"""Phase 9 (task 9.2, design D1/D7) — the sandbox lifecycle.

W4.6 (oss-release-remediation, G1): this module moved from
``scripts/databricks_e2e/`` into the estate — the sandbox lifecycle is
Databricks estate administration and belongs to the provider app (the
provider-boundary direction: estate tooling lives WITH the estate, not
in provider-agnostic scripts).

The ``meshant_e2e_*`` naming convention lives HERE and only here (the
workflow never hardcodes the prefix — one source of truth). The destroy
sweep is the idempotent backstop: it lists the account's workspaces and
deletes EVERY convention match — a failed earlier run's leftovers are
cleaned by the next run's always-step, so no run can leave a sandbox
behind. Creation and destruction both go through the PRODUCTION
``DatabricksAccountClient`` (the 8.3 client with the 9.2 delete ops).
"""

from __future__ import annotations

import json
import os
import sys
import uuid

SANDBOX_PREFIX = "meshant_e2e_"


def sandbox_name(run_id: str) -> str:
    """The convention name for a run — unique per run identity, bounded to
    the workspace-name limit by construction (the prefix + a run id)."""
    return f"{SANDBOX_PREFIX}{str(run_id).strip()}"


def owned_sandboxes(rows: list[dict]) -> list[dict]:
    """The destroy selector: every account workspace carrying the
    convention prefix (and ONLY those — real customer workspaces are
    never touched)."""
    return [
        row
        for row in rows
        if str(row.get("workspace_name", "")).startswith(SANDBOX_PREFIX)
    ]


def create_sandbox(client, run_id: str, *, aws_region: str = "us-east-1") -> dict:
    """Create the run's sandbox workspace through the account API."""
    return client.create_workspace(
        workspace_name=sandbox_name(run_id),
        deployment_name=f"e2e-{str(run_id).strip()}",
        aws_region=aws_region,
    )


def destroy_sandbox(client) -> None:
    """Idempotent: list the account's workspaces and delete EVERY
    convention match. No matches → one list call, zero deletes; a match
    already gone between list and delete is a classified 4xx, never a
    crash that would mask the sweep."""
    for row in owned_sandboxes(client.list_workspaces()):
        client.delete_workspace(str(row["workspace_id"]))


def _client_from_env():
    """Build the production account client from the environment (workflow
    secrets via the OIDC posture — never the repo).

    ``DATABRICKS_E2E_ACCOUNT_BASE_URL`` overrides the account endpoint —
    used by the failure-path TDD pins to drive the PRODUCTION client over
    a real local HTTP server (the 8.3 RecordingHandler convention) and
    available to operators targeting a mirror/private endpoint.
    """
    from hub.apps.databricks_admin.account_client import DatabricksAccountClient

    account_id = os.environ.get("DATABRICKS_E2E_ACCOUNT_ID", "").strip()
    token = os.environ.get("DATABRICKS_E2E_ACCOUNT_TOKEN", "").strip()
    if not account_id or not token:
        raise RuntimeError(
            "DATABRICKS_E2E_ACCOUNT_ID / DATABRICKS_E2E_ACCOUNT_TOKEN are "
            "required (workflow environment secrets)"
        )
    base_url = os.environ.get("DATABRICKS_E2E_ACCOUNT_BASE_URL", "").strip() or None
    return DatabricksAccountClient(account_id, {"token": token}, base_url=base_url)


def main(argv=None) -> int:
    """The workflow's CLI: ``create`` / ``destroy`` subcommands."""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: sandbox.py create|destroy", file=sys.stderr)
        return 2
    client = _client_from_env()
    if args[0] == "create":
        run_id = os.environ.get("GITHUB_RUN_ID", str(uuid.uuid4().int)[-8:])
        envelope = create_sandbox(client, run_id)
        print(json.dumps(envelope, default=str))
        return 0
    if args[0] == "destroy":
        destroy_sandbox(client)
        print("DESTROY COMPLETE: every meshant_e2e_* workspace deleted")
        return 0
    print(f"unknown subcommand {args[0]!r}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
