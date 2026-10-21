"""GATE-61 (oss-release-remediation W12.7) pins — no mocks, no stubs.

The RED phase of W12.7: the pins below ran against the REAL repository
before the triage landed and failed — no committed inventory existed,
web-vitals shipped unimported ("collected-then-discarded"), sw.js
shipped with zero registrations, and sunset endpoints served silently
(the middleware SKIPPED the warning header instead of enforcing 410).

Pins exercise the REAL gate as a subprocess against:
  * the real repository (master GREEN pins),
  * planted-violation temp trees (a reintroduced deleted stub, a wired
    row citing a missing/non-matching evidence file, a doc missing a
    row ID, an untriaged status, or an expired deferred ticket all flip
    the gate RED).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GATE = REPO_ROOT / "scripts" / "check_stub_inventory.py"
DOC = REPO_ROOT / "docs" / "audits" / "stub-inventory-2026.md"
REGISTRY = REPO_ROOT / "scripts" / "stub_inventory_registry.json"


def _run_gate(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATE), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _make_tree(tmp_path: Path, rows: list[dict], files: dict[str, str]) -> Path:
    tree = tmp_path / "tree"
    tree.mkdir()
    for rel, content in files.items():
        dst = tree / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(content)
    (tree / "scripts").mkdir(parents=True, exist_ok=True)
    (tree / "scripts" / "stub_inventory_registry.json").write_text(
        json.dumps({"rows": rows}, indent=2)
    )
    (tree / "docs" / "audits").mkdir(parents=True, exist_ok=True)
    (tree / "docs" / "audits" / "stub-inventory-2026.md").write_text(
        "# Stub / Placeholder Inventory — 2026\n\n"
        + "\n".join(f"STUB-ROW: {row['id']}" for row in rows)
        + "\n"
    )
    return tree


def _deleted_row(marker: str | None = None, absent_file: str | None = None):
    row = {"id": "STUB-X", "status": "deleted"}
    if marker:
        row["absent_marker"] = marker
    if absent_file:
        row["absent_file"] = absent_file
    return row


class TestRealRepository:
    """The master GREEN pins — the real tree satisfies the whole contract."""

    def test_real_repo_gate_passes(self):
        result = _run_gate("--check")
        assert result.returncode == 0, result.stdout + result.stderr
        assert "stub inventory clean" in result.stdout
        assert "zero untriaged" in result.stdout

    def test_real_repo_doc_carries_every_registry_row(self):
        payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
        doc_text = DOC.read_text(encoding="utf-8")
        for row in payload["rows"]:
            assert row["id"] in doc_text, f"{row['id']}: missing from the doc"

    def test_real_repo_inventory_has_no_ticket_deferred_rows(self):
        # Every named stub resolved to wired/deleted in this pass —
        # a future deferral must be a deliberate, expiring decision.
        payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for row in payload["rows"]:
            assert (
                row["status"] != "ticket-deferred"
            ), f"{row['id']}: unexpected deferral"


class TestPlantedViolationsBite:
    """Drift pins — a reintroduced stub or an dishonest row flips RED."""

    def test_planted_reintroduced_class_bites(self, tmp_path):
        tree = _make_tree(
            tmp_path,
            [_deleted_row(marker=r"class\s+MyStub")],
            {"hub/apps/x/mod.py": "class MyStub:\n    pass\n"},
        )
        result = _run_gate("--root", str(tree), "--check")
        assert result.returncode == 1
        assert "REINTRODUCED" in result.stdout

    def test_planted_reintroduced_route_bites(self, tmp_path):
        tree = _make_tree(
            tmp_path,
            [_deleted_row(marker=r'path\(\s*["\']legacy')],
            {
                "hub/apps/x/urls.py": (
                    "from django.urls import path\n" 'path("legacy/", view)\n'
                )
            },
        )
        result = _run_gate("--root", str(tree), "--check")
        assert result.returncode == 1
        assert "REINTRODUCED" in result.stdout

    def test_planted_absent_file_bites(self, tmp_path):
        tree = _make_tree(
            tmp_path,
            [_deleted_row(absent_file="docs/OLD_SUMMARY.md")],
            {"docs/OLD_SUMMARY.md": "# stale\n"},
        )
        result = _run_gate("--root", str(tree), "--check")
        assert result.returncode == 1
        assert "still exists" in result.stdout

    def test_wired_row_citing_missing_evidence_bites(self, tmp_path):
        tree = _make_tree(
            tmp_path,
            [
                {
                    "id": "STUB-X",
                    "status": "wired",
                    "present_marker": "REAL_IMPL",
                    "evidence": "hub/apps/x/gone.py",
                }
            ],
            {"hub/apps/x/other.py": "x = 1\n"},
        )
        result = _run_gate("--root", str(tree), "--check")
        assert result.returncode == 1
        assert "missing evidence" in result.stdout

    def test_wired_row_with_non_matching_evidence_bites(self, tmp_path):
        tree = _make_tree(
            tmp_path,
            [
                {
                    "id": "STUB-X",
                    "status": "wired",
                    "present_marker": "REAL_IMPL",
                    "evidence": "hub/apps/x/mod.py",
                }
            ],
            {"hub/apps/x/mod.py": "x = 1  # nothing real here\n"},
        )
        result = _run_gate("--root", str(tree), "--check")
        assert result.returncode == 1
        assert "does not contain" in result.stdout

    def test_doc_missing_a_row_id_bites(self, tmp_path):
        tree = _make_tree(
            tmp_path,
            [_deleted_row(absent_file="docs/OLD_SUMMARY.md")],
            {},
        )
        doc = tree / "docs" / "audits" / "stub-inventory-2026.md"
        doc.write_text("# inventory\n")  # no row IDs at all
        result = _run_gate("--root", str(tree), "--check")
        assert result.returncode == 1
        assert "does not carry the row" in result.stdout

    def test_untriaged_status_bites(self, tmp_path):
        tree = _make_tree(
            tmp_path,
            [{"id": "STUB-X", "status": "todo-later"}],
            {},
        )
        result = _run_gate("--root", str(tree), "--check")
        assert result.returncode == 1
        assert "untriaged status" in result.stdout

    def test_expired_deferred_ticket_bites(self, tmp_path):
        tree = _make_tree(
            tmp_path,
            [
                {
                    "id": "STUB-X",
                    "status": "ticket-deferred",
                    "ticket": "TICKET-1",
                    "expires": "2020-01-01",
                    "present_marker": "TICKET=TICKET-1",
                    "evidence": "hub/apps/x/mod.py",
                }
            ],
            {"hub/apps/x/mod.py": "# TICKET=TICKET-1 EXPIRES=2020-01-01\nx=1\n"},
        )
        result = _run_gate("--root", str(tree), "--check")
        assert result.returncode == 1
        assert "EXPIRED" in result.stdout

    def test_clean_deleted_row_passes(self, tmp_path):
        tree = _make_tree(
            tmp_path,
            [_deleted_row(marker=r"class\s+MyStub")],
            {"hub/apps/x/mod.py": "x = 1\n"},
        )
        result = _run_gate("--root", str(tree), "--check")
        assert result.returncode == 0, result.stdout + result.stderr
        assert "zero untriaged" in result.stdout
