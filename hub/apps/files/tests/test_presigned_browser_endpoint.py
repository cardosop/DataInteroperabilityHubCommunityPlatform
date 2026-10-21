"""U.6 — browser-facing presigned URLs honor the host MinIO port.

The compose staging stack exposes MinIO on a dedicated host port
(MINIO_API_PORT, 9012 by default in .env.staging — distinct from the
test stack's 9010). ``generate_presigned_upload_url(for_browser=True)``
rewrites the in-network endpoint (``minio:9000``) to a host-reachable one;
that rewrite MUST honor MINIO_API_PORT the same way the test-stack branch
honors MINIO_TEST_API_PORT, or browser uploads in staging sign against
localhost:9000 (the dev port) and fail.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from hub.apps.files.storage import S3StorageClient


@pytest.fixture
def storage_client():
    """S3StorageClient without constructor side effects (no boto3 network)."""
    client = S3StorageClient.__new__(S3StorageClient)
    client.endpoint_url = "http://minio:9000"
    client.client = MagicMock()
    client.bucket_name = "hub-files-staging"
    client._bucket_checked = True
    client.use_ssl = False
    client.client.generate_presigned_url.return_value = (
        "https://localhost:9000/hub-files-staging/k?"
        "X-Amz-Credential=minioapp%2F20260831%2Fus-east-1%2Fs3%2Faws4_request"
        "&X-Amz-Signature=abc&X-Amz-Expires=3600"
    )
    return client


def _captured_browser_endpoint(storage_client):
    captured = {}

    def fake_boto_client(_service, **kwargs):
        captured["endpoint_url"] = kwargs.get("endpoint_url")
        return storage_client.client

    with patch("hub.apps.files.storage.boto3.client", side_effect=fake_boto_client):
        storage_client.generate_presigned_upload_url("k", "text/plain", for_browser=True)
    return captured.get("endpoint_url")


class TestPresignedBrowserEndpointRewrite:
    def test_minio_host_uses_minio_api_port_env(self, storage_client):
        """Staging: minio:9000 → localhost:<MINIO_API_PORT> (9012)."""
        with patch.dict(os.environ, {"MINIO_API_PORT": "9012"}):
            endpoint = _captured_browser_endpoint(storage_client)
        assert endpoint == "http://localhost:9012"

    def test_minio_host_defaults_to_dev_port(self, storage_client):
        """No MINIO_API_PORT: the dev convention localhost:9000 remains."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("MINIO_API_PORT", None)
            endpoint = _captured_browser_endpoint(storage_client)
        assert endpoint == "http://localhost:9000"

    def test_test_stack_branch_unchanged(self, storage_client):
        """The minio-test branch still honors MINIO_TEST_API_PORT."""
        storage_client.endpoint_url = "http://minio-test:9000"
        with patch.dict(os.environ, {"MINIO_TEST_API_PORT": "9010"}):
            endpoint = _captured_browser_endpoint(storage_client)
        assert endpoint == "http://localhost:9010"
