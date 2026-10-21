"""W11.11 (oss-release-remediation) — authenticated ZAP DAST delta gate pins.

TDD pins for the W11.11 machinery, Django-free and mock-free:

* ``scripts/check_zap_delta.py`` (GATE-64) — the delta checker: a ZAP
  ``-J`` JSON report compared against a committed baseline must contain
  ZERO new HIGH alerts (new = a (pluginid, normalized-URI) pair at HIGH
  risk that the baseline does not carry at HIGH risk).  Risk escalation
  (MEDIUM/LOW → HIGH on the same pair) also fails — the gate must never
  hide a worsening.
* ``scripts/zap/w1111_role_matrix.json`` — the single DAST surface
  manifest (public + one entry per authenticated role); the GitHub
  workflow matrix must agree with it.
* ``scripts/zap/w1111_zap_auth_config.py`` — real-HTTP login against the
  API's login endpoint that emits ZAP ``-config`` replacer arguments
  (Authorization bearer injection) and never prints credentials; plus
  the post-scan secret-verification mode (a report containing the
  minted token must fail).
* ``.github/workflows/phase232-public-zap-baseline.yml`` — the extended
  workflow (per-role authenticated scans + the blocking delta gate).

Every test drives the REAL artifacts via subprocess (the checker and
auth script are executed, not imported), real files in a real tmpdir,
and real loopback HTTP servers for the login contract — no mocks.
"""

from __future__ import annotations

import http.server
import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "scripts" / "check_zap_delta.py"
AUTH_SCRIPT = ROOT / "scripts" / "zap" / "w1111_zap_auth_config.py"
MANIFEST = ROOT / "scripts" / "zap" / "w1111_role_matrix.json"
WORKFLOW = ROOT / ".github" / "workflows" / "phase232-public-zap-baseline.yml"
BASELINE_DIR = ROOT / "docs" / "security" / "zap" / "baselines"


# ── ZAP -J report builders (the real wire shape) ──────────────────────────────


def _alert(
    pluginid: str,
    name: str,
    riskcode: str,
    riskdesc: str,
    uris: list[str],
    method: str = "GET",
) -> dict:
    return {
        "pluginid": pluginid,
        "alertRef": pluginid,
        "name": name,
        "riskcode": riskcode,
        "confidence": "2",
        "riskdesc": riskdesc,
        "desc": f"{name} description",
        "instances": [
            {"uri": uri, "method": method, "param": "", "attack": "", "evidence": "ev"}
            for uri in uris
        ],
        "count": str(len(uris)),
    }


def _report(site: str, alerts: list[dict]) -> dict:
    return {
        "@version": "2.16.1",
        "@generated": "test",
        "site": [
            {
                "@name": site,
                "@host": "staging.example.com",
                "@port": "443",
                "@ssl": "true",
                "alerts": alerts,
            }
        ],
    }


SITE = "https://staging.example.com"
HIGH = "3"
MEDIUM = "2"
LOW = "1"


def _write(tmp_path: Path, name: str, payload: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload))
    return path


