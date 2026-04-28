"""
TDD unit tests for scripts/staging_prefix_purge.cjs — Phase 226 E2.

Background
----------
The `createdResources` fixture tears down per-test, but a hard runner
crash can leak rows. The prefix-purge cron is the staging-side safety
net: nightly, it lists every e2e-prefixed row older than the configured
age and bulk-cancels / soft-deletes them. A bug in the candidate filter
(too greedy → real data loss; too narrow → no cleanup) is high-blast,
so the pure-logic branches are pinned by this suite.

Pure logic
----------
The .cjs module exports `shouldPurge`, `extractCandidates`,
`cutoffIsoFor`, `parseArgs`, `validateArgs`, and `purgeFamily`. The
HTTP layer is testable by injecting a stub `fetchImpl` into `run` /
`purgeFamily`.

Run locally:
    pytest scripts/tests/test_staging_prefix_purge.py -v
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "staging_prefix_purge.cjs"


def _has_node() -> bool:
    try:
        res = subprocess.run(["node", "--version"], capture_output=True, timeout=10)
        return res.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


pytestmark = pytest.mark.skipif(
    not _has_node(),
    reason="node not available in PATH",
)


def _node_eval(expr: str) -> str:
    cmd = [
        "node",
        "-e",
        f"const m = require('{SCRIPT}'); process.stdout.write(JSON.stringify({expr}));",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    assert res.returncode == 0, f"node failed: {res.stderr}"
    return res.stdout


# ----------------------------- cutoffIsoFor -----------------------------

def test_cutoffIsoFor_subtracts_minutes_from_now() -> None:
    out = _node_eval(
        "m.cutoffIsoFor(new Date('2026-04-25T12:00:00Z'), 60)"
    )
    assert json.loads(out) == "2026-04-25T11:00:00.000Z"


def test_cutoffIsoFor_zero_minutes_returns_now() -> None:
    out = _node_eval(
        "m.cutoffIsoFor(new Date('2026-04-25T12:00:00Z'), 0)"
    )
    assert json.loads(out) == "2026-04-25T12:00:00.000Z"


# ----------------------------- shouldPurge ------------------------------

def test_shouldPurge_accepts_e2e_prefixed_old_active_row() -> None:
    row = {
        "id": "1",
        "name": "e2e-foo",
        "created_at": "2026-04-24T00:00:00Z",
        "status": "ACTIVE",
    }
    out = _node_eval(f"m.shouldPurge({json.dumps(row)}, 'e2e-', '2026-04-25T00:00:00Z')")
    assert json.loads(out) is True


def test_shouldPurge_rejects_unprefixed_name() -> None:
    row = {"id": "1", "name": "production-data", "created_at": "2026-04-24T00:00:00Z"}
    out = _node_eval(f"m.shouldPurge({json.dumps(row)}, 'e2e-', '2026-04-25T00:00:00Z')")
    assert json.loads(out) is False


def test_shouldPurge_rejects_in_flight_row_newer_than_cutoff() -> None:
    """A row created 5 minutes ago must NOT be purged — it might belong to a still-running spec."""
    row = {"id": "1", "name": "e2e-foo", "created_at": "2026-04-25T11:55:00Z"}
    out = _node_eval(f"m.shouldPurge({json.dumps(row)}, 'e2e-', '2026-04-25T11:00:00Z')")
    assert json.loads(out) is False


def test_shouldPurge_rejects_already_tombstoned_row() -> None:
    """RETIRED / DELETED / DISABLED / CANCELLED rows are already tombstones."""
    for status in ["RETIRED", "DELETED", "DISABLED", "CANCELLED", "retired"]:
        row = {"id": "1", "name": "e2e-foo", "created_at": "2026-04-24T00:00:00Z", "status": status}
        out = _node_eval(f"m.shouldPurge({json.dumps(row)}, 'e2e-', '2026-04-25T00:00:00Z')")
        assert json.loads(out) is False, f"status {status} should be skipped"


def test_shouldPurge_falls_back_to_title_then_username_then_email() -> None:
    """Different families surface name in different fields — shouldPurge accepts all."""
    out = _node_eval(
        f"m.shouldPurge({json.dumps({'id': '1', 'title': 'e2e-listing'})}, 'e2e-', '2030-01-01T00:00:00Z')"
    )
    assert json.loads(out) is True
    out = _node_eval(
        f"m.shouldPurge({json.dumps({'id': '1', 'username': 'e2e-bob'})}, 'e2e-', '2030-01-01T00:00:00Z')"
    )
    assert json.loads(out) is True
    out = _node_eval(
        f"m.shouldPurge({json.dumps({'id': '1', 'email': 'e2e-bob@x'})}, 'e2e-', '2030-01-01T00:00:00Z')"
    )
    assert json.loads(out) is True


def test_shouldPurge_returns_false_for_null_or_non_object() -> None:
    out = _node_eval("m.shouldPurge(null, 'e2e-', '2030-01-01T00:00:00Z')")
    assert json.loads(out) is False


# ----------------------------- extractCandidates ------------------------

def test_extractCandidates_handles_paginated_payload() -> None:
    payload = {
        "count": 2,
        "results": [
            {"id": "a", "name": "e2e-keep", "status": "ACTIVE"},
            {"id": "b", "name": "production"},
            {"id": "c", "name": "e2e-tombstone", "status": "RETIRED"},
        ],
    }
    out = _node_eval(
        f"m.extractCandidates({json.dumps(payload)}, 'e2e-', '2030-01-01T00:00:00Z')"
    )
    assert json.loads(out) == ["a"]


def test_extractCandidates_handles_bare_array_payload() -> None:
    payload = [
        {"id": "a", "name": "e2e-x", "status": "ACTIVE"},
        {"id": "b", "name": "real"},
    ]
    out = _node_eval(
        f"m.extractCandidates({json.dumps(payload)}, 'e2e-', '2030-01-01T00:00:00Z')"
    )
    assert json.loads(out) == ["a"]


def test_extractCandidates_returns_empty_for_malformed_payload() -> None:
    out = _node_eval("m.extractCandidates(null, 'e2e-', '2030-01-01T00:00:00Z')")
    assert json.loads(out) == []


# ----------------------------- validateArgs -----------------------------

def test_validateArgs_requires_base() -> None:
    out = _node_eval("m.validateArgs(m.parseArgs(['node', 'p']))")
    assert "missing required --base" in json.loads(out)


def test_validateArgs_requires_token_unless_dry_run() -> None:
    out = _node_eval(
        "m.validateArgs(m.parseArgs(['node', 'p', '--base=https://x/api/v1']))"
    )
    assert "missing required --token" in json.loads(out)
    out = _node_eval(
        "m.validateArgs(m.parseArgs(['node', 'p', '--base=https://x/api/v1', '--dry-run']))"
    )
    assert json.loads(out) is None  # OK without token in dry-run


def test_validateArgs_rejects_negative_minutes() -> None:
    out = _node_eval(
        "m.validateArgs(m.parseArgs("
        "['node', 'p', '--base=https://x/api/v1', '--token=t', '--older-than-minutes=-1']))"
    )
    assert "invalid --older-than-minutes" in json.loads(out)


# ----------------------------- purgeFamily integration ------------------

PURGE_FAMILY_HARNESS = """
const m = require('SCRIPT_PATH');
const args = {
  base: 'https://api.x/api/v1',
  token: 'tok',
  prefix: 'e2e-',
  olderThanMinutes: 60,
  maxPerType: 500,
  dryRun: DRY,
  json: false,
};
const fetchCalls = [];
const fetchImpl = async (url, init) => {
  fetchCalls.push({ url, method: init && init.method || 'GET' });
  if (init && init.method && init.method !== 'GET') {
    return MUTATION_RESPONSE;
  }
  return LIST_RESPONSE;
};
const family = m.FAMILIES.find((f) => f.type === FAMILY_TYPE);
m.purgeFamily(family, args, { fetchImpl, now: new Date('2026-04-25T12:00:00Z') })
  .then((r) => process.stdout.write(JSON.stringify({ result: r, fetchCalls })));
