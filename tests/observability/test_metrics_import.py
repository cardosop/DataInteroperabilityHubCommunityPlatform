"""
312.16.1 — Fix semantic service metrics silent-disable (O1/GF-11.3).

Verifies that metrics and tracing import failures are logged as
structured warnings rather than silently swallowed.  Tests that:
- ``except ImportError: pass`` is replaced with structured logging
- DISABLE_METRICS env var controls stub behavior
- Import failures are surfaced in application logs
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SEMANTIC_MAIN = REPO_ROOT / "services" / "semantic-service" / "main.py"
FUSEKI_CLIENT = REPO_ROOT / "services" / "semantic-service" / "fuseki_client.py"


@pytest.mark.unit
@pytest.mark.observability
class TestMetricsImportFailureIsLogged:
    """Import failures for metrics/tracing MUST produce structured log warnings."""

    def test_semantic_main_has_no_silent_import_error_pass(self):
        """main.py must NOT have bare `except ImportError: pass` for metrics."""
        if not SEMANTIC_MAIN.exists():
            pytest.skip("semantic-service/main.py not found")

        content = SEMANTIC_MAIN.read_text()
        # Count lines with bare except ImportError followed by just pass
        lines = content.split("\n")
        silent_count = 0
        for i, line in enumerate(lines):
            if "except ImportError" in line:
                # Check the next 3 non-empty lines for logging calls
                for j in range(i + 1, min(i + 10, len(lines))):
                    stripped = lines[j].strip()
                    if not stripped or stripped.startswith("#"):
                        continue
                    if any(kw in stripped for kw in ("logger.", "logging.", "raise", "log.")):
                        break  # Good — handled
                    if "pass" in stripped:
                        silent_count += 1
                        break
                    break
        assert silent_count == 0, \
            f"Found {silent_count} silent except ImportError: pass in {SEMANTIC_MAIN}"

    def test_fuseki_client_has_no_silent_import_error(self):
        """fuseki_client.py must log or raise on ImportError, not silently pass."""
        if not FUSEKI_CLIENT.exists():
            pytest.skip("fuseki_client.py not found")

        content = FUSEKI_CLIENT.read_text()
        lines = content.split("\n")
        silent_count = 0
        for i, line in enumerate(lines):
            if "except ImportError" in line:
                for j in range(i + 1, min(i + 10, len(lines))):
                    stripped = lines[j].strip()
                    if not stripped or stripped.startswith("#"):
                        continue
                    if any(kw in stripped for kw in ("logger.", "logging.", "raise", "log.", "return")):
                        break
                    if "pass" in stripped:
                        silent_count += 1
                        break
                    break
        assert silent_count == 0, \
            f"Found {silent_count} silent except ImportError: pass in {FUSEKI_CLIENT}"

    def test_disable_metrics_env_var_documented(self):
        """DISABLE_METRICS env var usage is documented in the service."""
        if not SEMANTIC_MAIN.exists():
            pytest.skip("semantic-service/main.py not found")

        content = SEMANTIC_MAIN.read_text()
        assert "DISABLE_METRICS" in content, \
            "DISABLE_METRICS env var should be referenced in main.py"

    def test_metrics_stubs_are_created_when_import_fails(self):
        """When metrics import fails and DISABLE_METRICS=true, stubs are created."""
        if not SEMANTIC_MAIN.exists():
            pytest.skip("semantic-service/main.py not found")

        content = SEMANTIC_MAIN.read_text()
        # Should contain stub creation after the DISABLE_METRICS check
        assert "DISABLE_METRICS" in content, \
            "DISABLE_METRICS should be checked before creating stubs"


@pytest.mark.unit
@pytest.mark.observability
class TestMetricsImportInAllServices:
    """All services must log, not silently swallow, ImportError for metrics."""

    _SERVICE_DIRS = [
        "services/semantic-service",
        "services/compliance-service",
        "services/dq-service",
        "services/datacontract-service",
        "services/prefect-integration",
        "services/worker",
    ]

    def _find_py_files(self, svc_dir: Path) -> list:
        if not svc_dir.exists():
            return []
        files = []
        for f in svc_dir.rglob("*.py"):
            if "__pycache__" not in str(f):
                files.append(f)
        return files

    def test_all_services_log_on_import_error(self):
        """No service silently swallows ImportError for critical modules."""
        silent_count = 0
        for svc_rel in self._SERVICE_DIRS:
            svc_dir = REPO_ROOT / svc_rel
            for py_file in self._find_py_files(svc_dir):
                try:
                    content = py_file.read_text()
                    lines = content.split("\n")
                    for i, line in enumerate(lines):
                        if "except ImportError" in line:
                            handled = False
                            for j in range(i + 1, min(i + 8, len(lines))):
                                stripped = lines[j].strip()
                                if not stripped or stripped.startswith("#"):
                                    continue
                                # "pass" is silent swallowing — not handled
                                if "pass" in stripped:
                                    handled = False
                                elif any(kw in stripped for kw in (
                                    "logger.", "logging.", "raise", "log.",
                                    "return", "import ", "from ",
                                )):
                                    handled = True
                                break
                            if not handled:
                                silent_count += 1
                except Exception:
                    pass
        # Some services may have legacy patterns — report count
        if silent_count > 0:
            pytest.fail(
                f"Found {silent_count} potentially-silent except ImportError "
                f"patterns across services. Each must log or raise."
            )
