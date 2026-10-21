"""
Phase 216.1.4 — drift test: ``cli/tests/_persona_provisioning.py`` and
``sdk/python/tests/_persona_provisioning.py`` MUST be byte-identical.

Same doctrine as Phase 215's ``_mvp_gates_sync`` and Phase 216.X.8's
``_parse_bool_env_drift``. No shared module (D129), so we enforce identity
via this ast-level comparison.
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CLI_PATH = _REPO_ROOT / "cli" / "tests" / "_persona_provisioning.py"
_SDK_PATH = _REPO_ROOT / "sdk" / "python" / "tests" / "_persona_provisioning.py"


def test_persona_provisioning_files_are_byte_identical():
    """CLI and SDK _persona_provisioning.py must be byte-identical."""
    cli_bytes = _CLI_PATH.read_bytes()
    sdk_bytes = _SDK_PATH.read_bytes()
    assert cli_bytes == sdk_bytes, (
        f"cli/tests/_persona_provisioning.py and "
        f"sdk/python/tests/_persona_provisioning.py have diverged. "
        f"They must be byte-identical (D129 doctrine). "
        f"CLI: {len(cli_bytes)} bytes, SDK: {len(sdk_bytes)} bytes."
    )


def test_persona_provisioning_parses_as_valid_python():
    """Both files must be valid Python (catches truncation/corruption)."""
    for path in (_CLI_PATH, _SDK_PATH):
        source = path.read_text()
        tree = ast.parse(source, filename=str(path))
        # Must contain the PersonaCredentials class and provision_persona function
        names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.ClassDef))
        }
        assert "PersonaCredentials" in names, f"{path} missing PersonaCredentials class"
        assert "provision_persona" in names, f"{path} missing provision_persona function"
