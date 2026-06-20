"""
Unit tests for SupportChannel object normalization.
"""

import json

from django.test import TestCase

from hub.apps.contracts.models import NormalizationStatus
from hub.apps.contracts.normalization import normalize_contract


class TestSupportChannelNormalization(TestCase):
    """Tests for SupportChannel object normalization."""

    def test_extract_support_channels_separate_from_contacts(self):
        """Test that support channels are extracted separately from contacts."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "support": [
                {
                    "name": "Support Team",
                    "email": "support@example.com",
                },
                {
                    "tool": "slack",
                    "url": "https://slack.example.com/channel",
                    "description": "Slack support channel",
                    "scope": "general",
                },
                {
                    "tool": "ticket",
                    "url": "https://tickets.example.com",
                    "description": "Ticket system",
                },
            ],
        }

        hub_contract, _spec_type, _spec_version, status, _errors, _warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract), format="JSON", spec_type="ODCS"
        )

        assert (
            status == NormalizationStatus.NORMALIZED_OK
            or status == NormalizationStatus.NORMALIZED_WITH_WARNINGS
        )
        assert hub_contract is not None

        # Check contacts (entries with name/email)
        assert "contact" in hub_contract
        assert len(hub_contract["contact"]) == 1
        assert hub_contract["contact"][0]["name"] == "Support Team"
        assert hub_contract["contact"][0]["email"] == "support@example.com"

        # Check support channels (entries without name/email)
        assert "support" in hub_contract
        assert len(hub_contract["support"]) == 2

        slack_channel = next((c for c in hub_contract["support"] if c.get("tool") == "slack"), None)
        assert slack_channel is not None
        assert slack_channel["url"] == "https://slack.example.com/channel"
        assert slack_channel["description"] == "Slack support channel"
        assert slack_channel["scope"] == "general"

        ticket_channel = next(
            (c for c in hub_contract["support"] if c.get("tool") == "ticket"), None
        )
        assert ticket_channel is not None
        assert ticket_channel["url"] == "https://tickets.example.com"

    def test_extract_support_channel_properties(self):
        """Test extraction of all support channel properties."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "support": [
                {
                    "tool": "email",
                    "url": "mailto:support@example.com",
                    "description": "Email support",
                    "scope": "technical",
                },
                {
                    "tool": "teams",
                    "url": "https://teams.microsoft.com/channel",
                    "description": "Microsoft Teams channel",
                    "scope": "general",
                },
                {
                    "tool": "discord",
                    "url": "https://discord.gg/channel",
                    "description": "Discord server",
                },
            ],
        }

        hub_contract, _spec_type, _spec_version, _status, _errors, _warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract), format="JSON", spec_type="ODCS"
        )

        assert hub_contract is not None
        assert "support" in hub_contract
        assert len(hub_contract["support"]) == 3

        for channel in hub_contract["support"]:
            assert "tool" in channel
            assert channel["tool"] in ["email", "teams", "discord"]
            assert "url" in channel
            assert "description" in channel

    def test_support_channels_without_contact_info(self):
        """Test that entries without name/email are treated as support channels."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "support": [
                {
                    "tool": "slack",
                    "url": "https://slack.example.com",
                },
            ],
        }

        hub_contract, _spec_type, _spec_version, _status, _errors, _warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract), format="JSON", spec_type="ODCS"
        )

        assert hub_contract is not None
        assert "support" in hub_contract
        assert len(hub_contract["support"]) == 1
        assert hub_contract["support"][0]["tool"] == "slack"

        # Should not be in contacts
        assert "contact" not in hub_contract or len(hub_contract.get("contact", [])) == 0

    def test_preserve_unmappable_fields_in_support_channels(self):
        """Test that unmappable fields are preserved in support channel extensions."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "support": [
                {
                    "tool": "custom",
                    "url": "https://custom.example.com",
                    "customProperty": "customValue",
                    "anotherCustom": {"nested": "value"},
                },
            ],
        }

        hub_contract, _spec_type, _spec_version, _status, _errors, _warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract), format="JSON", spec_type="ODCS"
        )

        assert hub_contract is not None
        assert "support" in hub_contract

        channel = hub_contract["support"][0]
        assert channel["tool"] == "custom"
        # Unmappable fields should be in extensions
        assert "extensions" in channel or channel.get("customProperty") is not None

    def test_missing_support_handling(self):
        """Test handling when support[] is missing."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        hub_contract, _spec_type, _spec_version, status, _errors, _warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract), format="JSON", spec_type="ODCS"
        )

        assert (
            status == NormalizationStatus.NORMALIZED_OK
            or status == NormalizationStatus.NORMALIZED_WITH_WARNINGS
        )
        assert hub_contract is not None
        # support should not be present if not in source
        assert "support" not in hub_contract or hub_contract.get("support") is None

    def test_invalid_support_data_handling(self):
        """Test handling of invalid support data."""
        odcs_contract = {
            "apiVersion": "odcs/v3",
            "kind": "DataContract",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
            "support": "invalid_string",  # Should be list
        }

        hub_contract, _spec_type, _spec_version, status, _errors, _warnings = normalize_contract(
            raw_contract=json.dumps(odcs_contract), format="JSON", spec_type="ODCS"
        )

        # Should still normalize but skip invalid support
        assert (
            status == NormalizationStatus.NORMALIZED_OK
            or status == NormalizationStatus.NORMALIZED_WITH_WARNINGS
        )
        assert hub_contract is not None
        # support should not be present if invalid
        assert (
            "support" not in hub_contract
            or hub_contract.get("support") is None
            or len(hub_contract.get("support", [])) == 0
        )
