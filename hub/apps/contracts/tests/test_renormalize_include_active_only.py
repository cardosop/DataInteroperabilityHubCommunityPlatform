"""
Phase 227 Wave 4 (227.W4.4) — `--include-active-only` flag tests.

The post-deploy structureless smoke gate (deploy.yml) only cares about
**active** structureless contracts: a DRAFT residue contract is the
data-engineer's local edit-buffer and shouldn't fail a deploy.
The smoke-test invocation is::

    python manage.py renormalize_contracts \\
        --filter=structureless \\
        --include-active-only \\
        --dry-run --output=count

These tests pin the flag's filter semantics end-to-end against real
``Contract`` rows (no mocks of internal code).
"""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command
from django.test import TestCase


def _create_tenant(slug_prefix: str = "w44"):
    import uuid as _uuid

    from hub.apps.tenants.models import Tenant

    suffix = _uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"{slug_prefix}-{suffix}",
        slug=f"{slug_prefix}-{suffix}",
    )


def _create_contract(tenant, *, status, hub_contract_json):
    from hub.apps.contracts.models import (
        Contract,
        ContractStatus,
        OriginalFormat,
        OriginalSpecType,
    )

    return Contract.objects.create(
        tenant=tenant,
        version=1,
        original_spec_type=OriginalSpecType.ODCS,
        original_spec_version="3.1.0",
        original_format=OriginalFormat.JSON,
        original_raw="{}",
        hub_contract_json=hub_contract_json,
        normalization_status="NORMALIZED_OK",
        validation_status="VALID",
        status=status or ContractStatus.DRAFT,
    )


_HC_STRUCTURELESS = {"models": [], "schema": {"fields": []}}


def _last_count_line(out: StringIO) -> int:
    """Return the integer count emitted by ``--output=count``.

    ``--output=count`` writes a single integer line; tests consume it
    as the report's authoritative value.
    """
    lines = [ln for ln in out.getvalue().splitlines() if ln.strip()]
    assert lines, f"expected at least one stdout line, got {out.getvalue()!r}"
    last = lines[-1].strip()
    assert last.lstrip("-").isdigit(), f"last stdout line should be an int: {last!r}"
    return int(last)


@pytest.mark.django_db(transaction=True)
class IncludeActiveOnlyFilterTests(TestCase):
    """The flag scopes the structureless predicate to ACTIVE contracts."""

    def setUp(self):
        """Purge structureless contracts left by a previous --reuse-db run."""
        from hub.apps.contracts.models import Contract
        Contract.objects.all().delete()

    def test_active_structureless_counted_when_flag_set(self):
        from hub.apps.contracts.models import ContractStatus

        tenant = _create_tenant("active")
        _create_contract(
            tenant,
            status=ContractStatus.ACTIVE,
            hub_contract_json=_HC_STRUCTURELESS,
        )

        out = StringIO()
        call_command(
            "renormalize_contracts",
            "--spec-version=3.1.0",
            "--filter=structureless",
            "--include-active-only",
            "--dry-run",
            "--output=count",
            stdout=out,
        )
        self.assertEqual(_last_count_line(out), 1)

    def test_draft_structureless_excluded_when_flag_set(self):
        """A DRAFT contract — even if structureless — must NOT count
        against the smoke gate. DRAFT is the data engineer's
        local-edit buffer; failing a deploy on it would block ops on
        a customer's in-progress work."""
        from hub.apps.contracts.models import ContractStatus

        tenant = _create_tenant("draft")
        _create_contract(
            tenant,
            status=ContractStatus.DRAFT,
            hub_contract_json=_HC_STRUCTURELESS,
        )

        out = StringIO()
        call_command(
            "renormalize_contracts",
            "--spec-version=3.1.0",
            "--filter=structureless",
            "--include-active-only",
            "--dry-run",
            "--output=count",
            stdout=out,
        )
        self.assertEqual(_last_count_line(out), 0)

    def test_retired_structureless_excluded_when_flag_set(self):
        """RETIRED contracts are tombstones — the customer has signed
        off on their inactivity. They must not block the smoke gate."""
        from hub.apps.contracts.models import ContractStatus

        tenant = _create_tenant("retired")
        _create_contract(
            tenant,
            status=ContractStatus.RETIRED,
            hub_contract_json=_HC_STRUCTURELESS,
        )

        out = StringIO()
        call_command(
            "renormalize_contracts",
            "--spec-version=3.1.0",
            "--filter=structureless",
            "--include-active-only",
            "--dry-run",
            "--output=count",
            stdout=out,
        )
        self.assertEqual(_last_count_line(out), 0)

    def test_flag_omitted_counts_all_statuses(self):
        """Without ``--include-active-only`` the predicate's behaviour
        is unchanged — DRAFT/ACTIVE/RETIRED structureless rows all
        count. Backwards-compatibility regression guard for the L7.6
        backlog gauge that already integrates with --output=count."""
        from hub.apps.contracts.models import ContractStatus

        tenant = _create_tenant("all")
        for status in (ContractStatus.DRAFT, ContractStatus.ACTIVE, ContractStatus.RETIRED):
            _create_contract(
                tenant,
                status=status,
                hub_contract_json=_HC_STRUCTURELESS,
            )

        out = StringIO()
        call_command(
            "renormalize_contracts",
            "--spec-version=3.1.0",
            "--filter=structureless",
            "--dry-run",
            "--output=count",
            stdout=out,
        )
        self.assertEqual(_last_count_line(out), 3)

    def test_flag_composes_with_tenant_id(self):
        """``--tenant-id`` AND ``--include-active-only`` compose; the
        intersection (one tenant, only ACTIVE structureless rows) is
        what the per-tenant smoke gate uses."""
        from hub.apps.contracts.models import ContractStatus

        a = _create_tenant("compose-a")
        b = _create_tenant("compose-b")
        _create_contract(a, status=ContractStatus.ACTIVE, hub_contract_json=_HC_STRUCTURELESS)
        _create_contract(b, status=ContractStatus.ACTIVE, hub_contract_json=_HC_STRUCTURELESS)
        # Draft on `a` must not count even with --tenant-id=a.
        _create_contract(a, status=ContractStatus.DRAFT, hub_contract_json=_HC_STRUCTURELESS)

        out = StringIO()
        call_command(
            "renormalize_contracts",
            "--spec-version=3.1.0",
            f"--tenant-id={a.id}",
            "--filter=structureless",
            "--include-active-only",
            "--dry-run",
            "--output=count",
            stdout=out,
        )
        # Only the ACTIVE row on tenant `a` is counted.
        self.assertEqual(_last_count_line(out), 1)


