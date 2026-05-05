"""
Phase 250.0.12 / D250.7 — tests for the 14-day soak-window helper on
``WorkflowVersionManager``.

The soak window is the contract that prevents the workflow re-sequence
in Phase 250.1.A from breaking in-flight runs: when a new version is
activated, the previous version remains eligible for in-flight progression
for a documented soak window (default 14 days, covers P99 long-running
async asset-creation workflows). After the soak expires, in-flight runs
on the deprecated version MUST be migrated or aborted.

Tests follow TDD doctrine:

* No mocks — real ORM rows + real timestamps via ``django.utils.timezone``.
* No stubs — uses ``WorkflowDefinition`` model directly per project doctrine.
* Root-cause coverage — every contract clause from D250.7 has a test.
"""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from hub.apps.orchestration.models import WorkflowDefinition
from hub.apps.orchestration.versioning import WorkflowVersionManager


pytestmark = pytest.mark.django_db


class TestSoakWindowEligibility:
    """D250.7 — currently-active version is ALWAYS eligible; recently-
    deactivated versions are eligible within the soak window; older
    deactivated versions are NOT eligible."""

    def test_active_version_alone_is_eligible(self):
        WorkflowDefinition.objects.create(
            name="asset_creation",
            version="1.0.0",
            dsl_json={"steps": []},
            is_active=True,
        )

        eligible = WorkflowVersionManager.get_versions_eligible_for_inflight_runs(
            workflow_name="asset_creation",
        )
        assert len(eligible) == 1
        assert eligible[0].version == "1.0.0"
        assert eligible[0].is_active is True

    def test_recently_deactivated_version_is_eligible_within_soak_window(self):
        old = WorkflowDefinition.objects.create(
            name="asset_creation",
            version="1.0.0",
            dsl_json={"steps": []},
            is_active=False,
        )
        new = WorkflowDefinition.objects.create(
            name="asset_creation",
            version="1.1.0",
            dsl_json={"steps": []},
            is_active=True,
        )

        # Move the OLD definition's updated_at to 7 days ago — well within
        # the 14-day default soak window.
        WorkflowDefinition.objects.filter(pk=old.pk).update(
            updated_at=timezone.now() - timedelta(days=7),
        )

        eligible = WorkflowVersionManager.get_versions_eligible_for_inflight_runs(
            workflow_name="asset_creation",
        )
        # Active version sorts first (per the helper's ordering contract);
        # then recently-deactivated.
        eligible_versions = [d.version for d in eligible]
        assert eligible_versions == ["1.1.0", "1.0.0"]

    def test_deactivated_version_outside_soak_window_is_not_eligible(self):
        old = WorkflowDefinition.objects.create(
            name="asset_creation",
            version="1.0.0",
            dsl_json={"steps": []},
            is_active=False,
        )
        WorkflowDefinition.objects.create(
            name="asset_creation",
            version="1.1.0",
            dsl_json={"steps": []},
            is_active=True,
        )

        # Move the OLD definition outside the soak window — 21 days ago.
        WorkflowDefinition.objects.filter(pk=old.pk).update(
            updated_at=timezone.now() - timedelta(days=21),
        )

        eligible = WorkflowVersionManager.get_versions_eligible_for_inflight_runs(
            workflow_name="asset_creation",
        )
        eligible_versions = [d.version for d in eligible]
        # Only the active version is eligible; the old one expired the soak.
        assert eligible_versions == ["1.1.0"]

    def test_custom_soak_days_overrides_default(self):
        """Per-call override of the soak window — the default is 14 days
        but a per-tenant or per-workflow override is supported."""
        old = WorkflowDefinition.objects.create(
            name="asset_creation",
            version="1.0.0",
            dsl_json={"steps": []},
            is_active=False,
        )
        WorkflowDefinition.objects.create(
            name="asset_creation",
            version="1.1.0",
            dsl_json={"steps": []},
            is_active=True,
        )
        WorkflowDefinition.objects.filter(pk=old.pk).update(
            updated_at=timezone.now() - timedelta(days=20),
        )

        # Default 14-day window: old is NOT eligible.
        default_eligible = [
            d.version for d in
            WorkflowVersionManager.get_versions_eligible_for_inflight_runs(
                workflow_name="asset_creation",
            )
        ]
        assert default_eligible == ["1.1.0"]

        # Custom 30-day window: old IS eligible.
        custom_eligible = [
            d.version for d in
            WorkflowVersionManager.get_versions_eligible_for_inflight_runs(
                workflow_name="asset_creation",
                soak_days=30,
            )
        ]
        assert "1.0.0" in custom_eligible
        assert "1.1.0" in custom_eligible


