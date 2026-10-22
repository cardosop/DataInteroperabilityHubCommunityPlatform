"""W4.6 (openspec oss-release-remediation, G1) — the unregistered-seam
defaults, pinned OUTSIDE a populated Django app registry.

Under Django the estate app registers every seam at app-ready, so the
"no provider registered" state only exists in a process WITHOUT Django
setup. Each pin therefore runs its assertions in a FRESH interpreter
subprocess that imports the REAL seam module bare (P3-1: the pre-fix
in-process shape failed whenever another pin in the same pytest run
had booted Django — ``ready()`` registered the seams and the
"unregistered default" vanished; the subprocess isolation makes the
pin hermetic regardless of the host process state):

- the m2m token-cache seam resolves None (consumers fall back to the
  best-effort no-cache mode);
- the budget-gate seam resolves None (no budget concept → no gate);
- the staging-volume provisioner refuses classified
  (``DatabricksStagingRefused``) — the refusal fires BEFORE any settings
  or cache access, so a bare import suffices.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

_PREAMBLE = "import sys; sys.path.insert(0, %r)\n" % str(ROOT)


def _bare_python(body: str) -> subprocess.CompletedProcess[str]:
    """Run `body` in a fresh interpreter with the repo root on sys.path
    (no pytest, no Django boot, no host-process state)."""
    return subprocess.run(
        [sys.executable, "-I", "-c", _PREAMBLE + body],
        capture_output=True,
        text=True,
        check=False,
    )


def test_m2m_token_cache_default_is_none_without_django():
    result = _bare_python(
        "from hub.apps.integrations.m2m_token_cache import default_m2m_token_cache\n"
        "assert default_m2m_token_cache() is None\n"
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_budget_gate_default_is_none_without_django():
    result = _bare_python(
        "from hub.apps.warehouses.budget_gate import enforce_budget\n"
        "assert enforce_budget('any-tenant') is None\n"
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_staging_provisioner_refuses_without_django():
    result = _bare_python(
        "from hub.data_movement.staging import (\n"
        "    DatabricksStagingRefused, ensure_staging_volume,\n"
        "    get_staging_volume_provisioner,\n"
        ")\n"
        "assert get_staging_volume_provisioner() is None\n"
        "class _BareTenant:\n"
        "    def __init__(self, tenant_id):\n"
        "        self.id = tenant_id\n"
        "        self.databricks_staging_volume_name = ''\n"
        "        self.databricks_s3_external_location_enabled = False\n"
        "try:\n"
        "    ensure_staging_volume(\n"
        "        tenant=_BareTenant('t-1'), catalog='cat', schema='sch',\n"
        "        client=object(), cache=object(),\n"
        "    )\n"
        "except DatabricksStagingRefused as exc:\n"
        "    assert 'no staging-volume provisioner registered' in str(exc)\n"
        "else:\n"
        "    raise AssertionError('the refusal must fire without a provider')\n"
    )
    assert result.returncode == 0, result.stdout + result.stderr
