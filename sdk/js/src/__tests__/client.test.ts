/**
 * Client Tests — W6.2: rewritten against a real local HTTP server
 * (the previous version mocked axios at the interceptor seam, which
 * never exercised the wire).
 */

import { DataHubClient } from '../client';
import { ValidationError, NotFoundError } from '../errors';
import { TestServer, startTestServer, json, errorEnvelope } from './helpers/testHttpServer';

describe('DataHubClient', () => {
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
      apiToken: 'test-token',
      backoffBaseMs: 1,
    });
  });

  describe('initialization', () => {
    it('should default timeout to 30000ms', () => {
      expect(client.getConfig().timeout).toBe(30000);
      expect(client.getConfig().userAgent).toBe('@meshant/interoperability-sdk/1.0.0');
    });

    it('should throw error if baseUrl is missing', () => {
      expect(() => {
        new DataHubClient({ baseUrl: '' } as any);
      }).toThrow('baseUrl is required');
    });
  });

  describe('authentication', () => {
    it('should set API token in Authorization header', async () => {
      server.setHandler((req, res) => json(res, 200, { ok: true }));

      await client.get('/whoami/');

      expect(server.requests[0].headers.authorization).toBe('Bearer test-token');
    });

    it('should allow setting token after initialization', async () => {
      client.setApiToken('new-token');
      server.setHandler((req, res) => json(res, 200, { ok: true }));

      await client.get('/whoami/');

      expect(server.requests[0].headers.authorization).toBe('Bearer new-token');
    });

    it('should preserve the base path when the request path starts with a slash', async () => {
      server.setHandler((req, res) => json(res, 200, { ok: true }));

      await client.get('/absolute-path/');

      // axios combineURLs semantics: /api/v1 prefix survives.
      expect(server.requests[0].url).toBe('/api/v1/absolute-path/');
    });
  });

  describe('error handling', () => {
    it('should parse and throw ValidationError for 400', async () => {
      server.setHandler((req, res) => {
        errorEnvelope(res, 400, 'VALIDATION_ERROR', 'Invalid input', {
          request_id: 'req-123',
        });
      });

      const error = await client.get('/invalid/').catch((e) => e);

      expect(error).toBeInstanceOf(ValidationError);
      expect(error.requestId).toBe('req-123');
    });

    it('should parse and throw NotFoundError for 404', async () => {
      server.setHandler((req, res) => {
        errorEnvelope(res, 404, 'NOT_FOUND', 'Resource not found');
      });

      await expect(client.get('/missing/')).rejects.toBeInstanceOf(NotFoundError);
    });
  });

  describe('retry logic', () => {
    it('should retry on 5xx errors', async () => {
      server.setHandler((req, res) => {
        if (server.requests.length <= 2) {
          errorEnvelope(res, 500, 'INTERNAL_ERROR', 'Server error');
        } else {
          json(res, 200, { success: true });
        }
      });

      const result = await client.get('/flaky/');

      expect(result).toEqual({ success: true });
      expect(server.requests).toHaveLength(3);
    });

    it('should not retry on 4xx errors', async () => {
      server.setHandler((req, res) => {
        errorEnvelope(res, 400, 'VALIDATION_ERROR', 'Invalid input');
      });

      await expect(client.get('/invalid/')).rejects.toBeInstanceOf(ValidationError);
      expect(server.requests).toHaveLength(1);
    });
  });
});
