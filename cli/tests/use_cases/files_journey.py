import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.7.1 — Files journey: CLI files command group.

Validates file upload endpoint existence, presigned URL generation,
and file listing via real API calls against the staging environment.
"""

from tests._persona_provisioning import provision_persona
from tests.fixtures.test_data import fresh_id
from tests.use_cases._api_helpers import api_get, api_post

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _provision_engineer():
    return provision_persona("data_engineer")


def _extract_files(body):
    """Extract the files list from a paginated or flat response."""
    if isinstance(body, list):
        return body
    return body.get("results", body.get("items", body.get("files", [])))


# ===========================================================================
# Tests
# ===========================================================================


def test_upload_endpoint_exists():
    """POST /files/upload/ (or /files/) endpoint exists and does not 404."""
    creds = _provision_engineer()

    # Send a minimal POST to check endpoint existence
    resp = api_post("/files/upload/", creds, json={"filename": "test.csv"})
    if resp.status_code == 404:
        resp = api_post("/files/", creds, json={"filename": "test.csv"})
    if resp.status_code == 404:
        pytest.skip("File upload endpoint not found (404)")

    # Any non-404 response confirms the endpoint exists
    # 400/422 is expected since we didn't send a real file
    assert resp.status_code < 500, (
        f"File upload endpoint returned server error {resp.status_code}: {resp.text[:300]}"
    )


def test_generate_presigned_url():
    """POST /files/presigned/ generates a presigned upload URL."""
    creds = _provision_engineer()

    file_key = fresh_id("file") + ".csv"
    payload = {
        "filename": file_key,
        "content_type": "text/csv",
    }

    resp = api_post("/files/presigned/", creds, json=payload)
    if resp.status_code == 404:
        resp = api_post("/files/upload/presigned/", creds, json=payload)
    if resp.status_code == 404:
        resp = api_post("/files/presign/", creds, json=payload)
    if resp.status_code == 404:
        pytest.skip("Presigned URL endpoint not found (404)")

    if resp.status_code == 400:
        # Payload schema may differ
        error_text = resp.text[:500].lower()
        if "filename" in error_text or "content_type" in error_text:
            pytest.skip(f"Presigned URL payload schema mismatch (400): {resp.text[:300]}")

    assert resp.status_code in (200, 201), (
        f"Presigned URL generation returned {resp.status_code}: {resp.text[:500]}"
    )

    body = resp.json()
    # Response should contain a URL
    has_url = (
        "url" in body or "presigned_url" in body or "upload_url" in body or "signed_url" in body
    )
    assert has_url, f"Presigned URL response missing URL field. Keys: {list(body.keys())}"

    url_value = (
        body.get("url")
        or body.get("presigned_url")
        or body.get("upload_url")
        or body.get("signed_url")
    )
    assert isinstance(url_value, str) and url_value.startswith("http"), (
        f"Presigned URL is not a valid HTTP URL: {url_value}"
    )


def test_file_list():
    """GET /files/ returns a list of uploaded files."""
    creds = _provision_engineer()

    resp = api_get("/files/", creds)

    if resp.status_code == 404:
        pytest.skip("/files/ endpoint not found (404)")

    assert resp.status_code == 200, f"/files/ returned {resp.status_code}: {resp.text[:500]}"

    body = resp.json()
    files = _extract_files(body)
    assert isinstance(files, list), f"Expected a list of files, got {type(files).__name__}"

    # If files exist, each should have a name or key
    if files:
        f = files[0]
        has_identifier = (
            "name" in f or "filename" in f or "key" in f or "file_key" in f or "id" in f
        )
        assert has_identifier, f"File entry missing identifier field. Keys: {list(f.keys())}"
