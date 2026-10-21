"""Publish gitleaks gate TDD suite (Phase P.8).

The publish script treated a MISSING gitleaks CLI as a pass: "gitleaks CLI
absent — SKIPPING (CI runs gitleaks-action)" and the publish proceeded
with zero scan evidence. A publish is the one place a secret leak is
non-recoverable (the public mirror is consumed downstream), and the
operator running the script is precisely the case where CI did NOT run.
The gate is now a hard failure: no gitleaks binary → no publish.

No mocks: the REAL gate function is invoked through the REAL script in a
subprocess; the "present" path runs a REAL gitleaks scan of the real tree.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GATES_SH = REPO_ROOT / "scripts" / "publish_gates.sh"
PUBLISH_SH = REPO_ROOT / "scripts" / "publish_public.sh"


def _run_gate(path_value: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            "bash",
            "-c",
            "source scripts/publish_gates.sh && require_gitleaks .",
        ],
        cwd=REPO_ROOT,
        env={**os.environ, "PATH": path_value},
        capture_output=True,
        text=True,
        check=False,
    )


class TestGitleaksGate:
    def test_missing_gitleaks_is_a_hard_failure(self):
        """The class this gate exists for: the CLI's absence must ABORT the
        publish, naming the missing tool — never a logged skip."""
        gitleaks_bin = shutil.which("gitleaks")
        assert gitleaks_bin, "gitleaks must be installed to run this suite"
        gitleaks_dir = Path(gitleaks_bin).resolve().parent
        stripped_path = ":".join(
            d for d in os.environ["PATH"].split(":") if d and Path(d).resolve() != gitleaks_dir
        )
        result = _run_gate(stripped_path)
        assert result.returncode != 0, "missing gitleaks must fail the gate"
        output = result.stdout + result.stderr
        assert "gitleaks" in output.lower()
        assert "refusing" in output.lower(), "the failure must say why"

    def test_present_gitleaks_runs_a_real_scan(self):
        """The gate is not a presence check — it must RUN the scan and the
        real tree must pass it."""
        result = _run_gate(os.environ["PATH"])
        assert result.returncode == 0, result.stdout + result.stderr


class TestPublishScriptWiring:
    def test_publish_public_sources_the_gate_and_drops_the_silent_skip(self):
        """The script must call the gate (preflight AND post-commit
        verification); the `command -v gitleaks` skip idiom must be gone.
        The pre-flight scan lives in publish_public.sh; the post-commit
        re-scan lives in publish_sync.sh (the P2-5 extraction — the same
        gate, run pre-push inside the public checkout)."""
        text = PUBLISH_SH.read_text(encoding="utf-8")
        assert "source scripts/publish_gates.sh" in text, (
            "publish_public.sh does not source the gates file"
        )
        assert "command -v gitleaks" not in text, (
            "the silent-skip idiom must be gone from publish_public.sh"
        )
        sync_text = (REPO_ROOT / "scripts" / "publish_sync.sh").read_text(encoding="utf-8")
        assert "require_gitleaks" in text, (
            "publish_public.sh must run the pre-flight scan on the built tree"
        )
        assert "require_gitleaks" in sync_text, (
            "publish_sync.sh must run the post-commit scan in the public checkout"
        )

    def test_publish_gates_the_built_tree_not_the_working_tree(self):
        """The boundary pre-flight must scan the BUILT tree (the exact
        shipped bytes) — a working-tree scan produces false failures on
        peer-lane WIP that the index-based publish never ships (P2-5
        finding: an uncommitted WIP import blocked the real publish)."""
        text = PUBLISH_SH.read_text(encoding="utf-8")
        assert '"$STAGING/scripts/check_core_boundary.py"' in text, (
            "the pre-flight must run the built tree's own GATE-29 checker"
        )
        # the working-tree form must be GONE from the pre-flight (it
        # still appears nowhere else in the script)
        assert 'log "GATE-29 boundary scan"' not in text or "built publish tree" in text

    def test_gates_file_has_no_skip_escape_hatch(self):
        """No env-var or flag may downgrade the failure to a warning — a
        deliberate override would belong in the operator's own fork. (The
        header comment legitimately quotes the OLD "SKIPPING" log line, so
        this check looks for downgrade MECHANISMS, not the word.)"""
        text = GATES_SH.read_text(encoding="utf-8")
        for pattern in ("ALLOW_SKIP", "SKIP_GITLEAKS", "SKIP=", "|| true"):
            assert pattern not in text, f"the gate carries a downgrade path ({pattern!r})"


class TestKubernetesSecretRule:
    """P0-9 (close-oss-release-conditions) root fix: the
    kubernetes-secret-yaml rule must catch a REAL inlined Secret manifest
    (``kind: Secret`` + baked ``data`` values) but NOT an ExternalSecret
    reference manifest (``kind: SecretStore`` — the W0.7 "secrets in
    ExternalSecrets only" contract). Before the boundary fix the rule
    prefix-matched "Secret" inside "SecretStore" and reported the
    remoteRef ``key: pilot/...`` entry as a baked value."""

    def test_rule_flags_secret_but_not_secretstore(self, tmp_path):
        secret_yaml = tmp_path / "secret.yaml"
        secret_yaml.write_text(
            "kind: Secret\n"
            "data:\n"
            "  foo: abcdefghijkl\n"
        )
        ext_yaml = tmp_path / "external.yaml"
        ext_yaml.write_text(
            "kind: SecretStore\n"
            "name: pilot-secret-store\n"
            "kind: ExternalSecret\n"
            "data:\n"
            "  - secretKey: X\n"
            "    remoteRef:\n"
            "      key: pilot/redis\n"
        )
        report = tmp_path / "report.json"
        result = subprocess.run(
            [
                "gitleaks",
                "detect",
                "--no-git",
                "--source",
                str(tmp_path),
                "--config",
                str(REPO_ROOT / ".gitleaks.toml"),
                "--report-format",
                "json",
                "--report-path",
                str(report),
                "--no-banner",
                "--log-level=error",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode in (0, 1), result.stderr
        findings = json.loads(report.read_text(encoding="utf-8"))
        # An absolute --source records absolute paths — compare basenames.
        files = {Path(f.get("File")).name for f in findings}
        assert "secret.yaml" in files, "a baked kind: Secret manifest must still be flagged"
        assert "external.yaml" not in files, (
            "an ExternalSecret reference manifest must not be flagged"
        )
