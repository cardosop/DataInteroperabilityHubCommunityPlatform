/**
 * Phase 228.F1.24 (REQ-LIN-F1-005) — listing-lineage load test.
 *
 * Validates the F1 perf SLOs:
 *
 * - Summary mode: P95 latency ≤ 250 ms at 100 req/s
 * - Full mode:    P95 latency ≤ 500 ms at 50 req/s
 * - Zero 5xx responses under nominal load
 * - Error rate ≤ 0.01%
 *
 * Run locally:
 *
 *     k6 run tests/load/listing_lineage.js \
 *       -e BASE_URL=https://api.stagingmeshant-internal.example.com \
 *       -e AUTH_TOKEN=<bearer> \
 *       -e LISTING_ID=<uuid> \
 *       -e LISTING_ID_FULL=<uuid-with-active-entitlement>
 *
 * Required env vars:
 *
 * - BASE_URL          API base URL (e.g. staging)
 * - AUTH_TOKEN        Bearer for the consumer-tenant test user
 * - LISTING_ID        Listing for the SUMMARY scenario (no entitlement)
 * - LISTING_ID_FULL   Listing for the FULL scenario (consumer has ACTIVE entitlement)
 *
 * The script runs two scenarios concurrently and prints a per-scenario
 * P95 + error-rate summary at the end.  CI-friendly: exits non-zero
 * when any threshold breaches.
 */
import http from 'k6/http';
import { check } from 'k6';
import { Rate } from 'k6/metrics';

// ---------- Config ----------
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const AUTH_TOKEN = __ENV.AUTH_TOKEN || '';
const LISTING_ID = __ENV.LISTING_ID || '00000000-0000-0000-0000-000000000000';
const LISTING_ID_FULL = __ENV.LISTING_ID_FULL || LISTING_ID;

// Per-scenario error rates so the threshold can isolate which tier broke.
const summaryErrorRate = new Rate('summary_error_rate');
const fullErrorRate = new Rate('full_error_rate');

// ---------- Scenarios + thresholds ----------
export const options = {
  scenarios: {
    summary: {
      executor: 'constant-arrival-rate',
      rate: 100,                // 100 req/s
      timeUnit: '1s',
      duration: '60s',
      preAllocatedVUs: 50,
      maxVUs: 200,
      exec: 'summaryLoad',
    },
    full: {
      executor: 'constant-arrival-rate',
      rate: 50,                 // 50 req/s
      timeUnit: '1s',
      duration: '60s',
      preAllocatedVUs: 30,
      maxVUs: 100,
      exec: 'fullLoad',
      startTime: '0s',
    },
  },
  thresholds: {
    // Per-scenario P95 + 5xx-free guarantees from REQ-LIN-F1-005.
    'http_req_duration{scenario:summary}': ['p(95)<250'],
    'http_req_duration{scenario:full}': ['p(95)<500'],
    summary_error_rate: ['rate<0.0001'],   // ≤ 0.01%
    full_error_rate: ['rate<0.0001'],
    // Zero 5xx responses under nominal load.
    'http_req_failed{scenario:summary}': ['rate<0.0001'],
    'http_req_failed{scenario:full}': ['rate<0.0001'],
  },
};

// ---------- Helpers ----------
function authHeaders() {
  return {
    Authorization: AUTH_TOKEN ? `Bearer ${AUTH_TOKEN}` : '',
    Accept: 'application/json',
  };
}

// ---------- Scenarios ----------

/** Pre-purchase summary tier — IP-stripped response. */
export function summaryLoad() {
  const url = `${BASE_URL}/api/v1/marketplace/listings/${LISTING_ID}/lineage/?detail=summary`;
  const res = http.get(url, { headers: authHeaders(), tags: { scenario: 'summary' } });
  const ok = check(res, {
    'status is 200': (r) => r.status === 200,
    'no 5xx': (r) => r.status < 500,
  });
  summaryErrorRate.add(!ok);
}

/** Post-purchase full tier — entitled consumer reads transformation IP. */
export function fullLoad() {
  const url = `${BASE_URL}/api/v1/marketplace/listings/${LISTING_ID_FULL}/lineage/?detail=full`;
  const res = http.get(url, { headers: authHeaders(), tags: { scenario: 'full' } });
  const ok = check(res, {
    'status is 200': (r) => r.status === 200,
    'detail is full': (r) => {
      try {
        const body = r.json();
        return body && body.detail === 'full';
      } catch (_e) {
        return false;
      }
    },
  });
  fullErrorRate.add(!ok);
}
