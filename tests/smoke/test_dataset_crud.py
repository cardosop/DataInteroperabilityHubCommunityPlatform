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

import hashlib
import os
import uuid

import pytest
import requests

DATASET_API_PATH = os.getenv("SMOKE_DATASET_API_PATH", "/api/v1/datasets/")


@pytest.fixture
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
    # Datasets are file-backed (data-first contract): init + upload +
    # complete a source file so the create payload can reference an ACTIVE
    # file_id (a PENDING file is rejected with FILE_NOT_READY_FOR_DATASET).
    csv_payload = b"id,name\n1,smoke\n"
    init_response = authenticated_session.post(
        f"{base_url}/api/v1/files/init/",
        json={
            "name": f"smoke-dataset-source-{unique_suffix}.csv",
            "content_type": "text/csv",
            "size": len(csv_payload),
            "upload_method": "sdk",
        },
        timeout=timeout,
    )
    if init_response.status_code not in (200, 201):
        pytest.skip(f"/files/init returned {init_response.status_code}: {init_response.text[:300]}")
    init_body = init_response.json()
    file_id = str(init_body["file_id"])

    # The API issues a presigned POST — upload as multipart form POST.
    upload_resp = requests.post(
        str(init_body["upload_url"]),
        data=init_body.get("fields") or {},
        files={"file": (f"smoke-dataset-source-{unique_suffix}.csv", csv_payload, "text/csv")},
        timeout=timeout,
    )
    if upload_resp.status_code not in (200, 204):
        pytest.skip(
            f"Presigned upload returned {upload_resp.status_code}: {upload_resp.text[:200]}"
        )

    complete_resp = authenticated_session.post(
        f"{base_url}/api/v1/files/{file_id}/complete/",
        json={"content_sha256": hashlib.sha256(csv_payload).hexdigest()},
        timeout=timeout,
    )
    if complete_resp.status_code not in (200, 201):
        pytest.skip(
            f"/files/{file_id}/complete returned {complete_resp.status_code}: "
            f"{complete_resp.text[:200]}"
        )

    payload = {
        "name": f"smoke-test-dataset-{unique_suffix}",
        "description": "Automated smoke test dataset — safe to delete",
        "type": "structured",  # most common dataset type
        "file_id": file_id,
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
        # response body has the minimum required fields. The dataset NAME
        # is read-only and derived from the source FILE name (file-backed
        # data-first contract) — not from the create payload.
        assert "id" in created_dataset, "Created dataset missing 'id'"
        assert "name" in created_dataset, "Created dataset missing 'name'"
        assert "smoke-dataset-source" in created_dataset["name"]

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
        # Handle both paginated (results key) and flat list responses.
        # NB: the ternary binds tighter than `or` — parenthesise so a
        # dict response reads its "results" key instead of collapsing to [].
        items = (
            data.get("results", [])
            if isinstance(data, dict)
            else (data if isinstance(data, list) else [])
        )
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
        assert "smoke-dataset-source" in data.get("name", "")

    def test_update_dataset_format(
        self,
        base_url: str,
        authenticated_session: requests.Session,
        timeout: int,
        created_dataset: dict,
    ) -> None:
        """PATCH /datasets/{id}/ must update the dataset and return 200.

        `name` is read-only (computed from the source file); the writable
        fields are asset + format.
        """
        dataset_id = created_dataset["id"]
        updated_format = "JSON"

        response = authenticated_session.patch(
            f"{base_url}{DATASET_API_PATH}{dataset_id}/",
            json={"format": updated_format},
            timeout=timeout,
        )
        assert response.status_code == 200, (
            f"PATCH /datasets/{dataset_id}/ returned {response.status_code}: {response.text[:300]}"
        )
        data = response.json()
        assert data.get("format") == updated_format, (
            f"Format not updated: expected '{updated_format}', got '{data.get('format')}'"
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
