"""TDD pins for ``check_time_sleep_in_tests.py`` — GATE-05 (close-test-coverage-gaps 8.2).

The gate counts ``time.sleep(`` occurrences in test files, with the
``# noqa: sleep-needed`` escape hatch. These pins lock the scanner's
semantics:

- REAL call sites count (annotated and unannotated),
- the noqa annotation works on the call's line AND the previous line,
- comment / docstring / string-literal MENTIONS of ``time.sleep(`` are
  NOT call sites — the pre-8.2 line-regex counted docstring mentions as
  calls, which pushed the tree over the max with three false positives
  (test_idempotency_error_handling.py:101, test_sync_job_models.py:493,
  test_job_monitoring_observability_validation.py:12). A regression back
  to line-regex counting fails these pins.

No mocks — every pin runs real text through the real scanner.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

import check_time_sleep_in_tests as gate  # type: ignore[import-not-found]  # runtime sys.path injection

check_file = gate.check_file


def _write(tmp_path: Path, content: str) -> str:
    p = tmp_path / "sample_test.py"
    p.write_text(content, encoding="utf-8")
    return str(p)


def test_real_sleep_call_counts_unannotated(tmp_path):
    path = _write(tmp_path, "import time\n\ndef test_x():\n    time.sleep(0.1)\n")
    total, unannotated = check_file(path)
    assert (total, unannotated) == (1, 1)


def test_noqa_on_same_line_annotates(tmp_path):
    path = _write(
        tmp_path,
        "import time\n\n"
        "def test_x():\n"
        "    time.sleep(0.1)  # noqa: sleep-needed  # INTENTIONAL: pacing\n",
    )
    total, unannotated = check_file(path)
    assert (total, unannotated) == (1, 0)


def test_noqa_on_previous_line_annotates(tmp_path):
    path = _write(
        tmp_path,
        "import time\n\n"
        "def test_x():\n"
        "    # noqa: sleep-needed  # INTENTIONAL: pacing\n"
        "    time.sleep(0.1)\n",
    )
    total, unannotated = check_file(path)
    assert (total, unannotated) == (1, 0)


def test_comment_mention_is_not_a_call_site(tmp_path):
    path = _write(
        tmp_path, "# an example: time.sleep(1) is discouraged here\n\ndef test_x():\n    pass\n"
    )
    total, unannotated = check_file(path)
    assert (total, unannotated) == (0, 0)


def test_multiline_docstring_mention_is_not_a_call_site(tmp_path):
    path = _write(
        tmp_path,
        '"""Module docstring: prefer polling over time.sleep(1).\n\n'
        "The second line keeps the docstring open for this example.\n"
        '"""\n'
        "\n"
        "def test_x():\n"
        "    pass\n",
    )
    total, unannotated = check_file(path)
    assert (total, unannotated) == (0, 0)


def test_single_line_docstring_mention_is_not_a_call_site(tmp_path):
    path = _write(
        tmp_path,
        'def test_x():\n    """Uses polling to avoid time.sleep(1)."""\n    pass\n',
    )
    total, unannotated = check_file(path)
    assert (total, unannotated) == (0, 0)


def test_string_literal_mention_is_not_a_call_site(tmp_path):
    path = _write(
        tmp_path,
        "def test_x():\n"
        '    example = "a caller must not literally write time.sleep(1) here"\n'
        "    assert example\n",
    )
    total, unannotated = check_file(path)
    assert (total, unannotated) == (0, 0)


def test_real_call_inside_a_docstring_line_is_ignored_but_adjacent_call_counts(tmp_path):
    path = _write(
        tmp_path,
        "import time\n\n"
        "def test_x():\n"
        '    """Docs mention time.sleep(9) as text."""\n'
        "    time.sleep(0.1)\n",
    )
    total, unannotated = check_file(path)
    assert (total, unannotated) == (1, 1)


def test_syntax_error_file_counts_nothing(tmp_path):
    path = _write(tmp_path, "def broken(:\n    time.sleep(0.1)\n")
    total, unannotated = check_file(path)
    assert (total, unannotated) == (0, 0)


def test_missing_file_counts_nothing(tmp_path):
    total, unannotated = check_file(str(tmp_path / "does-not-exist.py"))
    assert (total, unannotated) == (0, 0)
