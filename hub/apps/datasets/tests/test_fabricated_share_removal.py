"""5.5 — the fabricated dataset share descriptor action is removed.

Phase 275.D.3's ``GET /api/v1/datasets/{id}/share/`` action built a
hand-fabricated Delta Sharing descriptor (``{share, protocol, meta}``
with no protocol bearer-token auth and no ``semantic_federate_optout``
honoring). Design D6 removes it, not migrates it — the native protocol
surface (bearer-token auth, opt-out filtered listings + direct fetches)
replaced it under ``/api/v1/databricks/delta-sharing``.

These pins are pure URL resolution — no DB access needed.
"""

import pytest
from django.test import SimpleTestCase
from django.urls import NoReverseMatch, Resolver404, resolve, reverse

DATASET_UUID = "00000000-0000-0000-0000-000000000000"


class FabricatedDatasetShareRemovalTests(SimpleTestCase):
    """The share action's path and reverse name are gone."""

    def test_the_share_path_no_longer_resolves(self):
        with pytest.raises(Resolver404):
            resolve(f"/api/v1/datasets/{DATASET_UUID}/share/")

    def test_the_share_reverse_name_is_gone(self):
        with pytest.raises(NoReverseMatch):
            reverse("dataset-share", kwargs={"id": DATASET_UUID})
