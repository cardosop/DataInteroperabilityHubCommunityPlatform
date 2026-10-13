"""TDD pins for the DLT-pipeline creation chain (openspec
add-databricks-dlt-pipelines task 10.4) — the D3 gate.

``databricks.dlt.create`` = TenantScoping → settings allowlist (the
payload envelope: dict shape, workspace ownership, and the key
allowlist) → cluster policy (EVERY cluster carries a policy id — the
D4 cost-governance discipline) → channel (the 10.2 model enum's
vocabulary). Every refusal carries a classified code; the chain has NO
network surface by construction (the 10.3 pipelines client is never
constructed), so a gated request fails with ZERO network calls and no
mirror row.

No mocks: real Postgres tenants/workspaces, the REAL chain runner, the
REAL audit table (the runner's RULE_CHAIN_COMPLETED row read back).
"""

import inspect
import uuid

import pytest
from django.test import TestCase

from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests.test_uc_sync import _make_workspace
from hub.apps.databricks_admin.tests.test_views import _activate_billing
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)

CHAIN_NAME = "databricks.dlt.create"


def _seed():
    """A REAL tenant + ACTIVE workspace (unique-suffixed — the shared DB
    may carry leaked rows from parallel sessions)."""
    require_dns()
    tenant = TenantFactory.create_tenant()
    _activate_billing(tenant)
    workspace = _make_workspace(tenant, name=f"ws-{uuid.uuid4().hex[:8]}")
    return tenant, workspace


def _payload(**overrides):
    payload = {
        "name": "bronze-pipeline",
        "edition": "ADVANCED",
        "clusters": [{"label": "default", "policy_id": "pol-1234"}],
        "libraries": [],
        "target": "hive_metastore.bronze",
        "continuous": False,
    }
    payload.update(overrides)
    return payload


def _run(tenant, **kwargs):
    from django.db import transaction

    from hub.apps.core.business_rules.chains import execute_chain

    with transaction.atomic():
        return execute_chain(CHAIN_NAME, tenant=tenant, **kwargs)


def _failed_with(result, code):
    assert result["outcome"] == "FAIL", result
    return any(f"[{code}]" in err for err in result["errors"]), result


class TestChainRegistration:
    def test_chain_is_registered(self):
        from hub.apps.core.business_rules.chains import get_chain

        assert get_chain(CHAIN_NAME) is not None, f"{CHAIN_NAME} not registered"

    def test_chain_requires_an_active_transaction(self):
        """The runner's transaction contract, asserted BOTH ways: inside
        an explicit ``atomic()`` the call succeeds; OUTSIDE it raises.
        The outside leg runs on a fresh connection (``close_all()``)
        so a stale atomic leaked by a prior shared-DB test's failed
        flush (the suppressed-teardown residue class) can never mask
        the contract — residue-proof by construction."""
        from django.db import connections, transaction

        from hub.apps.core.business_rules.chains import execute_chain

        tenant, _ws = _seed()
        with transaction.atomic():
            result = execute_chain(CHAIN_NAME, tenant=tenant, payload=_payload())
        assert result["outcome"] == "PASS", result

        connections.close_all()
        with pytest.raises(RuntimeError, match="active transaction"):
            execute_chain(CHAIN_NAME, tenant=tenant, payload=_payload())


class TestSettingsAllowlist:
    def test_the_full_create_surface_passes(self):
        """Every allowlisted key at once — the API's create vocabulary
        (name + the settings surface + channel) passes end to end."""
        tenant, ws = _seed()
        result = _run(
            tenant,
            workspace=ws,
            payload=_payload(
                development=True,
                photon=False,
                notifications=[],
                catalog="prod_catalog",
                channel="CURRENT",
            ),
        )
        assert result["outcome"] == "PASS", result

    def test_allowlist_covers_the_model_settings_vocabulary(self):
        """The allowlist is the 10.2 model's documented settings surface
        (edition/clusters/libraries/target/continuous/development/
        photon/notifications/catalog) plus the request-level create
        fields (name, channel) — a single coherent vocabulary, pinned
        field-for-field against the module constant."""
        from hub.apps.databricks_admin.chains import DLT_SETTINGS_ALLOWLIST

        assert (
            frozenset(
                {
                    "name",
                    "edition",
                    "clusters",
                    "libraries",
                    "target",
                    "continuous",
                    "development",
                    "photon",
                    "notifications",
                    "catalog",
                    "channel",
                }
            )
            == DLT_SETTINGS_ALLOWLIST
        )

    def test_unknown_setting_key_is_refused(self):
        tenant, ws = _seed()
        refused, result = _failed_with(
            _run(tenant, workspace=ws, payload=_payload(storage="s3://bucket")),
            "DATABRICKS_DLT_SETTING_FORBIDDEN",
        )
        assert refused, result["errors"]

    def test_unknown_key_refusal_names_the_key(self):
        tenant, ws = _seed()
        refused, result = _failed_with(
            _run(tenant, workspace=ws, payload=_payload(storage="s3://bucket")),
            "DATABRICKS_DLT_SETTING_FORBIDDEN",
        )
        assert refused, result["errors"]
        assert any("'storage'" in err for err in result["errors"]), result["errors"]

    def test_non_dict_payload_fails(self):
        tenant, ws = _seed()
        refused, result = _failed_with(
            _run(tenant, workspace=ws, payload="not-a-dict"),
            "DATABRICKS_DLT_INVALID_CONFIG",
        )
        assert refused, result["errors"]

    def test_cross_tenant_workspace_fails(self):
        """The 3.4 ownership discipline: a workspace belonging to
        another tenant is an INVALID_CONFIG refusal, never a permissive
        pass."""
        tenant, _ws = _seed()
        other_tenant = TenantFactory.create_tenant()
        _activate_billing(other_tenant)
        foreign_workspace = _make_workspace(other_tenant, name="foreign-ws")
        refused, result = _failed_with(
            _run(tenant, workspace=foreign_workspace, payload=_payload()),
            "DATABRICKS_DLT_INVALID_CONFIG",
        )
        assert refused, result["errors"]