class TestIsVersionEligibleForInflight:
    """D250.7 — convenience wrapper for the per-run dispatch check."""

    def test_active_version_is_eligible(self):
        WorkflowDefinition.objects.create(
            name="asset_creation",
            version="1.0.0",
            dsl_json={"steps": []},
            is_active=True,
        )

        assert WorkflowVersionManager.is_version_eligible_for_inflight(
            workflow_name="asset_creation",
            version="1.0.0",
        ) is True

    def test_recently_deactivated_version_is_eligible(self):
        old = WorkflowDefinition.objects.create(
            name="asset_creation",
            version="1.0.0",
            dsl_json={"steps": []},
            is_active=False,
        )
        WorkflowDefinition.objects.create(
            name="asset_creation",
            version="1.1.0",
            dsl_json={"steps": []},
            is_active=True,
        )
        WorkflowDefinition.objects.filter(pk=old.pk).update(
            updated_at=timezone.now() - timedelta(days=10),
        )

        assert WorkflowVersionManager.is_version_eligible_for_inflight(
            workflow_name="asset_creation",
            version="1.0.0",
        ) is True

    def test_expired_deactivated_version_is_not_eligible(self):
        old = WorkflowDefinition.objects.create(
            name="asset_creation",
            version="1.0.0",
            dsl_json={"steps": []},
            is_active=False,
        )
        WorkflowDefinition.objects.create(
            name="asset_creation",
            version="1.1.0",
            dsl_json={"steps": []},
            is_active=True,
        )
        WorkflowDefinition.objects.filter(pk=old.pk).update(
            updated_at=timezone.now() - timedelta(days=21),
        )

        assert WorkflowVersionManager.is_version_eligible_for_inflight(
            workflow_name="asset_creation",
            version="1.0.0",
        ) is False

    def test_unknown_version_is_not_eligible(self):
        WorkflowDefinition.objects.create(
            name="asset_creation",
            version="1.0.0",
            dsl_json={"steps": []},
            is_active=True,
        )

        assert WorkflowVersionManager.is_version_eligible_for_inflight(
            workflow_name="asset_creation",
            version="999.0.0",
        ) is False

    def test_unknown_workflow_is_not_eligible(self):
        # No definitions for the workflow at all.
        assert WorkflowVersionManager.is_version_eligible_for_inflight(
            workflow_name="nonexistent_workflow",
            version="1.0.0",
        ) is False


class TestSoakWindowOrdering:
    """The helper MUST return the active version first, then deactivated
    versions newest-first. Ordering matters because dispatch picks the
    first eligible version when ``WorkflowInstance.workflow_version`` is
    not specified explicitly."""

    def test_ordering_active_first_then_deactivated_newest_first(self):
        v100 = WorkflowDefinition.objects.create(
            name="asset_creation",
            version="1.0.0",
            dsl_json={"steps": []},
            is_active=False,
        )
        v110 = WorkflowDefinition.objects.create(
            name="asset_creation",
            version="1.1.0",
            dsl_json={"steps": []},
            is_active=False,
        )
        WorkflowDefinition.objects.create(
            name="asset_creation",
            version="2.0.0",
            dsl_json={"steps": []},
            is_active=True,
        )

        # Make 1.0.0 deactivated 10 days ago, 1.1.0 deactivated 3 days ago.
        WorkflowDefinition.objects.filter(pk=v100.pk).update(
            updated_at=timezone.now() - timedelta(days=10),
        )
        WorkflowDefinition.objects.filter(pk=v110.pk).update(
            updated_at=timezone.now() - timedelta(days=3),
        )

        eligible = WorkflowVersionManager.get_versions_eligible_for_inflight_runs(
            workflow_name="asset_creation",
        )
        eligible_versions = [d.version for d in eligible]
        # Active (2.0.0) first; then deactivated newest-first by created_at:
        # 1.1.0 was created after 1.0.0, so 1.1.0 sorts before 1.0.0.
        assert eligible_versions == ["2.0.0", "1.1.0", "1.0.0"]
