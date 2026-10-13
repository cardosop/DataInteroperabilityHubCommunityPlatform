"""
Contract tests for scripts/check_tag_archive_manifest.py (oss-release-remediation
W0.6, GATE-52).

The committed manifest (docs/audits/tag-archive-manifest-2026-10-06.md)
must:

- exist and carry the mandated sections — the archive destination (bucket
  name REDACTED per W0.9), the 17 canonical tag-tree rows and the 19
  canonical backup-directory rows, each with a sha256 + `verified: yes` +
  `deleted: yes` — the gate is HONEST: any row not fully resolved fails
  it (the GATE-51 precedent — a gate that tolerates PENDING is vacuous);
- be backed by the W0.6 gitignore entries (`*.key`, `*.pem`,
  `infrastructure/staging/secrets/`) and the BLOCKING pre-commit gitleaks
  hook (no `exit 0` fallback on a missing binary — the W0.2 vacuity
  class);
- carry no TBD/TODO placeholders.

Plus the Makefile wiring pin: GATE-52 runs in ``quality-gates`` after
the credential-rotation gate.
"""

import importlib.util
import re
import sys
from pathlib import Path

import pytest

scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

script_path = scripts_dir / "check_tag_archive_manifest.py"
spec = importlib.util.spec_from_file_location("check_tag_archive_manifest", script_path)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

ROOT = scripts_dir.parent
MAKEFILE = ROOT / "Makefile"

TAG_NAMES = tuple(check.TAG_NAMES)
BACKUP_NAMES = tuple(check.BACKUP_NAMES)


def _row(
    name: str,
    commit: str | None = None,
    verified: str = "yes",
    deleted: str = "yes",
    sha: str = "a" * 64,
) -> str:
    commit_part = f" — commit {commit}" if commit else ""
    return (
        f"- {name}{commit_part} — key k/{name} — sha256 {sha} — "
        f"size 1 — ETag etag — verified: {verified} — deleted: {deleted}"
    )


def _record() -> str:
    tag_rows = "\n".join(_row(name, commit="3690717a8") for name in TAG_NAMES)
    backup_rows = "\n".join(_row(name) for name in BACKUP_NAMES)
    return (
        "# Tag Archive Manifest\n\n"
        "## Archive destination\n\n"
        "- the staging MinIO bucket (name length 17 — redacted)\n\n"
        "## Tag trees\n\n"
        f"{tag_rows}\n\n"
        "## Backup directories\n\n"
        f"{backup_rows}\n"
    )


@pytest.fixture
def record_file(tmp_path):
    path = tmp_path / "tag-archive-manifest-2026-10-06.md"
    path.write_text(_record())
    return path


def _run(record):
    return check.check(record)


class TestRecordContract:
    def test_valid_record_passes(self, record_file):
        assert _run(record_file) == []

    def test_missing_record_fails(self, tmp_path):
        problems = _run(tmp_path / "none.md")
        assert any("missing" in p for p in problems)

    @pytest.mark.parametrize(
        "section",
        ["## Archive destination", "## Tag trees", "## Backup directories"],
    )
    def test_missing_section_fails(self, record_file, section):
        record_file.write_text(_record().replace(section, "## Other"))
        problems = _run(record_file)
        assert any(section in p for p in problems)

    @pytest.mark.parametrize("name", TAG_NAMES[:4])
    def test_missing_tag_row_fails(self, record_file, name):
        record_file.write_text(_record().replace(_row(name, commit="3690717a8"), ""))
        problems = _run(record_file)
        assert any(name in p for p in problems)

    @pytest.mark.parametrize("name", BACKUP_NAMES[:4])
    def test_missing_backup_row_fails(self, record_file, name):
        record_file.write_text(_record().replace(_row(name), ""))
        problems = _run(record_file)
        assert any(name in p for p in problems)

    def test_unverified_row_fails_the_honest_gate(self, record_file):
        record_file.write_text(_record().replace("verified: yes", "verified: no", 1))
        problems = _run(record_file)
        assert any("verified" in p for p in problems)

    def test_undeleted_row_fails_the_honest_gate(self, record_file):
        record_file.write_text(_record().replace("deleted: yes", "deleted: no", 1))
        problems = _run(record_file)
        assert any("deleted" in p for p in problems)

    def test_missing_sha256_fails(self, record_file):
        record_file.write_text(_record().replace("sha256 " + "a" * 64, "sha256 x", 1))
        problems = _run(record_file)
        assert any("sha256" in p for p in problems)

    def test_placeholder_fails(self, record_file):
        record_file.write_text(_record().replace("redacted", "TODO"))
        problems = _run(record_file)
        assert any("TODO" in p for p in problems)


