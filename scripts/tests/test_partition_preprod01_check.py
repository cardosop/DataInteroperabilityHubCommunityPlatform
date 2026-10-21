"""
Unit tests for scripts/partition_preprod01_check.py (pilot-readiness task 1.1).

The checker classifies `git status --porcelain` lines so the preprod01 tree
partition is enforceable: run artefacts (batch logs, backups, report dirs,
stray files) must not be part of the ~3,000-file campaign diff, and every
remaining untracked file must look like real source/docs.
"""

from scripts.partition_preprod01_check import (
    ARTIFACT_ROOT_FILE_RE,
    IGNORED_ARTIFACT_PREFIXES,
    SOURCE_EXTENSIONS,
    classify_line,
    summarize,
)

# A porcelain line is "<XY> <path>" (renames carry " -> ").
OK = "?? "  # untracked
MOD = " M "  # modified, not staged


def lines(*specs):
    return "\n".join(f"{state}{path}" for state, path in specs)


class TestArtifactClassification:
    def test_batch_logs_flagged(self):
        for name in ("b12.txt", "b101a.txt", "f3.txt", "f8.txt"):
            line = f"?? {name}"
            kind, _msg = classify_line(line)
            assert kind == "artifacts", name

    def test_license_and_requirements_not_flagged(self):
        # These are tracked repo files — feed them in the modified state a
        # real `git status` would report (an untracked LICENSE.txt would be
        # genuinely suspicious and correctly lands in "unclassified").
        for name in ("LICENSE.txt", "requirements.txt", "requirements-core.txt"):
            kind, _msg = classify_line(f" M {name}")
            assert kind == "ok", name

    def test_backup_strays_and_probes_flagged(self):
        for path in (
            ".env.test.bak-181724",
            "OK",
            "testci.txt",
            "cilint.txt",
            "dlt-staging/something.parquet",
            "frontend/.ta002-probe.mjs",
        ):
            kind, _msg = classify_line(f"?? {path}")
            assert kind == "artifacts", path

    def test_tracked_report_dirs_flagged(self):
        for path in (
            "test_reports_e2e/foo.json",
            "test_reports_performance/bar.html",
            "test-results/results.json",
        ):
            for state in (MOD, OK):
                kind, _msg = classify_line(f"{state}{path}")
                assert kind == "artifacts", f"{state}{path}"

    def test_staged_deletion_of_artifacts_is_the_fix_not_a_violation(self):
        # `git rm --cached` leaves `D ` lines until the cleanup commit lands —
        # that state is the removal IN PROGRESS and must not block the gate.
        for path in (
            "test_reports_e2e/foo.json",
            "test-results/results.json",
        ):
            kind, _msg = classify_line(f"D  {path}")
            assert kind == "ok", path

    def test_source_files_pass(self):
        for path in (
            "hub/apps/assets/tests/test_x.py",
            "frontend/src/features/pricing/structuredData.ts",
            "docs/runbooks/PILOT_READINESS_PLAN.md",
            "openspec/changes/pilot-readiness/tasks.md",
            "scripts/check_batch_coverage.py",
        ):
            kind, _msg = classify_line(f"?? {path}")
            assert kind == "ok", path

    def test_unknown_extension_flagged_as_unclassified(self):
        kind, _msg = classify_line("?? mystery_file.xyz")
        assert kind == "unclassified"


class TestSummarize:
    def test_clean_snapshot_reports_zero(self):
        report = summarize(lines((OK, "hub/apps/example.py"), (MOD, "README.md")))
        assert report["artifacts"] == 0
        assert report["unclassified"] == 0

    def test_mixed_snapshot_counts_each_class(self):
        report = summarize(
            lines(
                (OK, "b12.txt"),
                (MOD, "test_reports_e2e/x.json"),
                (OK, "hub/apps/example.py"),
                (OK, "weird.bin"),
            )
        )
        assert report["artifacts"] == 2
        assert report["unclassified"] == 1
        assert report["ok"] == 1


class TestMainExitCode:
    def test_exit_one_when_artifacts_present(self, tmp_path, capsys):
        from scripts.partition_preprod01_check import main

        snapshot = tmp_path / "porcelain.txt"
        snapshot.write_text("?? b12.txt\n M hub/apps/example.py\n", encoding="utf-8")
        assert main(["partition_preprod01_check.py", str(snapshot)]) == 1

    def test_exit_zero_on_clean_snapshot(self, tmp_path, capsys):
        from scripts.partition_preprod01_check import main

        snapshot = tmp_path / "porcelain.txt"
        snapshot.write_text("?? hub/apps/example.py\n M README.md\n", encoding="utf-8")
        assert main(["partition_preprod01_check.py", str(snapshot)]) == 0


class TestRulesConstants:
    def test_artifact_patterns_are_root_anchored(self):
        # Root-anchored: only root-level batch logs count, not nested ones.
        assert ARTIFACT_ROOT_FILE_RE.match("b12.txt")
        assert not ARTIFACT_ROOT_FILE_RE.match("hub/b12.txt")
        assert not ARTIFACT_ROOT_FILE_RE.match("LICENSE.txt")

    def test_ignored_prefixes_cover_artefact_families(self):
        assert "test_reports_e2e/" in IGNORED_ARTIFACT_PREFIXES
        assert "test-results/" in IGNORED_ARTIFACT_PREFIXES

    def test_source_extensions_cover_repo_conventions(self):
        for ext in (".py", ".ts", ".tsx", ".md", ".yaml", ".yml", ".sh", ".toml"):
            assert ext in SOURCE_EXTENSIONS, ext
