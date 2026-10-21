#!/usr/bin/env python3
"""Phase Q.5 — gate falsifiability harness + registry.

A check that cannot fail is indistinguishable from a check that passes
(Phase 1.1 shipped four of them; CI shipped more). This harness runs a
TARGET check under a set of WEAKENINGS — each weakening must change the
result — and reports VACUOUS when a weakening survives.

Two weakening styles, per gate:

* SELF-MUTATION — for gates with their own pytest suite: the weakening
  mutates the GATE SCRIPT itself and the suite must fail (≥1 named test).
* OFFENDER-INJECTION — for bare scan gates: the weakening injects a real
  offender pattern into a real scanned file (``hub/tests/
  gate_falsifiability_probe.py``), the gate is re-run scoped to that file,
  and its exit code must flip 0 -> 1.

Q.5.2 extended this with the ``GATES`` registry + ``--gate`` / ``--audit``
modes so EVERY wired gate is audited, and made outcomes exit-code-aware:
script gates report no pytest summary line, so comparing summaries alone
would call a failing gate VACUOUS.

Usage:
    python scripts/verify_gate_falsifiability.py --gate gate-01-assert-true-true
    python scripts/verify_gate_falsifiability.py --audit   # every gate, table
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
# The probe lives in its OWN directory so dir-walking scan gates can be
# scoped to it (os.walk on a file path yields nothing — the Q.5.2 trap).
PROBE_DIR = str(REPO_ROOT / "hub" / "apps" / "core" / "tests" / "falsifiability_probe")
PROBE = str(
    REPO_ROOT / "hub" / "apps" / "core" / "tests" / "falsifiability_probe" / "test_gate_probe.py"
)

# Interpreter for checker commands: the canonical venv when present (this
# host has no bare `python` on PATH — the Q.5.1 trap), else python3/python.
_VENV_PYTHON = REPO_ROOT / "venv" / "bin" / "python"
PYTHON = (
    str(_VENV_PYTHON)
    if _VENV_PYTHON.exists()
    else ("python3" if shutil.which("python3") else "python")
)

# gate -> (checker command, mutation target, [(label, mutation command)])
# {target} is substituted in checker + mutation commands.
GATES: dict[str, tuple[str, str, list[tuple[str, str]]]] = {
    # ── Scan gates: offender-injection into the shared probe file ───────
    "gate-01-assert-true-true": (
        "{python} scripts/check_assert_true_true.py",
        PROBE,
        [
            (
                "inject-assertTrue(True)",
                "printf '\\n\\n    def test_probe_offender(self):\\n"
                "        self.assertTrue(True)\\n' >> {target}",
            ),
        ],
    ),
    "gate-02-unused-assert-raises": (
        "{python} scripts/check_unused_assert_raises.py --path hub/apps/core/tests/falsifiability_probe",
        PROBE,
        [
            (
                "inject-unused-cm",
                "printf '\\n\\n    def test_probe_unused_context(self):\\n"
                "        with self.assertRaises(ValueError) as cm:\\n"
                '            raise ValueError("probe")\\n\' >> {target}',
            ),
        ],
    ),
    "gate-03-broad-status-codes": (
        "{python} scripts/check_broad_status_codes.py --path hub/apps/core/tests/falsifiability_probe",
        PROBE,
        [
            (
                "inject-broad-status-list",
                "printf '\\n\\n    def test_probe_broad_statuses(self):\\n"
                '        response = type("R", (), {"status_code": 200})()\\n'
                "        self.assertIn(response.status_code, [200, 201, 400, 403, 404, 500, 503])\\n' >> {target}",
            ),
        ],
    ),
    "gate-05-time-sleep": (
        "{python} scripts/check_time_sleep_in_tests.py --max-allowed 0 --path hub/apps/core/tests/falsifiability_probe",
        PROBE,
        [
            (
                "inject-time-sleep",
                "printf '\\n\\n    def test_probe_sleeps(self):\\n"
                "        import time\\n        time.sleep(0.01)\\n' >> {target}",
            ),
        ],
    ),
    "gate-06-no-reverse-match": (
        "{python} scripts/check_no_reverse_match.py --path hub/apps/core/tests/falsifiability_probe",
        PROBE,
        [
            (
                "inject-noreversematch-handler",
                "printf '\\n\\n    def test_probe_reverse(self):\\n"
                "        try:\\n"
                "            self.assertEqual(1, 1)\\n"
                "        except NoReverseMatch:\\n"
                "            pass\\n' >> {target}",
            ),
        ],
    ),
    "gate-07-skip-in-body": (
        "{python} scripts/check_pytest_skip_in_body.py --path hub/apps/core/tests/falsifiability_probe",
        PROBE,
        [
            (
                "inject-skip-in-body",
                "printf '\\n\\n    def test_probe_skip_in_body(self):\\n"
                "        import pytest\\n"
                '        pytest.skip("probe")\\n\' >> {target}',
            ),
        ],
    ),
    "gate-08-empty-test-methods": (
        "{python} scripts/check_empty_test_methods.py --path hub/apps/core/tests/falsifiability_probe",
        PROBE,
        [
            (
                "inject-empty-test",
                "printf '\\n\\n    def test_probe_empty(self):\\n"
                '        """Docstring only — no meaningful body."""\\n\' >> {target}',
            ),
        ],
    ),
    "gate-09-bare-assert-called": (
        "{python} scripts/check_bare_assert_called.py --path hub/apps/core/tests/falsifiability_probe",
        PROBE,
        [
            (
                "inject-bare-assert-called",
                "printf '\\n\\n    def test_probe_bare_assert_called(self):\\n"
                "        from unittest import mock\\n"
                "        m = mock.Mock()\\n"
                "        m()\\n"
                "        m.assert_called()\\n' >> {target}",
            ),
        ],
    ),
    # ── Registry/flag gates: mutate the feature-flag registry ──────────
    "gate-23-stale-defaults": (
        "{python} scripts/check_stale_defaults.py",
        "hub/apps/tenants/feature_flag_registry.py",
        [
            (
                "inject-unjustified-ga-default-off",
                '{python} -c "\n'
                "import pathlib\n"
                "p = pathlib.Path('{target}')\n"
                "lines = p.read_text().splitlines()\n"
                "idx = max(i for i, l in enumerate(lines) if l.strip() == ']')\n"
                "flag = [\n"
                "    '    FeatureFlag(',\n"
                "    '        name=\\\"falsifiability_probe_q5\\\",',\n"
                "    '        description=\\\"Probe flag without documentation\\\",',\n"
                "    '        owner_team=\\\"probe-team\\\",',\n"
                "    '        owner_email=\\\"probe@meshant.com\\\",',\n"
                "    '        created_at=_PHASE_240_INTRODUCED,',\n"
                "    '        stage=\\\"GA\\\",',\n"
                "    '        retire_by=datetime(2030, 1, 1, tzinfo=UTC),',\n"
                "    '        default_existing_tenants=True,',\n"
                "    '        default_new_tenants=False,',\n"
                "    '        related_phase=\\\"Phase Q.5.2\\\",',\n"
                "    '    ),',\n"
                "]\n"
                "lines[idx:idx] = flag\n"
                "p.write_text(chr(10).join(lines) + chr(10))\n"
                '"',
            ),
        ],
    ),
    # ── Doc-marker gates: strip a real CRITICAL marker from a real test ──
    "gate-26-journey-marker-coverage": (
        "{python} scripts/lint_journey_marker_coverage.py --blocking",
        "tests/e2e/test_authentication.py",
        [
            (
                "strip-critical-journey-marker",
                'sed -i \'s/journey("JOURNEY-AUTH-001")/journey("JOURNEY-AUTH-001-STRIPPED")/\' {target}',
            ),
        ],
    ),
    "gate-27-journey-doc-marker-sync": (
        "{python} scripts/check_doc_journey_marker_sync.py --ci-mode",
        "tests/e2e/test_authentication.py",
        [
            (
                "strip-critical-journey-marker",
                'sed -i \'s/journey("JOURNEY-AUTH-001")/journey("JOURNEY-AUTH-001-STRIPPED")/\' {target}',
            ),
        ],
    ),
    # ── Suite-backed gates: self-mutation must fail ≥1 named test ───────
    "gate-w113-idor-matrix-veracity": (
        "{python} -m pytest scripts/tests/test_w113_idor_matrix_veracity.py -p no:django -q -c /dev/null",
        "docs/api-audit/idor-probe-manifest.json",
        [
            (
                "flip-probe-to-reasonless-allowlist",
                'sed -i \'0,/"disposition": "probe"/s//"disposition": "allowlist"/\' {target}',
            ),
            (
                "forge-coverage-pct",
                'sed -i \'s/"coverage_pct": [0-9.]*/"coverage_pct": 50.0/\' {target}',
            ),
        ],
    ),
    "gate-29-core-boundary": (
        "{python} -m pytest scripts/tests/test_check_core_boundary_guards.py -p no:django -q -c /dev/null",
        "scripts/check_core_boundary.py",
        [
            (
                "rename-classifier-string",
                'sed -i \'s/"try-covered-BROKEN"/"try-covered"/g\' {target}',
            ),
        ],
    ),
    "gate-30-openspec-structural": (
        "{python} -m pytest scripts/tests/test_validate_openspec_change.py -p no:django -q -c /dev/null",
        "scripts/validate_openspec_change.py",
        [
            (
                "blind-missing-section-check",
                "sed -i 's/if section not in text:/if section not in text and False:/' {target}",
            ),
        ],
    ),
    "gate-31-access-request-order": (
        "{python} -m pytest scripts/tests/test_check_access_request_order_kwarg.py -p no:django -q -c /dev/null",
        "scripts/check_access_request_order_kwarg.py",
        [
            (
                "break-detected-kwarg",
                'sed -i \'s/_ORDER_KW = "order"/_ORDER_KW = "order-BROKEN"/\' {target}',
            ),
        ],
    ),
    "gate-32-core-e2e-selection": (
        "{python} -m pytest scripts/tests/test_check_core_e2e_selection.py -p no:django -q -c /dev/null",
        "scripts/check_core_e2e_selection.py",
        [
            (
                "rename-read-entries",
                "sed -i 's/def _read_entries(core_only_path/def _read_entries_disabled(core_only_path/' {target}",
            ),
        ],
    ),
    "gate-33-docs-references": (
        "{python} -m pytest scripts/tests/test_check_docs_references.py -p no:django -q -c /dev/null",
        "scripts/check_docs_references.py",
        [
            (
                "rename-looks-like-path",
                "sed -i 's/def _looks_like_path(ref/def _looks_like_path_disabled(ref/' {target}",
            ),
        ],
    ),
    "gate-34-config-single-source": (
        "{python} -m pytest scripts/tests/test_check_config_single_source.py -p no:django -q -c /dev/null",
        "scripts/check_config_single_source.py",
        [
            (
                "drop-tools-entry",
                'sed -i \'s/"ruff": {/"ruff-DISABLED": {/\' {target}',
            ),
        ],
    ),
    "gate-35-lint-debt-ratchet": (
        "{python} -m pytest scripts/tests/test_check_lint_debt_ratchet.py -p no:django -q -c /dev/null",
        "scripts/check_lint_debt_ratchet.py",
        [
            (
                "break-baseline-compare",
                "sed -i 's/count > baseline_count/count > baseline_count + 999999/' {target}",
            ),
        ],
    ),
    "q42-env-provisioning": (
        "{python} -m pytest scripts/tests/test_check_env_provisioning.py -p no:django -q -c /dev/null",
        "scripts/check_env_provisioning.py",
        [
            (
                "always-report-nothing-missing",
                "sed -i 's/    return missing$/    return {}/' {target}",
            ),
        ],
    ),
    "gate-36-mypy-ratchet": (
        "{python} -m pytest scripts/tests/test_check_mypy_debt_ratchet.py -p no:django -q -c /dev/null",
        "scripts/check_mypy_debt_ratchet.py",
        [
            (
                "blind-growth-comparison",
                "sed -i 's/if count > baseline_total:/if count > baseline_total + 999999:/' {target}",
            ),
        ],
    ),
    "gate-37-bandit-ratchet": (
        "{python} -m pytest scripts/tests/test_check_bandit_debt_ratchet.py -p no:django -q -c /dev/null",
        "scripts/check_bandit_debt_ratchet.py",
        [
            (
                "blind-growth-comparison",
                "sed -i 's/if count > baseline_total:/if count > baseline_total + 999999:/' {target}",
            ),
        ],
    ),
    # P.2b — paid AppConfig.ready() registrations pinned at source: a deleted
    # set_* call in a paid apps.py orphans a contract slot and silently
    # degrades full mode to the (partly fail-open) core fallback.
    "gate-38-paid-ready-registrations": (
        "{python} -m pytest scripts/tests/test_check_paid_ready_registrations.py -p no:django -q -c /dev/null",
        "scripts/check_paid_ready_registrations.py",
        [
            (
                "blind-clean-pass",
                "sed -i 's/return violations/return []/' {target}",
            ),
        ],
    ),
    # T.1 / W13 — an assert-free test function passes vacuously; the gate
    # ratchets the count, so the weakening injects ONE offender into the
    # probe file (8-space indent appends a method INSIDE the probe's
    # TestCase) and the gate must grow by exactly one and fail.
    "gate-39-zero-assertion-tests": (
        "{python} scripts/check_zero_assertion_tests.py",
        PROBE,
        [
            (
                "inject-assert-free-test",
                "printf '\\n        def test_probe_offender(self):\\n            pass\\n' >> {target}",
            ),
        ],
    ),
    # W12.10 — an assertion that is true by construction documents a
    # check that never runs; the gate ratchets the site count, so the
    # weakening injects ONE tautology into the probe file and the gate
    # must grow by exactly one and fail.
    "gate-39-tautology-sites": (
        "{python} scripts/check_zero_assertion_tests.py",
        PROBE,
        [
            (
                "inject-tautology-assert-true",
                "printf '\\n        def test_probe_offender(self):\\n            assert True\\n' >> {target}",
            ),
        ],
    ),
    # T.5 / W17 — scaffold debt owns a ticket and an expiry. The weakening
    # injects an EXPIRED annotated skip into the probe file: the expiry
    # check fails even under baseline, so a gate that stops checking dates
    # (or stops scanning skip sites) is caught immediately.
    # T.6 / W18 — a CODEOWNERS typo ships its subtree with no codeowner
    # and no required reviewer. The weakening injects a dead path into
    # the committed CODEOWNERS document; the gate must fail naming it.
    "gate-41-codeowners-paths": (
        "{python} scripts/check_codeowners_paths.py",
        ".github/CODEOWNERS",
        [
            (
                "inject-dead-path",
                "printf '\\nthis/does/not/exist/ @meshant/data-platform-eng\\n' >> {target}",
            ),
        ],
    ),
    "gate-40-skip-expiry": (
        "{python} scripts/check_skip_expiry.py",
        PROBE,
        [
            (
                "inject-expired-skip",
                "printf '\\n\\nimport pytest\\n\\n"
                '@pytest.mark.skip(reason="probe [TICKET=PROBE-40 EXPIRES=2000-01-01]")\\n'
                "def test_probe_expired_skip():\\n    pass\\n' >> {target}",
            ),
        ],
    ),
    # oss-release-remediation M0 — the D1-D9 decision record must stay
    # decided + dated (D1-D8) and scheduled (D9). Weakening the first
    # DECIDED status to PENDING must fail the gate; the record file is the
    # mutation target and is backed up/restored by the harness.
    "gate-47-oss-decisions-record": (
        "{python} scripts/check_oss_decisions.py",
        "openspec/changes/oss-release-remediation/decisions.md",
        [
            (
                "pending-one-decided-decision",
                "sed -i '0,/\\*\\*Status:\\*\\* DECIDED/s//**Status:** PENDING/' {target}",
            ),
        ],
    ),
    # oss-release-remediation W0.1 — the root license contract must hold at
    # the file level: weakening the first LICENSE.txt line (the license
    # name) must fail the gate; the license file is the mutation target
    # and is backed up/restored by the harness.
    "gate-48-root-license": (
        "{python} scripts/check_root_license.py",
        "LICENSE.txt",
        [
            (
                "rename-license-to-proprietary",
                "sed -i '1s/Apache License/Proprietary License/' {target}",
            ),
        ],
    ),
    # oss-release-remediation W0.2 — the committed scan report must stay
    # redacted: appending a planted GitHub-PAT-shaped line must fail the
    # gate's gitleaks self-scan; the report file is the mutation target
    # and is backed up/restored by the harness.
    "gate-49-secret-scan-report": (
        "{python} scripts/check_secret_scan_report.py",
        "docs/audits/secret-scan-2026-10-06.md",
        [
            (
                "plant-secret-in-report",
                "{python} -c \"open('{target}','a').write(chr(10)+'planted_probe = '+'ghp_'+'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcdef'+chr(10))\"",
            ),
        ],
    ),
    # oss-release-remediation W0.3 — the maintenance-window notice must
    # keep its recorded guard evidence: flipping the recorded exit code
    # must fail the gate; the notice file is the mutation target and is
    # backed up/restored by the harness.
    "gate-50-maintenance-window": (
        "{python} scripts/check_maintenance_window.py",
        "openspec/changes/oss-release-remediation/maintenance-window-2026-10-06.md",
        [
            (
                "flip-recorded-guard-exit",
                "sed -i 's/guard exit=0/guard exit=1/' {target}",
            ),
        ],
    ),
    # oss-release-remediation W0.5 — the rotation record must keep every
    # surface ROTATED: flipping one row back to PENDING-U must fail the
    # gate (the honest-gate contract); renaming a step heading must fail
    # it too. The record file is the mutation target and is backed
    # up/restored by the harness.
    "gate-51-credential-rotation": (
        "{python} scripts/check_credential_rotation.py",
        "openspec/changes/oss-release-remediation/credential-rotation-2026-10-06.md",
        [
            (
                "flip-rotated-row-to-pending",
                r"sed -i 's/\*\*Status:\*\* ROTATED/\*\*Status:\*\* PENDING-U/' {target}",
            ),
            (
                "rename-step-heading",
                "sed -i 's/### step: postgres-certs/### step: postgres-certs-renamed/' {target}",
            ),
        ],
    ),
    # oss-release-remediation W0.6 — the tag-archive manifest must keep
    # every row verified+deleted: flipping the first row must fail the
    # gate (the honest-gate contract), deleting a canonical row must fail
    # it too. The manifest file is the mutation target and is backed
    # up/restored by the harness.
    "gate-52-tag-archive": (
        "{python} scripts/check_tag_archive_manifest.py",
        "docs/audits/tag-archive-manifest-2026-10-06.md",
        [
            (
                "flip-verified-row",
                r"sed -i 's/verified: yes/verified: no/' {target}",
            ),
            (
                "delete-canonical-tag-row",
                r"sed -i '/- backup-staging-20251207_194944 /d' {target}",
            ),
        ],
    ),
    # oss-release-remediation W1.0 — the IdP-JWKS decision note must keep
    # its recorded outcome: flipping JWKS_EXPOSED to JWKS_NOT_EXPOSED must
    # fail the gate (the positive cert-pinned fallback + D4 re-scope
    # markers would then be missing). The note file is the mutation target
    # and is backed up/restored by the harness.
    "gate-53-idp-jwks-decision": (
        "{python} scripts/check_idp_jwks_decision.py",
        "docs/audits/idp-jwks-verification-2026-10-07.md",
        [
            (
                "flip-outcome-to-not-exposed",
                r"sed -i 's/\*\*Outcome:\*\* JWKS_EXPOSED/\*\*Outcome:\*\* JWKS_NOT_EXPOSED/' {target}",
            ),
        ],
    ),
    # W4.6 (oss-release-remediation, G1) — renaming the estate prefix makes
    # the checker blind: the planted-violation + real-tree pins in the suite
    # flip RED (a checker that reports nothing detects nothing).
    "gate-54-provider-boundary": (
        "{python} -m pytest scripts/tests/test_check_provider_boundary.py -p no:django -q -c /dev/null",
        "scripts/check_provider_boundary.py",
        [
            (
                "rename-estate-prefix",
                'sed -i \'s/_ESTATE_APP = "hub.apps.databricks_admin"/_ESTATE_APP = "hub.apps.databricks_admin-DISABLED"/\' {target}',
            ),
        ],
    ),
    # W12.2 (oss-release-remediation) — renaming the legacy-file pattern
    # makes the dead-code gate blind to a reintroduced `_services_legacy.py`:
    # the planted-violation pin in the suite flips RED (a checker that
    # reports nothing detects nothing).
    "gate-57-dead-code": (
        "{python} -m pytest scripts/tests/test_audit_dead_code_gate.py -p no:django -q -c /dev/null",
        "scripts/audit_dead_code.py",
        [
            (
                "rename-legacy-file-pattern",
                "sed -i 's/_services_legacy.py/_services_legacyDISABLED.py/' {target}",
            ),
        ],
    ),
    # W12.3 (oss-release-remediation) — renaming the blind-type token
    # makes the exception ratchet blind to broad `except Exception`: the
    # planted untriaged-site pin in the suite flips RED (a checker that
    # reports nothing detects nothing).
    "gate-58-exception-ratchet": (
        "{python} -m pytest scripts/tests/test_check_exception_ratchet.py -p no:django -q -c /dev/null",
        "scripts/check_exception_ratchet.py",
        [
            (
                "rename-blind-type-token",
                'sed -i \'s/"Exception"/"ExceptionDISABLED"/\' {target}',
            ),
        ],
    ),
    # W12.4 (oss-release-remediation) — renaming the workflow seed glob
    # blinds the orphan-script gate to CI wiring: the real-repo master
    # pin in the suite flips RED (a checker that reports nothing detects
    # nothing).
    "gate-59-orphan-scripts": (
        "{python} -m pytest scripts/tests/test_check_orphan_scripts.py -p no:django -q -c /dev/null",
        "scripts/check_orphan_scripts.py",
        [
            (
                "rename-workflow-seed-glob",
                "sed -i 's/\\.github\\/workflows\\/\\*\\.yml/.github\\/workflowsDISABLED\\/\\*.yml/' {target}",
            ),
        ],
    ),
    # W12.6 (oss-release-remediation, delivered with W9.1) — renaming an
    # artifact path makes the version checker blind to that surface: the
    # real-tree drift pins in the suite flip RED (a checker that reports
    # nothing detects nothing).
    "gate-60-release-versions": (
        "{python} -m pytest scripts/tests/test_w91_version_single_source.py -p no:django -q -c /dev/null",
        "scripts/check_release_versions.py",
        [
            (
                "rename-hub-artifact-path",
                'sed -i \'s|REPO_ROOT / "hub" / "__init__.py"|REPO_ROOT / "hub-DISABLED" / "__init__.py"|\' {target}',
            ),
        ],
    ),
    # W12.7 (oss-release-remediation) — renaming the "wired" status
    # token blinds the stub-inventory gate to wired rows: the real-repo
    # master pin in the suite flips RED (a checker that cannot classify
    # its rows detects nothing).
    "gate-61-stub-inventory": (
        "{python} -m pytest scripts/tests/test_check_stub_inventory.py -p no:django -q -c /dev/null",
        "scripts/check_stub_inventory.py",
        [
            (
                "rename-wired-status-token",
                'sed -i \'s/"wired"/"wiredDISABLED"/\' {target}',
            ),
        ],
    ),
    # The 1.1 pin: proven end-to-end in Q.5.1 (rename weakening -> 17->0).
    # Requires the Django test env, so the no-django suite skips it; the
    # entry documents the proof.
    "1.1-commercial-hooks-pin": (
        "{python} -m pytest tests/unit/test_commercial_hooks_api_contract.py -q",
        "hub/apps/core/commercial_hooks.py",
        [
            (
                "rename-hook",
                "sed -i 's/def reset_hooks/def reset_hooks_BROKEN/' {target}",
            ),
        ],
    ),
    # W11.5 (oss-release-remediation, register row 18) — renaming the
    # token-keyword list blinds the CSPRNG gate: the planted-violation
    # pin in the suite flips RED (a checker that flags nothing detects
    # nothing).
    "gate-62-crypto-random": (
        "{python} -m pytest scripts/tests/test_w115_crypto_random_sweep.py -p no:django -q -c /dev/null",
        "scripts/check_crypto_random.py",
        [
            (
                "rename-token-keywords",
                "sed -i 's/_TOKEN_KEYWORDS = (/_TOKEN_KEYWORDS_DISABLED = (/' {target}",
            ),
        ],
    ),
    # W11.10 (oss-release-remediation, register rows 17/20) — the
    # security-tooling gates.  Each weakening must flip at least one
    # pin in the W11.10 suite RED.
    "gate-25-semgrep-local-rules": (
        "{python} -m pytest scripts/tests/test_w1110_security_tooling_gates.py -p no:django -q -c /dev/null",
        "scripts/check_semgrep_rules.py",
        [
            (
                "drop-a-local-rule",
                "sed -i 's#semgrep/rules/transformation.yaml#semgrep/rules/transformationDROPPED.yaml#' {target}",
            ),
        ],
    ),
    "gate-37-bandit-blocking-wiring": (
        "{python} -m pytest scripts/tests/test_w1110_security_tooling_gates.py -p no:django -q -c /dev/null",
        ".github/workflows/code-quality.yml",
        [
            (
                "re-warn-only",
                "sed -i 's#check_bandit_debt_ratchet.py --output-file bandit-quality.json#check_bandit_debt_ratchet.py --output-file bandit-quality.json\\n        continue-on-error: true#' {target}",
            ),
        ],
    ),
    "gate-47-dependency-vulns-wiring": (
        "{python} -m pytest scripts/tests/test_w1110_security_tooling_gates.py -p no:django -q -c /dev/null",
        "Makefile",
        [
            (
                "drop-from-quality-gates",
                "sed -i 's#python scripts/check_dependency_vulns.py#python scripts/check_dependency_vulnsDROPPED.py#' {target}",
            ),
        ],
    ),
    "trivy-deploy-gate": (
        "{python} -m pytest scripts/tests/test_w1110_security_tooling_gates.py -p no:django -q -c /dev/null",
        ".github/workflows/deploy.yml",
        [
            (
                "drop-exit-code",
                "sed -i \"s/exit-code: '1'/exit-code: '0'/\" {target}",
            ),
        ],
    ),
    "gitleaks-ci-gate": (
        "{python} -m pytest scripts/tests/test_w1110_security_tooling_gates.py -p no:django -q -c /dev/null",
        ".github/workflows/ci.yml",
        [
            (
                "drop-config-env",
                "sed -i 's/GITLEAKS_CONFIG: .gitleaks.toml/GITLEAKS_CONFIG: .gitleaksDROPPED.toml/' {target}",
            ),
        ],
    ),
    # W11.11 (oss-release-remediation) — re-pointing the HIGH-risk code
    # at a value no alert can carry blinds the delta gate: no alert is
    # ever classified HIGH, so the planted-new-high pin in the suite
    # flips RED (a checker that flags nothing detects nothing).
    "gate-64-zap-delta": (
        "{python} -m pytest scripts/tests/test_w1111_zap_delta.py -p no:django -q -c /dev/null",
        "scripts/check_zap_delta.py",
        [
            (
                "blind-high-risk-code",
                'sed -i \'s/HIGH_RISK = "3"/HIGH_RISK = "0"/\' {target}',
            ),
        ],
    ),
    # ── W10.1 (oss-release-remediation) — the convention-11 closure: every
    # W-lane gate/pin added since the harness's last audit is registered
    # here and drill-proven. Coverage enforced by
    # scripts/tests/test_w101_gate_harness_coverage.py.
    "gate-44-smoke-report": (
        "{python} scripts/check_smoke_report.py",
        "docs/runbooks/PILOT_SMOKE_REPORT.md",
        [
            (
                "drop-mandated-section",
                "sed -i '/^## Exercised paths/d' {target}",
            ),
        ],
    ),
    "gate-45-pilot-scope": (
        "{python} scripts/check_pilot_scope.py",
        "docs/runbooks/PILOT_SCOPE.md",
        [
            (
                "drop-mandated-section",
                "sed -i '/^## Journey selection/d' {target}",
            ),
        ],
    ),
    "gate-46-privacy-pack": (
        "{python} scripts/check_privacy_pack.py",
        "docs/runbooks/PILOT_PRIVACY_PACK.md",
        [
            (
                "drop-mandated-section",
                "sed -i '/^## DPIA run/d' {target}",
            ),
        ],
    ),
    "gate-55-shipped-tree-litter": (
        "{python} -m pytest scripts/tests/test_check_shipped_tree_litter.py -p no:django -q -c /dev/null",
        ".gitignore",
        [
            (
                "unignore-artifact-class",
                "sed -i 's#^storybook-static/$##storybook-static/#' {target}",
            ),
        ],
    ),
    "gate-56-fork-guards": (
        "{python} -m pytest scripts/tests/test_check_fork_guards.py -p no:django -q -c /dev/null",
        "scripts/check_fork_guards.py",
        [
            (
                "break-canonical-guard",
                "sed -i 's/return bool(_FORK_GUARD_RE.search(if_expr))/return False/' {target}; sed -i 's/if not if_expr or \"github.event_name\" not in if_expr:/if True:/' {target}",
            ),
        ],
    ),
    "gate-w111-threat-model-veracity": (
        "{python} -m pytest scripts/tests/test_w111_threat_model_veracity.py -p no:django -q -c /dev/null",
        "docs/security/threat-models/stride-money-w2.md",
        [
            (
                "drop-a-stride-section",
                "sed -i '/^## Spoofing/d' {target}",
            ),
        ],
    ),
    "gate-w112-matrix-veracity": (
        "{python} -m pytest scripts/tests/test_w112_matrix_veracity.py -p no:django -q -c /dev/null",
        "docs/security/adversarial-matrices/w112-auth-session-matrix.md",
        [
            (
                "drop-root-causes-section",
                "sed -i '/^## Root causes fixed/d' {target}",
            ),
        ],
    ),
    "gate-w114-property-veracity": (
        "{python} -m pytest scripts/tests/test_w114_property_suites_veracity.py -p no:django -q -c /dev/null",
        "docs/security/fuzz/w114-property-corpus.json",
        [
            (
                "rename-corpus-section",
                'sed -i \'s/"cents": \\[/"centsX": [/\' {target}',
            ),
        ],
    ),
    "gate-w116-leak-ban": (
        "{python} -m pytest scripts/tests/test_w116_exc_str_leak_ban.py -p no:django -q -c /dev/null",
        "hub/apps/api/exceptions.py",
        [
            (
                "break-typed-4xx-guard",
                "sed -i 's/http_status >= 500/http_status >= 999/' {target}",
            ),
        ],
    ),
    "gate-w117-business-logic-veracity": (
        "{python} -m pytest scripts/tests/test_w117_business_logic_matrix_veracity.py -p no:django -q -c /dev/null",
        "docs/security/adversarial-matrices/w117-business-logic-matrix.md",
        [
            (
                "break-a-cell-citation",
                "sed -i 's/::test_matrix_covers_the_real_surface_hops/::test_matrix_covers_the_real_surface_hopsX/' {target}",
            ),
        ],
    ),
    "gate-w118-upload-veracity": (
        "{python} -m pytest scripts/tests/test_w118_upload_abuse_veracity.py -p no:django -q -c /dev/null",
        "hub/apps/files/views.py",
        [
            (
                "drop-staging-design-marker",
                "sed -i 's/upload_staging_key/upload_stag1ng_key/g' {target}",
            ),
        ],
    ),
    "gate-w119-config-veracity": (
        "{python} -m pytest scripts/tests/test_w119_api_configuration_veracity.py -p no:django -q -c /dev/null",
        "docs/security/adversarial-matrices/w119-api-configuration-matrix.md",
        [
            (
                "rename-matrix-section",
                "sed -i 's/## Matrix 1 — Rate-limit matrix/## Matrix 1X — Rate-limit matrix/' {target}",
            ),
        ],
    ),
    "gate-w1112-ai-veracity": (
        "{python} -m pytest scripts/tests/test_w1112_ai_threat_model_veracity.py -p no:django -q -c /dev/null",
        "docs/security/adversarial-matrices/w1112-ai-prompt-injection-matrix.md",
        [
            (
                "drop-open-threats-section",
                "sed -i '/^## OPEN-THREATS/d' {target}",
            ),
        ],
    ),
    "gate-w1113-asvs-pack-veracity": (
        "{python} -m pytest scripts/tests/test_w1113_asvs_evidence_pack_veracity.py -p no:django -q -c /dev/null",
        "docs/audits/asvs-2026/asvs-evidence-pack.md",
        [
            (
                "drop-acceptance-below-l2",
                "sed -i '0,/\\*\\*Declared level: Level 2\\*\\*/s//**Declared level: Level 1**/' {target}",
            ),
        ],
    ),
    "gate-w104-gonogo-pack-veracity": (
        "{python} -m pytest scripts/tests/test_w104_gonogo_pack_veracity.py -p no:django -q -c /dev/null",
        "docs/operations/oss-go-nogo-ledger.md",
        [
            (
                "flip-go-decision-to-no",
                "sed -i 's/`confirmed = yes`/`confirmed = no`/' {target}",
            ),
        ],
    ),
    "gate-w105-deferred-debt-triage": (
        "{python} -m pytest scripts/tests/test_w105_deferred_debt_triage.py -p no:django -q -c /dev/null",
        "openspec/changes/oss-release-remediation/design.md",
        [
            (
                "renumber-section8-ticket",
                "sed -i 's/TICKET=W105-CONTRACTS-MONOLITH/TICKET=X105-CONTRACTS-MONOLITH/' {target}",
            ),
        ],
    ),
}

# Gates whose checker needs a running Django/service env — audited only when
# the caller opts in (the no-django suite skips them with reason).
ENV_GATED = {"1.1-commercial-hooks-pin"}

# Advisory gates that NEVER fail CI by design (stale flags are tech debt,
# not merge gates — the detector prints CRITICAL/WARNING/INFO). Their
# falsifiability contract is report-content accuracy, not exit-code flips,
# so they are excluded from the BITES registry and listed here explicitly
# rather than silently skipped.
ADVISORY = {
    "gate-20-stale-feature-flags": "never fails by design (detect_stale_feature_flags.py) — report-only",
}


def _summary(text: str) -> tuple[int, int]:
    """(passed, failed) parsed from a pytest -q tail line; (-1, 0) otherwise."""
    match = re.search(r"(\d+) passed", text)
    passed = int(match.group(1)) if match else -1
    match = re.search(r"(\d+) failed", text)
    failed = int(match.group(1)) if match else 0
    return passed, failed


def run_check(checker: str, target: str, weakening_command: str | None = None) -> tuple[int, str]:
    command = checker if weakening_command is None else weakening_command
    command = command.replace("{target}", target).replace("{python}", PYTHON)
    result = subprocess.run(
        command,
        shell=True,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, result.stdout + "\n" + result.stderr


def _outcome(rc: int, output: str) -> tuple[int, int, int]:
    """(rc, passed, failed) — rc is authoritative for script gates."""
    passed, failed = _summary(output)
    return rc, passed, failed


def verify(checker: str, target: str, weakenings: list[str]) -> tuple[bool, list[str]]:
    """Run baseline + each weakening; every weakening must change the outcome.

    Each weakening command MUTATES the target; the gate is then RE-RUN and
    its result compared against the baseline. The target is backed up and
    restored between weakenings so they stay independent.

    W7.4: when the BASELINE run is already failing (e.g. the honest
    credential-rotation gate blocking on PENDING-U surfaces), a weakening
    cannot change the outcome by construction — the weakenings are
    classified PRE-RED (not measurable, not vacuous) and the owning
    ledger documents why the gate is red.  A green-at-baseline gate
    whose weakening survives is the VACUOUS signal this harness exists
    to catch.
    """
    baseline = _outcome(*run_check(checker, target))
    report: list[str] = []
    for spec in weakenings:
        if baseline[0] != 0:
            label, _, _command = spec.partition(":")
            report.append(f"{label}: PRE-RED (gate failing at baseline — not measurable)")
            continue
        label, _, command = spec.partition(":")
        backup = target + ".falsifiability-backup"
        shutil.copy2(target, backup)
        try:
            run_check(checker, target, command)  # mutate
            weakened = _outcome(*run_check(checker, target))  # re-run the gate
        finally:
            shutil.move(backup, target)
        bites = weakened != baseline
        report.append(
            f"{label}: {'BITES' if bites else 'VACUOUS'} (baseline {baseline} -> {weakened})"
        )
    return all("VACUOUS" not in line for line in report), report


def _run_and_report(label: str, checker: str, target: str, weakenings: list[str]) -> int:
    """Run one gate's weakenings and print the report; return the exit code."""
    ok, report = verify(checker, target, weakenings)
    if label:
        print(f"{label}:")
    for line in report:
        print(f"  {line}" if label else line)
    if not ok:
        print("FALSIFIABILITY: VACUOUS weakening(s) detected — the gate cannot fail.")
        return 1
    print(f"FALSIFIABILITY: all {len(report)} weakenings bite.")
    return 0


