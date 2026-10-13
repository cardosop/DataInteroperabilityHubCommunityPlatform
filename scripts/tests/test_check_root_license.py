"""
Contract tests for scripts/check_root_license.py (oss-release-remediation
W0.1, GATE-48).

The root license gate must keep the D1 licensing decision enforced:

- LICENSE.txt is the canonical Apache-2.0 text (the proprietary text or
  any edit to the canonical wording fails);
- NOTICE.md exists and carries the product line, a Meshant copyright
  line, and the third-party attributions section (Apache 2.0 §4(d));
- every SDK/CLI package ships an MIT LICENSE file (sdk/python, sdk/js,
  cli — the package metadata that references them must not dangle);
- SDK/CLI package metadata stays MIT (pyproject, package.json, setup.py);
- no API metadata source declares the old Proprietary license
  (openapi_validation.py / openapi_enhancement.py) and the frontend
  package declares Apache-2.0.

Plus wiring pins: the CI license-scan workflow runs the same script
(no drift between the local gate and CI), and GATE-48 runs in
``quality-gates`` after the decisions gate.
"""

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest
import yaml

scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

script_path = scripts_dir / "check_root_license.py"
spec = importlib.util.spec_from_file_location("check_root_license", script_path)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

ROOT = scripts_dir.parent
MAKEFILE = ROOT / "Makefile"
WORKFLOW = ROOT / ".github/workflows/license-scan.yml"

PROPRIETARY = (
    "Meshant Data Interoperability Hub\n"
    "Copyright (c) 2026 Meshant\n\n"
    "This software is proprietary. All rights reserved.\n"
    "See NOTICE.md for third-party attributions.\n"
)

MIT_TEXT = (
    "Copyright (c) 2026 Meshant contributors\n\n"
    "Permission is hereby granted, free of charge, to any person obtaining a "
    "copy\n"
    'of this software and associated documentation files (the "Software"), '
    "to deal\n"
    "in the Software without restriction, including without limitation the "
    "rights\n"
    "to use, copy, modify, merge, publish, distribute, sublicense, and/or "
    "sell\n"
    "copies of the Software, and to permit persons to whom the Software is\n"
    "furnished to do so, subject to the following conditions:\n\n"
    "The above copyright notice and this permission notice shall be included "
    "in all\n"
    "copies or substantial portions of the Software.\n\n"
    'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, '
    "EXPRESS OR\n"
    "IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF "
    "MERCHANTABILITY,\n"
    "FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL "
    "THE\n"
    "AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\n"
    "LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING "
    "FROM,\n"
    "OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN "
    "THE\n"
    "SOFTWARE.\n"
)

NOTICE = (
    "# NOTICE\n\n"
    "Data Interoperability Hub\n"
    "Copyright 2026 Meshant contributors\n\n"
    "## Third-party attributions\n\n"
    "| Library | License |\n"
    "|---|---|\n"
    "| example-lib | MIT |\n"
)


