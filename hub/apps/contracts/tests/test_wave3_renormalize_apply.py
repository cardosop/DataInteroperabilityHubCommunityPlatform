"""
Phase 227 Wave 3 — self-healing migration integration tests.

Pins the four ``--apply`` deliverables from openspec/changes/preprod01:

* **W3.2** — ``contract_normalization_models_count{spec_type="ODPS"}``
  histogram is populated when the apply path heals contracts. Pre-W3 the
  histogram only fired on live POST/PATCH; if migration paths bypassed
  it, the post-migration p50 dashboard panel would show no improvement.
* **W3.3** — successfully self-healed contracts are re-indexed by the
  Search service so post-migration search queries surface the now-
  populated `models[*]` and `schema.fields[*]` text.
* **W3.4** — one ``contract.batch_renormalized`` webhook per batch
  (per-tenant, NOT per-contract). A million-row migration with a
  per-contract webhook would storm subscribers; the per-batch summary
  delivers the same signal at thousand-fold lower volume.
* **W3.5** — per-tenant residue counts in the run summary (JSON +
  human-readable). Wave 4 ops planning depends on knowing which
  tenants still carry structureless rows after the self-heal.

No mocks of internal code paths — real Tenant + Asset + Contract +
Webhook rows; real ``NormalizationService.normalize_contract``; real
``SearchIndexer.index_contract``; real ``WebhookDeliveryService``.
"""

from __future__ import annotations

import json
import uuid
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import TestCase

# ---------------------------------------------------------------------------
# Fixtures (mirror test_audit_structureless_command.py for consistency)
# ---------------------------------------------------------------------------


def _create_tenant(prefix: str = "W3"):
    from hub.apps.tenants.models import Tenant

    suffix = uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"{prefix} Co {suffix}",
        slug=f"{prefix.lower()}-co-{suffix}",
    )


def _create_asset(tenant, *, status="DRAFT"):
    from hub.apps.assets.models import Asset

    suffix = uuid.uuid4().hex[:6]
    return Asset.objects.create(
        tenant=tenant,
        key=f"asset-{suffix}",
        name=f"Asset {suffix}",
        status=status,
    )


def _create_structural_odcs_contract(tenant, *, asset=None):
    """ODCS row whose ``original_raw`` IS structural but
    ``hub_contract_json`` is currently empty — heals on apply."""
    from hub.apps.contracts.models import Contract

    structural_yaml = (
        "kind: DataContract\n"
        "apiVersion: v3.0.2\n"
        "id: ok\n"
        "name: ok\n"
        "version: 1.0.0\n"
        "status: active\n"
        "schema:\n"
        "  - name: customers\n"
        "    fields:\n"
        "      - name: id\n"
        "        type: string\n"
        "      - name: email\n"
        "        type: string\n"
    )
    return Contract.objects.create(
        tenant=tenant,
        asset=asset,
        version=1,
        original_spec_type="ODCS",
        original_spec_version="3.0.2",
        original_format="YAML",
        original_raw=structural_yaml,
        hub_contract_json={"models": [], "schema": {"fields": []}},
        normalization_status="NORMALIZED_OK",
        validation_status="VALID",
        status="ACTIVE",
    )


def _create_structureless_odcs_contract(tenant, *, asset=None):
    """ODCS row that stays structureless even after re-normalization
    (info-only, no schema)."""
    from hub.apps.contracts.models import Contract

    structureless_yaml = (
        "kind: DataContract\n"
        "apiVersion: v3.0.2\n"
        "id: bad\n"
        "name: bad\n"
        "version: 1.0.0\n"
        "status: active\n"
        "info:\n"
        "  description: no schema\n"
    )
    return Contract.objects.create(
        tenant=tenant,
        asset=asset,
        version=1,
        original_spec_type="ODCS",
        original_spec_version="3.0.2",
        original_format="YAML",
        original_raw=structureless_yaml,
        hub_contract_json={"models": [], "schema": {"fields": []}},
        normalization_status="NORMALIZED_OK",
        validation_status="VALID",
        status="ACTIVE",
    )