class TestGitignoreAndHookPins:
    def test_real_gitignore_and_hook_pass(self):
        # The checker reads the REAL .gitignore + .pre-commit-config.yaml;
        # the planted-removal variants below prove these pins are not
        # vacuous.
        assert check._gitignore_problems() == []
        assert check._hook_problems() == []

    def test_planted_gitignore_removal_flips_the_pin(self, tmp_path):
        fake = tmp_path / ".gitignore"
        fake.write_text("*.key\n*.pem\ninfrastructure/staging/secrets/\n")
        problems = check._gitignore_problems_for(fake)
        assert problems == []
        fake.write_text("*.key\n*.pem\n")
        problems = check._gitignore_problems_for(fake)
        assert any("staging/secrets" in p for p in problems)

    def test_blocking_hook_entry_is_required(self, tmp_path):
        fake = tmp_path / "pre-commit.yaml"
        fake.write_text(
            "- id: gitleaks\n"
            "  entry: bash -c 'command -v gitleaks || { echo missing; exit 1; }; "
            "gitleaks detect --source . --config .gitleaks.toml --redact --no-banner'\n"
        )
        assert check._hook_problems_for(fake) == []

    def test_exit_zero_hook_fallback_flips_the_pin(self, tmp_path):
        fake = tmp_path / "pre-commit.yaml"
        fake.write_text(
            "- id: gitleaks\n"
            "  entry: bash -c 'command -v gitleaks || { echo skipping; exit 0; }; "
            "gitleaks detect --source . --config .gitleaks.toml --redact --no-banner'\n"
        )
        problems = check._hook_problems_for(fake)
        assert any("exit 0" in p for p in problems)


class TestMainContract:
    def test_problems_exit_1(self, record_file, monkeypatch):
        record_file.write_text(_record().replace("verified: yes", "verified: no", 1))
        monkeypatch.setattr(
            sys, "argv", ["check_tag_archive_manifest.py", "--record", str(record_file)]
        )
        with pytest.raises(SystemExit) as exc_info:
            check.main()
        assert exc_info.value.code == 1

    def test_clean_exits_0(self, record_file, monkeypatch):
        monkeypatch.setattr(
            sys, "argv", ["check_tag_archive_manifest.py", "--record", str(record_file)]
        )
        with pytest.raises(SystemExit) as exc_info:
            check.main()
        assert exc_info.value.code == 0


def _quality_gates_recipe() -> list[str]:
    text = MAKEFILE.read_text()
    match = re.search(r"^quality-gates:.*\n((?:\t.*\n)+)", text, re.MULTILINE)
    assert match, "quality-gates target not found in Makefile"
    return list(match.group(1).splitlines())


class TestQualityGatesWiring:
    def test_gate52_wired_into_quality_gates(self):
        joined = "\n".join(_quality_gates_recipe())
        assert "check_tag_archive_manifest.py" in joined, "GATE-52 must run in quality-gates"

    def test_gate52_runs_after_the_rotation_gate(self):
        recipe = _quality_gates_recipe()
        gate51 = next(i for i, ln in enumerate(recipe) if "check_credential_rotation.py" in ln)
        gate52 = next(i for i, ln in enumerate(recipe) if "check_tag_archive_manifest.py" in ln)
        assert gate51 < gate52, "the tag-archive gate runs after GATE-51"
