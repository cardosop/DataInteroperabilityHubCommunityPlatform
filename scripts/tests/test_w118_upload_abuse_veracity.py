"""W11.8 (oss-release-remediation) — file-upload abuse veracity pins
(ASVS V12, register rows 3/14).

These pins keep the abuse suite HONEST (Django-free, CI no-django lint):

* **zip-bomb / zip-slip absence is PROVEN at the source level** — the
  non-test tree carries NO archive-extraction calls (``extractall`` /
  ``.extract(`` / ``unpack_archive`` / ``tarfile.open`` read modes);
  zip containers are REJECTED at the gates, never decompressed;
* the one read-side ``ZipFile`` (the exit-clause drill script) is
  pinned to ``namelist``/``read``-only usage;
* the production-deploy magic-byte posture is TRUE end-to-end — the
  settings default AND the helm value agree (the pre-fix helm shipped
  ``"false"`` while Python defaulted True — the W11.8 finding);
* the abuse suite exists and carries the named cells.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ABUSE_SUITE = REPO_ROOT / "hub" / "apps" / "files" / "tests" / "test_w118_upload_abuse.py"
REPLAY_SUITE = REPO_ROOT / "hub" / "apps" / "files" / "tests" / "test_presigned_replay_w112.py"
HELM_VALUES = REPO_ROOT / "helm" / "values.yaml"
SETTINGS = REPO_ROOT / "hub" / "settings.py"

_EXTRACT_CALLS = {"extractall", "unpack_archive"}
_EXCLUDED_PARTS = {"__pycache__", "migrations", "tests", "test_", ".venv", "venv", "site-packages"}


def _non_test_python_files() -> list[Path]:
    files = []
    for root_name in ("hub", "cli", "scripts", "services"):
        root = REPO_ROOT / root_name
        if not root.is_dir():
            continue
        files.extend(
            path
            for path in sorted(root.rglob("*.py"))
            if not (_EXCLUDED_PARTS & set(path.parts))
        )
    return files


def test_no_archive_extraction_anywhere_in_the_non_test_tree():
    """The zip-bomb/zip-slip class dies at the source: no extraction
    call exists anywhere in non-test code (a future extractor flips
    this RED and must ship with member-name + size/ratio guards)."""
    offenders: list[str] = []
    for path in _non_test_python_files():
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr in _EXTRACT_CALLS:
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno} {func.attr}")
                if isinstance(func, ast.Attribute) and func.attr == "extract":
                    # ZipFile.extract is the dangerous member-path write;
                    # unrelated ``.extract`` methods (e.g. OTel context
                    # propagation) are NOT archive extraction — require
                    # a zip-named receiver or a zip-mentioned source line.
                    line = source.splitlines()[node.lineno - 1] if node.lineno <= len(source.splitlines()) else ""
                    receiver = func.value.id if isinstance(func.value, ast.Name) else ""
                    if "zip" in receiver.lower() or "zip" in line.lower():
                        offenders.append(
                            f"{path.relative_to(REPO_ROOT)}:{node.lineno} .extract("
                        )
                if (
                    isinstance(func, ast.Attribute)
                    and func.attr == "open"
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "tarfile"
                ):
                    args = [ast.unparse(a) for a in node.args]
                    if any('"r' in a or "'r" in a for a in args):
                        offenders.append(
                            f"{path.relative_to(REPO_ROOT)}:{node.lineno} tarfile.open(read)"
                        )
    assert not offenders, "archive-extraction calls found:\n" + "\n".join(sorted(offenders))


def test_the_drill_script_zip_is_namelist_read_only():
    """The one read-side ZipFile (exit-clause drill) is pinned to
    namelist/read — never extraction, never filesystem writes."""
    path = REPO_ROOT / "scripts" / "run_exit_clause_drill.py"
    assert path.is_file(), "the exit-clause drill script must exist"
    source = path.read_text(encoding="utf-8")
    assert "zipfile.ZipFile" in source
    assert "extractall" not in source
    assert ".extract(" not in source


def test_helm_and_settings_magic_byte_posture_agree():
    """The production-deploy magic-byte posture is TRUE on BOTH trees
    (the pre-fix helm "false" silently disabled the gate)."""
    helm = HELM_VALUES.read_text(encoding="utf-8")
    match = re.search(r"MAGIC_BYTE_VALIDATION_ENABLED:\s*\"([^\"]+)\"", helm)
    assert match is not None, "helm must declare MAGIC_BYTE_VALIDATION_ENABLED"
    assert match.group(1) == "true", f"helm value must be true, got {match.group(1)!r}"

    settings = SETTINGS.read_text(encoding="utf-8")
    default = re.search(r"MAGIC_BYTE_VALIDATION_ENABLED = env\.bool\([^,]+,\s*default=(\w+)\)", settings)
    assert default is not None, "settings must declare the flag with a default"
    assert default.group(1) == "True", "settings default must be True"


def test_the_abuse_suite_exists_with_the_named_cells():
    assert ABUSE_SUITE.is_file(), "the W11.8 abuse suite must be committed"
    text = ABUSE_SUITE.read_text(encoding="utf-8")
    for marker in (
        "test_magic_byte_bypass_pe_as_csv_rejected_at_complete",
        "test_content_type_spoof_zip_as_csv_rejected",
        "test_unicode_overlong_and_rtl_names_roundtrip",
        "test_worker_inference_rejects_archive_extensions",
        "test_legacy_workflow_has_no_csv_default",
        "test_dataset_format_map_has_no_csv_default",
    ):
        assert marker in text, f"abuse suite missing {marker}"


def test_the_presigned_replay_suite_exists():
    assert REPLAY_SUITE.is_file(), "the W1.12 replay pins must be committed"
    text = REPLAY_SUITE.read_text(encoding="utf-8")
    assert "test_replay_put_after_completion_cannot_serve_as_clean" in text
    assert "test_completion_without_staging_object_fails_closed_in_production" in text


def test_staging_design_is_live_in_the_source():
    """The staging-key design (the W1.12 fix) is present in the live
    view + storage client — the pins are not green against a stub."""
    views = (REPO_ROOT / "hub" / "apps" / "files" / "views.py").read_text(encoding="utf-8")
    storage = (REPO_ROOT / "hub" / "apps" / "files" / "storage.py").read_text(encoding="utf-8")
    assert "upload_staging_key" in views
    assert "def copy_object" in storage
    assert 'code="STORAGE_COPY_FAILED"' in views
    assert 'code="FILE_OBJECT_MISSING"' in views