class TestClusterPolicy:
    def test_policy_carrying_clusters_pass(self):
        tenant, ws = _seed()
        assert _run(tenant, workspace=ws, payload=_payload())["outcome"] == "PASS"

    def test_policy_less_cluster_is_refused(self):
        tenant, ws = _seed()
        refused, result = _failed_with(
            _run(tenant, workspace=ws, payload=_payload(clusters=[{"label": "default"}])),
            "DATABRICKS_DLT_CLUSTER_POLICY_REQUIRED",
        )
        assert refused, result["errors"]

    def test_blank_policy_id_is_refused(self):
        tenant, ws = _seed()
        refused, result = _failed_with(
            _run(tenant, workspace=ws, payload=_payload(clusters=[{"policy_id": "  "}])),
            "DATABRICKS_DLT_CLUSTER_POLICY_REQUIRED",
        )
        assert refused, result["errors"]

    def test_non_string_policy_id_is_refused(self):
        """A non-string policy id cannot be attested by the gate — the
        same fail-closed shape as a missing one."""
        tenant, ws = _seed()
        refused, result = _failed_with(
            _run(tenant, workspace=ws, payload=_payload(clusters=[{"policy_id": 123}])),
            "DATABRICKS_DLT_CLUSTER_POLICY_REQUIRED",
        )
        assert refused, result["errors"]

    def test_missing_clusters_fails(self):
        tenant, ws = _seed()
        payload = _payload()
        del payload["clusters"]
        refused, result = _failed_with(
            _run(tenant, workspace=ws, payload=payload), "DATABRICKS_DLT_INVALID_CONFIG"
        )
        assert refused, result["errors"]

    def test_empty_clusters_fails(self):
        tenant, ws = _seed()
        refused, result = _failed_with(
            _run(tenant, workspace=ws, payload=_payload(clusters=[])),
            "DATABRICKS_DLT_INVALID_CONFIG",
        )
        assert refused, result["errors"]

    def test_non_list_clusters_fails(self):
        tenant, ws = _seed()
        refused, result = _failed_with(
            _run(tenant, workspace=ws, payload=_payload(clusters={"label": "x"})),
            "DATABRICKS_DLT_INVALID_CONFIG",
        )
        assert refused, result["errors"]

    def test_non_dict_cluster_entry_fails(self):
        tenant, ws = _seed()
        refused, result = _failed_with(
            _run(tenant, workspace=ws, payload=_payload(clusters=["default"])),
            "DATABRICKS_DLT_INVALID_CONFIG",
        )
        assert refused, result["errors"]

    def test_second_policy_less_cluster_is_refused(self):
        """The EVERY-cluster contract — one policy-carrying cluster does
        not vouch for a second policy-less one."""
        tenant, ws = _seed()
        refused, result = _failed_with(
            _run(
                tenant,
                workspace=ws,
                payload=_payload(
                    clusters=[
                        {"label": "good", "policy_id": "pol-1234"},
                        {"label": "bad"},
                    ]
                ),
            ),
            "DATABRICKS_DLT_CLUSTER_POLICY_REQUIRED",
        )
        assert refused, result["errors"]


