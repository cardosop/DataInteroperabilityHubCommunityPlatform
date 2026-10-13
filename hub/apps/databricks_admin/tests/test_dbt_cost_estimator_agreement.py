"""The P11 cost-estimator agreement pin (openspec
run-transformation-on-databricks task 11.7) — the ONE heuristic (D5):
the 11.4 dbt-run estimator and the 4.4 job-run estimator agree on the
same (duration, workers, rate) inputs. A drifted formula breaks HERE.

The pin lives in the databricks_admin suite because it imports BOTH
surfaces (the transformation sweep file stays provider-boundary-clean
— the 11.5 AST discipline applies to app modules, and the sweep's
transformation-side pins never touch the estate).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


class TestCostEstimatorAgreement:
    def test_the_estimators_agree_on_the_same_inputs(self):
        from hub.apps.databricks_admin.job_runs import estimate_run_cost
        from hub.apps.transformation.databricks_cost import estimate_dbt_run_cost

        dbt = estimate_dbt_run_cost(duration_seconds=3600, workers=2, dbh_rate=0.55)
        job = estimate_run_cost(
            {
                "run_duration": 3600000,
                "cluster_spec": {"num_workers": 2},
            }
        )
        # The ONE heuristic: duration_hours x rate x (1 + 0.5 x workers).
        assert dbt["size_factor"] == 2.0
        assert job["size_factor"] == 2.0
        # The default rate is one value in both surfaces (0.55).
        assert dbt["dbh_rate"] == 0.55
        assert job["dbh_rate"] == 0.55
        assert dbt["estimated_cost"] == pytest.approx(job["estimated_cost"])
        assert dbt["estimated_cost"] == pytest.approx(1.10)

    def test_malformed_workers_clamp_identically(self):
        from hub.apps.databricks_admin.job_runs import estimate_run_cost
        from hub.apps.transformation.databricks_cost import estimate_dbt_run_cost

        dbt = estimate_dbt_run_cost(duration_seconds=3600, workers=-3, dbh_rate=0.55)
        job = estimate_run_cost(
            {
                "run_duration": 3600000,
                "cluster_spec": {"num_workers": -3},
            }
        )
        assert dbt["size_factor"] == 1.0
        assert job["size_factor"] == 1.0
