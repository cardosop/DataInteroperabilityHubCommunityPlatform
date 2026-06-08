"""
Phase 213.H.10 — S3StorageClient credential-handling tests.

Validates the four layers of the IRSA credential fix:

1. Empty AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY must NOT be passed to
   boto3.client (so the default credential resolver chain runs).
2. Non-empty credentials must be passed through.
3. generate_presigned_upload_url must raise RuntimeError when the presigned
   URL has an empty AKID in X-Amz-Credential.
4. Startup STS probe: with ENVIRONMENT=staging and a failing STS call,
   __init__ must raise RuntimeError. With a successful STS call, it must
   log INFO.
"""
from unittest.mock import patch, MagicMock

import pytest
from django.test import TestCase, override_settings


class EmptyCredentialsBypassTest(TestCase):
    """H.10(a): empty creds must NOT be passed to boto3.client."""

    @override_settings(
        AWS_ACCESS_KEY_ID="",
        AWS_SECRET_ACCESS_KEY="",
        AWS_STORAGE_BUCKET_NAME="test-bucket",
        AWS_S3_ENDPOINT_URL="http://localhost:9000",
        ENVIRONMENT="test",
    )
    @patch("hub.apps.files.storage.boto3.client")
    def test_empty_creds_not_passed_to_boto3(self, mock_boto3_client):
        mock_boto3_client.return_value = MagicMock()
        from hub.apps.files.storage import S3StorageClient
        S3StorageClient()

        call_kwargs = mock_boto3_client.call_args_list[0]
        kw = call_kwargs.kwargs if call_kwargs.kwargs else call_kwargs[1]
        # Empty / falsy creds must not reach boto3 as usable values.
        ak = kw.get("aws_access_key_id", "NOT_SET")
        sk = kw.get("aws_secret_access_key", "NOT_SET")
        assert not ak, f"Empty aws_access_key_id leaked as {ak!r}"
        assert not sk, f"Empty aws_secret_access_key leaked as {sk!r}"

    @override_settings(
        AWS_ACCESS_KEY_ID="   ",
        AWS_SECRET_ACCESS_KEY="   ",
        AWS_STORAGE_BUCKET_NAME="test-bucket",
        AWS_S3_ENDPOINT_URL="http://localhost:9000",
        ENVIRONMENT="test",
    )
    @patch("hub.apps.files.storage.boto3.client")
    def test_whitespace_only_creds_not_passed(self, mock_boto3_client):
        mock_boto3_client.return_value = MagicMock()
        from hub.apps.files.storage import S3StorageClient
        S3StorageClient()

        kw = mock_boto3_client.call_args_list[0].kwargs or mock_boto3_client.call_args_list[0][1]
        ak = kw.get("aws_access_key_id", "")
        assert not ak.strip(), f"Whitespace cred leaked as {ak!r}"


class NonEmptyCredentialsPassThroughTest(TestCase):
    """H.10(b): non-empty creds must be passed through."""

    @override_settings(
        AWS_ACCESS_KEY_ID="AKIAIOSFODNN7EXAMPLE",
        AWS_SECRET_ACCESS_KEY="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        AWS_STORAGE_BUCKET_NAME="test-bucket",
        AWS_S3_ENDPOINT_URL="http://localhost:9000",
        ENVIRONMENT="test",
    )
    @patch("hub.apps.files.storage.boto3.client")
    def test_real_creds_passed_through(self, mock_boto3_client):
        mock_boto3_client.return_value = MagicMock()
        from hub.apps.files.storage import S3StorageClient
        S3StorageClient()

        kw = mock_boto3_client.call_args_list[0].kwargs or mock_boto3_client.call_args_list[0][1]
        assert kw["aws_access_key_id"] == "AKIAIOSFODNN7EXAMPLE"
        assert kw["aws_secret_access_key"] == "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"


