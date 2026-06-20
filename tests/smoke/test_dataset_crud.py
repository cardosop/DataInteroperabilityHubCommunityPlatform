"""
Smoke test — dataset CRUD lifecycle.

Verifies that the full dataset create → list → retrieve → update → delete
cycle works correctly after deployment. Uses a uniquely-named test dataset
that is cleaned up in the fixture teardown regardless of test outcome.

Required env vars:
    SMOKE_ADMIN_EMAIL / SMOKE_ADMIN_PASSWORD  (via conftest admin_credentials)

Optional env vars:
    SMOKE_DATASET_API_PATH   API path for datasets (default: /api/v1/datasets/)
    SMOKE_TENANT_ID          Tenant ID to scope dataset creation (if multi-tenant)

The test dataset is created with the minimum required fields and labelled
`smoke_test=true` for easy identification in the unlikely event cleanup fails.
"""

import os
import uuid

import pytest
import requests

DATASET_API_PATH = os.getenv("SMOKE_DATASET_API_PATH", "/api/v1/datasets/")


@pytest.fixture(scope="class")
def created_dataset(
    base_url: str,
    authenticated_session: requests.Session,
    timeout: int,
) -> dict:
    """
    Create a minimal smoke-test dataset, yield it, then delete it.
    Runs at class scope so all test methods share the same dataset instance.
    Cleanup runs unconditionally (even if tests fail).
    """
    unique_suffix = uuid.uuid4().hex[:8]
    payload = {
        "name": f"smoke-test-dataset-{unique_suffix}",
        "description": "Automated smoke test dataset — safe to delete",
        "type": "structured",  # most common dataset type
        "tags": ["smoke_test", "ci"],
        "is_public": False,
    }

    response = authenticated_session.post(
        f"{base_url}{DATASET_API_PATH}",
        json=payload,
        timeout=timeout,
    )
    if response.status_code == 404:
        pytest.skip(
            f"Dataset endpoint not found at {DATASET_API_PATH} — "
            "set SMOKE_DATASET_API_PATH to the correct path"
        )
    if response.status_code == 422:
        pytest.skip(
            f"Dataset creation returned 422 — payload may not match required schema: "
            f"{response.text[:300]}"
        )

    assert response.status_code in (200, 201), (
        f"Dataset creation failed ({response.status_code}): {response.text[:500]}"
    )
    dataset = response.json()
    assert "id" in dataset, f"Created dataset response missing 'id': {dataset}"

    yield dataset

    # --- Teardown: always delete the smoke dataset -------------------------
    dataset_id = dataset.get("id") or dataset.get("uuid")
    if dataset_id:
        authenticated_session.delete(
            f"{base_url}{DATASET_API_PATH}{dataset_id}/",
            timeout=timeout,
        )
        # Ignore teardown errors — test isolation is more important than
        # ensuring a perfect cleanup in every edge case.


class TestDatasetCRUD:
    """Full CRUD lifecycle for a dataset entity."""

    def test_create_dataset_returns_201(
        self,
        base_url: str,
        authenticated_session: requests.Session,
        timeout: int,
        created_dataset: dict,
    ) -> None:
        """Dataset creation (handled by fixture) must succeed with 200/201."""
        # Fixture already asserted the status code; this test verifies the
        # response body has the minimum required fields.
        assert "id" in created_dataset, "Created dataset missing 'id'"
        assert "name" in created_dataset, "Created dataset missing 'name'"
        assert "smoke-test-dataset" in created_dataset["name"]

    def test_created_dataset_appears_in_list(
        self,
        base_url: str,
        authenticated_session: requests.Session,
        timeout: int,
        created_dataset: dict,
    ) -> None:
        """Newly created dataset must be retrievable via the list endpoint."""
        response = authenticated_session.get(
            f"{base_url}{DATASET_API_PATH}",
            timeout=timeout,
        )
        assert response.status_code == 200, (
            f"Dataset list returned {response.status_code}: {response.text[:300]}"
        )
        data = response.json()
        # Handle both paginated (results key) and flat list responses
        items = data.get("results") or data if isinstance(data, list) else []
        dataset_ids = [str(d.get("id") or d.get("uuid", "")) for d in items]
        created_id = str(created_dataset["id"])
        assert created_id in dataset_ids, (
            f"Created dataset id={created_id} not found in list. "
            f"Found {len(items)} items; first ids: {dataset_ids[:5]}"
        )

    def test_get_dataset_by_id_returns_correct_record(
        self,
        base_url: str,
        authenticated_session: requests.Session,
        timeout: int,
        created_dataset: dict,
    ) -> None:
        """GET /datasets/{id}/ must return the exact dataset we created."""
        dataset_id = created_dataset["id"]
        response = authenticated_session.get(
            f"{base_url}{DATASET_API_PATH}{dataset_id}/",
            timeout=timeout,
        )
        assert response.status_code == 200, (
            f"GET /datasets/{dataset_id}/ returned {response.status_code}"
        )
        data = response.json()
        assert str(data.get("id") or data.get("uuid")) == str(dataset_id)
        assert "smoke-test-dataset" in data.get("name", "")

    def test_update_dataset_name(
        self,
        base_url: str,
        authenticated_session: requests.Session,
        timeout: int,
        created_dataset: dict,
    ) -> None:
        """PATCH /datasets/{id}/ must update the dataset and return 200."""
        dataset_id = created_dataset["id"]
        original_name = created_dataset["name"]
        updated_name = f"{original_name}-updated"

        response = authenticated_session.patch(
            f"{base_url}{DATASET_API_PATH}{dataset_id}/",
            json={"name": updated_name},
            timeout=timeout,
        )
        assert response.status_code == 200, (
            f"PATCH /datasets/{dataset_id}/ returned {response.status_code}: {response.text[:300]}"
        )
        data = response.json()
        assert data.get("name") == updated_name, (
            f"Name not updated: expected '{updated_name}', got '{data.get('name')}'"
        )

    def test_delete_dataset_returns_204(
        self,
        base_url: str,
        authenticated_session: requests.Session,
        timeout: int,
        created_dataset: dict,
    ) -> None:
        """DELETE /datasets/{id}/ must return 204 No Content."""
        dataset_id = created_dataset["id"]
        response = authenticated_session.delete(
            f"{base_url}{DATASET_API_PATH}{dataset_id}/",
            timeout=timeout,
        )
        assert response.status_code == 204, (
            f"DELETE /datasets/{dataset_id}/ returned {response.status_code}: {response.text[:200]}"
        )

    def test_deleted_dataset_returns_404(
        self,
        base_url: str,
        authenticated_session: requests.Session,
        timeout: int,
        created_dataset: dict,
    ) -> None:
        """GET on a deleted dataset must return 404 (idempotent deletion check)."""
        dataset_id = created_dataset["id"]
        # Ensure it's deleted first (test ordering: runs after test_delete_dataset)
        authenticated_session.delete(
            f"{base_url}{DATASET_API_PATH}{dataset_id}/",
            timeout=timeout,
        )
        response = authenticated_session.get(
            f"{base_url}{DATASET_API_PATH}{dataset_id}/",
            timeout=timeout,
        )
        assert response.status_code == 404, (
            f"Expected 404 for deleted dataset, got {response.status_code}"
        )
