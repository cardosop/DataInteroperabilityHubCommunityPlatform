"""check_docs_references.py tests — TDD fixtures, no mocks."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from check_docs_references import collect_violations, main

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _write_doc(root: Path, rel: str, content: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


class TestRules:
    def test_existing_reference_passes(self, tmp_path):
        _write_doc(tmp_path, "docs/x.md", "see `scripts/check_core_boundary.py`\n")
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "check_core_boundary.py").write_text("# x\n")
        assert collect_violations(tmp_path, ("docs/x.md",)) == []

    def test_broken_reference_fails(self, tmp_path):
        _write_doc(tmp_path, "docs/x.md", "see `scripts/renamed_tool.py`\n")
        violations = collect_violations(tmp_path, ("docs/x.md",))
        assert any("renamed_tool.py" in v for v in violations)

    def test_allowlisted_env_files_are_not_flagged(self, tmp_path):
        _write_doc(tmp_path, "docs/x.md", "edit `.env.test` and `.env`\n")
        assert collect_violations(tmp_path, ("docs/x.md",)) == []

    def test_non_path_code_spans_are_ignored(self, tmp_path):
        _write_doc(
            tmp_path,
            "docs/x.md",
            "run `docker ps` and see `Up` — plus `p313-pg`\n",
        )
        assert collect_violations(tmp_path, ("docs/x.md",)) == []

    def test_missing_doc_itself_is_reported(self, tmp_path):
        violations = collect_violations(tmp_path, ("docs/nope.md",))
        assert any("doc file itself missing" in v for v in violations)


class TestRealDocs:
    def test_real_phase3_docs_resolve(self):
        assert main(["--root", str(REPO_ROOT)]) == 0
