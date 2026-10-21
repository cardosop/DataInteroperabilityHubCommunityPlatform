/**
 * Authentication Tests — W6.2: rewritten against a real local HTTP
 * server.  JWTs are built at runtime (no committed token literals in
 * the shipped tree).
 */

import { DataHubClient } from '../client';
import { UnauthorizedError, ForbiddenError } from '../errors';
import { TestServer, startTestServer, json, errorEnvelope } from './helpers/testHttpServer';

/**
 * Build an unsigned JWT-shaped token at runtime.  The client never
 * verifies signatures (it only reads the payload), so tests need no
 * crypto — and no committed credentials.
 */
function makeJwt(claims: Record<string, unknown> = { sub: 'sdk-test' }): string {
  const encode = (obj: unknown) =>
    Buffer.from(JSON.stringify(obj)).toString('base64url');
  return `${encode({ alg: 'none', typ: 'JWT' })}.${encode(claims)}.testsig`;
}

describe('Authentication', () => {
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
      baseUrl: `${server.baseUrl}/api/v1`,
      apiToken: 'test-api-key',
      backoffBaseMs: 1,
    });
  });

  describe('API Key Authentication', () => {
    it('should set API token in Authorization header', async () => {
      server.setHandler((req, res) => json(res, 200, { ok: true }));

      await client.get('/whoami/');

      expect(server.requests[0].headers.authorization).toBe('Bearer test-api-key');
    });

    it('should allow setting token after initialization', async () => {
      client.setApiToken('new-api-key');
      server.setHandler((req, res) => json(res, 200, { ok: true }));

      await client.get('/whoami/');

      expect(server.requests[0].headers.authorization).toBe('Bearer new-api-key');
    });

    it('should work without token if not provided', async () => {
      const anon = new DataHubClient({ baseUrl: `${server.baseUrl}/api/v1` });
      server.setHandler((req, res) => json(res, 200, { ok: true }));

      await anon.get('/public/');

      expect(server.requests[0].headers.authorization).toBeUndefined();
    });

    it('should send ApiKey header format when authType is apikey', async () => {
      const keyed = new DataHubClient({
        baseUrl: `${server.baseUrl}/api/v1`,
        apiToken: 'key_abc',
        authType: 'apikey',
      });
      server.setHandler((req, res) => json(res, 200, { ok: true }));

      await keyed.get('/whoami/');

      expect(server.requests[0].headers.authorization).toBe('ApiKey key_abc');
    });
  });

  describe('JWT Token Authentication', () => {
    it('should accept JWT token as API token', async () => {
      const jwtToken = makeJwt();
      const jwtClient = new DataHubClient({
        baseUrl: `${server.baseUrl}/api/v1`,
        apiToken: jwtToken,
      });
      server.setHandler((req, res) => json(res, 200, { ok: true }));

      await jwtClient.get('/whoami/');

      expect(server.requests[0].headers.authorization).toBe(`Bearer ${jwtToken}`);
    });
  });

  describe('Token Refresh', () => {
    it('should refresh token on 401 error and retry once', async () => {
      server.setHandler((req, res) => {
        if (server.requests.length === 1) {
          errorEnvelope(res, 401, 'AUTH_UNAUTHORIZED', 'Token expired');
        } else {
          json(res, 200, { success: true });
        }
      });

      let refreshCalls = 0;
      client.setTokenRefreshCallback(async () => {
        refreshCalls++;
        return 'fresh-token';
      });

      const result = await client.get('/protected/');

      expect(result).toEqual({ success: true });
      expect(refreshCalls).toBe(1);
      expect(server.requests[0].headers.authorization).toBe('Bearer test-api-key');
      expect(server.requests[1].headers.authorization).toBe('Bearer fresh-token');
    });

    it('should throw UnauthorizedError if token refresh fails', async () => {
      server.setHandler((req, res) => {
        errorEnvelope(res, 401, 'AUTH_UNAUTHORIZED', 'Token expired');
      });

      client.setTokenRefreshCallback(async () => {
        throw new Error('Refresh failed');
      });

      const error = await client.get('/protected/').catch((e) => e);

      expect(error).toBeInstanceOf(UnauthorizedError);
      expect(error.message).toBe('Token refresh failed');
      expect(server.requests).toHaveLength(1);
    });

    it('should not refresh token if callback not set', async () => {
      server.setHandler((req, res) => {
        errorEnvelope(res, 401, 'AUTH_UNAUTHORIZED', 'Token expired');
      });

      await expect(client.get('/protected/')).rejects.toBeInstanceOf(UnauthorizedError);
      expect(server.requests).toHaveLength(1);
    });
  });

  describe('Authentication Error Handling', () => {
    it('should throw UnauthorizedError for 401 responses', async () => {
      server.setHandler((req, res) => {
        errorEnvelope(res, 401, 'AUTH_UNAUTHORIZED', 'Invalid credentials', {
          request_id: 'req-123',
        });
      });

      const error = await client.get('/login-required/').catch((e) => e);
      expect(error).toBeInstanceOf(UnauthorizedError);
      expect(error.requestId).toBe('req-123');
    });

    it('should throw ForbiddenError for 403 responses', async () => {
      server.setHandler((req, res) => {
        errorEnvelope(res, 403, 'AUTH_FORBIDDEN', 'Permission denied', {
          request_id: 'req-123',
        });
      });

      await expect(client.get('/admin-only/')).rejects.toBeInstanceOf(ForbiddenError);
    });

    it('should include request ID in error', async () => {
      server.setHandler((req, res) => {
        errorEnvelope(res, 401, 'AUTH_UNAUTHORIZED', 'Invalid credentials', {
          request_id: 'req-456',
        });
      });

      const error = await client.get('/login-required/').catch((e) => e);
      expect(error).toBeInstanceOf(UnauthorizedError);
      expect(error.requestId).toBe('req-456');
    });
  });
});
