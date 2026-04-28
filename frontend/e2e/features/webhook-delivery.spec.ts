/**
 * E2E Feature: Webhook delivery (Phase 226 G11).
 *
 * Resolves Open Question §8 by using the in-tree E2E sink at
 * ``/api/v1/test/webhook-sink/<sink_id>/`` (see
 * ``hub/apps/api/webhook_sink_views.py``). Each test creates a fresh
 * sink id, registers a webhook with that sink as its target, triggers
 * an event, and asserts delivery on both sides:
 *
 *   1. Backend list ``/api/v1/webhooks/{id}/deliveries/`` shows a row
 *      with the expected event_type and SUCCESS status.
 *   2. The sink endpoint shows the payload it received, including the
 *      resource id of the trigger event.
 *
 * The retry + DLQ subflow uses the sink's forced-failure mode
 * (``?fail=503``) to make every delivery attempt return 503; the
 * delivery row should record the failure, attempt_number > 1, and
 * eventually FAILED status.
 *
 * Requires ``E2E_TEST_SECRET`` to be configured on the target backend
 * (the sink read endpoint is token-gated). When unset, the spec skips
 * cleanly — production backends never set this secret.
 *
 * No mocks. Real backend.
 */

import { randomUUID } from 'node:crypto';
import { expect, test } from '../fixtures/guardedTest';
import { getTestUser } from '../fixtures/auth';
import { createAssetViaApi } from '../fixtures/api-assets';

const API_BASE = '/api/v1';

interface AuthCtx {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  page: any;
  token: string;
}

async function login(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  page: any,
  email: string,
  password: string,
): Promise<string> {
  const res = await page.request.post(`${API_BASE}/auth/login/`, {
    data: { email, password },
    headers: { 'Content-Type': 'application/json' },
  });
  expect(res.ok()).toBe(true);
  return (await res.json()).access_token as string;
}

interface DeliveryRow {
  id: string;
  event_type?: string;
  status?: string;
  http_status_code?: number;
  attempt_number?: number;
  payload?: { resource_id?: string; event_type?: string; data?: Record<string, unknown> };
}

interface SinkDelivery {
  received_at: string;
  method: string;
  body_parsed: Record<string, unknown> | null;
  status_returned: number;
}

async function getDeliveryRows(
  ctx: AuthCtx,
  webhookId: string,
): Promise<DeliveryRow[]> {
  const res = await ctx.page.request.get(
    `${API_BASE}/webhooks/${webhookId}/deliveries/?page_size=20`,
    { headers: { Authorization: `Bearer ${ctx.token}` } },
  );
  if (!res.ok()) {
    throw new Error(
      `GET /webhooks/${webhookId}/deliveries/ returned ${res.status()}: ${(await res.text()).slice(0, 200)}`,
    );
  }
  const body = (await res.json()) as { results?: DeliveryRow[] } | DeliveryRow[];
  return Array.isArray(body) ? body : body.results ?? [];
}

async function getSinkPayloads(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  page: any,
  e2eToken: string,
  sinkId: string,
): Promise<SinkDelivery[]> {
  const res = await page.request.get(
    `${API_BASE}/test/webhook-sink/${sinkId}/?token=${encodeURIComponent(e2eToken)}`,
  );
  if (res.status() === 404) {
    // Sink unavailable on this env — caller decides whether to skip.
    return [];
  }
  if (!res.ok()) {
    throw new Error(`sink read returned ${res.status()}: ${(await res.text()).slice(0, 200)}`);
  }
  const body = (await res.json()) as { deliveries?: SinkDelivery[] };
  return body.deliveries ?? [];
}

interface SinkProbeResult {
  e2eToken: string | null;
  sinkUrl: string;
}

/**
 * Establish that the E2E webhook-sink endpoint is enabled and
 * `E2E_TEST_SECRET` is configured. Returns the secret + the absolute
 * sink URL the test must register with the webhook. Returns null on
 * `e2eToken` when the sink is not reachable; the caller should skip.
 *
 * The secret is sourced from `process.env.E2E_TEST_SECRET` (set in the
 * test runner environment to match the backend's setting). Without it,
 * we cannot read back what the sink received and the test is moot.
 */
async function probeSink(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  page: any,
  sinkId: string,
): Promise<SinkProbeResult> {
  const e2eToken = process.env.E2E_TEST_SECRET ?? null;
  // The webhook-target URL must be absolute (not a relative path) because
  // the WebhookDeliveryService calls it via outbound HTTP. Resolve from
  // the same origin Playwright uses.
  let originBase = process.env.VITE_PROXY_TARGET ?? process.env.E2E_API_BASE_URL ?? '';
  if (!originBase) {
    // Fallback: derive from the page's current URL.
    const url = new URL(page.url() || 'http://localhost:5173');
    originBase = `${url.protocol}//${url.host}`;
  }
  originBase = originBase.replace(/\/$/, '');
  const sinkUrl = originBase.endsWith('/api/v1')
    ? `${originBase}/test/webhook-sink/${sinkId}/`
    : `${originBase}/api/v1/test/webhook-sink/${sinkId}/`;
  return { e2eToken, sinkUrl };
}

