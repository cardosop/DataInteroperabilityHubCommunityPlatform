"""TDD pins for the dev-only protocol oracle (openspec
add-delta-sharing-server task 5.6) — the `delta-sharing` package is a
DEV-ONLY dependency:

- ABSENT from every runtime requirement file (requirements.txt +
  requirements-core.txt) — the Hub's NATIVE server (5.3) is the runtime
  surface, never the reference package;
- DECLARED in requirements-dev.txt with the documented oracle role
  (P9 validates the native wire shapes against it);
- NEVER imported by a production module — an AST import scan over the
  production tree (the 2.9 denylist-scan convention); the 5.9 oracle
  validation imports it from the TEST side only;
- ABSENT from the runtime NOTICE tables (NOTICE.md + the public-overlay
  publish tree's NOTICE) — the published dependency sets no longer
  distribute it.

FILE-CONTENT contracts (the requirement files are the single source of
truth for installs) — no DB, no mocks.
"""

import ast
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]

RUNTIME_FILES = ("requirements.txt", "requirements-core.txt")
DEV_FILE = "requirements-dev.txt"
NOTICE_FILES = ("NOTICE.md", "scripts/publish_public_overlay/NOTICE.md")

_PKG_RE = re.compile(r"^delta-sharing", re.MULTILINE)
_DEV_ENTRY_RE = re.compile(r"^delta-sharing>=\d", re.MULTILINE)


def _declared_package_lines(name: str) -> list[str]:
    """The bare package-declaration lines in a requirement file."""
    return [
        line
        for line in (REPO_ROOT / name).read_text().splitlines()
        if re.match(r"^delta-sharing\b", line.strip())
    ]


class TestRuntimeRequirementIsolation:
    """The runtime requirement files never ship the package."""

    @pytest.mark.parametrize("name", RUNTIME_FILES)
    def test_the_package_is_absent_from_every_runtime_file(self, name):
        assert _declared_package_lines(name) == [], (
            f"{name} must not ship delta-sharing at runtime — the native "
            "server is the runtime surface"
        )

    def test_the_dev_file_declares_the_oracle_itself(self):
        # requirements-dev.txt includes -r requirements.txt; the package
        # must arrive through the dev file's OWN entry, not the include.
        text = (REPO_ROOT / DEV_FILE).read_text()
        assert _DEV_ENTRY_RE.search(text), (
            "requirements-dev.txt must declare delta-sharing as the dev-only oracle"
        )
        assert _declared_package_lines(DEV_FILE) == [
            line for line in text.splitlines() if re.match(r"^delta-sharing\b", line.strip())
        ], "exactly one declaration, in the dev file"

    def test_the_dev_entry_documents_the_oracle_role(self):
        text = (REPO_ROOT / DEV_FILE).read_text()
        block_start = max(
            index
            for index, line in enumerate(text.splitlines())
            if re.match(r"^delta-sharing\b", line.strip())
        )
        block = "\n".join(text.splitlines()[block_start - 4 : block_start + 1])
        assert "protocol oracle" in block.lower(), (
            "the dev entry must document the P9 protocol-oracle role"
        )
        assert "5.6" in block or "P9" in block, "the entry cites the spec task"


class TestNoProductionImports:
    """No production module imports the oracle — the native server is
    the only runtime surface (the 2.9 AST-scan convention)."""

    def test_no_production_module_imports_the_oracle(self):
        offenders: list[str] = []
        for root in (REPO_ROOT / "hub", REPO_ROOT / "cli"):
            for path in root.rglob("*.py"):
                relative = path.relative_to(REPO_ROOT)
                if "/tests/" in str(relative) or path.name.startswith("test_"):
                    continue
                try:
                    tree = ast.parse(path.read_text())
                except (SyntaxError, UnicodeDecodeError):
                    continue
                for node in ast.walk(tree):
                    imports_oracle = (
                        isinstance(node, ast.Import)
                        and any(alias.name == "delta_sharing" for alias in node.names)
                    ) or (isinstance(node, ast.ImportFrom) and node.module == "delta_sharing")
                    if imports_oracle:
                        offenders.append(str(relative))
        assert offenders == [], f"production modules must never import the oracle: {offenders}"


class TestRuntimeNoticeIsolation:
    """The runtime NOTICE tables no longer list the distributed package."""

    @pytest.mark.parametrize("name", NOTICE_FILES)
    def test_the_runtime_notice_no_longer_lists_the_package(self, name):
        text = (REPO_ROOT / name).read_text()
        assert not re.search(r"^\s*[-|]\s*`?delta-sharing`?\b", text, re.MULTILINE), (
            f"{name} must not attribute delta-sharing as a shipped dependency"
        )

    def test_the_runtime_notice_records_the_dev_only_move(self):
        # The attribution is kept honest: the root NOTICE documents that
        # the package lives in the dev requirements only.
        text = (REPO_ROOT / "NOTICE.md").read_text()
        assert "requirements-dev.txt" in text, (
            "NOTICE.md must record the dev-only move for the attribution trail"
        )
