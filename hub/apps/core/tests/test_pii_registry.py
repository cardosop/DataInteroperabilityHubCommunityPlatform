"""CI guard: curated PII inventory matches live Django models (Phase 232.0)."""

import pytest
from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.test import SimpleTestCase

from hub.apps.core.pii_registry import (
    PII_HOLDING_REGISTRY,
    registered_model_labels,
)


class PIIRegistryTests(SimpleTestCase):
    @pytest.mark.unit
    def test_registry_non_empty(self):
        self.assertGreaterEqual(len(PII_HOLDING_REGISTRY), 11)

    @pytest.mark.unit
    def test_catalogue_rows_sorted_by_app_and_model(self):
        keys = [(e.app_label, e.model_name) for e in PII_HOLDING_REGISTRY]
        self.assertEqual(keys, sorted(keys))

    @pytest.mark.unit
    def test_each_entry_maps_to_model_and_fields(self):
        for entry in PII_HOLDING_REGISTRY:
            model_cls = apps.get_model(entry.app_label, entry.model_name)
            for field_name in entry.fields:
                try:
                    model_cls._meta.get_field(field_name)
                except FieldDoesNotExist:
                    self.fail(f"{entry.app_label}.{entry.model_name} missing field {field_name}")

    @pytest.mark.unit
    def test_registered_labels_are_unique(self):
        labels = registered_model_labels()
        self.assertEqual(len(labels), len(set(labels)))