class PresignedUrlAKIDValidationTest(TestCase):
    """H.10(c): presigned URL with empty AKID must raise RuntimeError."""

    @override_settings(
        AWS_ACCESS_KEY_ID="AKIAIOSFODNN7EXAMPLE",
        AWS_SECRET_ACCESS_KEY="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        AWS_STORAGE_BUCKET_NAME="test-bucket",
        AWS_S3_ENDPOINT_URL="http://localhost:9000",
        ENVIRONMENT="test",
    )
    @patch("hub.apps.files.storage.boto3.client")
    def test_empty_akid_raises_runtime_error(self, mock_boto3_client):
        mock_s3 = MagicMock()
        # Return a presigned URL with EMPTY AKID (the exact bug)
        mock_s3.generate_presigned_url.return_value = (
            "https://bucket.s3.amazonaws.com/key?"
            "X-Amz-Credential=/20260409/us-east-1/s3/aws4_request"
            "&X-Amz-Signature=abc123"
        )
        mock_s3.head_bucket.return_value = {}
        mock_boto3_client.return_value = mock_s3

        from hub.apps.files.storage import S3StorageClient
        client = S3StorageClient()

        with pytest.raises(RuntimeError, match="invalid AKID"):
            client.generate_presigned_upload_url(
                "test/key.txt", "text/plain", expires_in=60
            )

    @override_settings(
        AWS_ACCESS_KEY_ID="AKIAIOSFODNN7EXAMPLE",
        AWS_SECRET_ACCESS_KEY="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        AWS_STORAGE_BUCKET_NAME="test-bucket",
        AWS_S3_ENDPOINT_URL="http://localhost:9000",
        ENVIRONMENT="test",
    )
    @patch("hub.apps.files.storage.boto3.client")
    def test_valid_akid_passes(self, mock_boto3_client):
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.return_value = (
            "https://bucket.s3.amazonaws.com/key?"
            "X-Amz-Credential=AKIAIOSFODNN7EXAMPLE/20260409/us-east-1/s3/aws4_request"
            "&X-Amz-Signature=abc123"
        )
        mock_s3.head_bucket.return_value = {}
        mock_boto3_client.return_value = mock_s3

        from hub.apps.files.storage import S3StorageClient
        client = S3StorageClient()

        # Should not raise
        result = client.generate_presigned_upload_url(
            "test/key.txt", "text/plain", expires_in=60
        )
        assert result["upload_url"]
        assert result["key"] == "test/key.txt"


class STSProbeTest(TestCase):
    """H.10(d): startup STS probe via the extracted _run_sts_probe() method.

    The __init__ STS probe is guarded by ``_is_test`` which is true inside
    pytest. Testing it end-to-end through __init__ would require patching
    sys.modules to hide pytest — fragile and unreliable. Instead we test
    the extracted ``_run_sts_probe`` static method directly, which contains
    all the load-bearing logic (STS call, error wrapping, logging).
    """

    @patch("hub.apps.files.storage.boto3.client")
    def test_sts_failure_raises_runtime_error(self, mock_boto3_client):
        from botocore.exceptions import NoCredentialsError
        from hub.apps.files.storage import S3StorageClient

        mock_sts = MagicMock()
        mock_sts.get_caller_identity.side_effect = NoCredentialsError()
        mock_boto3_client.return_value = mock_sts

        with pytest.raises(RuntimeError, match="STS get_caller_identity.*failed in staging"):
            S3StorageClient._run_sts_probe("staging", {})

    @patch("hub.apps.files.storage.boto3.client")
    def test_sts_failure_message_includes_irsa_hint(self, mock_boto3_client):
        from hub.apps.files.storage import S3StorageClient

        mock_sts = MagicMock()
        mock_sts.get_caller_identity.side_effect = ConnectionError("no route")
        mock_boto3_client.return_value = mock_sts

        with pytest.raises(RuntimeError) as exc_info:
            S3StorageClient._run_sts_probe("production", {})

        msg = str(exc_info.value)
        assert "IRSA annotation" in msg
        assert "AWS_ACCESS_KEY_ID" in msg
        assert "ConnectionError" in msg

    @patch("hub.apps.files.storage.boto3.client")
    def test_sts_success_returns_identity(self, mock_boto3_client):
        from hub.apps.files.storage import S3StorageClient

        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {
            "Arn": "arn:aws:sts::279554171209:assumed-role/hub-staging-eks-irsa-api-service/botocore-session",
            "Account": "279554171209",
            "UserId": "AROAEXAMPLE:botocore-session",
        }
        mock_boto3_client.return_value = mock_sts

        identity = S3StorageClient._run_sts_probe("staging", {})
        assert identity["Arn"].startswith("arn:aws:sts::")
        assert identity["Account"] == "279554171209"

    @patch("hub.apps.files.storage.boto3.client")
    def test_sts_probe_passes_credential_kwargs(self, mock_boto3_client):
        """When static creds are present, they must be forwarded to STS."""
        from hub.apps.files.storage import S3StorageClient

        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Arn": "arn:test", "Account": "123"}
        mock_boto3_client.return_value = mock_sts

        cred_kwargs = {
            "aws_access_key_id": "AKIAEXAMPLE",
            "aws_secret_access_key": "SECRET",
        }
        S3StorageClient._run_sts_probe("staging", cred_kwargs)

        mock_boto3_client.assert_called_once_with(
            "sts",
            aws_access_key_id="AKIAEXAMPLE",
            aws_secret_access_key="SECRET",
        )
