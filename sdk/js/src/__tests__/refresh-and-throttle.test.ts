/**
 * W6.2 (oss-release-remediation R2-X2) — refresh-cap + Retry-After pins.
 *
 * Two defects the axios client shipped:
 *
 *  1. 401 refresh loop — the response interceptor retried a 401 through
 *     the interceptor chain again, so a server that kept returning 401
 *     (e.g. a refresh callback returning a stale token) recursed
 *     unboundedly.  Contract: at most ONE refresh per logical request;
 *     a second 401 surfaces as UnauthorizedError.
 *
 *  2. Retry-After never read — the 429/503 backoff used plain
 *     exponential backoff and never consulted the real `Retry-After`
 *     header (parseError received response DATA, not headers, so the
 *     parse branch was dead code).  Contract: the retry delay is at
 *     least the server's Retry-After (seconds or HTTP-date).
 *
 * All pins run against a real local HTTP server — no mocks.
 */

import { DataHubClient } from '../client';
import { RateLimitError, UnauthorizedError, ServerError } from '../errors';
import { TestServer, startTestServer, json, errorEnvelope } from './helpers/testHttpServer';

describe('W6.2 — 401 refresh attempt cap', () => {
  let server: TestServer;
  let client: DataHubClient;
  let refreshCalls: number;

  beforeAll(async () => {
    server = await startTestServer();
  });

  afterAll(async () => {
    await server.close();
  });

  beforeEach(() => {
    server.reset();
    refreshCalls = 0;
    client = new DataHubClient({
      baseUrl: server.baseUrl,
      apiToken: 'expired-token',
      backoffBaseMs: 1,
    });
    client.setTokenRefreshCallback(async () => {
      refreshCalls++;
      // The "refreshed" token is also rejected by this server — the
      // classic stale-refresh loop scenario.
      return 'still-rejected-token';
    });
  });

  it('caps the refresh at one attempt per request — a persistent 401 throws, not loops', async () => {
    server.setHandler((req, res) => {
      errorEnvelope(res, 401, 'AUTH_UNAUTHORIZED', 'Token rejected');
    });

    await expect(client.get('/loop-risk/')).rejects.toThrow(UnauthorizedError);

    // Exactly one refresh, exactly two wire attempts (initial + retry).
    expect(refreshCalls).toBe(1);
    expect(server.requests.length).toBe(2);
  });

  it('sends the refreshed token on the retried attempt', async () => {
    server.setHandler((req, res) => {
      if (server.requests.length === 1) {
        errorEnvelope(res, 401, 'AUTH_UNAUTHORIZED', 'Token expired');
      } else {
        json(res, 200, { ok: true });
      }
    });
    // Refresh produces a token this server accepts.
    client.setTokenRefreshCallback(async () => {
      refreshCalls++;
      return 'fresh-token';
    });

    const result = await client.get('/refresh-once/');

    expect(result).toEqual({ ok: true });
    expect(refreshCalls).toBe(1);
    expect(server.requests).toHaveLength(2);
    expect(server.requests[0].headers.authorization).toBe('Bearer expired-token');
    expect(server.requests[1].headers.authorization).toBe('Bearer fresh-token');
  });

  it('does not refresh at all when no callback is registered', async () => {
    const bareClient = new DataHubClient({ baseUrl: server.baseUrl, backoffBaseMs: 1 });
    server.setHandler((req, res) => {
      errorEnvelope(res, 401, 'AUTH_UNAUTHORIZED', 'Authentication required');
    });

    await expect(bareClient.get('/no-callback/')).rejects.toThrow(UnauthorizedError);
    expect(server.requests).toHaveLength(1);
  });

  it('retries after refresh even with a zero retry budget', async () => {
    const zeroRetry = new DataHubClient({
      baseUrl: server.baseUrl,
      apiToken: 'expired-token',
      maxRetries: 0,
      backoffBaseMs: 1,
    });
    zeroRetry.setTokenRefreshCallback(async () => {
      refreshCalls++;
      return 'fresh-token';
    });
    server.setHandler((req, res) => {
      if (server.requests.length === 1) {
        errorEnvelope(res, 401, 'AUTH_UNAUTHORIZED', 'Token expired');
      } else {
        json(res, 200, { ok: true });
      }
    });

    const result = await zeroRetry.get('/refresh-despite-zero-retries/');

    // The refresh retry must NOT consume the transient-retry budget.
    expect(result).toEqual({ ok: true });
    expect(refreshCalls).toBe(1);
    expect(server.requests).toHaveLength(2);
  });
});

