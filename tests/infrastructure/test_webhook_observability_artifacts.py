"""
Phase 233.6 — Static-content tests for the cross-cutting webhook
observability artefacts: alert rules, Grafana dashboard, and runbook.

These tests run as a lean CI gate (no Django bootstrap, no DB) — pure
file inspection that catches drift in the artefacts before they reach
ops review. Mirrors the pattern at
``tests/infrastructure/test_kms_rotation_runbook_test_contract.py`` +
``tests/infrastructure/test_concurrent_upload_memory_test_contract.py``.

Three artefacts under audit:

  1. ``monitoring/prometheus/alerts/webhook.yml`` — 5 alert rules
     (Phase 233.6.4) covering rate-limit spikes, signature compute
     duration, trigger-volume anomalies, cross-tenant rate-limit, and
     duplicate-skip ratio.

  2. ``monitoring/grafana/dashboards/webhook-health.json`` — Phase
     233.6.3 dashboard with explicit ``uid: "webhook-health"`` so the
     alert rule's ``dashboard_url`` annotation resolves.

  3. ``docs/runbooks/webhook-key-rotation.md`` — Phase 233.6.5 ops
     runbook with the alert-response playbook the alert annotations
     link to.

The tests assert load-bearing CONTENT (specific alert names, the dashboard
uid, runbook section headers) — the artefacts won't validate without the
content the alert annotations reference.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

_ALERTS_PATH = (
    _REPO_ROOT / "monitoring" / "prometheus" / "alerts" / "webhook.yml"
)
_DASHBOARD_PATH = (
    _REPO_ROOT / "monitoring" / "grafana" / "dashboards" / "webhook-health.json"
)
_RUNBOOK_PATH = _REPO_ROOT / "docs" / "runbooks" / "webhook-key-rotation.md"


# Each load-bearing alert rule MUST exist in the alerts file. The names
# match the alert annotations in the runbook + dashboard.
_REQUIRED_ALERT_RULES = (
    "WebhookRateLimitedSpikePerTenant",
    "WebhookSignatureComputeDurationHigh",
    "WebhookTriggerVolumeAnomalyHigh",
    "WebhookRateLimitBlockedAcrossManyTenants",
    "WebhookDuplicateSkipRateHigh",
)


# Each Phase 233.6.2 metric MUST appear in at least one alert expression.
_REQUIRED_METRICS_IN_ALERTS = (
    "meshant_webhook_outbound_total",
    "meshant_webhook_signature_verification_duration_seconds",
    "meshant_webhook_rate_limit_blocks_total",
)


class TestWebhookAlertsYaml:
    """Phase 233.6.4 — webhook.yml structural + content asserts."""

    def test_alerts_file_exists(self) -> None:
        assert _ALERTS_PATH.exists(), f"missing alerts file: {_ALERTS_PATH}"

    def test_alerts_file_has_all_required_rules(self) -> None:
        text = _ALERTS_PATH.read_text()
        # Each rule appears as ``- alert: <Name>`` in the YAML.
        for rule_name in _REQUIRED_ALERT_RULES:
            pattern = rf"^\s*-\s+alert:\s+{re.escape(rule_name)}\s*$"
            assert re.search(pattern, text, flags=re.MULTILINE), (
                f"alert rule '{rule_name}' is missing from {_ALERTS_PATH}"
            )

    def test_alerts_file_references_all_three_metrics(self) -> None:
        text = _ALERTS_PATH.read_text()
        for metric in _REQUIRED_METRICS_IN_ALERTS:
            assert metric in text, (
                f"alert file does not reference metric '{metric}' "
                f"(Phase 233.6.2 metric should be alerted on)"
            )

    def test_each_alert_has_runbook_url_annotation(self) -> None:
        """Every alert rule MUST link to the webhook-key-rotation runbook
        so the on-call can navigate from PagerDuty to the response
        playbook in one click."""
        text = _ALERTS_PATH.read_text()
        # Count alert rules.
        alert_count = len(
            re.findall(r"^\s*-\s+alert:\s+", text, flags=re.MULTILINE)
        )
        # Count runbook_url annotations.
        runbook_url_count = len(
            re.findall(r"runbook_url:\s+\".*webhook-key-rotation", text)
        )
        assert runbook_url_count == alert_count, (
            f"expected {alert_count} runbook_url annotations pointing at "
            f"webhook-key-rotation, found {runbook_url_count}. Every "
            "alert rule must annotate its runbook target."
        )

    def test_alerts_yaml_parses(self) -> None:
        """The YAML file MUST parse — guards against unbalanced quotes,
        bad indentation, etc."""
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError:
            pytest.skip("PyYAML not installed")
        with _ALERTS_PATH.open() as fp:
            data = yaml.safe_load(fp)
        assert isinstance(data, dict) and "groups" in data
        assert len(data["groups"]) >= 1
        rules = data["groups"][0].get("rules", [])
        assert len(rules) == len(_REQUIRED_ALERT_RULES), (
            f"expected exactly {len(_REQUIRED_ALERT_RULES)} alert rules; "
            f"got {len(rules)}"
        )


class TestWebhookHealthDashboard:
    """Phase 233.6.3 — webhook-health.json structural + content asserts."""

    def test_dashboard_file_exists(self) -> None:
        assert _DASHBOARD_PATH.exists(), f"missing dashboard: {_DASHBOARD_PATH}"

    def test_dashboard_parses_as_json(self) -> None:
        with _DASHBOARD_PATH.open() as fp:
            data = json.load(fp)
        assert isinstance(data, dict)

    def test_dashboard_has_canonical_uid_for_alert_links(self) -> None:
        """The dashboard's ``uid`` MUST equal ``webhook-health`` so the
        alert annotations' ``dashboard_url=https://meshant-internal.example.com/d/webhook-health``
        resolve. Without this, alert clickers land on a 404."""
        with _DASHBOARD_PATH.open() as fp:
            data = json.load(fp)
        assert data.get("uid") == "webhook-health", (
            f"dashboard uid is '{data.get('uid')}', expected 'webhook-health'"
        )

    def test_dashboard_panels_reference_all_three_metrics(self) -> None:
        """Each Phase 233.6.2 metric MUST be visualised on at least one
        panel — otherwise the metric is unobservable."""
        text = _DASHBOARD_PATH.read_text()
        for metric in _REQUIRED_METRICS_IN_ALERTS:
            assert metric in text, (
                f"dashboard does not visualise metric '{metric}'"
            )

    def test_dashboard_has_alert_state_indicators(self) -> None:
        """Three load-bearing alerts MUST have firing-state stat panels
        on the dashboard so the on-call sees alert state alongside the
        underlying metrics."""
        text = _DASHBOARD_PATH.read_text()
        for alert in (
            "WebhookRateLimitedSpikePerTenant",
            "WebhookSignatureComputeDurationHigh",
            "WebhookRateLimitBlockedAcrossManyTenants",
        ):
            assert alert in text, (
                f"dashboard missing alert-state panel for '{alert}'"
            )

    def test_dashboard_has_at_least_eight_panels(self) -> None:
        """Sanity — guards against the dashboard being gutted to a single
        panel by accident."""
        with _DASHBOARD_PATH.open() as fp:
            data = json.load(fp)
        assert len(data.get("panels", [])) >= 8, (
            "dashboard has fewer than 8 panels; appears to have been gutted"
        )


class TestWebhookKeyRotationRunbook:
    """Phase 233.6.5 — webhook-key-rotation.md content asserts."""

    def test_runbook_file_exists(self) -> None:
        assert _RUNBOOK_PATH.exists(), f"missing runbook: {_RUNBOOK_PATH}"

    def test_runbook_has_required_sections(self) -> None:
        text = _RUNBOOK_PATH.read_text()
        for header in (
            "## Planned rotation procedure",
            "## Compromise response",
            "## Reading the dashboard",
            "## Alert response playbook",
            "## Common failure modes",
            "## Sign-off",
        ):
            # Allow trailing parenthetical (e.g. "Compromise response (immediate
            # rotation)"). Match the prefix.
            assert any(
                line.startswith(header) for line in text.splitlines()
            ), f"runbook missing required section header: '{header}'"

    def test_runbook_references_each_alert_in_response_playbook(self) -> None:
        """The "Alert response playbook" section MUST mention each of the
        load-bearing alerts so the on-call has a documented response
        for every alert annotation that links here."""
        text = _RUNBOOK_PATH.read_text()
        for alert in _REQUIRED_ALERT_RULES:
            assert alert in text, (
                f"runbook does not reference alert '{alert}' — the alert's "
                "annotation links here, but the runbook has no response "
                "playbook for it"
            )

    def test_runbook_references_phase_artefacts(self) -> None:
        """The runbook MUST cross-link to the load-bearing artefacts so a
        future audit can verify the cross-references are intact."""
        text = _RUNBOOK_PATH.read_text()
        # The customer migration guide.
        assert "webhook-rolling-key-rotation.md" in text, (
            "runbook does not cross-link to the customer migration guide"
        )
        # The alert rules file.
        assert "monitoring/prometheus/alerts/webhook.yml" in text, (
            "runbook does not cross-link to the alert rules file"
        )
        # The dashboard.
        assert "monitoring/grafana/dashboards/webhook-health.json" in text, (
            "runbook does not cross-link to the dashboard"
        )

    def test_runbook_documents_compromise_response_force_retire(self) -> None:
        """The compromise-response section MUST document the manual
        force-retire SQL. Without this documented, an operator
        responding to a leak would default to the standard 24h overlap
        rotation — leaving the leaked secret valid for 24 hours."""
        text = _RUNBOOK_PATH.read_text()
        assert "UPDATE webhook_signing_keys" in text, (
            "runbook compromise-response section does not document the "
            "manual force-retire SQL — operators would not know how to "
            "revoke a leaked secret faster than the 24h overlap window"
        )