def _run_checker(*args: str) -> subprocess.CompletedProcess:
    # A missing artifact must FAIL the pin, not pass it — python exits 2
    # on a missing script path, which would vacuously satisfy the
    # typed-error pins.
    assert CHECKER.is_file(), "check_zap_delta.py missing"
    return subprocess.run(
        [sys.executable, str(CHECKER), *args],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


# ── Delta semantics ───────────────────────────────────────────────────────────


def test_delta_identical_scan_is_green(tmp_path):
    alerts = [
        _alert("10096", "Timestamp Disclosure", HIGH, "High (Medium)", [f"{SITE}/api/v1/assets/"])
    ]
    scan = _write(tmp_path, "scan.json", _report(SITE, alerts))
    baseline = _write(tmp_path, "baseline.json", _report(SITE, alerts))
    report = tmp_path / "delta.json"

    proc = _run_checker(
        "--scan", str(scan), "--baseline", str(baseline), "--report", str(report), "--ci"
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(report.read_text())
    assert payload["verdict"] == "PASS"
    assert payload["new_highs"] == []
    assert payload["escalated"] == []


def test_new_high_alert_flips_red_and_names_it(tmp_path):
    baseline = _write(
        tmp_path,
        "baseline.json",
        _report(
            SITE,
            [
                _alert(
                    "10096", "Timestamp Disclosure", LOW, "Low (Medium)", [f"{SITE}/api/v1/assets/"]
                )
            ],
        ),
    )
    scan = _write(
        tmp_path,
        "scan.json",
        _report(
            SITE,
            [
                _alert(
                    "10096", "Timestamp Disclosure", LOW, "Low (Medium)", [f"{SITE}/api/v1/assets/"]
                ),
                _alert(
                    "40012",
                    "Cross Site Scripting (Reflected)",
                    HIGH,
                    "High (Medium)",
                    [f"{SITE}/api/v1/search/?q=1"],
                ),
            ],
        ),
    )
    report = tmp_path / "delta.json"

    proc = _run_checker(
        "--scan", str(scan), "--baseline", str(baseline), "--report", str(report), "--ci"
    )

    assert proc.returncode == 1, proc.stdout
    payload = json.loads(report.read_text())
    assert payload["verdict"] == "FAIL"
    assert [h["pluginid"] for h in payload["new_highs"]] == ["40012"]
    assert payload["new_highs"][0]["name"] == "Cross Site Scripting (Reflected)"
    assert "40012" in proc.stdout  # the gate names the new high


def test_risk_escalation_medium_to_high_flips_red(tmp_path):
    uri = f"{SITE}/api/v1/contracts/"
    baseline = _write(
        tmp_path,
        "baseline.json",
        _report(SITE, [_alert("10020", "SQL Injection", MEDIUM, "Medium (Medium)", [uri])]),
    )
    scan = _write(
        tmp_path,
        "scan.json",
        _report(SITE, [_alert("10020", "SQL Injection", HIGH, "High (Medium)", [uri])]),
    )
    report = tmp_path / "delta.json"

    proc = _run_checker(
        "--scan", str(scan), "--baseline", str(baseline), "--report", str(report), "--ci"
    )

    assert proc.returncode == 1, proc.stdout
    payload = json.loads(report.read_text())
    assert payload["verdict"] == "FAIL"
    assert payload["new_highs"] == []
    assert [e["pluginid"] for e in payload["escalated"]] == ["10020"]


def test_new_medium_and_low_stay_green_but_are_reported(tmp_path):
    baseline = _write(tmp_path, "baseline.json", _report(SITE, []))
    scan = _write(
        tmp_path,
        "scan.json",
        _report(
            SITE,
            [
                _alert(
                    "10096", "Timestamp Disclosure", LOW, "Low (Medium)", [f"{SITE}/api/v1/assets/"]
                ),
                _alert(
                    "10021",
                    "X-Frame-Options Header Not Set",
                    MEDIUM,
                    "Medium (Medium)",
                    [f"{SITE}/api/v1/"],
                ),
            ],
        ),
    )
    report = tmp_path / "delta.json"

    proc = _run_checker(
        "--scan", str(scan), "--baseline", str(baseline), "--report", str(report), "--ci"
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(report.read_text())
    assert payload["verdict"] == "PASS"
    assert payload["new_medium_low_count"] == 2


def test_resolved_high_is_reported_as_improvement(tmp_path):
    uri = f"{SITE}/api/v1/files/"
    baseline = _write(
        tmp_path,
        "baseline.json",
        _report(SITE, [_alert("10017", "Cross-domain", HIGH, "High (Medium)", [uri])]),
    )
    scan = _write(tmp_path, "scan.json", _report(SITE, []))
    report = tmp_path / "delta.json"

    proc = _run_checker(
        "--scan", str(scan), "--baseline", str(baseline), "--report", str(report), "--ci"
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(report.read_text())
    assert payload["verdict"] == "PASS"
    assert payload["resolved_high_count"] == 1


def test_url_normalization_trailing_slash_and_fragment_are_identity(tmp_path):
    # The same endpoint reported with/without a trailing slash (and a
    # fragment that never travels on the wire) must NOT count as new.
    baseline = _write(
        tmp_path,
        "baseline.json",
        _report(
            SITE,
            [
                _alert(
                    "10096",
                    "Timestamp Disclosure",
                    HIGH,
                    "High (Medium)",
                    [f"{SITE}/api/v1/assets/"],
                )
            ],
        ),
    )
    scan = _write(
        tmp_path,
        "scan.json",
        _report(
            SITE,
            [
                _alert(
                    "10096",
                    "Timestamp Disclosure",
                    HIGH,
                    "High (Medium)",
                    [f"{SITE}/api/v1/assets#frag"],
                )
            ],
        ),
    )
    report = tmp_path / "delta.json"

    proc = _run_checker(
        "--scan", str(scan), "--baseline", str(baseline), "--report", str(report), "--ci"
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(report.read_text())
    assert payload["new_highs"] == []


def test_distinct_query_values_are_distinct_identities(tmp_path):
    # Conservative matching: the same endpoint with a different query
    # value is a DIFFERENT identity — the gate must never hide a new
    # high by over-merging.
    baseline = _write(
        tmp_path,
        "baseline.json",
        _report(
            SITE, [_alert("40012", "XSS", HIGH, "High (Medium)", [f"{SITE}/api/v1/search/?q=abc"])]
        ),
    )
    scan = _write(
        tmp_path,
        "scan.json",
        _report(
            SITE, [_alert("40012", "XSS", HIGH, "High (Medium)", [f"{SITE}/api/v1/search/?q=zzz"])]
        ),
    )
    report = tmp_path / "delta.json"

    proc = _run_checker(
        "--scan", str(scan), "--baseline", str(baseline), "--report", str(report), "--ci"
    )

    assert proc.returncode == 1, proc.stdout


def test_malformed_scan_json_is_a_typed_usage_error(tmp_path):
    baseline = _write(tmp_path, "baseline.json", _report(SITE, []))
    scan = tmp_path / "scan.json"
    scan.write_text("{not json")

    proc = _run_checker("--scan", str(scan), "--baseline", str(baseline))

    assert proc.returncode == 2, proc.stdout
    assert "scan" in proc.stderr.lower()


def test_missing_site_key_is_a_typed_usage_error(tmp_path):
    baseline = _write(tmp_path, "baseline.json", _report(SITE, []))
    scan = tmp_path / "scan.json"
    scan.write_text(json.dumps({"@version": "2.16.1"}))

    proc = _run_checker("--scan", str(scan), "--baseline", str(baseline))

    assert proc.returncode == 2, proc.stdout


def test_alert_without_instances_uses_site_identity(tmp_path):
    alert = _alert("10021", "X-Frame-Options Header Not Set", HIGH, "High (Medium)", [f"{SITE}/"])
    alert.pop("instances")  # ZAP emits site-level alerts without instances
    baseline = _write(tmp_path, "baseline.json", _report(SITE, [alert]))
    scan = _write(tmp_path, "scan.json", _report(SITE, [alert]))
    report = tmp_path / "delta.json"

    proc = _run_checker(
        "--scan", str(scan), "--baseline", str(baseline), "--report", str(report), "--ci"
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(report.read_text())
    assert payload["new_highs"] == []


# ── Baselines + role matrix + workflow agreement ──────────────────────────────


def test_committed_role_matrix_is_well_formed():
    payload = json.loads(MANIFEST.read_text())
    assert payload["version"] >= 1
    assert "target_suffix" in payload
    surfaces = payload["surfaces"]
    assert any(s["authenticated"] is False for s in surfaces), "public surface required"
    auth_roles = [s["key"] for s in surfaces if s["authenticated"]]
    assert auth_roles, "authenticated role surfaces required"
    for s in surfaces:
        assert s["baseline"].endswith(".json")
        assert s["report_file"].endswith(".json")
        assert s["description"]


def test_every_manifest_baseline_exists_and_parses(tmp_path):
    payload = json.loads(MANIFEST.read_text())
    for surface in payload["surfaces"]:
        path = BASELINE_DIR / surface["baseline"]
        assert path.is_file(), f"baseline missing: {path}"
        data = json.loads(path.read_text())
        assert "site" in data, f"baseline has no site key: {path}"


def test_verify_baselines_mode_flags_an_invalid_baseline(tmp_path):
    proc = _run_checker("--verify-baselines")
    assert proc.returncode == 0, proc.stderr

    # Plant an invalid baseline copy and point the manifest at it via a
    # scratch manifest — the checker takes --manifest for testability.
    broken = tmp_path / "broken.json"
    broken.write_text("{broken")
    payload = json.loads(MANIFEST.read_text())
    payload["surfaces"][0]["baseline"] = str(broken)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(payload))

    proc = _run_checker("--verify-baselines", "--manifest", str(manifest))
    assert proc.returncode == 1, proc.stdout


def test_workflow_matrix_agrees_with_manifest_roles():
    workflow_text = WORKFLOW.read_text()
    manifest = json.loads(MANIFEST.read_text())
    auth_roles = sorted(s["key"] for s in manifest["surfaces"] if s["authenticated"])

    # The workflow matrix block must carry exactly the manifest roles.
    matrix_block = re.search(r"role:\s*\[(.*?)\]", workflow_text, re.DOTALL)
    assert matrix_block, "no `role: [...]` matrix in the workflow"
    roles = sorted(re.findall(r"[A-Z_]+", matrix_block.group(1)))
    assert roles == auth_roles, f"workflow matrix {roles} != manifest {auth_roles}"


def test_workflow_carries_the_full_dast_contract():
    text = WORKFLOW.read_text()

    assert "DORMANT" not in text, "the phase-232 dormancy header must be gone (W11.11 reactivates)"
    assert "action-baseline@v0.12.0" in text, "the public job keeps the pinned baseline action"
    assert "zap.sh" in text
    assert "-autorun" in text, "role scans run the automation plan"
    assert "openapi.json" in text, "role scans import the live OpenAPI spec"
    assert "w1111_reduce_spec.py" in text, "the spec is reduced before import (importer cannot finish on the full spec)"
    assert "zaproxy/zap-stable" in text, "role scans use the same image the action pins"
    assert "-configfile" in text, "the replacer config reaches ZAP via -configfile"
    assert "-port 18080" in text, "the scan proxy avoids the host's traefik 8080"
    assert "targetUrl: $DAST_TARGET\n" in text, (
        "the openapi target is the ORIGIN — the spec's paths are absolute "
        "(/api/v1/...) and a prefixed target doubles every scanned URL"
    )
    assert "timeout 3900 docker run" in text, (
        "the scan is timeout-capped with enough headroom for import + "
        "active scan + report (the 1800s draft killed scans mid-active)"
    )
    assert "maxScanDurationInMins" in text, (
        "the active scan is time-capped (the unrecognized maxDuration param "
        "left it unbounded — the 3-hour hang the first plan run exposed)"
    )
    assert "maxDuration: 30" not in text, (
        "the activeScan's unrecognized maxDuration param must be gone "
        "(passiveScan-wait's maxDuration IS the valid parameter there)"
    )
    assert "w1111_zap_auth_config.py" in text, "login + replacer config come from the auth script"
    assert "-J" in text, "machine-readable JSON reports are produced"
    assert "check_zap_delta.py" in text or "w1111_delta_run.py" in text, (
        "the delta gate job runs the checker via the runner"
    )
    assert "w1111-replacer.properties" in text, (
        "the login step's replacer properties are written for the scan"
    )
    assert "login-config" in text
    assert "--password-env DAST_PASSWORD" in text, (
        "credentials reach the login step only via the environment"
    )
    assert "w1111_role_matrix.json" in text or "docs/security/zap/baselines/" in text, (
        "delta compares against committed baselines"
    )
    # The runner (driven by the workflow) runs the checker in --ci mode
    # — the gate must never run in a warn-only shape.
    runner = (ROOT / "scripts" / "zap" / "w1111_delta_run.py").read_text()
    assert "--ci" in runner
    assert "check_zap_delta.py" in runner
    # Never a silent skip: missing secrets must fail the job loudly.
    assert "missing" in text, "the secret guard must name missing secrets"
    # Least privilege preserved from the original workflow.
    assert "contents: read" in text
    perms = re.findall(r"permissions:\s*\n(?:\s+[a-z-]+:\s+[a-z-]+\s*\n?)+", text)
    assert all("write" not in block for block in perms), "no write permissions anywhere"


def test_quality_gates_wire_the_delta_baseline_verification():
    makefile = (ROOT / "Makefile").read_text()
    assert "scripts/check_zap_delta.py --verify-baselines" in makefile, (
        "GATE-64 must run in quality-gates"
    )


def test_makefile_exposes_the_local_dast_runner():
    makefile = (ROOT / "Makefile").read_text()
    assert "dast-local:" in makefile, "make dast-local must exist (runbook entry point)"
    assert "scripts/zap/w1111_dast_local.sh" in makefile, "the local runner is wired into the Makefile"
    runner = (ROOT / "scripts" / "zap" / "w1111_dast_local.sh").read_text()
    # G12: never a committed password fallback — the runner requires the
    # operator to supply credentials at runtime.
    assert "DAST_LOCAL_PASSWORD" in runner
    assert "w1111_zap_auth_config.py" in runner, "local scans reuse the CI auth script"
    assert "openapi.json" in runner, "local role scans are OpenAPI-driven (coverage)"
    assert "zap.sh" in runner, "the local runner and the CI workflow share the invocation"


def test_runbook_documents_the_dast_operating_contract():
    runbook = (ROOT / "docs" / "runbooks" / "w1111-dast-zap.md").read_text()
    assert "DAST_<ROLE>_USERNAME" in runbook, "provisioning contract documented"
    assert "check_zap_delta.py" in runbook, "the gate is documented"
    assert "re-baseline" in runbook or "rebaseline" in runbook, "triage + re-baseline process documented"


def test_email_settings_mirror_smtp_into_email_vars():
    # W11.11 live-bring-up root fix: Django 6.1's get_connection() reads
    # the EMAIL_* settings — the MAILERS dict is NOT consulted, so the
    # staging send_mail path refused every connection while MAILERS named
    # the mailhog relay. The runtime branch must mirror SMTP_* into
    # EMAIL_*; the test-runner branch must keep the locmem mailer.
    settings = (ROOT / "hub" / "settings.py").read_text()
    assert "EMAIL_HOST = SMTP_HOST" in settings
    assert "EMAIL_PORT = SMTP_PORT" in settings
    assert "EMAIL_USE_TLS = SMTP_USE_TLS" in settings
    # The mirror lives in the NON-locmem branch (below the if/else split).
    assert "_use_locmem_mailer" in settings, "the mirror is runtime-only"
    assert settings.index("locmem.EmailBackend") < settings.index("EMAIL_HOST = SMTP_HOST")


def test_delta_runner_flags_missing_reports_and_baselines(tmp_path):
    """The workflow's orchestrator must FAIL (never skip) on a missing
    report or a missing baseline, with verdicts the ledger can record."""
    import subprocess

    runner = ROOT / "scripts" / "zap" / "w1111_delta_run.py"
    assert runner.is_file(), "w1111_delta_run.py missing"

    # A scan report present but NO baseline → NO_BASELINE verdict + exit 1.
    # (Point at an EMPTY baseline dir — the repo's real baselines exist.)
    empty_baselines = tmp_path / "no-baselines"
    empty_baselines.mkdir()
    _write(tmp_path, "w1111-auth-AUDITOR.json", _report(SITE, []))
    proc = subprocess.run(
        [
            sys.executable, str(runner),
            "--input-dir", str(tmp_path),
            "--out-dir", str(tmp_path / "out"),
            "--baseline-dir", str(empty_baselines),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1, proc.stdout
    row = json.loads((tmp_path / "out" / "ledger-row.json").read_text())
    verdicts = {k: v["verdict"] for k, v in row["surfaces"].items()}
    assert verdicts.get("AUDITOR") == "NO_BASELINE"
    assert any(v == "MISSING" for v in verdicts.values())

    # Baseline + scan both present → the checker runs and the verdict is
    # recorded (no new highs on identical content → PASS).
    baseline_dir = tmp_path / "baselines"
    baseline_dir.mkdir()
    _write(baseline_dir, "w1111-auth-AUDITOR-baseline.json", _report(SITE, []))
    manifest = json.loads(MANIFEST.read_text())
    manifest["surfaces"] = [
        s for s in manifest["surfaces"] if s["key"] == "AUDITOR"
    ]
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    proc = subprocess.run(
        [
            sys.executable,
            str(runner),
            "--input-dir",
            str(tmp_path),
            "--out-dir",
            str(tmp_path / "out2"),
            "--manifest",
            str(manifest_path),
            "--baseline-dir",
            str(baseline_dir),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    row = json.loads((tmp_path / "out2" / "ledger-row.json").read_text())
    assert row["outcome"] == "PASS"


def test_reduce_spec_preserves_structure_and_resolves_refs(tmp_path):
    """The live OpenAPI spec is too large for ZAP's importer to finish
    (11.7 MB — the first import ran 10+ minutes without completing, so
    the plan-driven scan needs a reduced spec). The reducer must be
    STRUCTURALLY IDENTITY-PRESERVING: same paths/methods/parameters/
    requestBodies, every $ref still resolving, all description/example
    noise gone, and the result a fraction of the size — anything less
    changes what the scan covers."""
    import subprocess

    reducer = ROOT / "scripts" / "zap" / "w1111_reduce_spec.py"
    assert reducer.is_file(), "w1111_reduce_spec.py missing"

    # Build a representative spec with description noise + a $ref chain.
    src = {
        "openapi": "3.0.2",
        "info": {"title": "t", "version": "1", "description": "noise" * 500},
        "paths": {
            "/api/v1/assets/": {
                "get": {
                    "description": "noise" * 500,
                    "parameters": [
                        {"name": "q", "in": "query", "description": "noise" * 500, "schema": {"type": "string"}}
                    ],
                    "responses": {"200": {"description": "ok"}},
                },
                "post": {
                    "requestBody": {
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Asset"}}}
                    },
                    "responses": {"201": {"description": "ok"}},
                },
            }
        },
        "servers": [{"url": "/api/v1", "description": "noise"}],
        "components": {
            "schemas": {
                "Asset": {
                    "type": "object",
                    "description": "noise" * 500,
                    "properties": {"name": {"type": "string", "description": "noise" * 500}},
                }
            }
        },
    }
    src_path = tmp_path / "spec.json"
    src_path.write_text(json.dumps(src))
    out = tmp_path / "reduced.json"
    proc = subprocess.run(
        [sys.executable, str(reducer), "--input", str(src_path), "--output", str(out)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    reduced = json.loads(out.read_text())

    # Structure identity.
    assert set(reduced["paths"]) == set(src["paths"])
    for path, ops in src["paths"].items():
        assert set(reduced["paths"][path]) == set(ops)
        for method, op in ops.items():
            r_op = reduced["paths"][path][method]
            assert [p["name"] for p in r_op.get("parameters", [])] == [
                p["name"] for p in op.get("parameters", [])
            ]
            assert ("requestBody" in r_op) == ("requestBody" in op)

    # Every $ref resolves inside the reduced spec.
    def refs(node, acc):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "$ref" and isinstance(v, str):
                    acc.append(v)
                refs(v, acc)
        elif isinstance(node, list):
            for v in node:
                refs(v, acc)

    found = []
    refs(reduced, found)
    assert found, "the fixture must exercise a $ref"
    for ref in found:
        assert ref.startswith("#/components/schemas/"), ref
        name = ref.rsplit("/", 1)[1]
        assert name in reduced["components"]["schemas"], ref

    # Noise gone (the only surviving `description` keys are the OpenAPI-
    # REQUIRED info/responses ones, emptied), size shrank.
    blob = json.dumps(reduced)

    def descriptions(node, acc):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "description":
                    acc.append(v)
                descriptions(v, acc)
        elif isinstance(node, list):
            for v in node:
                descriptions(v, acc)

    descs = []
    descriptions(reduced, descs)
    assert descs, "the fixture must exercise a required description"
    assert all(d == "" for d in descs), "only emptied required descriptions"
    # The REQUIRED response descriptions survive as empty strings.
    for path, ops in reduced["paths"].items():
        for op in ops.values():
            for code, resp in op.get("responses", {}).items():
                assert "description" in resp, (
                    f"{path} {code}: response description must survive (required)"
                )
                assert resp["description"] == ""
    assert "example" not in blob
    # The servers block is dropped: its relative /api/v1 path doubles
    # against the targetUrl at import time (every URL scanned 404'd).
    assert "servers" not in reduced
    assert len(blob) < len(json.dumps(src)) * 0.3


def test_reduce_spec_drops_31_style_schema_content_keeps_media_content(tmp_path):
    """drf-spectacular emits OpenAPI 3.1 `schema.content` inside the 3.0
    spec — the strict importer rejects it (`attribute ...schema.content
    is unexpected`, seen live on the staging spec). The reducer drops it
    from schema objects while KEEPING media-type `content` on
    requestBody/response objects (that is real structure)."""
    import subprocess

    reducer = ROOT / "scripts" / "zap" / "w1111_reduce_spec.py"
    src = {
        "openapi": "3.0.2",
        "info": {"title": "t", "version": "1", "description": ""},
        "paths": {
            "/x/": {
                "get": {
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "content": {"application/json": {}},
                                    }
                                }
                            },
                        }
                    }
                }
            }
        },
    }
    src_path = tmp_path / "spec.json"
    src_path.write_text(json.dumps(src))
    out = tmp_path / "reduced.json"
    proc = subprocess.run(
        [sys.executable, str(reducer), "--input", str(src_path), "--output", str(out)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    reduced = json.loads(out.read_text())
    media_content = reduced["paths"]["/x/"]["get"]["responses"]["200"]["content"]
    assert "application/json" in media_content, "media-type content must survive"
    schema = media_content["application/json"]["schema"]
    assert "content" not in schema, "schema.content must be dropped"


def test_no_unguarded_int_query_param_casts_remain():
    """The DAST SQL-Injection HIGH class root cause: unvalidated
    ``int(request.query_params.get(...))`` casts 500'd on fuzzed params
    (governance/expiring, observability/pipelines — RED-proven live).
    The canonical helper is hub/apps/core/query_params.py; the only
    surviving raw casts are the two datasets sites that are ALREADY
    guarded by their own try/except (falls back to a safe default)."""
    import subprocess

    hub = ROOT / "hub"
    proc = subprocess.run(
        ["grep", "-rn", "int(request.query_params.get(", str(hub)],
        capture_output=True,
        text=True,
        check=False,
    )
    lines = [
        raw_line
        for raw_line in proc.stdout.splitlines()
        if "/tests/" not in raw_line and "query_params.py" not in raw_line
    ]
    # The only acceptable sites: guarded by an immediately preceding
    # try/except in datasets/views.py. (grep emits absolute paths —
    # normalize to the repo-relative form.)
    allowed = {"hub/apps/datasets/views.py:552", "hub/apps/datasets/views.py:1609"}
    offenders = []
    for raw_line in lines:
        rel = raw_line.replace(str(ROOT) + "/", "")
        path_lineno = rel.split(":")[0] + ":" + rel.split(":")[1]
        if path_lineno in allowed:
            continue
        offenders.append(rel)
    assert not offenders, f"unguarded int casts remain: {offenders}"


def test_files_search_fields_is_a_tuple_not_a_string():
    """W11.11 DAST finding: ``search_fields = "name"`` made DRF iterate
    the string's CHARACTERS as search fields — ``Cannot resolve keyword
    'n'`` 500 on fuzzed search terms. Must be a tuple/list."""
    views = (ROOT / "hub" / "apps" / "files" / "views.py").read_text()
    assert 'search_fields = ("name",)' in views
    assert 'search_fields = "name"' not in views


def test_falsifiability_harness_registers_the_delta_gate():
    verifier = (ROOT / "scripts" / "verify_gate_falsifiability.py").read_text()
    assert "gate-64-zap-delta" in verifier, (
        "convention 11: the new gate is falsifiability-registered"
    )
    assert "test_w1111_zap_delta.py" in verifier


# ── Auth config: real-HTTP login → ZAP replacer args ─────────────────────────


@pytest.fixture
def login_server():
    """A real loopback HTTP server implementing the API login contract."""
    state: dict = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):  # silence
            pass

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            state["body"] = body
            if body.get("email") == "ok@example.com" and body.get("password") == "secret-pw":
                payload = json.dumps(
                    {
                        "token_type": "Bearer",
                        "expires_in": 3600,
                        "access_token": "tok-abc-123",
                        "refresh_token": "rt-xyz",
                    }
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            else:
                payload = json.dumps({"email": "Invalid email or password"}).encode()
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    state["port"] = server.server_address[1]
    yield state
    server.shutdown()
    thread.join(timeout=5)


def _run_auth(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    assert AUTH_SCRIPT.is_file(), "w1111_zap_auth_config.py missing"
    full_env = dict(os.environ)
    full_env.pop("DAST_TEST_PASSWORD", None)
    if env:
        full_env.update(env)
    return subprocess.run(
        [sys.executable, str(AUTH_SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=60,
        env=full_env,
        check=False,
    )


def test_auth_login_emits_replacer_config_with_bearer_token(tmp_path, login_server):
    out = tmp_path / "zap-config.args"
    env = {"DAST_TEST_PASSWORD": "secret-pw"}
    proc = _run_auth(
        "login-config",
        "--target",
        f"http://127.0.0.1:{login_server['port']}",
        "--username",
        "ok@example.com",
        "--password-env",
        "DAST_TEST_PASSWORD",
        "--output",
        str(out),
        env=env,
    )

    assert proc.returncode == 0, proc.stderr
    args = out.read_text()
    assert "replacer.full_list(0).enabled=true" in args
    assert "replacer.full_list(0).matchtype=REQ_HEADER" in args
    assert "replacer.full_list(0).matchstr=Authorization" in args
    assert "replacer.full_list(0).replacement=Bearer tok-abc-123" in args
    assert login_server["body"] == {"email": "ok@example.com", "password": "secret-pw"}
    # The login request body must be JSON with the two fields only.
    assert "secret-pw" not in proc.stdout
    assert "secret-pw" not in proc.stderr


def test_auth_login_failure_never_prints_the_password(tmp_path, login_server):
    env = {"DAST_TEST_PASSWORD": "wrong-pw"}
    proc = _run_auth(
        "login-config",
        "--target",
        f"http://127.0.0.1:{login_server['port']}",
        "--username",
        "nope@example.com",
        "--password-env",
        "DAST_TEST_PASSWORD",
        "--output",
        str(tmp_path / "zap-config.args"),
        env=env,
    )

    assert proc.returncode == 2, proc.stdout
    assert "wrong-pw" not in proc.stdout
    assert "wrong-pw" not in proc.stderr


def test_cookie_auth_mode_extracts_bearer_from_set_cookie(tmp_path):
    """Staging runs USE_HTTPONLY_AUTH_COOKIES=true: the login body carries
    NO access_token — the token lives in the httpOnly Set-Cookie. The same
    JWT is valid in the Authorization header (JWTAuthentication checks
    Bearer first), so the auth script must extract it from Set-Cookie and
    emit the bearer replacer. Verified against the live staging stack
    (login returned {token_type, expires_in} only)."""

    class CookieLoginHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            payload = json.dumps({"token_type": "Bearer", "expires_in": 3600}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header(
                "Set-Cookie",
                "access_token=cookie-jwt-xyz; Path=/; HttpOnly; Secure; SameSite=Strict",
            )
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), CookieLoginHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        out = tmp_path / "zap-config.args"
        proc = _run_auth(
            "login-config",
            "--target",
            f"http://127.0.0.1:{server.server_address[1]}",
            "--username",
            "ok@example.com",
            "--password-env",
            "DAST_TEST_PASSWORD",
            "--output",
            str(out),
            env={"DAST_TEST_PASSWORD": "secret-pw"},
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert proc.returncode == 0, proc.stderr
    args = out.read_text()
    assert "replacer.full_list(0).replacement=Bearer cookie-jwt-xyz" in args
    assert "replacer.full_list(0).matchstr=Authorization" in args


def test_auth_login_missing_token_is_a_typed_error(tmp_path, login_server):
    # A 200 response WITHOUT an access_token (cookie-auth mode) must be
    # a typed error, not a silent empty-config success.
    class NoTokenHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            payload = json.dumps({"token_type": "Bearer", "expires_in": 3600}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), NoTokenHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        proc = _run_auth(
            "login-config",
            "--target",
            f"http://127.0.0.1:{server.server_address[1]}",
            "--username",
            "ok@example.com",
            "--password-env",
            "DAST_TEST_PASSWORD",
            "--output",
            str(tmp_path / "zap-config.args"),
            env={"DAST_TEST_PASSWORD": "secret-pw"},
        )
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert proc.returncode == 2, proc.stdout
    assert "access_token" in proc.stderr.lower()


def test_verify_report_flags_an_embedded_token(tmp_path):
    token = tmp_path / "dast.token"
    token.write_text("tok-abc-123")
    report = tmp_path / "zap.json"
    report.write_text(json.dumps(_report(SITE, [])))
    clean_proc = _run_auth("verify-report", "--report", str(report), "--token-file", str(token))
    assert clean_proc.returncode == 0, clean_proc.stderr

    report.write_text(json.dumps(_report(SITE, [])) + "\n")
    leaked = tmp_path / "zap-leak.json"
    leaked.write_text(
        json.dumps(
            {"site": [{"@name": SITE, "alerts": [], "_leak": "Authorization: Bearer tok-abc-123"}]}
        )
    )
    proc = _run_auth("verify-report", "--report", str(leaked), "--token-file", str(token))
    assert proc.returncode == 1, proc.stdout
    assert "token" in proc.stderr.lower()


def test_auth_script_masks_token_for_github_actions(tmp_path, login_server):
    out = tmp_path / "zap-config.args"
    env = {"DAST_TEST_PASSWORD": "secret-pw", "GITHUB_ACTIONS": "true"}
    proc = _run_auth(
        "login-config",
        "--target",
        f"http://127.0.0.1:{login_server['port']}",
        "--username",
        "ok@example.com",
        "--password-env",
        "DAST_TEST_PASSWORD",
        "--output",
        str(out),
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    assert "::add-mask::tok-abc-123" in proc.stdout
