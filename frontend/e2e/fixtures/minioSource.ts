/**
 * MinIO source seeding for the scheduled-ingestion journeys.
 *
 * The ingestion S3 connector runs INSIDE the worker/API containers, so the
 * source endpoint must be the compose service name `http://minio-test:9000`
 * (the host-side `localhost:9010` mapping is unreachable from containers).
 *
 * Credentials are NOT hardcoded: .env.test rotates MINIO_ROOT_USER/PASSWORD
 * (the compose `minio`/`minio123` defaults were superseded), and the API
 * container's env carries the authoritative values (AWS_ACCESS_KEY_ID /
 * AWS_SECRET_ACCESS_KEY). The fixture reads them from the same container
 * the ingestion connector will run in, so the seeded source always matches
 * the live stack.
 */
import { execSync } from 'child_process';

export interface MinioSource {
  bucket: string;
  key: string;
  /** Compose-internal endpoint — the ONLY endpoint the containers can reach. */
  endpoint: string;
  accessKeyId: string;
  secretAccessKey: string;
}

export function provisionMinioSource(options: {
  bucket: string;
  prefix?: string;
  key?: string;
  csvBody?: string;
}): MinioSource {
  const prefix = options.prefix ?? 'in/';
  const key = options.key ?? `${prefix}sample.csv`;
  const csvBody = options.csvBody ?? 'id,name\n1,alpha\n2,beta\n';

  const script = [
    'import boto3',
    'import json',
    'import os',
    'from botocore.config import Config',
    'from botocore.exceptions import ClientError',
    's3 = boto3.client(',
    "    's3',",
    "    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),",
    "    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),",
    "    endpoint_url='http://minio-test:9000',",
    "    config=Config(signature_version='s3v4'),",
    "    region_name='us-east-1',",
    ')',
    `bucket = '${options.bucket}'`,
    'try:',
    '    s3.create_bucket(Bucket=bucket)',
    'except ClientError as exc:',
    "    if exc.response['Error']['Code'] != 'BucketAlreadyOwnedByYou':",
    '        raise',
    `s3.put_object(Bucket=bucket, Key='${key}', Body=${JSON.stringify(csvBody)})`,
    'print(json.dumps({',
    "    'bucket': bucket,",
    "    'key': '${key}',",
    "    'access_key_id': os.environ.get('AWS_ACCESS_KEY_ID', ''),",
    "    'secret_access_key': os.environ.get('AWS_SECRET_ACCESS_KEY', ''),",
    '}))',
  ].join('\n');

  const out = execSync(`docker exec -i hub-test-api python -c ${shellQuote(script)}`, {
    encoding: 'utf-8',
    timeout: 120_000,
  });

  // Same structlog-banner-tolerant line-scan as provisionIngestion() in
  // JOURNEY-DB-014.spec.ts — never assume the payload is the first line.
  const payload = out
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .map((line) => {
      try {
        const outer = JSON.parse(line) as Record<string, unknown>;
        if (typeof outer.message === 'string') {
          return JSON.parse(outer.message) as Record<string, unknown>;
        }
        return outer;
      } catch {
        return null;
      }
    })
    .find((obj) => obj !== null && 'bucket' in obj && 'key' in obj);
  if (!payload) {
    throw new Error(`MinIO provisioning produced no payload: ${out}`);
  }
  if (!payload.access_key_id || !payload.secret_access_key) {
    throw new Error(
      'MinIO credentials missing from hub-test-api env (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY).'
    );
  }
  return {
    bucket: String(payload.bucket),
    key: String(payload.key),
    endpoint: 'http://minio-test:9000',
    accessKeyId: String(payload.access_key_id),
    secretAccessKey: String(payload.secret_access_key),
  };
}

function shellQuote(script: string): string {
  // Single-quote the python script for sh -c; escape embedded quotes.
  return `'${script.replace(/'/g, `'\\''`)}'`;
}
