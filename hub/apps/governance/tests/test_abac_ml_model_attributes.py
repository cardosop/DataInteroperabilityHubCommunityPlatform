"""
Phase 313.H.3 — ABAC ML_MODEL attribute enrichment boundary.

``ABACEngine._get_resource_attributes`` enriches ML_MODEL attributes
through the commercial hook ``get_ml_model_attributes`` (the paid ml
app registers the provider). Core-only mode has no provider → the
base attributes are returned without ML enrichment (no ML models
exist there).

NO MOCKS at contract boundaries: real Postgres, real ORM, real
ABAC engine, real ml models in full mode.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.core import commercial_hooks
from hub.apps.governance.abac import ABACEngine
from hub.apps.ml.models import MLModel, ModelStatus, ModelType
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class AbacMlModelAttributeTests(TestCase):
    """ML_MODEL attribute resolution — full-mode vs core-only."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"T-{uid}", slug=f"t-{uid}", status="ACTIVE")
        self.user = User.objects.create_user(
            email=f"u-{uid}@meshant.test", password="testpass", tenant=self.tenant
        )
        self.ml_model = MLModel.objects.create(
            tenant=self.tenant,
            odh_model_id=f"odh-{uid}",
            odh_model_name="Sentinel Classifier",
            odh_model_version="v1",
            model_type=ModelType.CLASSIFICATION,
            status=ModelStatus.DEPLOYED,
        )

    def _resolve(self):
        return ABACEngine._get_resource_attributes(
            "ML_MODEL",
            str(self.ml_model.id),
            str(self.tenant.id),
        )

    def test_full_mode_enriches_ml_model_attributes(self):
        attributes = self._resolve()
        assert attributes["ml_model_name"] == "Sentinel Classifier"
        assert attributes["ml_model_type"] == self.ml_model.model_type
        assert attributes["ml_model_version"] == "v1"

    def test_core_only_returns_base_attributes_without_enrichment(self):
        with commercial_hooks.hooks_snapshot():
            commercial_hooks.reset_hooks()
            attributes = self._resolve()
        assert attributes["resource_type"] == "ML_MODEL"
        assert "ml_model_name" not in attributes
