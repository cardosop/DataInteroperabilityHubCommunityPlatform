"""Phase 232.8.16 — Phase-232 subsystem events are valid WebhookEventType choices."""

from __future__ import annotations

import pytest
from django.test import SimpleTestCase

from hub.apps.webhooks.models import WebhookEventType


class Phase232WebhookRegistryTests(SimpleTestCase):
    @pytest.mark.unit
    def test_subsystem_event_bundle_nonempty(self):
        types_ = WebhookEventType.get_phase232_subsystem_event_types()
        self.assertGreaterEqual(len(types_), 7)
        choice_values = {c[0] for c in WebhookEventType.choices}
        for t in types_:
            self.assertIn(t, choice_values, msg=f"missing from WebhookEventType.choices: {t}")
