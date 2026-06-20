"""
Shared test fixtures for AWS Data Exchange tests.

When AWS credentials are not available, patches ``boto3.client`` to
return mock clients with deterministic sample data.  This allows the
full connector code path to be exercised without external dependencies.

Usage in test classes::

    from .conftest import ensure_aws_credentials_or_mock

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._aws_patcher = ensure_aws_credentials_or_mock()
        ...
        credentials = get_aws_credentials_or_mock()
        cls.connector = AWSDataExchangeConnector(**credentials)

Also provides factory state save/restore helpers because
``MarketplaceConnectorFactory._connectors`` is a class-level dict
shared across all test files.  Tests that mutate it MUST restore
the original state to prevent cross-test contamination.
"""

from __future__ import annotations

import copy
import os
import unittest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Factory state save / restore — prevents cross-test contamination
# ---------------------------------------------------------------------------

_ORIGINAL_FACTORY_CONNECTORS: dict | None = None


def capture_factory_state():
    """Save a deep copy of the factory connector registry.

    Call once at module level (``setUpModule``) so tests that mutate
    ``MarketplaceConnectorFactory._connectors`` can restore the
    original state in ``tearDownModule``.
    """
    global _ORIGINAL_FACTORY_CONNECTORS
    from hub.apps.integrations.factory import MarketplaceConnectorFactory

    if _ORIGINAL_FACTORY_CONNECTORS is None:
        _ORIGINAL_FACTORY_CONNECTORS = copy.deepcopy(
            MarketplaceConnectorFactory._connectors
        )


def restore_factory_state():
    """Restore the factory connector registry to its captured state."""
    global _ORIGINAL_FACTORY_CONNECTORS
    from hub.apps.integrations.factory import MarketplaceConnectorFactory

    if _ORIGINAL_FACTORY_CONNECTORS is not None:
        MarketplaceConnectorFactory._connectors.clear()
        MarketplaceConnectorFactory._connectors.update(
            copy.deepcopy(_ORIGINAL_FACTORY_CONNECTORS)
        )


# ---------------------------------------------------------------------------
# Sample data — realistic enough to exercise the full connector code path
# ---------------------------------------------------------------------------

SAMPLE_DATASET_ID = "f1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"
SAMPLE_REVISION_ID = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
SAMPLE_JOB_ID = "job-12345-abcde"
SAMPLE_ASSET_ID = "asset-67890-fghij"
SAMPLE_BUCKET = "aws-dataexchange-test-bucket"
SAMPLE_KEY = "exported-data/sample-dataset/rev-1/data.csv"

# Timestamps as AWS-style epoch seconds
_TS_NOW = 1700000000


def _make_list_datasets_response():
    return {
        "DataSets": [
            {
                "Id": SAMPLE_DATASET_ID,
                "Arn": f"arn:aws:dataexchange:us-east-1:123456789012:data-sets/{SAMPLE_DATASET_ID}",
                "AssetType": "S3_SNAPSHOT",
                "Name": "Sample AWS Data Exchange Dataset",
                "Description": "A sample dataset for integration testing",
                "Origin": "ENTITLED",
                "CreatedAt": _TS_NOW - 86400 * 30,
                "UpdatedAt": _TS_NOW - 86400,
                "OriginDetails": {},
            }
        ],
        "NextToken": None,
    }


def _make_get_dataset_response(dataset_id=SAMPLE_DATASET_ID):
    return {
        "Id": dataset_id,
        "Arn": f"arn:aws:dataexchange:us-east-1:123456789012:data-sets/{dataset_id}",
        "AssetType": "S3_SNAPSHOT",
        "Name": "Sample AWS Data Exchange Dataset",
        "Description": "A sample dataset for integration testing",
        "Origin": "ENTITLED",
        "CreatedAt": _TS_NOW - 86400 * 30,
        "UpdatedAt": _TS_NOW - 86400,
        "OriginDetails": {},
    }


