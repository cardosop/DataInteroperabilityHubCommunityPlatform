"""
Contract tests for the mock-audit artifact hygiene (oss-release-remediation
W0.10).

``scripts/audit_mocks_stubs.py`` is diagnostic tooling whose run dumps a
7k-line JSON into the REPO ROOT (``mock_audit_results.json``) — untracked
litter that every session must remember not to commit (the G8
DO-NOT-COMMIT class). The generator must target an ephemeral location and
the repo root must stay clean:

1. the artifact does not exist in the repo root;
2. the generator's default output path is NOT the repo root (an
   ephemeral/system temp location), with the printed path telling the
   operator where the results landed.
"""

import importlib.util
import sys
from pathlib import Path

scripts_dir = Path(__file__).parent.parent
REPO_ROOT = scripts_dir.parent
sys.path.insert(0, str(scripts_dir))

script_path = scripts_dir / "audit_mocks_stubs.py"
spec = importlib.util.spec_from_file_location("audit_mocks_stubs", script_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_repo_root_carries_no_mock_audit_artifact():
    artifact = REPO_ROOT / "mock_audit_results.json"
    assert not artifact.exists(), (
        "mock_audit_results.json sits in the repo root — it is generated "
        "litter (the G8 DO-NOT-COMMIT class). Delete it and keep the "
        "generator pointed at an ephemeral location."
    )


class TestGeneratorTarget:
    def test_generator_default_output_is_not_the_repo_root(self):
        src = script_path.read_text()
        assert 'project_root / "mock_audit_results.json"' not in src, (
            "audit_mocks_stubs.py still writes its output into the repo "
            "root — point the default at an ephemeral/temp location so a "
            "diagnostic run can never litter the tree again."
        )
        assert "mock_audit_results.json" in src, (
            "the generator no longer names its artifact — the pin is vacuous"
        )