async function pollUntil<T>(
  fetcher: () => Promise<T>,
  predicate: (v: T) => boolean,
  options: { budgetMs?: number; intervalMs?: number; description: string },
): Promise<T> {
  const budget = options.budgetMs ?? 30_000;
  const interval = options.intervalMs ?? 1_000;
  const deadline = Date.now() + budget;
  let last: T | null = null;
  while (Date.now() < deadline) {
    const v = await fetcher();
    last = v;
    if (predicate(v)) return v;
    await new Promise((r) => setTimeout(r, interval));
  }
  throw new Error(
    `pollUntil exhausted ${budget} ms waiting for ${options.description}. Last: ${JSON.stringify(last).slice(0, 400)}`,
  );
}

test.describe('Feature: Webhook delivery', () => {
  test.setTimeout(180_000);

  test('register → trigger → delivery row + sink received payload', async ({ page }) => {
    const sinkId = randomUUID();
    const probe = await probeSink(page, sinkId);
    if (!probe.e2eToken) {
      test.skip(
        true,
        'E2E_TEST_SECRET is not set on the test runner; cannot read the sink. ' +
          'Configure it in CI to match the backend `E2E_TEST_SECRET` setting.',
      );
    }

    const provider = await getTestUser();
    const token = await login(page, provider.email, provider.password);
    const ctx: AuthCtx = { page, token };

    // Sanity: confirm the sink is enabled on this backend before registering.
    const sinkProbe = await page.request.get(
      `${API_BASE}/test/webhook-sink/${sinkId}/?token=${encodeURIComponent(probe.e2eToken!)}`,
    );
    if (!sinkProbe.ok()) {
      test.skip(
        true,
        `webhook sink endpoint unavailable on this backend (status=${sinkProbe.status()}). ` +
          `Verify hub.apps.api.webhook_sink_views is wired and ENVIRONMENT in (test, staging, debug).`,
      );
    }

    // Register the webhook. ``url`` must be absolute and SSRF-safe — the
    // sink lives behind the same public hostname as the API in staging,
    // so it passes the SSRF guard.
    const webhookCreateRes = await page.request.post(`${API_BASE}/webhooks/`, {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      data: {
        name: `E2E Webhook Delivery ${Date.now()}`,
        url: probe.sinkUrl,
        secret: 'e2e-webhook-secret-12345',
        event_types: ['asset.created'],
        status: 'ACTIVE',
        max_retries: 3,
        retry_intervals: [1, 2, 4],
      },
    });
    if (!webhookCreateRes.ok()) {
      const body = (await webhookCreateRes.text()).slice(0, 400);
      // SSRF guard rejects local/loopback URLs — local dev hits this, staging doesn't.
      if (/SSRF|private|reserved IP|not permitted/i.test(body)) {
        test.skip(
          true,
          `webhook create blocked by SSRF guard for sink URL ${probe.sinkUrl}. ` +
            `This spec is intended for environments where the sink resolves to a public IP.`,
        );
      }
      throw new Error(`webhook create failed: ${webhookCreateRes.status()}: ${body}`);
    }
    const webhook = (await webhookCreateRes.json()) as { id: string };

    // Trigger an event by creating an asset. The signal handler chain
    // (assets/signals.py → events bus → webhooks/mesh_event_subscriber)
    // dispatches asset.created → WebhookDeliveryService.deliver().
    const assetId = await createAssetViaApi(provider, { forceNew: true });
    expect(assetId.length).toBeGreaterThan(30);

    // ----- Backend delivery-row assertion ---------------------------------
    const matchingRow = await pollUntil<DeliveryRow | null>(
      async () => {
        const rows = await getDeliveryRows(ctx, webhook.id);
        return (
          rows.find(
            (r) =>
              r.event_type === 'asset.created' &&
              (r.payload?.resource_id === assetId ||
                r.payload?.data?.asset_id === assetId ||
                JSON.stringify(r.payload ?? {}).includes(assetId)),
          ) ?? null
        );
      },
      (row) => row !== null && row.status?.toUpperCase() !== 'PENDING',
      { budgetMs: 60_000, description: `delivery row for asset ${assetId}` },
    );
    expect(matchingRow).not.toBeNull();
    expect(matchingRow!.status?.toUpperCase()).toMatch(/SUCCEEDED|SUCCESS|DELIVERED/);
    expect(matchingRow!.http_status_code).toBeGreaterThanOrEqual(200);
    expect(matchingRow!.http_status_code).toBeLessThan(300);

    // ----- Sink-side assertion --------------------------------------------
    const sinkPayloads = await pollUntil<SinkDelivery[]>(
      () => getSinkPayloads(page, probe.e2eToken!, sinkId),
      (payloads) =>
        payloads.some((d) =>
          JSON.stringify(d.body_parsed ?? {}).includes(assetId),
        ),
      { budgetMs: 30_000, description: `sink received payload for asset ${assetId}` },
    );
    const ourDelivery = sinkPayloads.find((d) =>
      JSON.stringify(d.body_parsed ?? {}).includes(assetId),
    );
    expect(ourDelivery, 'sink must record the delivery').toBeTruthy();
    expect(ourDelivery!.method).toBe('POST');
    expect(ourDelivery!.status_returned).toBe(200);
    // The payload must reference the event type — exact shape varies by
    // dispatcher version (top-level event_type, payload.event_type, or
    // headers). Looking at the JSON form is sufficient.
    expect(JSON.stringify(ourDelivery!.body_parsed ?? {})).toMatch(/asset\.created/);
  });

  test('forced-failure subflow: retry + DLQ on persistent 503', async ({ page }) => {
    const sinkId = randomUUID();
    const probe = await probeSink(page, sinkId);
    if (!probe.e2eToken) {
      test.skip(true, 'E2E_TEST_SECRET not set; cannot exercise retry/DLQ subflow');
    }
    const provider = await getTestUser();
    const token = await login(page, provider.email, provider.password);

    const sinkProbe = await page.request.get(
      `${API_BASE}/test/webhook-sink/${sinkId}/?token=${encodeURIComponent(probe.e2eToken!)}`,
    );
    if (!sinkProbe.ok()) {
      test.skip(true, `webhook sink unavailable on this backend (${sinkProbe.status()})`);
    }

    // Webhook URL with the forced-failure query so EVERY delivery attempt
    // returns 503. Real outbound retry policy applies; the spec asserts
    // that the platform retried and ultimately marked the row FAILED.
    const failingUrl = `${probe.sinkUrl}?fail=503`;
    const createRes = await page.request.post(`${API_BASE}/webhooks/`, {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      data: {
        name: `E2E Webhook Retry/DLQ ${Date.now()}`,
        url: failingUrl,
        secret: 'e2e-webhook-secret-12345',
        event_types: ['asset.created'],
        status: 'ACTIVE',
        max_retries: 3,
        // Tight intervals so the test completes within budget — production
        // would use 1, 5, 30, 300, 1800.
        retry_intervals: [1, 1, 1],
      },
    });
    if (!createRes.ok()) {
      const body = (await createRes.text()).slice(0, 400);
      if (/SSRF|private|reserved IP|not permitted/i.test(body)) {
        test.skip(true, `SSRF guard blocked sink URL — environment-specific skip`);
      }
      throw new Error(`webhook create failed: ${createRes.status()}: ${body}`);
    }
    const webhook = (await createRes.json()) as { id: string };

    const assetId = await createAssetViaApi(provider, { forceNew: true });

    // Wait for the delivery row to converge to FAILED (after max_retries
    // exhaust). The sink will have recorded ≥ 1 attempt regardless.
    const ctx: AuthCtx = { page, token };
    const failedRow = await pollUntil<DeliveryRow | null>(
      async () => {
        const rows = await getDeliveryRows(ctx, webhook.id);
        return (
          rows.find(
            (r) =>
              r.event_type === 'asset.created' &&
              JSON.stringify(r.payload ?? {}).includes(assetId),
          ) ?? null
        );
      },
      (row) => row !== null && /FAILED|DEAD_LETTER|EXHAUSTED/i.test(row.status ?? ''),
      { budgetMs: 90_000, description: `delivery row for asset ${assetId} reaches FAILED` },
    );
    expect(failedRow).not.toBeNull();
    expect(/FAILED|DEAD_LETTER|EXHAUSTED/i.test(failedRow!.status ?? '')).toBe(true);
    expect(failedRow!.attempt_number ?? 0).toBeGreaterThan(1);
    expect(failedRow!.http_status_code).toBe(503);

    // The sink should have recorded at least one attempt with status_returned=503.
    const payloads = await getSinkPayloads(page, probe.e2eToken!, sinkId);
    const matchingAttempts = payloads.filter((d) =>
      JSON.stringify(d.body_parsed ?? {}).includes(assetId),
    );
    expect(matchingAttempts.length, 'sink must record retry attempts').toBeGreaterThanOrEqual(
      1,
    );
    for (const attempt of matchingAttempts) {
      expect(attempt.status_returned).toBe(503);
    }
  });
});