def _make_list_revisions_response():
    return {
        "Revisions": [
            {
                "Id": SAMPLE_REVISION_ID,
                "Arn": f"arn:aws:dataexchange:us-east-1:123456789012:data-sets/{SAMPLE_DATASET_ID}/revisions/{SAMPLE_REVISION_ID}",
                "DataSetId": SAMPLE_DATASET_ID,
                "Comment": "Sample revision",
                "CreatedAt": _TS_NOW - 86400 * 7,
                "UpdatedAt": _TS_NOW - 86400 * 7,
                "Finalized": True,
            }
        ],
        "NextToken": None,
    }


def _make_list_revision_assets_response():
    return {
        "Assets": [
            {
                "Id": SAMPLE_ASSET_ID,
                "Arn": f"arn:aws:dataexchange:us-east-1:123456789012:data-sets/{SAMPLE_DATASET_ID}/revisions/{SAMPLE_REVISION_ID}/assets/{SAMPLE_ASSET_ID}",
                "DataSetId": SAMPLE_DATASET_ID,
                "RevisionId": SAMPLE_REVISION_ID,
                "Name": "sample-data.csv",
                "AssetType": "S3_SNAPSHOT",
                "CreatedAt": _TS_NOW - 86400 * 7,
                "UpdatedAt": _TS_NOW - 86400 * 7,
                "AssetDetails": {
                    "S3SnapshotAsset": {
                        "Size": 1024,
                        "S3Bucket": {"Bucket": SAMPLE_BUCKET, "Key": SAMPLE_KEY},
                    }
                },
            }
        ],
        "NextToken": None,
    }


def _make_create_job_response():
    return {
        "Id": SAMPLE_JOB_ID,
        "Arn": f"arn:aws:dataexchange:us-east-1:123456789012:jobs/{SAMPLE_JOB_ID}",
        "Type": "EXPORT_ASSETS_TO_S3",
        "State": "COMPLETED",
        "CreatedAt": _TS_NOW,
        "UpdatedAt": _TS_NOW,
        "Details": {
            "ExportAssetsToS3": {
                "DataSetId": SAMPLE_DATASET_ID,
                "RevisionId": SAMPLE_REVISION_ID,
                "AssetDestinations": [
                    {
                        "AssetId": SAMPLE_ASSET_ID,
                        "Bucket": SAMPLE_BUCKET,
                        "Key": SAMPLE_KEY,
                    }
                ],
            }
        },
    }


def _make_start_job_response():
    return {"State": "COMPLETED"}


def _make_get_job_response():
    return {
        "Id": SAMPLE_JOB_ID,
        "State": "COMPLETED",
        "CreatedAt": _TS_NOW,
        "UpdatedAt": _TS_NOW,
        "Details": {
            "ExportAssetsToS3": {
                "DataSetId": SAMPLE_DATASET_ID,
                "RevisionId": SAMPLE_REVISION_ID,
                "AssetDestinations": [
                    {
                        "AssetId": SAMPLE_ASSET_ID,
                        "Bucket": SAMPLE_BUCKET,
                        "Key": SAMPLE_KEY,
                    }
                ],
            }
        },
    }


def _make_s3_list_objects_response():
    return {
        "Contents": [
            {
                "Key": SAMPLE_KEY,
                "Size": 1024,
                "LastModified": _TS_NOW,
                "ETag": '"abc123def456"',
            }
        ]
    }


def _make_s3_get_object_response():
    body = MagicMock()
    body.read.return_value = b"col1,col2,col3\nval1,val2,val3\n"
    return {"Body": body, "ContentLength": 30, "ContentType": "text/csv"}


# ---------------------------------------------------------------------------
# Mock boto3 clients
# ---------------------------------------------------------------------------


def _create_fake_dataexchange_client():
    """Return a MagicMock configured to respond to AWS Data Exchange API calls.

    Specific dataset IDs trigger error responses so error-mapping tests
    can run without real AWS:

    * ``\"0\" * 32`` (32 zeros) or IDs starting with ``\"invalid-\"`` →
      ``NotFoundException`` (simulates non-existent resource).
    """
    client = MagicMock(name="dataexchange")

    # list_data_sets always returns sample data.
    client.list_data_sets.return_value = _make_list_datasets_response()

    # get_data_set raises NotFoundError for known-invalid IDs.
    def _get_data_set(DataSetId, **kwargs):
        if DataSetId == "0" * 32 or str(DataSetId).startswith("invalid-"):
            raise _make_not_found_exception("GetDataSet", DataSetId)
        return _make_get_dataset_response(DataSetId)

    client.get_data_set.side_effect = _get_data_set

    # list_listings also calls get_data_set internally via _get_dataset_details.
    # list_revisions and list_assets return sample data.
    client.list_data_set_revisions.return_value = _make_list_revisions_response()
    client.list_revision_assets.return_value = _make_list_revision_assets_response()
    client.create_job.return_value = _make_create_job_response()
    client.start_job.return_value = _make_start_job_response()
    client.get_job.return_value = _make_get_job_response()
    return client


