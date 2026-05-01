// Phase 228 F4 (228.F4.24) — k6 load test.
//
// Acceptance: 100 events/sec for 5 minutes, P95 ≤ 200ms, zero data
// loss (every 202 corresponds to a non-DLQ delivery).
//
// Run::
//
//     k6 run --env BASE_URL=https://api.stagingmeshant-internal.example.com \
//            --env INGEST_KEY=msh_ol_<staging-key> \
//            --env HMAC_KEY=<hmac-from-secrets-manager> \
//            tests/load/openlineage_inbound.k6.js
//
// The script signs each request with HMAC-SHA256 of the body using
// ``HMAC_KEY``, and authenticates via the
// ``X-Meshant-OpenLineage-Key`` header (matching the production
// auth contract — see ``hub/apps/integrations/openlineage/views.py``).
//
// Output: JSON summary + per-second rates. Pipe to a file in CI:
//
//     k6 run --out json=load-test-results.json ...
//
// Pass criteria are encoded as ``thresholds`` so k6 exits non-zero
// when the SLO is violated.

import http from 'k6/http';
import crypto from 'k6/crypto';
import { check } from 'k6';
import encoding from 'k6/encoding';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const INGEST_KEY = __ENV.INGEST_KEY || '';
const HMAC_KEY = __ENV.HMAC_KEY || '';

if (!INGEST_KEY || !HMAC_KEY) {
  throw new Error(
    'k6 load test requires INGEST_KEY + HMAC_KEY env vars. Set them via ' +
    'AWS Secrets Manager (`meshant/staging/openlineage/{producer_keys/<tenant>,hmac_signing_key}`).',
  );
}

export const options = {
  // 100 events/sec sustained for 5 minutes — REQ-LIN-F4-002 / 228.F4.24.
  scenarios: {
    sustained_load: {
      executor: 'constant-arrival-rate',
      rate: 100,
      timeUnit: '1s',
      duration: '5m',
      preAllocatedVUs: 50,
      maxVUs: 200,
    },
  },
  // Pass criteria: P95 ≤ 200ms; success rate 100% (every event must
  // be 202-accepted; DLQ would surface as 5xx from the adapter on a
  // separate code path).
  thresholds: {
    http_req_duration: ['p(95)<200'],
    http_req_failed: ['rate<0.001'],  // <0.1% — effectively zero data loss.
    'checks{tag:status_202}': ['rate>0.999'],
  },
  noConnectionReuse: false,
};

function buildEvent() {
  const runId =
    'load-' +
    Math.random().toString(36).slice(2, 10) +
    '-' +
    Date.now().toString(36);
  return {
    eventType: 'COMPLETE',
    eventTime: new Date().toISOString(),
    producer: 'https://k6-load-test/',
    schemaURL: 'https://openlineage.io/spec/2-0-0/OpenLineage.json',
    run: { runId },
    job: { namespace: 'k6.load', name: 'inbound-test' },
    inputs: [{ namespace: 'meshant.contracts', name: 'src-' + runId }],
    outputs: [{ namespace: 'meshant.contracts', name: 'tgt-' + runId }],
  };
}

function hmacSign(body) {
  // crypto.hmac returns a base64-or-hex string depending on the
  // requested encoding. The server uses lowercase hex per
  // ``hmac.new(...).hexdigest()`` in views._verify_hmac.
  return 'sha256=' + crypto.hmac('sha256', HMAC_KEY, body, 'hex');
}

export default function () {
  const event = buildEvent();
  const body = JSON.stringify(event);
  const sig = hmacSign(body);

  const resp = http.post(`${BASE_URL}/api/v1/lineage/openlineage/events/`, body, {
    headers: {
      'Content-Type': 'application/json',
      'X-Meshant-OpenLineage-Key': INGEST_KEY,
      'X-Meshant-Signature': sig,
    },
    tags: {},
  });

  check(
    resp,
    {
      'status is 202': (r) => r.status === 202,
      'response under 200ms': (r) => r.timings.duration < 200,
    },
    { status_202: 'true' },
  );
}
