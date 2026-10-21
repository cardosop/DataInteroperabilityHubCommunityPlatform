"""Fixture mixing ORM queries and status-code assertions. Expected counts:

- except_exception_pass_count: 0
- orm_query_count: 3  (Asset.objects.get, Asset.objects.filter, Dataset.objects.create)
- status_code_assertion_count: 3  (== 201, == 200, != 500)
- test_skip_call_count: 1  (pytest.skip)
"""

import pytest


class FakeAsset:
    objects = None


class FakeDataset:
    objects = None


def test_create_asset(client):
    resp = client.post("/api/v1/assets/", {"name": "foo"})
    assert resp.status_code == 201
    asset = FakeAsset.objects.get(id=resp.json()["id"])
    assert asset.name == "foo"


def test_list_assets(client):
    resp = client.get("/api/v1/assets/")
    assert resp.status_code == 200
    _ = FakeAsset.objects.filter(tenant_id=1)


def test_no_server_error(client):
    resp = client.get("/api/v1/health/")
    assert resp.status_code != 500


def test_create_dataset(client):
    pytest.skip("not wired yet")
    FakeDataset.objects.create(name="x")
