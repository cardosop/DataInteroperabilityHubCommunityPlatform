/**
 * Error Handling Tests — W6.2: rewritten against real local HTTP
 * servers (network failures, timeouts, retries and error mapping all
 * exercise the real fetch round-trip; the previous suite drove mocked
 * axios interceptors directly).
 */

import { DataHubClient, calculateBackoffDelay } from '../client';
import {
  DataHubError,
  ValidationError,
  UnauthorizedError,
  NotFoundError,
  RateLimitError,
  ServerError,
  NetworkError,
} from '../errors';
import { TestServer, startTestServer, json, errorEnvelope } from './helpers/testHttpServer';

describe('Error Handling', () => {
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

  describe('Network Errors', () => {
    it('should throw NetworkError for network failures', async () => {
      // A port that was live moments ago and is now closed: guaranteed
      // connection refusal.
      const dead = await startTestServer();
      await dead.close();

      const isolated = new DataHubClient({
        baseUrl: `${dead.baseUrl}/api/v1`,
        maxRetries: 0,
      });

      await expect(isolated.get('/unreachable/')).rejects.toBeInstanceOf(NetworkError);
    });

    it('should throw NetworkError for timeout errors', async () => {
      const impatient = new DataHubClient({
        baseUrl: `${server.baseUrl}/api/v1`,
        timeout: 50,
        maxRetries: 0,
      });

      server.setHandler((req, res) => {
        // Never respond within the client's timeout window.
        setTimeout(() => {
          try {
            json(res, 200, { late: true });
          } catch {
            // Socket already gone — expected.
          }
        }, 500);
      });

      await expect(impatient.get('/slow/')).rejects.toBeInstanceOf(NetworkError);
    });

    it('should retry on network errors', async () => {
      server.setHandler((req, res) => {
        if (server.requests.length === 1) {
          // Simulate a connection dropped mid-flight: destroy the socket
          // without a response.
          req.socket.destroy();
        } else {
          json(res, 200, { success: true });
        }
      });

      const result = await client.get('/flaky-socket/');

      expect(result).toEqual({ success: true });
      expect(server.requests).toHaveLength(2);
    });
  });

  describe('API Errors', () => {
    it('should throw ValidationError for 400 responses', async () => {
      server.setHandler((req, res) => {
        errorEnvelope(res, 400, 'VALIDATION_ERROR', 'Invalid input', {
          request_id: 'req-123',
        });
      });

      const error = await client.get('/bad/').catch((e) => e);
      expect(error).toBeInstanceOf(ValidationError);
      expect(error.requestId).toBe('req-123');
    });

    it('should throw UnauthorizedError for 401 responses', async () => {
      server.setHandler((req, res) => {
        errorEnvelope(res, 401, 'AUTH_UNAUTHORIZED', 'Authentication required');
      });

      await expect(client.get('/unauth/')).rejects.toBeInstanceOf(UnauthorizedError);
    });

    it('should throw NotFoundError for 404 responses', async () => {
      server.setHandler((req, res) => {
        errorEnvelope(res, 404, 'NOT_FOUND', 'Resource not found');
      });

      await expect(client.get('/gone/')).rejects.toBeInstanceOf(NotFoundError);
    });

    it('should throw RateLimitError for 429 responses', async () => {
      server.setHandler((req, res) => {
        errorEnvelope(res, 429, 'RATE_LIMIT_EXCEEDED', 'Rate limit exceeded', {}, {
          'Retry-After': '60',
        });
      });

      const error = await client.get('/limited/', { retries: 0 }).catch((e) => e);
      expect(error).toBeInstanceOf(RateLimitError);
      expect(error.retryAfter).toBe(60);
    });

    it('should throw ServerError for 500 responses', async () => {
      server.setHandler((req, res) => {
        errorEnvelope(res, 500, 'INTERNAL_ERROR', 'Internal server error');
      });

      await expect(client.get('/broken/')).rejects.toBeInstanceOf(ServerError);
    });

    it('should throw ServerError for 502 responses', async () => {
      server.setHandler((req, res) => {
        errorEnvelope(res, 502, 'BAD_GATEWAY', 'Bad gateway');
      });

      await expect(client.get('/gateway/')).rejects.toBeInstanceOf(ServerError);
    });

    it('should throw ServerError for 503 responses', async () => {
      server.setHandler((req, res) => {
        errorEnvelope(res, 503, 'SERVICE_UNAVAILABLE', 'Service unavailable');
      });

      await expect(client.get('/down/')).rejects.toBeInstanceOf(ServerError);
    });

    it('should throw DataHubError with HTTP_ERROR for non-JSON error bodies', async () => {
      server.setHandler((req, res) => {
        res.writeHead(502, { 'Content-Type': 'text/html', Connection: 'close' });
        res.end('<html>Bad Gateway</html>');
      });

      const error = await client.get('/html-error/').catch((e) => e);
      expect(error).toBeInstanceOf(DataHubError);
      expect(error.httpStatus).toBe(502);
    });
  });

  describe('Retry Logic', () => {
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

    it('should retry on 429 rate limit errors', async () => {
      server.setHandler((req, res) => {
        if (server.requests.length === 1) {
          errorEnvelope(res, 429, 'RATE_LIMIT_EXCEEDED', 'Rate limit exceeded');
        } else {
          json(res, 200, { success: true });
        }
      });

      const result = await client.get('/limited-retry/');
      expect(result).toEqual({ success: true });
      expect(server.requests).toHaveLength(2);
    });

    it('should not retry on 4xx errors (except 429)', async () => {
      server.setHandler((req, res) => {
        errorEnvelope(res, 400, 'VALIDATION_ERROR', 'Invalid input');
      });

      await expect(client.get('/bad/')).rejects.toBeInstanceOf(ValidationError);
      expect(server.requests).toHaveLength(1);
    });

    it('should respect maxRetries configuration', async () => {
      const limited = new DataHubClient({
        baseUrl: `${server.baseUrl}/api/v1`,
        apiToken: 'test-token',
        maxRetries: 1,
        backoffBaseMs: 1,
      });

      server.setHandler((req, res) => {
        errorEnvelope(res, 500, 'INTERNAL_ERROR', 'Server error');
      });

      await expect(limited.get('/always-broken/')).rejects.toBeInstanceOf(ServerError);
      // Initial + exactly one retry.
      expect(server.requests).toHaveLength(2);
    });

    it('should support per-request retries override', async () => {
      server.setHandler((req, res) => {
        errorEnvelope(res, 500, 'INTERNAL_ERROR', 'Server error');
      });

      await expect(client.get('/no-retry/', { retries: 0 })).rejects.toBeInstanceOf(ServerError);
      expect(server.requests).toHaveLength(1);
    });
  });

  describe('Backoff', () => {
    it('should double the base delay per attempt', () => {
      expect(calculateBackoffDelay(0, 1000)).toBe(1000);
      expect(calculateBackoffDelay(1, 1000)).toBe(2000);
      expect(calculateBackoffDelay(2, 1000)).toBe(4000);
    });

    it('should honour Retry-After over exponential backoff', () => {
      expect(calculateBackoffDelay(0, 1, 2)).toBe(2000);
      expect(calculateBackoffDelay(3, 1000, 2)).toBe(8000);
    });

    it('should use exponential backoff for retries in practice', async () => {
      server.setHandler((req, res) => {
        if (server.requests.length <= 2) {
          errorEnvelope(res, 500, 'INTERNAL_ERROR', 'Server error');
        } else {
          json(res, 200, { success: true });
        }
      });

      const started = Date.now();
      const result = await client.get('/backoff/');
      const elapsed = Date.now() - started;

      expect(result).toEqual({ success: true });
      expect(server.requests).toHaveLength(3);
      // backoffBaseMs=1 → sleeps ~1ms + ~2ms; assert no accidental
      // default-second-scale backoff leaked in.
      expect(elapsed).toBeLessThan(500);
    });
  });

  describe('Timeout Handling', () => {
    it('should respect timeout configuration', () => {
      const customClient = new DataHubClient({
        baseUrl: `${server.baseUrl}/api/v1`,
        apiToken: 'test-token',
        timeout: 5000,
      });

      expect(customClient.getConfig().timeout).toBe(5000);
    });
  });

  describe('Error Details', () => {
    it('should preserve error details from API response', async () => {
      server.setHandler((req, res) => {
        errorEnvelope(res, 400, 'VALIDATION_ERROR', 'Invalid input', {
          request_id: 'req-123',
          timestamp: '2025-01-15T10:00:00Z',
          details: {
            field_errors: [{ field: 'name', message: 'Name is required' }],
          },
        });
      });

      const error = await client.get('/bad/').catch((e) => e);

      expect(error).toBeInstanceOf(ValidationError);
      expect(error.requestId).toBe('req-123');
      expect(error.timestamp).toBe('2025-01-15T10:00:00Z');
      expect(error.details).toEqual({
        field_errors: [{ field: 'name', message: 'Name is required' }],
      });
    });

    it('should convert error to JSON', async () => {
      server.setHandler((req, res) => {
        errorEnvelope(res, 400, 'VALIDATION_ERROR', 'Invalid input', {
          request_id: 'req-123',
        });
      });

      const error = await client.get('/bad/').catch((e) => e);
      const jsonError = error.toJSON();

      expect(jsonError.error.code).toBe('VALIDATION_ERROR');
      expect(jsonError.error.message).toBe('Invalid input');
      expect(jsonError.error.http_status).toBe(400);
      expect(jsonError.error.request_id).toBe('req-123');
    });
  });
});