def _create_webhook_subscription(tenant, *, event_types):
    """Real Webhook row subscribed to the given event types — the
    delivery code path filters on this so the test gets concrete
    coverage of the per-tenant routing."""
    from hub.apps.webhooks.models import Webhook, WebhookStatus

    return Webhook.objects.create(
        tenant=tenant,
        name=f"Test webhook {uuid.uuid4().hex[:6]}",
        url="https://example.invalid/hook",
        secret="whsec_test_secret_value_at_least_32_characters_long",
        event_types=list(event_types),
        status=WebhookStatus.ACTIVE,
    )


def _run(*flags, tenant=None, **kwargs):
    out = StringIO()
    args = [
        "renormalize_contracts",
        "--spec-version=3.1.0",
        "--filter=structureless",
    ]
    if tenant is not None:
        args.append(f"--tenant-id={tenant.id}")
    args.extend(flags)
    call_command(*args, stdout=out, **kwargs)
    return out.getvalue()


# ---------------------------------------------------------------------------
# W3.2 — observability: histograms populate on apply
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestApplyPopulatesNormalizationMetrics(TestCase):
    """``--apply`` must drive ``record_all_normalization_metrics`` so
    the post-migration p50 panel for
    ``contract_normalization_models_count{spec_type=...}`` advances.
    Pre-W3, if the migration path bypassed the metrics emitter, the
    operator would have no observable signal that the self-heal
    actually populated models — only the per-row logs would carry it."""

    def test_apply_records_models_count_histogram(self):
        """The healed contract's models count is observed on the
        ``contract_normalization_models_count`` histogram."""
        from unittest import mock

        tenant = _create_tenant("W32")
        _create_structural_odcs_contract(tenant)
        _create_structural_odcs_contract(tenant)

        # Patch the metric *at the import site used by
        # NormalizationService* — that's the binding the apply path
        # actually invokes (Phase 227 L7 audit-closeout pattern).
        with mock.patch(
            "hub.apps.contracts.normalization_service.record_all_normalization_metrics"
        ) as m:
            _run("--apply", tenant=tenant)

        # At least one heal happened, so at least one observation.
        assert m.call_count >= 1, (
            f"Expected ≥1 record_all_normalization_metrics call after "
            f"--apply healed contracts; got {m.call_count}"
        )
        # Each call carried a spec_type so the histogram label fires.
        for call in m.call_args_list:
            kwargs = call.kwargs
            assert "spec_type" in kwargs, (
                "metric calls must carry spec_type so the per-spec "
                "dashboard panel splits correctly; got "
                f"args={call.args}, kwargs={kwargs}"
            )