def _write(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def _root(tmp_path, mutate=None):
    """A valid W0.1 tree; mutate is a callable receiving the root path."""
    _write(tmp_path, "LICENSE.txt", check.APACHE_2_0_TEXT)
    _write(tmp_path, "NOTICE.md", NOTICE)
    _write(tmp_path, "sdk/python/LICENSE", MIT_TEXT)
    _write(tmp_path, "sdk/js/LICENSE", MIT_TEXT)
    _write(tmp_path, "cli/LICENSE", MIT_TEXT)
    _write(tmp_path, "sdk/python/pyproject.toml", 'license = {text = "MIT"}\n')
    _write(tmp_path, "sdk/js/package.json", json.dumps({"license": "MIT"}))
    _write(
        tmp_path,
        "cli/setup.py",
        'classifiers=["License :: OSI Approved :: MIT License"]\n',
    )
    _write(
        tmp_path,
        "hub/apps/api/openapi_validation.py",
        'license = {"name": "Apache-2.0"}\n',
    )
    _write(
        tmp_path,
        "hub/apps/api/openapi_enhancement.py",
        'license = {"name": "Apache-2.0", "url": "https://www.apache.org/licenses/LICENSE-2.0"}\n',
    )
    _write(tmp_path, "frontend/package.json", json.dumps({"license": "Apache-2.0"}))
    if mutate:
        mutate(tmp_path)
    return tmp_path


def test_valid_tree_passes(tmp_path):
    problems = check.check(_root(tmp_path))
    assert problems == []


def test_missing_license_fails(tmp_path):
    problems = check.check(
        _root(tmp_path, mutate=lambda r: (r / "LICENSE.txt").unlink())
    )
    assert any("LICENSE.txt" in p and "missing" in p for p in problems)


def test_proprietary_license_fails(tmp_path):
    problems = check.check(
        _root(tmp_path, mutate=lambda r: _write(r, "LICENSE.txt", PROPRIETARY))
    )
    assert any("Apache-2.0" in p and "LICENSE.txt" in p for p in problems)


def test_edited_apache_text_fails(tmp_path):
    problems = check.check(
        _root(
            tmp_path,
            mutate=lambda r: _write(
                r,
                "LICENSE.txt",
                check.APACHE_2_0_TEXT.replace(
                    "Version 2.0, January 2004", "Version 2.1, January 2026"
                ),
            ),
        )
    )
    assert any("Apache-2.0" in p for p in problems)


def test_missing_notice_fails(tmp_path):
    problems = check.check(_root(tmp_path, mutate=lambda r: (r / "NOTICE.md").unlink()))
    assert any("NOTICE.md" in p and "missing" in p for p in problems)


def test_notice_without_copyright_line_fails(tmp_path):
    problems = check.check(
        _root(
            tmp_path,
            mutate=lambda r: _write(
                r,
                "NOTICE.md",
                NOTICE.replace("Copyright 2026 Meshant contributors\n", ""),
            ),
        )
    )
    assert any("copyright" in p for p in problems)


def test_notice_without_attributions_fails(tmp_path):
    problems = check.check(
        _root(
            tmp_path,
            mutate=lambda r: _write(
                r,
                "NOTICE.md",
                NOTICE.replace("## Third-party attributions", "## Notes"),
            ),
        )
    )
    assert any("attributions" in p for p in problems)


@pytest.mark.parametrize(
    "path", ["sdk/python/LICENSE", "sdk/js/LICENSE", "cli/LICENSE"]
)
def test_missing_sdk_license_fails(tmp_path, path):
    problems = check.check(_root(tmp_path, mutate=lambda r: (r / path).unlink()))
    assert any(path in p and "missing" in p for p in problems)


@pytest.mark.parametrize(
    "path", ["sdk/python/LICENSE", "sdk/js/LICENSE", "cli/LICENSE"]
)
def test_non_mit_sdk_license_fails(tmp_path, path):
    problems = check.check(
        _root(tmp_path, mutate=lambda r: _write(r, path, "GPL-3.0 — you may not.\n"))
    )
    assert any(path in p and "MIT" in p for p in problems)


def test_pyproject_license_drift_fails(tmp_path):
    problems = check.check(
        _root(
            tmp_path,
            mutate=lambda r: _write(
                r, "sdk/python/pyproject.toml", 'license = {text = "GPL-3.0"}\n'
            ),
        )
    )
    assert any("pyproject.toml" in p and "MIT" in p for p in problems)


def test_js_package_license_drift_fails(tmp_path):
    problems = check.check(
        _root(
            tmp_path,
            mutate=lambda r: _write(
                r, "sdk/js/package.json", json.dumps({"license": "UNLICENSED"})
            ),
        )
    )
    assert any("package.json" in p and "MIT" in p for p in problems)


def test_cli_classifier_drift_fails(tmp_path):
    problems = check.check(
        _root(
            tmp_path,
            mutate=lambda r: _write(
                r,
                "cli/setup.py",
                'classifiers=["License :: OSI Approved :: GPL License"]\n',
            ),
        )
    )
    assert any("cli/setup.py" in p and "MIT" in p for p in problems)


def test_openapi_proprietary_declaration_fails(tmp_path):
    problems = check.check(
        _root(
            tmp_path,
            mutate=lambda r: _write(
                r,
                "hub/apps/api/openapi_validation.py",
                'license = {"name": "Proprietary"}\n',
            ),
        )
    )
    assert any("Proprietary" in p and "openapi_validation" in p for p in problems)


def test_frontend_license_drift_fails(tmp_path):
    problems = check.check(
        _root(
            tmp_path,
            mutate=lambda r: _write(
                r, "frontend/package.json", json.dumps({"license": "UNLICENSED"})
            ),
        )
    )
    assert any("frontend/package.json" in p and "Apache-2.0" in p for p in problems)


def test_default_paths_exist():
    assert (ROOT / "LICENSE.txt").exists()
    assert (ROOT / "NOTICE.md").exists()
    assert (ROOT / "sdk/python/LICENSE").exists()
    assert (ROOT / "sdk/js/LICENSE").exists()
    assert (ROOT / "cli/LICENSE").exists()


class TestMainContract:
    def test_problems_exit_1(self, tmp_path, monkeypatch):
        root = _root(tmp_path)
        (root / "LICENSE.txt").unlink()
        monkeypatch.setattr(sys, "argv", ["check_root_license.py", "--root", str(root)])
        with pytest.raises(SystemExit) as exc_info:
            check.main()
        assert exc_info.value.code == 1

    def test_clean_exits_0(self, tmp_path, monkeypatch):
        root = _root(tmp_path)
        monkeypatch.setattr(sys, "argv", ["check_root_license.py", "--root", str(root)])
        with pytest.raises(SystemExit) as exc_info:
            check.main()
        assert exc_info.value.code == 0


class TestLicenseScanWorkflow:
    """The CI workflow must run the SAME script the local gate runs."""

    def _steps(self):
        workflow = yaml.safe_load(WORKFLOW.read_text())
        steps = []
        for job in workflow["jobs"].values():
            steps.extend(job.get("steps", []))
        return steps

    def test_workflow_runs_root_license_gate(self):
        runs = [
            step.get("run", "")
            for step in self._steps()
            if isinstance(step.get("run"), str)
        ]
        assert any(
            "check_root_license.py" in run for run in runs
        ), "license-scan.yml must run scripts/check_root_license.py"

    def test_workflow_paths_include_license_files(self):
        workflow = yaml.safe_load(WORKFLOW.read_text())
        # PyYAML's YAML 1.1 semantics parse the workflow key `on` as the
        # boolean True — GitHub Actions YAML quirk.
        trigger = workflow.get(True) or workflow.get("on", {})
        paths = trigger["pull_request"]["paths"]
        assert "LICENSE.txt" in paths
        assert "NOTICE.md" in paths
        assert "scripts/check_root_license.py" in paths


def _quality_gates_recipe() -> list[str]:
    text = MAKEFILE.read_text()
    match = re.search(r"^quality-gates:.*\n((?:\t.*\n)+)", text, re.MULTILINE)
    assert match, "quality-gates target not found in Makefile"
    return list(match.group(1).splitlines())


class TestQualityGatesWiring:
    def test_gate48_wired_into_quality_gates(self):
        recipe = _quality_gates_recipe()
        joined = "\n".join(recipe)
        assert "check_root_license.py" in joined, "GATE-48 must run in quality-gates"

    def test_gate48_runs_after_the_decisions_gate(self):
        recipe = _quality_gates_recipe()
        gate47 = next(
            i for i, ln in enumerate(recipe) if "check_oss_decisions.py" in ln
        )
        gate48 = next(i for i, ln in enumerate(recipe) if "check_root_license.py" in ln)
        assert gate47 < gate48, "the license gate runs after the decisions gate"
