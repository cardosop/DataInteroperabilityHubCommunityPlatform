"""W6.1 (oss-release-remediation, D3 amended) — publish-wiring pins.

TDD contract, no mocks: every pin reads the REAL artifacts (package
metadata, the publish workflow, the regenerate script) and asserts the
D3-amended publish model:

  * the handwritten packages are the publish surface
    (sdk/python → `datahub-interoperability`, sdk/js →
    `@meshant/interoperability-sdk` [W6.0 amendment], cli → `datahub-cli`);
  * the namespace collision is resolved at the SOURCE — the generated-py
    pipeline must never again emit `packageName=datahub_interoperability`
    (the handwritten module's import namespace);
  * the CI publish workflow drives the handwritten packages through
    `twine check` / `npm pack --dry-run` and never publishes the retired
    generated artifacts (`sdk/typescript`, `sdk/python_generated`);
  * the three packages are version-consistent.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SDK_PY = REPO_ROOT / "sdk" / "python"
SDK_JS = REPO_ROOT / "sdk" / "js"
CLI = REPO_ROOT / "cli"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "sdk-release.yml"
REGEN_PY = REPO_ROOT / "scripts" / "regenerate_python_sdk.sh"

D3_PYPI_NAMES = {"datahub-interoperability": SDK_PY, "datahub-cli": CLI}
D3_NPM_NAME = "@meshant/interoperability-sdk"  # W6.0 amendment (org @datahub third-party)


def _package_version(pkg_dir: Path) -> str:
    if (pkg_dir / "pyproject.toml").exists():
        text = (pkg_dir / "pyproject.toml").read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("version ="):
                return stripped.split("=", 1)[1].strip().strip('"')
    if (pkg_dir / "setup.py").exists():
        # The truthful source: setup.py delegates to <pkg>/__init__.__version__.
        setup_text = (pkg_dir / "setup.py").read_text(encoding="utf-8")
        init_files = list(pkg_dir.glob("*[!_test]/__init__.py"))
        if not init_files and (pkg_dir / "__init__.py").exists():
            init_files = [pkg_dir / "__init__.py"]
        for init_file in init_files:
            init_text = init_file.read_text(encoding="utf-8")
            for line in init_text.splitlines():
                stripped = line.strip()
                if stripped.startswith('__version__'):
                    return stripped.split("=", 1)[1].strip().strip('"').strip("'")
        raise AssertionError(f"no __version__ found under {pkg_dir} (setup.py: {setup_text[:80]!r})")
    raise AssertionError(f"no version found in {pkg_dir}")


def test_handwritten_python_packages_declare_the_d3_names():
    pyproject = (SDK_PY / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "datahub-interoperability"' in pyproject

    setup_py = (CLI / "setup.py").read_text(encoding="utf-8")
    assert 'name="datahub-cli"' in setup_py


def test_js_package_declares_the_amended_meshant_scope():
    """W6.0 amendment: the @datahub org is third-party-owned — the npm
    package publishes under @meshant (org registered + verified live)."""
    pkg = json.loads((SDK_JS / "package.json").read_text(encoding="utf-8"))
    assert pkg["name"] == D3_NPM_NAME


def test_js_publish_docs_carry_no_stale_datahub_scope():
    """PUBLISH.md/README.md must not instruct installing from the
    impossible @datahub scope."""
    publish = (SDK_JS / "PUBLISH.md").read_text(encoding="utf-8")
    readme = (SDK_JS / "README.md").read_text(encoding="utf-8")
    for text in (publish, readme):
        assert "@datahub" not in text
        assert "@meshant/interoperability-sdk" in text


def test_generated_py_pipeline_no_longer_collides_with_the_handwritten_module():
    """The generated-py pipeline emitted packageName=datahub_interoperability —
    the SAME import namespace as the handwritten sdk/python package. Two
    installed packages clobbering one module is the collision D3 named."""
    script = REGEN_PY.read_text(encoding="utf-8")
    assert "packageName=datahub_interoperability" not in script
    # The retired generator keeps a NON-colliding namespace if anyone runs it.
    assert "packageName=datahub_generated_sdk" in script


def test_workflow_publishes_the_handwritten_packages_only():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    # The three handwritten packages are the publish surface.
    assert "working-directory: sdk/python" in workflow
    assert "working-directory: sdk/js" in workflow
    assert "working-directory: cli" in workflow
    # The retired generated artifacts are OUT of the publish path — no
    # step may target them as a working directory (the header comment
    # names them to document WHY; physical deletion of sdk/typescript
    # is W12.1 per D3).
    assert "working-directory: sdk/python_generated" not in workflow
    assert "working-directory: sdk/typescript" not in workflow
    assert "regenerate_typescript_sdk.sh" not in workflow
    assert "regenerate_python_sdk.sh" not in workflow


def test_workflow_runs_the_d3_dry_run_gates():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "twine check" in workflow
    assert "npm pack" in workflow
    # Dry-run remains the default dispatch mode (never publish by accident).
    assert "dry_run" in workflow
    assert "default: true" in workflow


def test_three_packages_are_version_consistent():
    versions = {
        "sdk/python": _package_version(SDK_PY),
        "sdk/js": json.loads((SDK_JS / "package.json").read_text(encoding="utf-8"))["version"],
        "cli": _package_version(CLI),
    }
    assert len(set(versions.values())) == 1, f"version drift: {versions}"


def test_cli_entry_point_matches_the_published_console_script():
    setup_py = (CLI / "setup.py").read_text(encoding="utf-8")
    # The shipped console script: `datahub` → datahub_cli.main:main.
    assert "entry_points" in setup_py
    assert "datahub=datahub_cli.main:main" in setup_py


def test_sdk_python_build_metadata_is_single_sourced():
    """The W6.1 drill found the sdk/python wheel build BROKEN: setup.py read
    requirements.txt with a CWD-relative path (FileNotFoundError inside the
    isolated sdist build) and its install_requires/extras_require clobbered
    pyproject's (already drifting: black>=23 vs >=26). The build metadata
    now lives in pyproject alone — pin that the dual-config drift cannot
    return."""
    setup_py = (SDK_PY / "setup.py").read_text(encoding="utf-8")
    assert "requirements.txt" not in setup_py
    assert "install_requires" not in setup_py
    assert "extras_require" not in setup_py

    pyproject = (SDK_PY / "pyproject.toml").read_text(encoding="utf-8")
    assert 'license = "MIT"' in pyproject
    assert "License :: OSI Approved" not in pyproject  # PEP 639 superseded


def test_js_package_has_no_axios_dependency():
    """W6.2 (R2-X2) — axios evicted: the client is implemented on the
    platform fetch API.  This pin was xfailed (TICKET=W62-axios-eviction)
    until W6.2 landed; the public npm publish gate is now green."""
    pkg = json.loads((SDK_JS / "package.json").read_text(encoding="utf-8"))
    assert "axios" not in pkg.get("dependencies", {})
    # The retired openapi-generator devDependency transitively pulled
    # axios too — removed alongside (the generator left the publish
    # path in W6.1).
    assert "axios" not in pkg.get("devDependencies", {})
    client = (SDK_JS / "src" / "client.ts").read_text(encoding="utf-8")
    # No import/require of axios (comments may name it for history).
    assert "from 'axios'" not in client
    assert 'require("axios")' not in client
    assert "require('axios')" not in client
    # The resolved dependency tree must not carry axios at all.
    lockfile = (SDK_JS / "package-lock.json").read_text(encoding="utf-8")
    assert "axios" not in lockfile
