/**
 * Phase 260.7.I — Concurrent upload memory pressure test
 * (closes pass-3 T3-2).
 *
 * Acceptance (per spec):
 *   * 100 concurrent 1GB multipart uploads simulated against the API.
 *   * API container memory stays < 2GB peak; no OOM.
 *
 * Architectural property under test:
 *   The Meshant upload pipeline streams bytes BROWSER → S3 directly
 *   via presigned URLs. The API never touches the file payload — it
 *   only generates presigned URLs (init → chunks/init × N → complete)
 *   and the response bodies are tiny JSON (<1 KB each). Therefore
 *   100 concurrent 1GB uploads should NOT spike API memory beyond a
 *   modest allocation (request handlers, JSON encoding buffers,
 *   Django ORM connection pool).
 *
 *   The 2GB peak ceiling is conservative: a Django/gunicorn process
 *   serving steady state at 100 concurrent presigned-URL requests
 *   should stay well under 1GB; the 2GB ceiling allows headroom for
 *   transient allocations (DRF serializer scratch, audit-event
 *   payload assembly) and provides early warning if a regression
 *   accidentally introduces request-body buffering.
 *
 * What this test EXERCISES:
 *   * POST /files/init/   — generates the multipart upload + first
 *                            chunk presigned URL.
 *   * POST /files/{id}/chunks/init/  — generates per-chunk presigned
 *                                       URLs (one per chunk).
 *   * POST /files/{id}/complete/      — finalises the multipart upload.
 *
 * What this test DOES NOT EXERCISE (deliberately):
 *   * The S3 PUT of the actual chunk bytes. Sending 100 × 1GB to S3
 *     would cost real money and saturate the test runner's egress.
 *     The API-memory contract is independent of S3 throughput; the
 *     skip is acceptable because the API never sees those bytes.
 *
 * Run:
 *   k6 run --env BASE_URL=https://api.stagingmeshant-internal.example.com \
 *          --env AUTH_TOKEN=<staging-jwt> \
 *          tests/load/concurrent_uploads_memory.k6.js
 *
 * Memory assertion (out-of-band):
 *   The k6 script tracks API request-side metrics. The 2GB memory
 *   ceiling is asserted by the nightly workflow
 *   (.github/workflows/upload-memory-nightly.yml) which polls
 *   `kubectl top pod` against the staging API deployment for the
 *   duration of the k6 run and computes peak RSS.
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Counter, Rate } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const AUTH_TOKEN = __ENV.AUTH_TOKEN || '';

// Phase 260.7.I — file-size simulation pinned at exactly 1 GiB.
// The size triggers the multipart path (server splits >100 MB
// uploads into chunks; see hub/apps/files/views.py:415).
const SIZE_BYTES = 1024 * 1024 * 1024;  // 1 GiB
const CHUNK_SIZE_BYTES = 10 * 1024 * 1024;  // 10 MiB
const CHUNK_COUNT = Math.ceil(SIZE_BYTES / CHUNK_SIZE_BYTES);  // 103

if (!AUTH_TOKEN) {
  throw new Error(
    'k6 concurrent-upload-memory test requires AUTH_TOKEN env var. ' +
    'Pass a staging JWT issued for the load-test tenant. The token must ' +
    'have file:write scope.',
  );
}

const initLatency = new Trend('upload_init_latency_ms');
const chunkInitLatency = new Trend('upload_chunk_init_latency_ms');
const completeLatency = new Trend('upload_complete_latency_ms');
const fullFlowLatency = new Trend('upload_full_flow_latency_ms');
const apiErrorCounter = new Counter('upload_api_errors_total');
const initSuccessRate = new Rate('upload_init_success_rate');

export const options = {
  // 260.7.I — 100 concurrent virtual users, sustained for 5 minutes.
  // ramp-up over 30s avoids a thundering-herd init spike; steady state
  // is the load profile that exercises the API's heap stability.
  scenarios: {
    concurrent_uploads: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '30s', target: 100 },  // ramp to 100 VUs
        { duration: '5m', target: 100 },   // hold at 100 VUs for 5 minutes
        { duration: '30s', target: 0 },    // ramp down (drain in-flight)
      ],
      gracefulStop: '60s',
    },
  },
  // Thresholds gate CI pass/fail at the API-request level. The 2GB
  // memory ceiling is asserted by the nightly workflow's separate
  // kubectl-top-pod monitor, not by k6 (k6 cannot read pod memory
  // directly).
  thresholds: {
    upload_init_latency_ms: ['p(95)<500'],
    upload_chunk_init_latency_ms: ['p(95)<300'],
    upload_complete_latency_ms: ['p(95)<2000'],
    // <0.5% error rate — anything higher signals API instability
    // that would mask the memory measurement.
    upload_api_errors_total: ['count<5000'],  // ~0.5% of N runs
    upload_init_success_rate: ['rate>0.99'],
  },
};

function authHeaders() {
  return {
    Authorization: `Bearer ${AUTH_TOKEN}`,
    'Content-Type': 'application/json',
  };
}

function generateFileName(vu, iter) {
  // Unique per VU + iteration so concurrent calls don't collide on
  // the per-tenant ``unique_active_filename_per_tenant`` constraint.
  return `k6-mem-${vu}-${iter}-${Date.now()}.csv`;
}

export default function () {
  const flowStart = Date.now();
  const fileName = generateFileName(__VU, __ITER);

  // 1. POST /files/init/  — get the multipart upload id + first chunk URL.
  const initStart = Date.now();
  const initResp = http.post(
    `${BASE_URL}/api/v1/files/init/`,
    JSON.stringify({
      name: fileName,
      content_type: 'text/csv',
      size: SIZE_BYTES,
      upload_method: 'sdk',  // SDK path keeps Docker-resolvable host
    }),
    { headers: authHeaders() },
  );
  initLatency.add(Date.now() - initStart);

  const initOk = check(initResp, {
    'init: 201': (r) => r.status === 201,
    'init: requires_multipart': (r) =>
      r.json('requires_multipart') === true,
    'init: has upload_id': (r) => Boolean(r.json('upload_id')),
  });
  initSuccessRate.add(initOk);

  if (!initOk) {
    apiErrorCounter.add(1);
    return;
  }

  const fileId = initResp.json('file_id');
  // chunk #1 URL is in the response — already counted in init latency.
  // Skip the actual S3 PUT (see file-level docstring for rationale).

  // 2. POST /files/{id}/chunks/init/  — for chunks 2..N.
  // This loop is the API-memory-pressure surface: each chunk is a
  // separate API request that allocates a serializer + presigned URL.
  // Pre-260.7.I no test exercised this path concurrently at scale.
  for (let chunkNumber = 2; chunkNumber <= CHUNK_COUNT; chunkNumber++) {
    const chunkStart = Date.now();
    const chunkResp = http.post(
      `${BASE_URL}/api/v1/files/${fileId}/chunks/init/`,
      JSON.stringify({
        chunk_number: chunkNumber,
        chunk_size: CHUNK_SIZE_BYTES,
      }),
      { headers: authHeaders() },
    );
    chunkInitLatency.add(Date.now() - chunkStart);

    const chunkOk = check(chunkResp, {
      'chunk-init: 200': (r) => r.status === 200,
      'chunk-init: has upload_url': (r) => Boolean(r.json('upload_url')),
    });
    if (!chunkOk) {
      apiErrorCounter.add(1);
      // Continue the loop — partial chunk failures don't abort the
      // VU; they degrade the success rate metric instead.
    }
  }

  // 3. POST /files/{id}/complete/  — finalise the multipart upload.
  // This call would normally validate the parts list. We pass an
  // empty list to exercise the validation path without actually
  // having uploaded bytes. The API rejects the call (409 / 400) but
  // the request still passes through the same deserialiser /
  // routing layer, exercising the same memory surface as a real
  // complete. The error is expected and tracked separately.
  const completeStart = Date.now();
  const completeResp = http.post(
    `${BASE_URL}/api/v1/files/${fileId}/complete/`,
    JSON.stringify({
      content_sha256: 'a'.repeat(64),  // synthetic hash; rejected at validation
      parts: [],  // empty — exercises the parts-validation path
    }),
    { headers: authHeaders() },
  );
  completeLatency.add(Date.now() - completeStart);

  // The complete call is EXPECTED to fail (we didn't actually upload
  // bytes); we track the latency but don't count it as an error.
  // Any 5xx (server-side regression in validation) DOES count.
  if (completeResp.status >= 500) {
    apiErrorCounter.add(1);
  }

  fullFlowLatency.add(Date.now() - flowStart);

  // Brief breathing room between iterations so a single VU doesn't
  // saturate its connection-pool slot. The thread-of-execution model
  // for k6 is one fetch at a time per VU.
  sleep(0.5);
}

export function handleSummary(data) {
  // Compact stdout summary for CI logs; full JSON written to file
  // via `--out json=...` flag at the call site.
  const peak = data.metrics.upload_full_flow_latency_ms?.values?.['p(95)'] || 0;
  const errors = data.metrics.upload_api_errors_total?.values?.count || 0;
  return {
    stdout:
      `\n[k6-260.7.I] full-flow p95=${peak.toFixed(0)}ms errors=${errors}\n` +
      `             memory ceiling (<2GB) asserted out-of-band by ` +
      `upload-memory-nightly.yml workflow.\n`,
  };
}
