/**
 * E2E Test: JOURNEY-DB-012 — Consume a Delta Share
 *
 * Persona: Data Consumer
 * Reference: docs/USER_JOURNEYS.md, docs/mvpdocs/journeys/JOURNEY-DB-012.md
 *
 * Real backend, deterministic: the spec drives the shipped P5 protocol
 * contract only — the v1 profile, the oracle catalog envelopes, the
 * ndjson metadata shape, the presigned-URL version leg, and the 401
 * boundary. The recipient + bearer token + asset + snapshot row are
 * provisioned through the API container's Django shell (the 0.15/3.7
 * CLI real-API pattern); the protocol is bearer-only, so no login is
 * involved — the provisioned token IS the credential. No mocks — the
 * backend decides every response.
 */

import { expect, test } from '@playwright/test';
import { execSync } from 'node:child_process';
import { skipIfRemoteApi } from '../../fixtures/helpers';

const DEFAULT_API_PORT = process.env.E2E_WEB_PORT ? '8001' : '8000';
const API_BASE_URL =
  process.env.E2E_API_BASE_URL ||
  (process.env.VITE_PROXY_TARGET
    ? `${process.env.VITE_PROXY_TARGET.replace(/\/$/, '')}/api/v1`
    : null) ||
  `http://localhost:${DEFAULT_API_PORT}/api/v1`;

const PROTOCOL_BASE = `${API_BASE_URL}/databricks/delta-sharing`;

/**
 * One retry on a transport-level failure: the fetch pool holds a
 * keep-alive connection across the ~15s docker-exec provisioning gap
 * and the API's gunicorn (keepalive=5s) closes it idle server-side —
 * the pooled socket is then reused and reset ("other side closed").
 * The retry opens a fresh connection; the API contract is what the
 * assertions pin, never the connection-reuse behavior.
 */
async function fetchWithRetry(url: string, init?: RequestInit): Promise<Response> {
  // globalThis.fetch — never the helper itself (a blanket rename of the
  // call sites must not recurse into this function).
  try {
    return await globalThis.fetch(url, init);
  } catch (error) {
    if (!(error instanceof TypeError) || !/fetch failed/.test(error.message)) {
      throw error;
    }
    return globalThis.fetch(url, init);
  }
}

interface Provisioned {
  schema: string;
  table: string;
  bearerToken: string;
}

/**
 * A dedicated tenant + shareable asset + recipient with a REAL issued
 * bearer token + one snapshot row, provisioned through the API
 * container's Django shell. The journey spec never mutates the shared
 * E2E tenant.
 */
function provisionShare(): Provisioned {
  skipIfRemoteApi(test, 'Delta-share provisioning requires docker exec');
  const suffix = Math.random().toString(16).slice(2, 10);
  const script = `
import json
from datetime import timedelta
from django.utils import timezone
from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.tenants.models import Tenant, TenantConfig, TenantPlan
from hub.apps.assets.models import Asset, DataStrategy
from hub.apps.warehouses.models import WarehouseConnection, WarehouseType
from hub.apps.databricks_admin.models import (
    DeltaShareRecipient, DeltaShareToken, DeltaShareSnapshot,
)
tenant = Tenant.objects.create(name='dshare-e2e-${suffix}', slug='dshare-e2e-${suffix}')
TenantConfig.objects.get_or_create(tenant=tenant)
free_plan = TenantPlan.objects.filter(slug='free', is_active=True).first()
Subscription.objects.create(
    tenant=tenant, plan=free_plan, category='BASE', status=SubscriptionStatus.ACTIVE,
)
connection = WarehouseConnection.objects.create(
    tenant=tenant, name='conn-dshare-e2e-${suffix}',
    warehouse_type=WarehouseType.DATABRICKS,
    config={'host': 'adb-123.azuredatabricks.net', 'http_path': '/sql/1.0/warehouses/wh-1',
            'pat_token': 'dapi-e2e-${suffix}'},
)
table_ref = 'catalog.schema.orders-${suffix}'
asset = Asset.objects.create(
    tenant=tenant, key='asset-dshare-e2e-${suffix}', name='orders',
    data_strategy=DataStrategy.LIVE_QUERY, warehouse_connection=connection,
    semantic_federate_optout=False,
    metadata_json={'external_table_ref': table_ref},
)
schema = str(asset.id).replace('-', '')
recipient = DeltaShareRecipient.objects.create(tenant=tenant, name='consumer-${suffix}')
token, plaintext = DeltaShareToken.issue(recipient=recipient, share_name='meshant')
DeltaShareSnapshot.objects.create(
    tenant=tenant, share_name='meshant', schema_name=schema, table_name=table_ref,
    version=5,
    files=[{'id': 'part-00000',
            'path': 'delta-share-snapshots/meshant/${suffix}/part-00000-5.parquet',
            'size': 4096, 'partition_values': {}}],
    expires_at=timezone.now() + timedelta(hours=1),
)
print(json.dumps({'schema': schema, 'table': table_ref, 'bearerToken': plaintext}))
`;
  // The script goes in via STDIN (docker exec -i) — indentation and
  // quoting are preserved exactly; no shell -c collapsing.
  const out = execSync('docker exec -i hub-test-api python hub/manage.py shell', {
    encoding: 'utf-8',
    timeout: 120000,
    input: script,
  });
  const lines = out.split('\n').filter((line) => line.trim().startsWith('{"schema"'));
  expect(lines.length, `provisioning failed: ${out.slice(0, 400)}`).toBeGreaterThan(0);
  return JSON.parse(lines[0].trim()) as Provisioned;
}

