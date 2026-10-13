"""TDD pins for the DLT pipeline mirror (openspec
add-databricks-dlt-pipelines task 10.2) — the
`DatabricksDltPipeline`/`DatabricksDltPipelineUpdate` models with
indirect-FK RLS.

The mirror is a READ cache of the Databricks-owned state (the 4.2 job
mirror's discipline): rows carry the pipelines API's reported identity,
settings, and state vocabularies — a state the API did not report is
REFUSED at the model level, never invented. No mocks: real Postgres
rows + RLS (policy scans + a runtime probe through the 1.12 helper).
The registry sync lands with 10.3 (the pipelines client) — these pins
are the model + policy contract it will write into.
"""

import uuid

import pytest
from django.test import TestCase

from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests.test_uc_sync import _make_workspace
from hub.apps.databricks_admin.tests.test_views import _activate_billing
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


class TestModelRegistration:
    """The import pins — RED first: the models must be importable."""

    def test_pipeline_models_are_importable(self):
        from hub.apps.databricks_admin.models import (
            DatabricksDltPipeline,
            DatabricksDltPipelineUpdate,
        )

        assert DatabricksDltPipeline is not None
        assert DatabricksDltPipelineUpdate is not None

    def test_state_vocabularies_are_the_reported_api_sets(self):
        from hub.apps.databricks_admin.models import (
            DatabricksDltChannel,
            DatabricksDltPipelineState,
            DatabricksDltPipelineUpdateState,
        )

        assert set(DatabricksDltPipelineState.values) == {
            "IDLE",
            "ACTIVE",
            "DELETING",
            "FAILED",
            "DELETED",
        }, "the pipeline state vocabulary is the pipelines API's reported set"
        assert set(DatabricksDltPipelineUpdateState.values) == {
            "CREATING",
            "QUEUED",
            "WAITING_FOR_RESOURCES",
            "SETTING_UP_TABLES",
            "MAINTENANCE",
            "RUNNING",
            "STOPPING",
            "CANCELING",
            "COMPLETED",
            "FAILED",
            "CANCELED",
            "TIMED_OUT",
        }, "the update state vocabulary is the updates API's reported set"
        assert set(DatabricksDltChannel.values) == {"CURRENT", "PREVIEW"}


class TestDatabricksDltPipelineModel(TestCase):
    """The pipeline mirror: identity, the reported-state vocabulary,
    the settings cache, cascade."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.workspace = _make_workspace(self.tenant)

    def _make(self, pipeline_id="p-1", **overrides):
        from hub.apps.databricks_admin.models import DatabricksDltPipeline

        fields = {
            "workspace": self.workspace,
            "pipeline_id": pipeline_id,
            "name": "nightly-dlt",
            "state": "IDLE",
        }
        fields.update(overrides)
        return DatabricksDltPipeline.objects.create(**fields)

    def test_unique_per_workspace_by_pipeline_id(self):
        from django.core.exceptions import ValidationError

        self._make()
        with pytest.raises(ValidationError):
            self._make()  # same pipeline_id on the same workspace → uniqueness

    def test_state_is_the_reported_vocabulary_never_invented(self):
        from django.core.exceptions import ValidationError

        for state in ("IDLE", "ACTIVE", "DELETING", "FAILED", "DELETED"):
            row = self._make(pipeline_id=f"p-{state}", state=state)
            assert row.state == state
        with pytest.raises(ValidationError):
            self._make(pipeline_id="p-bogus", state="WARPING")

    def test_channel_is_constrained_and_nullable(self):
        from django.core.exceptions import ValidationError

        for channel in ("CURRENT", "PREVIEW"):
            row = self._make(pipeline_id=f"p-{channel}", channel=channel)
            assert row.channel == channel
        assert self._make(pipeline_id="p-no-channel", channel=None).channel is None
        with pytest.raises(ValidationError):
            self._make(pipeline_id="p-bad-channel", channel="NIGHTLY")

    def test_settings_default_to_an_empty_object(self):
        row = self._make()
        assert row.settings == {}

    def test_identity_fields_must_be_non_empty(self):
        from django.core.exceptions import ValidationError

        with pytest.raises(ValidationError):
            self._make(pipeline_id="")
        with pytest.raises(ValidationError):
            self._make(name="")

    def test_workspace_delete_cascades_the_pipeline_mirror(self):
        from hub.apps.databricks_admin.models import DatabricksDltPipeline

        row = self._make()
        self.workspace.delete()
        assert not DatabricksDltPipeline.objects.filter(pk=row.pk).exists()

    def test_rls_policy_ships_for_the_pipelines_table(self):
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT policyname FROM pg_policies WHERE tablename = 'databricks_dlt_pipelines'"
            )
            policies = [row[0] for row in cursor.fetchall()]
        assert policies, "the pipeline mirror table must ship a paired RLS policy"


class TestDatabricksDltPipelineUpdateModel(TestCase):
    """The update mirror: identity, the reported-state vocabulary, the
    refresh semantics, cascade."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.workspace = _make_workspace(self.tenant)
        from hub.apps.databricks_admin.models import DatabricksDltPipeline

        self.pipeline = DatabricksDltPipeline.objects.create(
            workspace=self.workspace, pipeline_id="p-1", name="nightly-dlt", state="IDLE"
        )

    def _make(self, update_id="u-1", **overrides):
        from hub.apps.databricks_admin.models import DatabricksDltPipelineUpdate

        fields = {
            "pipeline": self.pipeline,
            "update_id": update_id,
            "state": "RUNNING",
        }
        fields.update(overrides)
        return DatabricksDltPipelineUpdate.objects.create(**fields)

    def test_unique_per_pipeline_by_update_id(self):
        from django.core.exceptions import ValidationError

        self._make()
        with pytest.raises(ValidationError):
            self._make()  # same update_id on the same pipeline → uniqueness

    def test_state_is_the_reported_vocabulary_never_invented(self):
        from django.core.exceptions import ValidationError

        for state in (
            "CREATING",
            "QUEUED",
            "WAITING_FOR_RESOURCES",
            "SETTING_UP_TABLES",
            "MAINTENANCE",
            "RUNNING",
            "STOPPING",
            "CANCELING",
            "COMPLETED",
            "FAILED",
            "CANCELED",
            "TIMED_OUT",
        ):
            row = self._make(update_id=f"u-{state}", state=state)
            assert row.state == state
        with pytest.raises(ValidationError):
            self._make(update_id="u-bogus", state="WARPING")

    def test_refresh_semantics_are_carried_not_invented(self):
        row = self._make(full_refresh=True, refresh_selection={"tables": ["bronze_customers"]})
        assert row.full_refresh is True
        assert row.refresh_selection == {"tables": ["bronze_customers"]}
        plain = self._make(update_id="u-2", refresh_selection=None)
        assert plain.full_refresh is False
        assert plain.refresh_selection is None

    def test_dbu_and_error_message_are_nullable_until_reported(self):
        row = self._make()
        assert row.dbu is None
        assert row.error_message is None

    def test_pipeline_delete_cascades_its_updates(self):
        from hub.apps.databricks_admin.models import DatabricksDltPipelineUpdate

        row = self._make()
        self.pipeline.delete()
        assert not DatabricksDltPipelineUpdate.objects.filter(pk=row.pk).exists()

    def test_rls_policy_ships_for_the_updates_table(self):
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT policyname FROM pg_policies "
                "WHERE tablename = 'databricks_dlt_pipeline_updates'"
            )
            policies = [row[0] for row in cursor.fetchall()]
        assert policies, "the update mirror table must ship a paired RLS policy"


