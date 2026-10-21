"""U.6 — REAL (no-mock) browser-facing presigned-URL roundtrip against the
compose staging MinIO.

Proves the actual browser mechanics end-to-end: a presigned PUT + GET against
the browser-facing HOST port (MINIO_API_PORT, 9012 in .env.staging) using the
real staging app credentials — the exact URL shape the ``for_browser`` rewrite
in storage.py produces (unit-pinned by test_presigned_browser_endpoint.py).
No MagicMock, no patched boto3: a real object is written and read back through
the signed URLs a browser would use.

Skipped where ``.env.staging`` is absent (CI — gitignored secret material,
same precedent as scripts/tests/test_staging_env_contract.py). When the file
exists, MinIO reachability follows the W16 environment policy: CI raises
loudly, local runs keep the graceful skip.
"""

import urllib.request
from pathlib import Path

import boto3
import pytest
from botocore.config import Config
from botocore.exceptions import ClientError, EndpointConnectionError

from envpolicy import environment_guard, skip_or_fail

# tests → files → apps → hub → repo root (parents[4])
PROJECT_ROOT = Path(__file__).resolve().parents[4]
ENV_STAGING = PROJECT_ROOT / ".env.staging"


def _env_get(key: str) -> str:
    for line in ENV_STAGING.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.partition("=")[2]
    return ""


pytestmark = pytest.mark.skipif(
    not ENV_STAGING.exists(),
    reason=".env.staging is gitignored secret material — the real-MinIO "
    "browser drill runs only where the staging secrets exist",
)


class TestStagingMinioBrowserPresign:
    def test_presigned_put_get_roundtrip_on_browser_port(self):
        endpoint = f"http://localhost:{_env_get('MINIO_API_PORT') or '9000'}"
        key_id = _env_get("AWS_ACCESS_KEY_ID")
        secret = _env_get("AWS_SECRET_ACCESS_KEY")
        bucket = _env_get("AWS_STORAGE_BUCKET_NAME")
        assert key_id, "AWS_ACCESS_KEY_ID missing from .env.staging"
        assert secret, "AWS_SECRET_ACCESS_KEY missing from .env.staging"
        assert bucket, "AWS_STORAGE_BUCKET_NAME missing from .env.staging"

        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=key_id,
            aws_secret_access_key=secret,
            region_name="us-east-1",
            config=Config(signature_version="s3v4"),
        )
        try:
            client.head_bucket(Bucket=bucket)
        except (ClientError, EndpointConnectionError, OSError):
            # Any S3/connectivity failure means the stack is down — W16
            # policy decides skip vs loud CI failure.
            environment_guard(
                "staging MinIO unreachable on the browser port — bring the "
                "stack up first (make staging-up)"
            )
            skip_or_fail("staging MinIO not reachable — stack is down")

        probe_key = "post-deploy-probe-presign.txt"
        put_url = client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": bucket,
                "Key": probe_key,
                "ContentType": "text/plain",
            },
            ExpiresIn=3600,
        )
        put_req = urllib.request.Request(
            put_url,
            data=b"browser presign probe",
            method="PUT",
            headers={"Content-Type": "text/plain"},
        )
        with urllib.request.urlopen(put_req, timeout=10) as resp:
            assert resp.status == 200, "presigned PUT failed"

        get_url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": probe_key},
            ExpiresIn=3600,
        )
        with urllib.request.urlopen(get_url, timeout=10) as resp:
            assert resp.read() == b"browser presign probe", "presigned GET returned wrong content"

        client.delete_object(Bucket=bucket, Key=probe_key)
