/**
 * Phase 118C — JS SDK Critical Fixes Tests — W6.2: the wiring tests
 * now assert through a real local HTTP server (the previous version
 * inspected mocked axios interceptors).
 *
 * 118C.1: authType bearer|apikey — ApiKey header format
 * 118C.2: Request camelCase → snake_case
 * 118C.3: Response snake_case → camelCase
 * 118C.4: Async race condition fix in token refresh
 */

import { DataHubClient } from '../client';
import { camelToSnake, snakeToCamel } from '../caseTransform';
import { UnauthorizedError } from '../errors';
import { TestServer, startTestServer, json, errorEnvelope } from './helpers/testHttpServer';

describe('Phase 118C — JS SDK Critical Fixes', () => {
  let server: TestServer;

  beforeAll(async () => {
    server = await startTestServer();
  });

  afterAll(async () => {
    await server.close();
  });

  beforeEach(() => {
    server.reset();
  });

  // ===========================================================
  // 118C.1 — authType: 'bearer' | 'apikey'
  // ===========================================================
  describe('118C.1 — authType config', () => {
    it('should default to bearer auth', async () => {
      const client = new DataHubClient({
        baseUrl: `${server.baseUrl}/api/v1`,
        apiToken: 'tok_123',
      });
      server.setHandler((req, res) => json(res, 200, { ok: true }));

      await client.get('/whoami/');

      expect(server.requests[0].headers.authorization).toBe('Bearer tok_123');
    });

    it('should send ApiKey header when authType is apikey', async () => {
      const client = new DataHubClient({
        baseUrl: `${server.baseUrl}/api/v1`,
        apiToken: 'key_abc',
        authType: 'apikey',
      });
      server.setHandler((req, res) => json(res, 200, { ok: true }));

      await client.get('/whoami/');

      expect(server.requests[0].headers.authorization).toBe('ApiKey key_abc');
    });

    it('should send Bearer header when authType is bearer', async () => {
      const client = new DataHubClient({
        baseUrl: `${server.baseUrl}/api/v1`,
        apiToken: 'jwt_xyz',
        authType: 'bearer',
      });
      server.setHandler((req, res) => json(res, 200, { ok: true }));

      await client.get('/whoami/');

      expect(server.requests[0].headers.authorization).toBe('Bearer jwt_xyz');
    });
  });

  // ===========================================================
  // 118C.2 — camelCase → snake_case request transform
  // ===========================================================
  describe('118C.2 — camelToSnake transform', () => {
    it('should convert flat camelCase keys to snake_case', () => {
      expect(camelToSnake({ firstName: 'John', lastName: 'Doe' }))
        .toEqual({ first_name: 'John', last_name: 'Doe' });
    });

    it('should convert nested objects recursively', () => {
      expect(camelToSnake({
        tenantId: 'abc',
        metadata: { createdBy: 'admin', lastModifiedAt: '2026-01-01' },
      })).toEqual({
        tenant_id: 'abc',
        metadata: { created_by: 'admin', last_modified_at: '2026-01-01' },
      });
    });

    it('should convert arrays of objects', () => {
      expect(camelToSnake({
        items: [{ planSlug: 'pro' }, { planSlug: 'free' }],
      })).toEqual({
        items: [{ plan_slug: 'pro' }, { plan_slug: 'free' }],
      });
    });

    it('should leave primitives unchanged', () => {
      expect(camelToSnake(42)).toBe(42);
      expect(camelToSnake('hello')).toBe('hello');
      expect(camelToSnake(null)).toBe(null);
      expect(camelToSnake(undefined)).toBe(undefined);
    });

    it('should preserve already_snake_case keys', () => {
      expect(camelToSnake({ already_snake: 'ok' }))
        .toEqual({ already_snake: 'ok' });
    });

    it('should transform the request body on the wire', async () => {
      const client = new DataHubClient({
        baseUrl: `${server.baseUrl}/api/v1`,
        apiToken: 'tok',
      });
      server.setHandler((req, res) => json(res, 200, { ok: true }));

      await client.post('/orders/', { planSlug: 'pro', metadataJson: { createdBy: 'admin' } });

      expect(JSON.parse(server.requests[0].body)).toEqual({
        plan_slug: 'pro',
        metadata_json: { created_by: 'admin' },
      });
    });
  });

  // ===========================================================
  // 118C.3 — snake_case → camelCase response transform
  // ===========================================================
  describe('118C.3 — snakeToCamel transform', () => {
    it('should convert flat snake_case keys to camelCase', () => {
      expect(snakeToCamel({ first_name: 'John', last_name: 'Doe' }))
        .toEqual({ firstName: 'John', lastName: 'Doe' });
    });

    it('should convert nested objects recursively', () => {
      expect(snakeToCamel({
        tenant_id: 'abc',
        metadata_json: { created_by: 'admin', last_modified_at: '2026-01-01' },
      })).toEqual({
        tenantId: 'abc',
        metadataJson: { createdBy: 'admin', lastModifiedAt: '2026-01-01' },
      });
    });

    it('should convert arrays of objects', () => {
      expect(snakeToCamel({
        items: [{ plan_slug: 'pro' }, { plan_slug: 'free' }],
      })).toEqual({
        items: [{ planSlug: 'pro' }, { planSlug: 'free' }],
      });
    });

    it('should leave primitives unchanged', () => {
      expect(snakeToCamel(42)).toBe(42);
      expect(snakeToCamel('hello')).toBe('hello');
      expect(snakeToCamel(null)).toBe(null);
    });

    it('should transform the response body from the wire', async () => {
      const client = new DataHubClient({
        baseUrl: `${server.baseUrl}/api/v1`,
        apiToken: 'tok',
      });
      server.setHandler((req, res) =>
        json(res, 200, { plan_slug: 'pro', metadata_json: { created_by: 'admin' } })
      );

      const result = await client.get('/orders/');

      expect(result).toEqual({
        planSlug: 'pro',
        metadataJson: { createdBy: 'admin' },
      });
    });
  });

  // ===========================================================
  // 118C.4 — Async race condition fix in token refresh
  // ===========================================================
  describe('118C.4 — Token refresh race condition', () => {
    it('should serialize concurrent 401 token refresh attempts', async () => {
      const client = new DataHubClient({
        baseUrl: `${server.baseUrl}/api/v1`,
        apiToken: 'expired-token',
        backoffBaseMs: 1,
      });

      let refreshCallCount = 0;
      client.setTokenRefreshCallback(async () => {
        refreshCallCount++;
        // Small pause widens the race window so a non-serialized
        // implementation would visibly double-fire.
        await new Promise((r) => setTimeout(r, 30));
        return 'new-token';
      });

      server.setHandler((req, res) => {
        if (req.headers.authorization === 'Bearer new-token') {
          json(res, 200, { ok: true });
        } else {
          errorEnvelope(res, 401, 'AUTH_UNAUTHORIZED', 'Token expired');
        }
      });

      const [r1, r2] = await Promise.all([
        client.get('/a/'),
        client.get('/b/'),
      ]);

      expect(r1).toEqual({ ok: true });
      expect(r2).toEqual({ ok: true });
      // The second request must have waited for the first refresh.
      expect(refreshCallCount).toBe(1);
    });

    it('should propagate refresh failure to all waiting requests', async () => {
      const client = new DataHubClient({
        baseUrl: `${server.baseUrl}/api/v1`,
        apiToken: 'expired-token',
        backoffBaseMs: 1,
      });

      client.setTokenRefreshCallback(async () => {
        throw new Error('refresh failed');
      });

      server.setHandler((req, res) => {
        errorEnvelope(res, 401, 'AUTH_UNAUTHORIZED', 'Token expired');
      });

      const [e1, e2] = await Promise.all([
        client.get('/a/').catch((e) => e),
        client.get('/b/').catch((e) => e),
      ]);

      expect(e1).toBeInstanceOf(UnauthorizedError);
      expect(e2).toBeInstanceOf(UnauthorizedError);
    });
  });
});