def _make_not_found_exception(operation, resource_id):
    """Build a botocore-style ResourceNotFoundException."""
    error_response = {
        "Error": {
            "Code": "ResourceNotFoundException",
            "Message": f"Resource {resource_id} not found",
        }
    }
    try:
        from botocore.exceptions import ClientError
    except ImportError:
        return RuntimeError(f"Not found: {resource_id}")
    return ClientError(error_response, operation)


def _create_fake_s3_client():
    """Return a MagicMock configured to respond to AWS S3 API calls."""
    client = MagicMock(name="s3")
    client.list_objects_v2.return_value = _make_s3_list_objects_response()
    client.get_object.return_value = _make_s3_get_object_response()
    client.head_object.return_value = {"ContentLength": 30}
    client.generate_presigned_url.return_value = (
        f"https://{SAMPLE_BUCKET}.s3.amazonaws.com/{SAMPLE_KEY}"
    )
    return client


def _fake_boto3_client(service_name, **kwargs):
    """Drop-in replacement for ``boto3.client`` that returns mock clients.

    Detects invalid credentials (``aws_access_key_id="invalid-key"``)
    and returns a client that raises ``AccessDeniedException`` for
    ``dataexchange`` calls, so error-mapping tests run without real AWS.
    """
    if service_name == "dataexchange":
        key = kwargs.get("aws_access_key_id", "")
        if key in ("invalid-key", "invalid-access-key") or key.startswith("AKIAINVALID"):
            return _create_fake_dataexchange_client_denied()
        return _create_fake_dataexchange_client()
    elif service_name == "s3":
        return _create_fake_s3_client()
    elif service_name in ("sts",):
        client = MagicMock(name=f"boto3-{service_name}")
        client.assume_role.return_value = {
            "Credentials": {
                "AccessKeyId": "mock-access-key",
                "SecretAccessKey": "mock-secret-key",
                "SessionToken": "mock-session-token",
            }
        }
        return client
    else:
        return MagicMock(name=f"boto3-{service_name}")


def _create_fake_dataexchange_client_denied():
    """Return a MagicMock that raises AccessDeniedException on all API calls."""
    client = MagicMock(name="dataexchange-denied")
    _denied = _make_access_denied_exception()
    client.list_data_sets.side_effect = _denied
    client.get_data_set.side_effect = _denied
    client.list_data_set_revisions.side_effect = _denied
    client.list_revision_assets.side_effect = _denied
    client.create_job.side_effect = _denied
    client.start_job.side_effect = _denied
    client.get_job.side_effect = _denied
    return client


def _make_access_denied_exception():
    """Build a botocore-style AccessDeniedException."""
    error_response = {
        "Error": {
            "Code": "AccessDeniedException",
            "Message": "User is not authorized to perform this action",
        }
    }
    try:
        from botocore.exceptions import ClientError
    except ImportError:
        return RuntimeError("Access denied")
    return ClientError(error_response, "ListDataSets")


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

_MOCK_AWS_CREDENTIALS = {
    "aws_access_key_id": "mock-access-key-id",
    "aws_secret_access_key": "mock-secret-access-key",
    "aws_session_token": "mock-session-token",
    "role_arn": "arn:aws:iam::123456789012:role/mock-data-exchange-role",
    "region_name": "us-east-1",
}

TEST_DATASET_ID = SAMPLE_DATASET_ID

_USING_MOCK = False  # Set to True when ensure_aws_credentials_or_mock() patches