def _audit(gates: list[str]) -> tuple[bool, list[str]]:
    ok = True
    rows: list[str] = []
    for name in gates:
        checker, target, weakenings = GATES[name]
        passed, report = verify(checker, target, [f"{label}:{cmd}" for label, cmd in weakenings])
        status = "FALSIFIABLE" if passed else "VACUOUS"
        ok = ok and passed
        rows.append(f"{name}: {status}")
        for line in report:
            rows.append(f"    {line}")
    return ok, rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gate falsifiability harness + registry")
    parser.add_argument(
        "--checker", help="command running the gate; may use {target} (direct mode)"
    )
    parser.add_argument("--target", help="the file the weakenings mutate (direct mode)")
    parser.add_argument("--weaken", action="append", default=[], help="label:command (direct mode)")
    parser.add_argument("--gate", help="run one registry gate by name")
    parser.add_argument("--audit", action="store_true", help="run every registry gate")
    parser.add_argument(
        "--include-env-gated", action="store_true", help="audit env-gated gates too"
    )
    args = parser.parse_args(argv)

    if args.gate:
        if args.gate not in GATES:
            print(f"FALSIFIABILITY: unknown gate {args.gate!r}; registry has {len(GATES)} gates")
            return 2
        checker, target, weakenings = GATES[args.gate]
        return _run_and_report(
            args.gate,
            checker,
            target,
            [f"{wlabel}:{wcommand}" for wlabel, wcommand in weakenings],
        )

    if args.audit:
        names = [n for n in GATES if args.include_env_gated or n not in ENV_GATED]
        ok, rows = _audit(names)
        for row in rows:
            print(row)
        audited = len(names)
        if ADVISORY:
            print(f"ADVISORY (excluded by design): {', '.join(sorted(ADVISORY))}")
        if ENV_GATED and not args.include_env_gated:
            print(
                "ENV-GATED (skipped; run with --include-env-gated in the full env): "
                + ", ".join(sorted(ENV_GATED))
            )
        if not ok:
            print(
                f"FALSIFIABILITY: {sum(1 for r in rows if 'VACUOUS' in r)} of {audited} "
                "audited gates are VACUOUS."
            )
            return 1
        print(f"FALSIFIABILITY: all {audited} audited gates are falsifiable.")
        return 0

    if not (args.checker and args.target and args.weaken):
        parser.error("direct mode requires --checker --target --weaken; or use --gate/--audit")

    return _run_and_report("", args.checker, args.target, args.weaken)


if __name__ == "__main__":
    raise SystemExit(main())