test.describe('JOURNEY-DB-012: Consume a Delta Share', () => {
  test.setTimeout(180000);

  test('the protocol catalog walk serves the oracle envelopes', async () => {
    const provisioned = provisionShare();
    const headers = { Authorization: `Bearer ${provisioned.bearerToken}` };

    // Step 1 — the v1 profile.
    const profile = await fetchWithRetry(`${PROTOCOL_BASE}/profile`, { headers });
    const profileText = await profile.text();
    expect(profile.status, `profile failed: ${profileText}`).toBe(200);
    const profileBody = JSON.parse(profileText) as {
      shareCredentialsVersion?: number;
      endpoint?: string;
      bearerToken?: string;
    };
    expect(profileBody.shareCredentialsVersion).toBe(1);
    expect(String(profileBody.endpoint ?? '')).toContain('/databricks/delta-sharing');
    expect(profileBody.bearerToken).toBe(provisioned.bearerToken);

    // Step 2 — the catalog hierarchy envelopes.
    const shares = await fetchWithRetry(`${PROTOCOL_BASE}/shares`, { headers });
    const sharesText = await shares.text();
    expect(shares.status, `shares failed: ${sharesText}`).toBe(200);
    const sharesBody = JSON.parse(sharesText) as { items?: { name?: string }[] };
    expect(sharesBody.items).toEqual([{ name: 'meshant' }]);

    const schemas = await fetchWithRetry(`${PROTOCOL_BASE}/shares/meshant/schemas`, { headers });
    const schemasText = await schemas.text();
    expect(schemas.status, `schemas failed: ${schemasText}`).toBe(200);
    const schemasBody = JSON.parse(schemasText) as { items?: { name?: string; share?: string }[] };
    expect(
      schemasBody.items?.map((item) => item.name),
      `schemas listing: ${schemasText}`
    ).toContain(provisioned.schema);

    const tables = await fetchWithRetry(
      `${PROTOCOL_BASE}/shares/meshant/schemas/${provisioned.schema}/tables`,
      { headers }
    );
    const tablesText = await tables.text();
    expect(tables.status, `tables failed: ${tablesText}`).toBe(200);
    const tablesBody = JSON.parse(tablesText) as {
      items?: { name?: string; share?: string; schema?: string }[];
    };
    expect(tablesBody.items).toEqual([
      { name: provisioned.table, share: 'meshant', schema: provisioned.schema },
    ]);

    // Step 3 — the ndjson metadata envelope with the version header.
    const metadata = await fetchWithRetry(
      `${PROTOCOL_BASE}/shares/meshant/schemas/${provisioned.schema}` +
        `/tables/${encodeURIComponent(provisioned.table)}/metadata`,
      { headers }
    );
    const metadataText = await metadata.text();
    expect(metadata.status, `metadata failed: ${metadataText}`).toBe(200);
    expect(metadata.headers.get('delta-table-version')).toBe('5');
    const lines = metadataText
      .split('\n')
      .filter((line) => line.trim())
      .map((line) => JSON.parse(line) as Record<string, unknown>);
    expect(lines[0]).toEqual({ protocol: { minReaderVersion: 1 } });
    const metaData = lines[1]?.['metaData'] as Record<string, unknown> | undefined;
    expect(metaData?.['name']).toBe(provisioned.table);
    expect(metaData?.['format']).toEqual({ provider: 'parquet' });
  });

  test('the version endpoint serves a real presigned file action', async () => {
    const provisioned = provisionShare();
    const headers = { Authorization: `Bearer ${provisioned.bearerToken}` };

    const response = await fetchWithRetry(
      `${PROTOCOL_BASE}/shares/meshant/schemas/${provisioned.schema}` +
        `/tables/${encodeURIComponent(provisioned.table)}/version`,
      { headers }
    );
    const responseText = await response.text();
    expect(response.status, `version failed: ${responseText}`).toBe(200);
    expect(response.headers.get('delta-table-version')).toBe('5');
    const lines = responseText
      .split('\n')
      .filter((line) => line.trim())
      .map((line) => JSON.parse(line) as Record<string, unknown>);
    const action = lines[2]?.['file'] as
      | { url?: string; id?: string; size?: number; partitionValues?: Record<string, unknown> }
      | undefined;
    expect(action?.id).toBe('part-00000');
    expect(action?.size).toBe(4096);
    expect(String(action?.url ?? '')).toContain('X-Amz-Expires');
    expect(String(action?.url ?? '')).toContain('X-Amz-Signature');
    expect(String(action?.url ?? '')).toContain('part-00000-5.parquet');
  });

  test('an absent token surfaces the 401 boundary with the bearer challenge', async () => {
    const response = await fetchWithRetry(`${PROTOCOL_BASE}/shares`);
    const responseText = await response.text();
    expect(response.status, `expected 401, got: ${responseText}`).toBe(401);
    expect(String(response.headers.get('WWW-Authenticate') ?? '').toLowerCase()).toContain(
      'bearer'
    );
  });
});