describe('W6.2 — Retry-After honoured from real headers', () => {
  let server: TestServer;
  let client: DataHubClient;

  beforeAll(async () => {
    server = await startTestServer();
  });

  afterAll(async () => {
    await server.close();
  });

  beforeEach(() => {
    server.reset();
    client = new DataHubClient({
      baseUrl: server.baseUrl,
      backoffBaseMs: 1,
      maxRetries: 1,
    });
  });

  it('waits at least Retry-After seconds before retrying a 429', async () => {
    const started = Date.now();
    server.setHandler((req, res) => {
      if (server.requests.length === 1) {
        errorEnvelope(
          res,
          429,
          'RATE_LIMIT_EXCEEDED',
          'Slow down',
          {},
          { 'Retry-After': '2' }
        );
      } else {
        json(res, 200, { ok: true });
      }
    });

    const result = await client.get('/throttled/');

    expect(result).toEqual({ ok: true });
    expect(server.requests).toHaveLength(2);
    // The retry must have waited ≥2s (the server's Retry-After), which
    // the old exponential-only backoff (base 1ms) never did.
    expect(Date.now() - started).toBeGreaterThanOrEqual(1900);
  });

  it('parses an HTTP-date Retry-After', async () => {
    const started = Date.now();
    // HTTP-dates have 1s resolution: +2000ms rounds down to a 2s wait
    // (worst-case truncation still yields ceil(1001ms/1000) = 2s).
    const retryAt = new Date(Date.now() + 2000);
    server.setHandler((req, res) => {
      if (server.requests.length === 1) {
        errorEnvelope(
          res,
          429,
          'RATE_LIMIT_EXCEEDED',
          'Slow down',
          {},
          { 'Retry-After': retryAt.toUTCString() }
        );
      } else {
        json(res, 200, { ok: true });
      }
    });

    const result = await client.get('/throttled-date/');

    expect(result).toEqual({ ok: true });
    expect(server.requests).toHaveLength(2);
    expect(Date.now() - started).toBeGreaterThanOrEqual(1500);
  });

  it('surfaces RateLimitError with the parsed retryAfter when retries are exhausted', async () => {
    server.setHandler((req, res) => {
      errorEnvelope(
        res,
        429,
        'RATE_LIMIT_EXCEEDED',
        'Slow down',
        {},
        { 'Retry-After': '60' }
      );
    });

    // retries: 0 → the error surfaces immediately, carrying the header.
    const error = await client
      .get('/exhausted/', { retries: 0 })
      .catch((e) => e);

    expect(error).toBeInstanceOf(RateLimitError);
    expect(error.retryAfter).toBe(60);
  });

  it('honours Retry-After on 503 responses too', async () => {
    const started = Date.now();
    server.setHandler((req, res) => {
      if (server.requests.length === 1) {
        errorEnvelope(
          res,
          503,
          'SERVICE_UNAVAILABLE',
          'Maintenance',
          {},
          { 'Retry-After': '1' }
        );
      } else {
        json(res, 200, { ok: true });
      }
    });

    const result = await client.get('/maintenance/');

    expect(result).toEqual({ ok: true });
    expect(server.requests).toHaveLength(2);
    expect(Date.now() - started).toBeGreaterThanOrEqual(900);
  });

  it('still throws ServerError when 503 persists past the retry budget', async () => {
    server.setHandler((req, res) => {
      errorEnvelope(
        res,
        503,
        'SERVICE_UNAVAILABLE',
        'Maintenance',
        {},
        { 'Retry-After': '0' }
      );
    });

    await expect(client.get('/down/')).rejects.toThrow(ServerError);
  });
});
