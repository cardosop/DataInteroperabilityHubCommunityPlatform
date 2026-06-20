"""
TDD unit tests for scripts/check_sparql_health.cjs — Phase 226 OQ2.

Exercises the pure helpers exposed by the script (buildProbeQuery,
validateAskResponse, parseArgs) via plain `node -e` evaluations. Avoids
spinning up a real HTTP server — the network call lives in `main()` and
is exercised end-to-end by the CI step that runs the script against staging.

Run locally:
    pytest scripts/tests/test_check_sparql_health.py -v
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_sparql_health.cjs"


def _has_node() -> bool:
    try:
        res = subprocess.run(["node", "--version"], check=False, capture_output=True, timeout=10)
        return res.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


pytestmark = pytest.mark.skipif(not _has_node(), reason="node not available")


def _eval_pure(js: str) -> str:
    """Run a tiny JS snippet that imports the script's pure exports and
    returns stdout. Avoids the network-bound `main()` path entirely.

    The script's CLI wrapper is kept side-effect-free at module-load
    (parseArgs returns a failure shape rather than exiting) precisely so
    `require()` here doesn't trigger a process.exit. If the script is
    ever changed to call process.exit at module scope, this helper will
    surface the regression as a clear node-eval failure.
    """
    src = (
        f"const m = require({json.dumps(str(SCRIPT))});process.stdout.write(JSON.stringify({js}));"
    )
    res = subprocess.run(
        ["node", "-e", src],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if res.returncode != 0:
        raise AssertionError(f"node eval failed: {res.stderr}")
    return res.stdout


def test_probe_query_is_a_minimal_sparql_ask() -> None:
    out = _eval_pure("m.buildProbeQuery()")
    query = json.loads(out)
    # ASK is the cheapest SPARQL form that still exercises parser +
    # dispatcher; it returns a single boolean rather than a result set.
    assert query.startswith("ASK")
    assert "{ ?s ?p ?o }" in query


def test_validate_ask_response_accepts_canonical_shape() -> None:
    out = _eval_pure('m.validateAskResponse({ "head": {}, "boolean": true })')
    assert json.loads(out) == {"ok": True}


def test_validate_ask_response_rejects_select_result_shape() -> None:
    # SELECT-style binding result must NOT be misread as an ASK result.
    out = _eval_pure(
        'm.validateAskResponse({ "head": { "vars": ["s"] }, "results": { "bindings": [] } })'
    )
    parsed = json.loads(out)
    assert parsed["ok"] is False
    assert "boolean" in parsed["reason"]


def test_validate_ask_response_rejects_html_body() -> None:
    # E.g. an upstream proxy returning a 200 HTML maintenance page; the
    # JSON parse would have failed earlier, but the helper is still safe.
    out = _eval_pure("m.validateAskResponse(null)")
    parsed = json.loads(out)
    assert parsed["ok"] is False


def test_validate_ask_response_rejects_non_boolean_field() -> None:
    out = _eval_pure('m.validateAskResponse({ "boolean": "true" })')
    parsed = json.loads(out)
    assert parsed["ok"] is False


def test_cli_requires_base_url() -> None:
    res = subprocess.run(
        ["node", str(SCRIPT)],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert res.returncode == 2
    assert "--base-url" in res.stderr


def test_cli_rejects_unknown_arg() -> None:
    res = subprocess.run(
        ["node", str(SCRIPT), "--bogus"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert res.returncode == 2
    assert "unknown argument" in res.stderr


def test_cli_rejects_invalid_timeout() -> None:
    res = subprocess.run(
        ["node", str(SCRIPT), "--base-url=http://x", "--timeout-ms=-1"],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert res.returncode == 2
