"""Phase 1 (openspec add-databricks-uc-read task 1.12) — fixture-JSON loader.

The UC REST estate fixtures live in ``tests/fixtures/databricks/`` (the
repo's fixture-directory convention — ``tests/fixtures/odps/``,
``tests/fixtures/contracts/``). They are DATA fixtures, not mocks: tests
serve these files through a REAL threaded HTTP server to the PRODUCTION
``DatabricksApiClient`` — the transport is real, the payloads come from
files so the estate the sync/browse surfaces are pinned against is a
single auditable artifact.

- ``estate.json`` — the canonical UC estate (every mirror surface). The
  SAME data ``test_uc_sync._estate()`` served inline before 1.12; the
  helper now loads this file (single source of truth).
- ``estate_multi_page.json`` — the same estate with tables + models split
  across ``next_page_token`` pages (``routes`` maps a UC REST path to the
  ORDERED envelope list ``UCEstateHandler`` serves).
- ``effective_permissions.json`` — the UC REST
  ``effective-permissions/table`` answer (privilege_assignments).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FIXTURES_DIR = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "databricks"


def load_fixture(name: str) -> Any:
    """Load ``tests/fixtures/databricks/<name>.json`` and parse it."""
    path = FIXTURES_DIR / f"{name}.json"
    return json.loads(path.read_text())