class TestDltMirrorRuntimeRLS(TestCase):
    """The indirect-FK policies FILTER at runtime, not just exist."""

    def setUp(self):
        require_dns()
        self.tenant_a = TenantFactory.create_tenant()
        _activate_billing(self.tenant_a)
        self.tenant_b = TenantFactory.create_tenant()
        _activate_billing(self.tenant_b)
        self.workspace = _make_workspace(self.tenant_a, name=f"ws-dlt-{uuid.uuid4().hex[:8]}")
        from hub.apps.databricks_admin.models import (
            DatabricksDltPipeline,
            DatabricksDltPipelineUpdate,
        )

        self.pipeline = DatabricksDltPipeline.objects.create(
            workspace=self.workspace, pipeline_id="p-1", name="nightly-dlt", state="IDLE"
        )
        DatabricksDltPipelineUpdate.objects.create(
            pipeline=self.pipeline, update_id="u-1", state="RUNNING"
        )

    def _probe_role(self):
        from hub.apps.databricks_admin.tests.test_uc_rls_isolation import (
            _connection_bypasses_rls,
            _ensure_rls_probe_role,
        )

        if _connection_bypasses_rls():
            _ensure_rls_probe_role()
            return "hub_rls_probe"
        return None

    def test_pipeline_rows_are_hidden_from_foreign_tenants(self):
        from hub.apps.databricks_admin.tests.test_uc_rls_isolation import _visible_count_as

        probe = self._probe_role()
        assert _visible_count_as(probe, self.tenant_a.id, "databricks_dlt_pipelines") == 1
        assert _visible_count_as(probe, self.tenant_b.id, "databricks_dlt_pipelines") == 0, (
            "tenant B must see ZERO of tenant A's pipelines (RLS runtime enforcement)"
        )

    def test_update_rows_are_hidden_from_foreign_tenants(self):
        # The 2-hop chain: updates → pipelines → workspaces.tenant_id.
        from hub.apps.databricks_admin.tests.test_uc_rls_isolation import _visible_count_as

        probe = self._probe_role()
        assert _visible_count_as(probe, self.tenant_a.id, "databricks_dlt_pipeline_updates") == 1
        assert _visible_count_as(probe, self.tenant_b.id, "databricks_dlt_pipeline_updates") == 0, (
            "the pipeline→workspace chain policy must hide the update from tenant B"
        )

    def test_no_tenant_context_hides_all_mirror_rows(self):
        # An UNSET tenant GUC (the fail-closed default) must surface
        # NOTHING through either policy.
        from django.db import connection

        probe = self._probe_role()
        with connection.cursor() as cursor:
            try:
                if probe:
                    cursor.execute(f"SET ROLE {probe}")
                for table in ("databricks_dlt_pipelines", "databricks_dlt_pipeline_updates"):
                    cursor.execute(f"SELECT count(*) FROM {table}")
                    assert cursor.fetchone()[0] == 0, (
                        f"without a tenant context the {table} policy must hide everything"
                    )
            finally:
                if probe:
                    cursor.execute("RESET ROLE")
