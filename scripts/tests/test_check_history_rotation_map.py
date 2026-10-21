"""
Contract tests for scripts/check_history_rotation_map.py (close-oss-release-
conditions P1-3, the G8 force-push gate).

The history-content → rotation-status mapping is the Phase-2 gate: every
credential CLASS visible in the tainted history (enumerated by the real
gitleaks-over-history pass and committed as the candidate list) must map
to dated rotation/retirement evidence. A class without dead-value evidence
blocks the force-push.

These tests pin the checker's contract with real tmp files — no mocks:

- every candidate class (rule|category) must have a map row;
- every MANDATED class (the 6 GATE-51 surfaces, the ANTHROPIC token, the
  staging passwords, the postgres TLS certs, the test stack) must have a
  map row even when gitleaks never flagged it;
- every map row must carry DATED evidence — an undated row, a PENDING
  row, or a placeholder fails the gate (a gate that tolerates PENDING is
  the vacuous failure mode);
- the CLI exits 0 only when the mapping is complete and evidenced;
- the checker is wired into ``quality-gates``.
"""

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest

scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

script_path = scripts_dir / "check_history_rotation_map.py"
spec = importlib.util.spec_from_file_location("check_history_rotation_map", script_path)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

ROOT = scripts_dir.parent
MAKEFILE = ROOT / "Makefile"

CANDIDATES = """# gitleaks-over-history candidates (values never recorded)
| Rule | Class | Findings | Example commits |
|---|---|---|---|
| jwt | frontend/test-results/** | 3290 | abc1234 |
| generic-api-key | openspec/changes/** | 6 | def5678 |
| private-key | infrastructure/postgres/certs/** | 3 | aaa1111 |
"""


def _map(rows: str) -> str:
    return (
        "# History-content → rotation-status map\n\n"
        "| Class key | Rotation / retirement evidence |\n"
        "|---|---|\n"
        f"{rows}"
    )


ALL_MAPPED = _map(
    "| `jwt\\|frontend/test-results/**` | 2026-10-19 dead-check: all sampled "
    "tokens EXPIRED (exp 2026-03-12) |\n"
    "| `generic-api-key\\|openspec/changes/**` | 2026-10-19 verified: sha256 "
    "digests only, never a credential |\n"
    "| `private-key\\|infrastructure/postgres/certs/**` | 2026-10-07 "
    "regenerated (postgres-certs ROTATED) |\n"
    "| gcp-sa-key | 2026-10-19 dead-check PASS (invalid_grant) |\n"
    "| aws-pair | 2026-10-19 dead-check PASS (InvalidClientTokenId) |\n"
    "| azure-sp-secret | 2026-10-19 dead-check PASS (invalid_client) |\n"
    "| databricks-pat | 2026-10-19 dead-check PASS (403) |\n"
    "| snowflake-pat | 2026-10-19 dead-check PASS (auth-class) |\n"
    "| stripe-test-key | 2026-10-19 dead-check PASS (HTTP 401) |\n"
    "| anthropic-auth-token | 2026-10-19 provider-revoked |\n"
    "| staging-passwords | 2026-10-06 rotated (rotate_env_secrets) |\n"
    "| postgres-certs | 2026-10-07 regenerated (fingerprints differ) |\n"
    "| test-stack | 2026-10-06 wiped + re-minted; 2026-10-19 reinit |\n"
)


@pytest.fixture
def files(tmp_path):
    candidates = tmp_path / "candidates.md"
    candidates.write_text(CANDIDATES)
    return {"candidates": candidates}


def _run(candidates, map_file):
    return subprocess.run(
        [
            sys.executable,
            str(scripts_dir / "check_history_rotation_map.py"),
            "--candidates",
            str(candidates),
            "--map",
            str(map_file),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


class TestCompleteness:
    def test_every_candidate_class_mapped_passes(self, files, tmp_path):
        map_file = tmp_path / "map.md"
        map_file.write_text(ALL_MAPPED)
        result = _run(files["candidates"], map_file)
        assert result.returncode == 0, result.stdout + result.stderr

    def test_unmapped_candidate_fails(self, files, tmp_path):
        map_file = tmp_path / "map.md"
        map_file.write_text(ALL_MAPPED.replace(
            "| `jwt\\|frontend/test-results/**` |", "| `jwt\\|OTHER/**` |", 1))
        result = _run(files["candidates"], map_file)
        assert result.returncode != 0
        assert "frontend/test-results" in result.stdout

    def test_mandated_class_missing_fails(self, files, tmp_path):
        map_file = tmp_path / "map.md"
        map_file.write_text(ALL_MAPPED.replace(
            "| anthropic-auth-token |", "| someone-elses-token |", 1))
        result = _run(files["candidates"], map_file)
        assert result.returncode != 0
        assert "anthropic-auth-token" in result.stdout

    def test_candidate_file_missing_fails(self, tmp_path):
        result = _run(tmp_path / "nope.md", tmp_path / "map.md")
        assert result.returncode != 0


class TestEvidence:
    def test_pending_row_fails_the_honest_gate(self, files, tmp_path):
        # The force-push gate: a class without dead-value evidence blocks
        # Phase 2 — a PENDING row must fail, never be tolerated.
        map_file = tmp_path / "map.md"
        map_file.write_text(ALL_MAPPED.replace(
            "| stripe-test-key | 2026-10-19 dead-check PASS (HTTP 401) |",
            "| stripe-test-key | PENDING-U (dashboard roll) |", 1))
        result = _run(files["candidates"], map_file)
        assert result.returncode != 0
        assert "stripe-test-key" in result.stdout

    def test_undated_evidence_fails(self, files, tmp_path):
        map_file = tmp_path / "map.md"
        map_file.write_text(ALL_MAPPED.replace(
            "| gcp-sa-key | 2026-10-19 dead-check PASS (invalid_grant) |",
            "| gcp-sa-key | dead-check PASS (invalid_grant) |", 1))
        result = _run(files["candidates"], map_file)
        assert result.returncode != 0
        assert "gcp-sa-key" in result.stdout

    def test_placeholder_fails(self, files, tmp_path):
        map_file = tmp_path / "map.md"
        map_file.write_text(ALL_MAPPED.replace(
            "| snowflake-pat | 2026-10-19 dead-check PASS (auth-class) |",
            "| snowflake-pat | TODO |", 1))
        result = _run(files["candidates"], map_file)
        assert result.returncode != 0


class TestWiring:
    def test_checker_wired_into_quality_gates(self):
        text = MAKEFILE.read_text()
        match = re.search(r"^quality-gates:.*\n((?:\t.*\n)+)", text, re.MULTILINE)
        assert match, "quality-gates target not found in Makefile"
        assert "check_history_rotation_map.py" in match.group(1), (
            "the P1-3 force-push gate must run in quality-gates"
        )

    def test_default_paths_exist(self):
        assert (
            ROOT / "docs/audits/gitleaks-history-candidates-2026-10-19.md"
        ).exists()
        assert (
            ROOT / "docs/audits/history-content-rotation-map-2026-10-19.md"
        ).exists()