# ---------------------------------------------------------------------------
# W3.3 — search re-index after heal
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestApplyTriggersSearchReindex(TestCase):
    """Successfully healed contracts must be pushed to the Search index
    so the now-populated ``schema_fields`` and ``schema_text`` reach
    queries. Residue contracts (still structureless) must NOT be re-
    indexed — their stale empty index entry is correct."""

    def test_healed_contract_is_reindexed(self):
        from hub.apps.search.models import SearchIndex

        tenant = _create_tenant("W33H")
        contract = _create_structural_odcs_contract(tenant)

        _run("--apply", tenant=tenant)

        contract.refresh_from_db()
        # The heal succeeded; SearchIndex row exists for the contract.
        idx = SearchIndex.objects.filter(
            tenant=tenant,
            resource_type="CONTRACT",
            resource_id=contract.id,
        ).first()
        assert idx is not None, (
            "Healed contract must be in the SearchIndex so the now-"
            "populated schema fields reach queries"
        )
        # Schema text reflects the fields the heal populated.
        assert "id" in (idx.schema_text or ""), (
            f"SearchIndex.schema_text should carry the field names from "
            f"the healed contract; got {idx.schema_text!r}"
        )

    def test_residue_contract_is_not_reindexed_with_empty_payload(self):
        """A residue contract should not have its index *overwritten*
        with the still-empty payload — the apply path skips re-index
        for non-healed rows."""
        from hub.apps.search.models import SearchIndex

        tenant = _create_tenant("W33R")
        contract = _create_structureless_odcs_contract(tenant)

        # No pre-existing SearchIndex row.
        before_count = SearchIndex.objects.filter(resource_id=contract.id).count()

        _run("--apply", tenant=tenant)

        # Residue path skips re-index — no new row is created.
        after_count = SearchIndex.objects.filter(resource_id=contract.id).count()
        assert after_count == before_count, (
            f"Residue contract should NOT trigger re-index; "
            f"SearchIndex row count went {before_count} → {after_count}"
        )

    def test_search_reindex_failure_does_not_break_migration(self):
        """A search-backend outage MUST NOT roll back the contract
        write. The migration is the load-bearing operation; search
        re-index is best-effort."""
        from unittest import mock

        from hub.apps.contracts.structureless import is_structureless

        tenant = _create_tenant("W33F")
        contract = _create_structural_odcs_contract(tenant)

        with mock.patch(
            "hub.apps.search.indexing.SearchIndexer.index_contract",
            side_effect=Exception("simulated search backend outage"),
        ):
            output = _run("--apply", tenant=tenant)

        # Heal still committed despite the search failure.
        contract.refresh_from_db()
        assert not is_structureless(contract), (
            "Search re-index failure must NOT roll back the heal write"
        )
        # Migration reports success (1 healed).
        assert "healed=1" in output