class TestChannelGate:
    def test_absent_channel_passes(self):
        """No channel key → the API's default applies (the 10.2 model's
        NULL-able channel column)."""
        tenant, ws = _seed()
        assert _run(tenant, workspace=ws, payload=_payload())["outcome"] == "PASS"

    def test_current_channel_passes(self):
        tenant, ws = _seed()
        assert _run(tenant, workspace=ws, payload=_payload(channel="CURRENT"))["outcome"] == "PASS"

    def test_preview_channel_passes(self):
        tenant, ws = _seed()
        assert _run(tenant, workspace=ws, payload=_payload(channel="PREVIEW"))["outcome"] == "PASS"

    def test_unknown_channel_is_refused(self):
        """The SDK-style token (CHANNEL_PREVIEW) is not the API's JSON
        value — the gate validates the wire vocabulary only."""
        tenant, ws = _seed()
        refused, result = _failed_with(
            _run(tenant, workspace=ws, payload=_payload(channel="CHANNEL_PREVIEW")),
            "DATABRICKS_DLT_CHANNEL_INVALID",
        )
        assert refused, result["errors"]

    def test_channel_vocabulary_is_the_model_enum(self):
        """The gate consumes DatabricksDltChannel — the model enum is
        the single source of truth for the wire values."""
        from hub.apps.databricks_admin.models import DatabricksDltChannel

        assert set(DatabricksDltChannel.values) == {"CURRENT", "PREVIEW"}


class TestGateLeavesNoTrace:
    def test_refused_chains_create_no_mirror_row(self):
        from hub.apps.databricks_admin.models import DatabricksDltPipeline

        tenant, ws = _seed()
        _run(tenant, workspace=ws, payload=_payload(storage="s3://bucket"))  # allowlist-refused
        _run(tenant, workspace=ws, payload=_payload(clusters=[{"label": "x"}]))  # policy-refused
        _run(tenant, workspace=ws, payload=_payload(channel="CHANNEL_PREVIEW"))  # channel-refused
        assert (
            not DatabricksDltPipeline.objects.filter(workspace=ws)
            .filter(name="bronze-pipeline")
            .exists()
        ), "a refused chain must create no mirror row"

    def test_zero_network_by_construction(self):
        """The chain's builder never touches the pipelines client or any
        HTTP stack — the gate is pure policy over local state (the 0.11
        AST-scan convention)."""
        from hub.apps.databricks_admin import chains as chains_module

        src = inspect.getsource(chains_module._dlt_create_chain)
        assert "pipelines_client" not in src
        assert "DatabricksApiClient" not in src
        assert "httpx" not in src


class TestRunnerIntegration:
    def test_failed_chain_writes_the_rule_chain_completed_audit_row(self):
        """The runner's single-audit contract (274.7.2), exercised
        through THIS chain: a FAIL execution leaves a real
        RULE_CHAIN_COMPLETED row with the chain name, the FAIL outcome,
        and the business-rules retention category."""
        from hub.apps.audit.models import AuditEvent

        tenant, ws = _seed()
        result = _run(tenant, workspace=ws, payload=_payload(storage="s3://bucket"))
        assert result["outcome"] == "FAIL"
        row = (
            AuditEvent.objects.filter(action="RULE_CHAIN_COMPLETED")
            .filter(details_json__chain=CHAIN_NAME)
            .order_by("-timestamp")
            .first()
        )
        assert row is not None, "the runner must write the chain-completed audit row"
        assert row.resource_type == "RULE_CHAIN"
        assert row.result == "FAILURE"
        assert row.details_json["outcome"] == "FAIL"
        assert row.details_json["audit_retention_category"] == "business_rules"

    def test_passed_chain_writes_success_and_all_four_steps(self):
        """A PASS runs every step (no short-circuit) — the steps list
        carries the four names in the D3 order, and the audit row
        records the PASS outcome."""
        from hub.apps.audit.models import AuditEvent

        tenant, ws = _seed()
        result = _run(tenant, workspace=ws, payload=_payload(channel="CURRENT"))
        assert result["outcome"] == "PASS", result
        assert list(result["steps"].keys()) == [
            "_tenant_scoping",
            "_settings_allowlist",
            "_cluster_policy",
            "_channel",
        ], result["steps"]
        row = (
            AuditEvent.objects.filter(action="RULE_CHAIN_COMPLETED")
            .filter(details_json__chain=CHAIN_NAME)
            .order_by("-timestamp")
            .first()
        )
        assert row is not None
        assert row.result == "SUCCESS"
        assert row.details_json["steps"] == list(result["steps"].keys())

    def test_missing_tenant_context_is_a_caller_error(self):
        """The canonical scoping step: a missing tenant context is a
        caller error — never a silent pass."""
        from django.db import transaction

        from hub.apps.core.business_rules.chains import execute_chain

        with transaction.atomic():
            result = execute_chain(CHAIN_NAME, payload=_payload())
        assert result["outcome"] == "FAIL"
        assert "Tenant context required" in result["errors"][0]


class TestSeedSanity(TestCase):
    """The pin-suite's own scaffolding sanity — the fixture world is
    real (a tenant + ACTIVE workspace exist on Postgres)."""

    def test_seed_rows_exist(self):
        from hub.apps.databricks_admin.models import DatabricksWorkspace

        tenant, ws = _seed()
        assert DatabricksWorkspace.objects.filter(id=ws.id, tenant=tenant).exists()
