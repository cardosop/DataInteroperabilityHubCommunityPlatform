"""TDD suite for the CODEOWNERS path gate (Phase T.6 / W18).

The gate pins what the W18 incident proved: a CODEOWNERS typo
(``sdk/py/`` vs the real ``sdk/python/``) is invisible until a security
test ships with no codeowner and no required reviewer — because nothing
checks that CODEOWNERS path prefixes resolve to the tree.

Contract under test (``scripts/check_codeowners_paths.py``):
  * DIRECTORY rules (trailing ``/``) must resolve to an existing directory.
  * FILE rules (no glob characters) must resolve to an existing file.
  * GLOB rules (``*``/``?``/``[``) must match at least one path — single
    ``*`` at the same depth as the literal prefix (GitHub semantics), the
    double-star ``**`` recursive.
  * Negation rules (``!pattern``) are excluded from resolution (they modify
    earlier rules; GitHub owns their semantics).
  * Comment/blank lines and the owner columns are ignored.

No mocks: synthetic CODEOWNERS documents written to real temp dirs whose
trees mirror the document; the real-repo assertions run against the
committed .github/CODEOWNERS.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import check_codeowners_paths as gate  # type: ignore[import-not-found]  # runtime sys.path injection, scripts/ is not a package


def write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def tree(tmp_path: Path, *paths: str) -> None:
    for p in paths:
        full = tmp_path / p
        if p.endswith("/"):
            full.mkdir(parents=True, exist_ok=True)
        else:
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text("x\n", encoding="utf-8")


class TestParsing:
    def test_comments_and_blanks_ignored(self, tmp_path):
        doc = write(
            tmp_path, "CODEOWNERS", "# comment\n\nsdk/python/ @team\n\n# another\nhub/ @team\n"
        )
        entries = gate.parse_codeowners(doc)
        assert [(e.pattern, e.owners) for e in entries] == [
            ("sdk/python/", ["@team"]),
            ("hub/", ["@team"]),
        ]

    def test_negation_rules_are_excluded(self, tmp_path):
        doc = write(tmp_path, "CODEOWNERS", "docs/ @team\n!docs/private/ @team\n")
        entries = gate.parse_codeowners(doc)
        assert [e.pattern for e in entries] == ["docs/"]


class TestResolution:
    def test_dir_rule_resolves_to_existing_dir(self, tmp_path):
        tree(tmp_path, "sdk/python/")
        doc = write(tmp_path, "CODEOWNERS", "sdk/python/ @team\n")
        assert gate.resolve_violations(doc, tmp_path) == []

    def test_dir_rule_typo_is_a_violation(self, tmp_path):
        tree(tmp_path, "sdk/python/")
        doc = write(tmp_path, "CODEOWNERS", "sdk/py/ @team\n")
        violations = gate.resolve_violations(doc, tmp_path)
        assert violations == ["sdk/py/"]

    def test_file_rule_resolves_to_existing_file(self, tmp_path):
        tree(tmp_path, "SECURITY.md")
        doc = write(tmp_path, "CODEOWNERS", "SECURITY.md @team\n")
        assert gate.resolve_violations(doc, tmp_path) == []

    def test_file_rule_dead_file_is_a_violation(self, tmp_path):
        doc = write(tmp_path, "CODEOWNERS", "SECURITY.md @team\n")
        assert gate.resolve_violations(doc, tmp_path) == ["SECURITY.md"]

    def test_glob_rule_matching_is_clean(self, tmp_path):
        tree(tmp_path, "Dockerfile", "requirements.txt")
        doc = write(tmp_path, "CODEOWNERS", "Dockerfile* @team\nrequirements*.txt @team\n")
        assert gate.resolve_violations(doc, tmp_path) == []

    def test_glob_rule_matching_nothing_is_a_violation(self, tmp_path):
        doc = write(tmp_path, "CODEOWNERS", "Dockerfile* @team\n")
        assert gate.resolve_violations(doc, tmp_path) == ["Dockerfile*"]

    def test_root_star_matches_root_files_only(self, tmp_path):
        tree(tmp_path, "README.md", "sub/README.md")
        doc = write(tmp_path, "CODEOWNERS", "*.md @team\n")
        # Single `*` must not cross directories (GitHub semantics): README.md
        # at the root matches, so the rule is clean regardless of sub/.
        assert gate.resolve_violations(doc, tmp_path) == []

    def test_double_star_is_recursive(self, tmp_path):
        tree(tmp_path, "sub/README.md")
        doc = write(tmp_path, "CODEOWNERS", "**.md @team\n")
        assert gate.resolve_violations(doc, tmp_path) == []

    def test_dead_dir_and_typo_reported_together(self, tmp_path):
        tree(tmp_path, "sdk/python/")
        doc = write(
            tmp_path, "CODEOWNERS", "sdk/py/ @team\nhub/apps/lineage/ @team\nsdk/python/ @team\n"
        )
        assert gate.resolve_violations(doc, tmp_path) == ["sdk/py/", "hub/apps/lineage/"]


class TestRealRepo:
    def test_real_codeowners_has_no_dead_paths(self):
        """The W18 incident class: the committed CODEOWNERS must resolve
        every path. The sdk/py typo, the unowned sdk/typescript, and the
        dead hub/apps/lineage were fixed in T.6 — this pin keeps them
        gone."""
        violations = gate.resolve_violations(REPO_ROOT / ".github" / "CODEOWNERS", REPO_ROOT)
        assert violations == [], violations

    def test_real_codeowners_owns_both_sdk_trees(self):
        entries = gate.parse_codeowners(REPO_ROOT / ".github" / "CODEOWNERS")
        patterns = {e.pattern for e in entries}
        assert "sdk/python/" in patterns
        assert "sdk/typescript/" in patterns
        assert "sdk/py/" not in patterns