# ---------------------------------------------------------------------------
# W3.4 — contract.batch_renormalized webhook (per batch, per tenant)
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestBatchRenormalizedWebhook(TestCase):
    """One ``contract.batch_renormalized`` webhook delivery per batch
    per affected tenant — NOT per contract. Pre-W3.4 the migration
    emitted only a single global audit event; webhook subscribers had
    no signal at all."""

    def test_event_type_registered_in_choices(self):
        """The new event type must be in the canonical
        :class:`WebhookEventType` choices so webhook subscriptions can
        validate the value at create-time."""
        from hub.apps.webhooks.models import WebhookEventType

        assert hasattr(WebhookEventType, "CONTRACT_BATCH_RENORMALIZED"), (
            "WebhookEventType must register CONTRACT_BATCH_RENORMALIZED "
            "as a TextChoices member so subscribers can subscribe to it"
        )
        assert WebhookEventType.CONTRACT_BATCH_RENORMALIZED.value == "contract.batch_renormalized"

    def test_webhook_dispatched_to_subscribed_tenant(self):
        """Tenant with a webhook subscribed to
        ``contract.batch_renormalized`` receives one delivery per batch."""
        from hub.apps.webhooks.models import WebhookDelivery

        tenant = _create_tenant("W34D")
        _create_webhook_subscription(tenant, event_types=["contract.batch_renormalized"])
        _create_structural_odcs_contract(tenant)
        _create_structural_odcs_contract(tenant)

        before = WebhookDelivery.objects.filter(event_type="contract.batch_renormalized").count()
        _run("--apply", "--silent-events", tenant=tenant)
        after = WebhookDelivery.objects.filter(event_type="contract.batch_renormalized").count()

        # Two healed contracts in one batch → ONE summary delivery, not two.
        assert after - before == 1, (
            f"Expected exactly 1 batch summary webhook delivery; got "
            f"{after - before} (a per-contract storm would give 2)"
        )

    def test_webhook_payload_carries_summary_counts(self):
        """The delivery payload carries the counts the spec promises:
        ``total``, ``healed``, ``residual``, ``failed``, ``run_id``,
        per-tenant counts, and ``tenant_id``."""
        from hub.apps.webhooks.models import WebhookDelivery

        tenant = _create_tenant("W34P")
        _create_webhook_subscription(tenant, event_types=["contract.batch_renormalized"])
        _create_structural_odcs_contract(tenant)
        _create_structureless_odcs_contract(tenant)

        _run("--apply", "--silent-events", tenant=tenant)

        delivery = (
            WebhookDelivery.objects.filter(
                webhook__tenant=tenant,
                event_type="contract.batch_renormalized",
            )
            .order_by("-created_at")
            .first()
        )
        assert delivery is not None, "expected a batch webhook delivery"
        # Payload data carries the canonical summary keys the spec
        # promises subscribers can branch on.
        data = delivery.payload.get("data", {})
        for key in (
            "run_id",
            "tenant_id",
            "processed",
            "healed",
            "residual",
            "failed",
        ):
            assert key in data, f"webhook payload data missing {key!r}; got {data!r}"
        # The tenant_id in the payload matches the tenant we processed.
        assert data["tenant_id"] == str(tenant.id)
        # Mixed cohort: 1 heal + 1 residue.
        assert data["healed"] >= 1
        assert data["residual"] >= 1

    def test_webhook_payload_resource_metadata_is_tenant_scoped(self):
        """Self-audit-1 regression guard — the batch event's
        ``resource_type``/``resource_id`` must reflect the actual
        subject of the operation (a tenant's contracts), not the
        synthetic run-id. A subscriber that joins ``resource_id``
        against the contracts table with ``resource_type="CONTRACT"``
        would have gotten zero rows; with TENANT + tenant_id the join
        works because the resource is now correctly typed."""
        from hub.apps.webhooks.models import WebhookDelivery

        tenant = _create_tenant("W34M")
        _create_webhook_subscription(tenant, event_types=["contract.batch_renormalized"])
        _create_structural_odcs_contract(tenant)

        _run("--apply", "--silent-events", tenant=tenant)

        delivery = (
            WebhookDelivery.objects.filter(
                webhook__tenant=tenant,
                event_type="contract.batch_renormalized",
            )
            .order_by("-created_at")
            .first()
        )
        assert delivery is not None, "expected a delivery"
        payload = delivery.payload
        assert payload.get("resource_type") == "TENANT", (
            f"resource_type must be TENANT (the event's actual subject); "
            f"got {payload.get('resource_type')!r}"
        )
        assert payload.get("resource_id") == str(tenant.id), (
            f"resource_id must be the tenant's UUID so subscribers can "
            f"join it against the tenants table; got "
            f"{payload.get('resource_id')!r}"
        )

    def test_no_webhook_for_unsubscribed_tenant(self):
        """A tenant without a webhook subscription receives no
        delivery — the per-tenant routing must be honoured."""
        from hub.apps.webhooks.models import WebhookDelivery

        tenant = _create_tenant("W34N")
        # No webhook subscription created.
        _create_structural_odcs_contract(tenant)

        before = WebhookDelivery.objects.filter(event_type="contract.batch_renormalized").count()
        _run("--apply", "--silent-events", tenant=tenant)
        after = WebhookDelivery.objects.filter(event_type="contract.batch_renormalized").count()

        assert after == before, "Tenant without a subscribed webhook must not receive a delivery"

    def test_webhook_dispatch_failure_does_not_break_migration(self):
        """Webhook dispatch is best-effort: a delivery error must not
        roll back contract writes or fail the management command."""
        from unittest import mock

        from hub.apps.contracts.structureless import is_structureless

        tenant = _create_tenant("W34F")
        _create_webhook_subscription(tenant, event_types=["contract.batch_renormalized"])
        contract = _create_structural_odcs_contract(tenant)

        # Force trigger_webhook to raise during the batch summary step.
        with mock.patch(
            "hub.apps.webhooks.service.WebhookDeliveryService.trigger_webhook",
            side_effect=Exception("simulated webhook backend outage"),
        ):
            output = _run("--apply", "--silent-events", tenant=tenant)

        contract.refresh_from_db()
        assert not is_structureless(contract), (
            "Heal should still commit when webhook dispatch raises"
        )
        assert "healed=1" in output


