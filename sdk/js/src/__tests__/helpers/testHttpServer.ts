/**
 * Test HTTP server helper — real round-trips, no mocks (W6.2).
 *
 * Every SDK client test runs against an in-process Node HTTP server on
 * an ephemeral port.  Requests are recorded (method, url, headers, body)
 * so suites can assert exactly what reached the wire, and the handler is
 * swappable per test to script response sequences (401→200, 500×2→200,
 * 429 with Retry-After, …).
 *
 * This file is a shared helper, not a test suite — jest.config.js
 * testPathIgnorePatterns excludes helpers/ from collection.
 */

import * as http from 'http';
import { AddressInfo } from 'net';

export interface RecordedRequest {
  method: string;
  url: string;
  headers: http.IncomingHttpHeaders;
  body: string;
}

export type ServerHandler = (
  req: http.IncomingMessage,
  res: http.ServerResponse,
  index: number
) => void;

export interface TestServer {
  /** Base URL of the live server, e.g. http://127.0.0.1:45678 */
  baseUrl: string;
  /** Every request the server has received, in order. */
  requests: RecordedRequest[];
  /** Swap the response-scripting handler. */
  setHandler(handler: ServerHandler): void;
  /** Clear the recorded requests (and pending waiters). */
  reset(): void;
  /** Resolve once the server has recorded at least `count` requests. */
  waitForRequests(count: number): Promise<void>;
  /** Close the server (fails the test if a request is still in flight). */
  close(): Promise<void>;
}

/**
 * Write a JSON response.  `Connection: close` tells the client (undici)
 * not to keep the socket alive, so jest exits promptly after the server
 * shuts down.
 */
export function json(
  res: http.ServerResponse,
  status: number,
  data: unknown,
  headers: Record<string, string> = {}
): void {
  const body = JSON.stringify(data);
  res.writeHead(status, {
    'Content-Type': 'application/json',
    'Content-Length': String(Buffer.byteLength(body)),
    Connection: 'close',
    ...headers,
  });
  res.end(body);
}

/** Write the hub error envelope `{error: {code, message, http_status, …}}`. */
export function errorEnvelope(
  res: http.ServerResponse,
  status: number,
  code: string,
  message: string,
  extra: Record<string, unknown> = {},
  headers: Record<string, string> = {}
): void {
  json(res, status, { error: { code, message, http_status: status, ...extra } }, headers);
}

export async function startTestServer(): Promise<TestServer> {
  const requests: RecordedRequest[] = [];
  let handler: ServerHandler = (req, res) => {
    json(res, 200, { ok: true });
  };

  const waiters: Array<() => void> = [];

  const server = http.createServer((req, res) => {
    let body = '';
    req.on('data', (chunk) => {
      body += chunk;
    });
    req.on('end', () => {
      const index = requests.length;
      requests.push({
        method: req.method || 'GET',
        url: req.url || '/',
        headers: req.headers,
        body,
      });
      for (const wake of waiters.splice(0)) {
        wake();
      }
      handler(req, res, index);
    });
  });

  await new Promise<void>((resolve) => {
    server.listen(0, '127.0.0.1', resolve);
  });
  const port = (server.address() as AddressInfo).port;

  return {
    baseUrl: `http://127.0.0.1:${port}`,
    requests,
    setHandler: (next) => {
      handler = next;
    },
    reset: () => {
      requests.length = 0;
    },
    waitForRequests: (count) =>
      requests.length >= count
        ? Promise.resolve()
        : new Promise<void>((resolve) => waiters.push(resolve)),
    close: () =>
      new Promise<void>((resolve, reject) => {
        server.close((err) => (err ? reject(err) : resolve()));
      }),
  };
}