"""


def _purge_family(
    family_type: str,
    list_response: str,
    mutation_response: str = "{ ok: true, status: 204, text: async () => '' }",
    dry_run: bool = False,
) -> dict:
    code = (PURGE_FAMILY_HARNESS
            .replace("SCRIPT_PATH", str(SCRIPT))
            .replace("FAMILY_TYPE", json.dumps(family_type))
            .replace("LIST_RESPONSE", list_response)
            .replace("MUTATION_RESPONSE", mutation_response)
            .replace("DRY", "true" if dry_run else "false"))
    res = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=15)
    assert res.returncode == 0, res.stderr
    return json.loads(res.stdout)


def test_purgeFamily_dry_run_lists_candidates_without_mutating() -> None:
    list_resp = (
        "{ ok: true, status: 200, "
        "json: async () => ({ results: ["
        "  { id: 'a', name: 'e2e-old', created_at: '2026-04-25T10:00:00Z', status: 'ACTIVE' },"
        "  { id: 'b', name: 'production' }"
        "]}), text: async () => '' }"
    )
    out = _purge_family("asset", list_resp, dry_run=True)
    assert out["result"]["attempted"] == 1
    assert out["result"]["candidates"] == ["a"]
    # Only the LIST call should be in fetchCalls — no DELETE.
    assert len(out["fetchCalls"]) == 1
    assert "GET" == out["fetchCalls"][0]["method"]


def test_purgeFamily_deletes_candidates_and_treats_404_as_success() -> None:
    list_resp = (
        "{ ok: true, status: 200, "
        "json: async () => ({ results: ["
        "  { id: 'a', name: 'e2e-x', created_at: '2026-04-25T10:00:00Z', status: 'ACTIVE' }"
        "]}), text: async () => '' }"
    )
    # Mutation returns 404 — already gone; counts as success.
    mut = "{ ok: false, status: 404, text: async () => '' }"
    out = _purge_family("asset", list_resp, mutation_response=mut)
    assert out["result"]["attempted"] == 1
    assert out["result"]["succeeded"] == 1
    assert out["result"]["failures"] == []


def test_purgeFamily_records_failures_for_5xx() -> None:
    list_resp = (
        "{ ok: true, status: 200, "
        "json: async () => ({ results: ["
        "  { id: 'a', name: 'e2e-x', created_at: '2026-04-25T10:00:00Z', status: 'ACTIVE' }"
        "]}), text: async () => '' }"
    )
    mut = "{ ok: false, status: 500, text: async () => 'boom' }"
    out = _purge_family("asset", list_resp, mutation_response=mut)
    assert out["result"]["succeeded"] == 0
    assert len(out["result"]["failures"]) == 1
    assert "asset/a" in out["result"]["failures"][0]
    assert "500" in out["result"]["failures"][0]


def test_purgeFamily_marks_fatal_on_401_list() -> None:
    list_resp = "{ ok: false, status: 401, text: async () => '' }"
    out = _purge_family("asset", list_resp)
    assert out["result"]["fatal"] is True
    assert out["result"]["error"] == "list 401"


def test_purgeFamily_uses_cancel_for_orders() -> None:
    list_resp = (
        "{ ok: true, status: 200, "
        "json: async () => ({ results: ["
        "  { id: 'o1', name: 'e2e-x', created_at: '2026-04-25T10:00:00Z', status: 'PENDING' }"
        "]}), text: async () => '' }"
    )
    mut = "{ ok: true, status: 200, text: async () => '' }"
    out = _purge_family("order", list_resp, mutation_response=mut)
    # Last fetch call should be POST /marketplace/orders/o1/cancel/
    delete_call = out["fetchCalls"][-1]
    assert delete_call["method"] == "POST"
    assert "/marketplace/orders/o1/cancel/" in delete_call["url"]