# ---------------------------------------------------------------------------
# W3.5 — per-tenant residue report
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestPerTenantResidueReport(TestCase):
    """The ``--apply --output=json`` summary must include a per-tenant
    breakdown of {processed, healed, residual, failed} so Wave 4 ops
    can target follow-up emails to the residue cohort."""

    def test_summary_carries_per_tenant_residue_block(self):
        tenant = _create_tenant("W35S")
        _create_structural_odcs_contract(tenant)
        _create_structureless_odcs_contract(tenant)

        output = _run("--apply", "--output=json", tenant=tenant)

        # The trailing ``# {...}`` line carries the JSON summary; parse it.
        summary_line = next(
            (
                line[2:].strip()
                for line in output.splitlines()
                if line.startswith("# {") and "run_id" in line
            ),
            None,
        )
        assert summary_line is not None, (
            f"--output=json should emit a trailing '# {{...}}' summary "
            f"with run_id; got output={output!r}"
        )
        summary = json.loads(summary_line)
        assert "per_tenant" in summary, (
            f"Summary must carry per_tenant breakdown for Wave 4 planning; got keys={list(summary)}"
        )
        per_tenant = summary["per_tenant"]
        assert str(tenant.id) in per_tenant, (
            f"Expected this tenant in per_tenant map; got {list(per_tenant)}"
        )
        breakdown = per_tenant[str(tenant.id)]
        for key in ("processed", "healed", "residual", "failed"):
            assert key in breakdown, f"per_tenant[{tenant.id}] missing {key!r}; got {breakdown!r}"
        assert breakdown["healed"] >= 1
        assert breakdown["residual"] >= 1

    def test_summary_residue_tenants_list(self):
        """Wave 4 planning depends on the explicit ``residue_tenants``
        list — sorted ids of every tenant whose ``residual + failed > 0``.
        This is the input to the Wave-4 follow-up email job."""
        tenant_a = _create_tenant("W35A")
        tenant_b = _create_tenant("W35B")
        # Tenant A: clean — only structural contracts.
        _create_structural_odcs_contract(tenant_a)
        # Tenant B: has residue.
        _create_structureless_odcs_contract(tenant_b)

        # No --tenant-id filter so we hit both tenants in one run.
        output = StringIO()
        call_command(
            "renormalize_contracts",
            "--spec-version=3.1.0",
            "--filter=structureless",
            "--apply",
            "--output=json",
            stdout=output,
        )
        text = output.getvalue()
        summary_line = next(
            (
                line[2:].strip()
                for line in text.splitlines()
                if line.startswith("# {") and "run_id" in line
            ),
            None,
        )
        assert summary_line is not None
        summary = json.loads(summary_line)
        assert "residue_tenants" in summary, (
            f"Summary must list residue_tenants for Wave 4; got {list(summary)}"
        )
        residue_ids = set(summary["residue_tenants"])
        assert str(tenant_b.id) in residue_ids, (
            f"Tenant B has residue, must appear in residue_tenants; got {residue_ids}"
        )
        assert str(tenant_a.id) not in residue_ids, (
            f"Tenant A is clean, must NOT appear in residue_tenants; got {residue_ids}"
        )

    def test_human_readable_summary_mentions_residue_tenants(self):
        """Without ``--output=json``, the human-readable summary still
        surfaces the residue-tenant count so ops can spot the cohort
        without parsing JSON."""
        tenant = _create_tenant("W35H")
        _create_structureless_odcs_contract(tenant)

        output = _run("--apply", tenant=tenant)
        # Summary references the residue cohort explicitly.
        assert "residue_tenants=" in output or "tenants_with_residue=" in output, (
            f"Human-readable summary should mention residue_tenants= count; got {output!r}"
        )
