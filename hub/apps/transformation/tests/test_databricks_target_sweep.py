"""Sweep pins for the P11 cross-surface agreements (openspec
run-transformation-on-databricks task 11.7) — the vocabulary/contract
AGREEMENTS across the four shipped coverage areas (target selection
11.2, credential resolution 11.3, lineage/ledger 11.4, local
regression 11.5). A drifted vocabulary or profile shape breaks HERE,
not at runtime in the worker.

- the D1 target vocabulary agreement — every shipped member resolves
  (and the local default is the D6 contract),
- the profile-shape agreement — the 11.3 resolver's
  ``_databricks_output`` branch carries EXACTLY the keys the 11.2
  executor's warehouse-direct pins expect (a drifted branch breaks
  every written profiles.yml),
- the ledger-source agreement — the P7 ledger's
  ``DatabricksCostLedgerSource`` choice and the cost module's wire
  source are ONE vocabulary.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestTargetVocabularyAgreement:
    def test_every_shipped_member_resolves(self):
        from hub.apps.transformation.execution_targets import (
            ExecutionTarget,
            resolve_execution_target,
        )

        assert set(ExecutionTarget) == {
            ExecutionTarget.LOCAL,
            ExecutionTarget.DATABRICKS_WAREHOUSE,
            ExecutionTarget.DATABRICKS_JOB,
        }
        for member in ExecutionTarget:
            assert resolve_execution_target(member.value) is member

    def test_the_local_default_is_the_d6_contract(self):
        from hub.apps.transformation.execution_targets import (
            ExecutionTarget,
            resolve_execution_target,
        )

        assert resolve_execution_target(None) is ExecutionTarget.LOCAL
        assert resolve_execution_target("") is ExecutionTarget.LOCAL


class TestProfileShapeAgreement:
    def test_the_resolver_branch_carries_exactly_the_executor_keys(self):
        """The 11.3 branch's output shape == the shape the 11.2
        warehouse-direct pins assert — one vocabulary across the two
        suites."""
        from hub.apps.transformation.credential_resolver import _databricks_output

        output = _databricks_output(
            {
                "host": "dbc-abc.cloud.databricks.com",
                "http_path": "/sql/1.0/warehouses/wh1",
                "token": "dapi-test",
            }
        )
        assert set(output) == {
            "type",
            "host",
            "http_path",
            "token",
            "catalog",
            "schema",
            "threads",
        }
        assert output["type"] == "databricks"


class TestLedgerSourceAgreement:
    def test_the_source_vocabulary_is_one(self):
        from hub.apps.databricks_admin.models import DatabricksCostLedgerSource

        assert DatabricksCostLedgerSource.DBT_RUN == "dbt_run"
