"""
W6.4 (oss-release-remediation) — docs dedup pins.

The pre-fix tree maintained the SAME five topic guides twice —
`cli/docs/*.md` and `sdk/python/docs/*.md` — diverging freely (the
MARKETPLACE pair alone drifted by ~1.6k diff lines). The W6.4 contract:
the SDK copies are canonical; the CLI copies are command references
that POINT at the canonical guide and keep only the CLI command
examples.
"""

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TOPICS = ["BAAS_USAGE", "MARKETPLACE_USAGE", "MODEL_SERVING_USAGE", "ODH_USAGE", "ODPS_USAGE"]


@pytest.mark.parametrize("topic", TOPICS)
def test_cli_doc_points_at_the_sdk_canonical(topic):
    cli_doc = (REPO / "cli" / "docs" / f"{topic}.md").read_text()
    assert f"../../sdk/python/docs/{topic}.md" in cli_doc
    # The command reference keeps the actual CLI commands (not just a pointer).
    assert "datahub " in cli_doc


@pytest.mark.parametrize("topic", TOPICS)
def test_sdk_canonical_exists_and_is_rich(topic):
    sdk_doc = REPO / "sdk" / "python" / "docs" / f"{topic}.md"
    assert sdk_doc.exists()
    assert len(sdk_doc.read_text().splitlines()) > 200


class TestPerPackageChangelogs:
    """W6.4 — every published package carries a Keep-a-Changelog file
    whose latest version matches the package's own version."""

    @pytest.mark.parametrize(
        ("changelog", "version_source"),
        [
            ("cli/CHANGELOG.md", "cli/datahub_cli/__init__.py"),
            ("sdk/python/CHANGELOG.md", "sdk/python/pyproject.toml"),
            ("sdk/js/CHANGELOG.md", "sdk/js/package.json"),
        ],
    )
    def test_changelog_exists_with_matching_version(self, changelog, version_source):
        changelog = REPO / changelog
        assert changelog.exists(), changelog
        text = changelog.read_text()
        assert "Keep a Changelog" in text
        assert "## [Unreleased]" in text

        import re

        source = (REPO / version_source).read_text()
        match = re.search(r'version["\': =]*([0-9]+\.[0-9]+\.[0-9]+)', source)
        if not match:
            match = re.search(r'__version__\s*=\s*["\']([0-9.]+)', source)
        assert match, version_source
        assert f"## [{match.group(1)}]" in text


@pytest.mark.parametrize("topic", TOPICS)
def test_cli_doc_is_a_reference_not_a_duplicate(topic):
    cli_lines = (REPO / "cli" / "docs" / f"{topic}.md").read_text().splitlines()
    sdk_lines = (REPO / "sdk" / "python" / "docs" / f"{topic}.md").read_text().splitlines()
    # The reference must be meaningfully smaller than the canonical guide.
    assert len(cli_lines) < len(sdk_lines)