def is_aws_credentials_available() -> bool:
    """Check if tests are running with real AWS Data Exchange credentials.

    Returns False when mock mode is active (regardless of env vars).
    Requires the dedicated ``AWS_DATA_EXCHANGE_ACCESS_KEY_ID`` and
    ``AWS_DATA_EXCHANGE_SECRET_ACCESS_KEY`` env vars.  Does NOT fall back
    to ``AWS_ACCESS_KEY_ID`` / ``AWS_SECRET_ACCESS_KEY`` because those
    may point to MinIO or local S3 in test environments.
    """
    if _USING_MOCK:
        return False
    return bool(
        os.getenv("AWS_DATA_EXCHANGE_ACCESS_KEY_ID")
        and os.getenv("AWS_DATA_EXCHANGE_SECRET_ACCESS_KEY")
    )


def ensure_aws_credentials_or_mock(*, force_mock: bool = False):
    """Patch boto3.client if real AWS credentials are not available OR
    the configured credentials lack Data Exchange permissions.

    Sets the module-level ``_USING_MOCK`` flag so ``is_aws_credentials_available()``
    returns False when mock mode is active.

    Args:
        force_mock: Always use mock mode (for performance/concurrency tests
                    that should not depend on real AWS API rate limits).

    Returns a patcher object; the caller is responsible for calling
    ``patcher.stop()`` in ``tearDownClass``.
    """
    global _USING_MOCK

    if not force_mock and is_aws_credentials_available():
        creds = get_aws_credentials_or_mock()
        import boto3
        from botocore.exceptions import ClientError

        # Try up to 3 times to account for IAM propagation delays.
        for attempt in range(3):
            try:
                client = boto3.client(
                    "dataexchange",
                    aws_access_key_id=creds["aws_access_key_id"],
                    aws_secret_access_key=creds["aws_secret_access_key"],
                    region_name=creds.get("region_name", "us-east-1"),
                )
                # Verify the full permission chain needed by integration tests:
                # list datasets → get details → list revisions → list assets.
                resp = client.list_data_sets(MaxResults=1)
                if resp.get("DataSets"):
                    ds_id = resp["DataSets"][0]["Id"]
                    client.get_data_set(DataSetId=ds_id)
                    revs = client.list_data_set_revisions(DataSetId=ds_id, MaxResults=1)
                    if revs.get("Revisions"):
                        rev_id = revs["Revisions"][0]["Id"]
                        client.list_revision_assets(
                            DataSetId=ds_id, RevisionId=rev_id, MaxResults=1
                        )
                return _NoOpPatcher()
            except ClientError:
                if attempt < 2:
                    import time
                    time.sleep(2)
                continue

    _USING_MOCK = True
    patcher = patch(
        "hub.apps.integrations.connectors.aws_data_exchange_connector.boto3.client",
        side_effect=_fake_boto3_client,
    )
    patcher.start()
    return patcher


class _NoOpPatcher:
    """Placeholder when no patching is needed."""

    def stop(self):
        pass


def get_aws_credentials_or_mock() -> dict:
    """Return real credentials if available, otherwise mock credentials.

    Optional IAM features (session token, role ARN) use mock values
    when the corresponding env vars are not set, so tests that depend
    on those features don't skip when running against real AWS without
    the full IAM setup.
    """
    if is_aws_credentials_available():
        return {
            "aws_access_key_id": os.getenv("AWS_DATA_EXCHANGE_ACCESS_KEY_ID") or os.getenv(
                "AWS_ACCESS_KEY_ID"
            ),
            "aws_secret_access_key": os.getenv("AWS_DATA_EXCHANGE_SECRET_ACCESS_KEY") or os.getenv(
                "AWS_SECRET_ACCESS_KEY"
            ),
            "aws_session_token": os.getenv("AWS_SESSION_TOKEN") or "mock-session-token",
            "role_arn": os.getenv("AWS_ROLE_ARN") or "arn:aws:iam::123456789012:role/mock-data-exchange-role",
            "region_name": os.getenv("AWS_REGION", "us-east-1"),
        }
    return dict(_MOCK_AWS_CREDENTIALS)


def verify_aws_connection_or_mock(connector) -> bool:
    """Return True — mock connector always passes connection check."""
    if is_aws_credentials_available():
        try:
            return connector.test_connection()
        except Exception:
            return False
    return True