@pytest.mark.django_db(transaction=True)
class IncludeActiveOnlyGaugeIsolationTests(TestCase):
    """W4.4-AUDIT-1 regression — ``--include-active-only`` MUST NOT
    write to the global ``contract_structureless_backlog`` Prometheus
    gauge.

    The gauge's canonical semantic (set by the daily backlog cron
    that omits ``--include-active-only``) is "all structureless
    contracts".  The W4.4 smoke gate runs every staging deploy with
    ``--include-active-only`` — writing the active-only count to the
    same gauge would persistently corrupt it.
    """

    def test_include_active_only_does_not_call_set_structureless_backlog(self):
        from unittest.mock import patch

        from hub.apps.contracts.models import ContractStatus

        tenant = _create_tenant("gauge-active")
        _create_contract(
            tenant,
            status=ContractStatus.ACTIVE,
            hub_contract_json=_HC_STRUCTURELESS,
        )

        with patch(
            "hub.apps.contracts.normalization_metrics.set_structureless_backlog"
        ) as mock_set:
            call_command(
                "renormalize_contracts",
                "--spec-version=3.1.0",
                "--filter=structureless",
                "--include-active-only",
                "--dry-run",
                "--output=count",
                stdout=StringIO(),
            )
        mock_set.assert_not_called()

    def test_omitting_active_only_still_calls_set_structureless_backlog(self):
        """Backwards-compat regression: the daily backlog cron's
        invocation (no ``--include-active-only``) MUST keep updating
        the gauge — otherwise the L7.6 backlog dashboard goes dark."""
        from unittest.mock import patch

        from hub.apps.contracts.models import ContractStatus

        tenant = _create_tenant("gauge-all")
        _create_contract(
            tenant,
            status=ContractStatus.ACTIVE,
            hub_contract_json=_HC_STRUCTURELESS,
        )

        with patch(
            "hub.apps.contracts.normalization_metrics.set_structureless_backlog"
        ) as mock_set:
            call_command(
                "renormalize_contracts",
                "--spec-version=3.1.0",
                "--filter=structureless",
                "--dry-run",
                "--output=count",
                stdout=StringIO(),
            )
        # The daily-cron path must still hit the gauge.
        mock_set.assert_called_once()
