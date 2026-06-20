#!/usr/bin/env python3
"""
Check that DQ, Compliance, MinIO, and S3 are ready before Data Quality / DQ batches.
Used by run_phase_12a_batched.sh to avoid heredoc parsing issues.
Exit 0 if all ready, 1 otherwise.
"""

import os
import sys
import urllib.request


def ok(url, timeout=5):
    try:
        urllib.request.urlopen(
            urllib.request.Request(url, method="GET"),
            timeout=timeout,
        )
        return True
    except Exception:
        return False


def main():
    dq = ok(os.getenv("DQ_SERVICE_URL", "http://dq-service-test:8083") + "/health")
    comp = ok(
        os.getenv("COMPLIANCE_SERVICE_URL", "http://compliance-service-test:8082") + "/health"
    )
    ep = (
        os.getenv("AWS_S3_ENDPOINT_URL", "http://minio-test:9000")
        .replace("http://", "")
        .replace("https://", "")
        .split("/")[0]
    )
    minio_http = ok("http://" + ep + "/minio/health/live")
    s3_ready = False
    if dq and comp and minio_http:
        try:
            import boto3
            from botocore.exceptions import ClientError

            c = boto3.client(
                "s3",
                endpoint_url=os.getenv("AWS_S3_ENDPOINT_URL", "http://minio-test:9000"),
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "minioadmin"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin"),
            )
            try:
                c.head_bucket(Bucket=os.getenv("AWS_STORAGE_BUCKET_NAME", "hub-test"))
            except ClientError as e:
                if e.response.get("Error", {}).get("Code", "") in (
                    "404",
                    "NoSuchBucket",
                ):
                    c.create_bucket(Bucket=os.getenv("AWS_STORAGE_BUCKET_NAME", "hub-test"))
                else:
                    raise
            c.put_object(
                Bucket=os.getenv("AWS_STORAGE_BUCKET_NAME", "hub-test"),
                Key=".batch10-ready",
                Body=b"ok",
            )
            s3_ready = True
        except Exception:
            pass
    sys.exit(0 if (dq and comp and minio_http and s3_ready) else 1)


def diagnose():
    """Print readiness of each service to stderr and exit 1."""
    import sys as _sys

    dq = ok(
        os.getenv("DQ_SERVICE_URL", "http://dq-service-test:8083") + "/health",
        timeout=3,
    )
    comp = ok(
        os.getenv("COMPLIANCE_SERVICE_URL", "http://compliance-service-test:8082") + "/health",
        timeout=3,
    )
    ep = (
        os.getenv("AWS_S3_ENDPOINT_URL", "http://minio-test:9000")
        .replace("http://", "")
        .replace("https://", "")
        .split("/")[0]
    )
    minio_http = ok("http://" + ep + "/minio/health/live", timeout=3)
    print("  DQ:", dq, "Compliance:", comp, "MinIO:", minio_http, file=_sys.stderr)
    _sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--diagnose":
        diagnose()
    main()
