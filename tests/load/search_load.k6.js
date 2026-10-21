// 311.18 (G24) — k6 load test: search latency SLO (p95 < 500ms)
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '2m', target: 100 },
    { duration: '2m', target: 100 },
    { duration: '1m', target: 0 },
  ],
  thresholds: {
    'http_req_duration{endpoint:search}': ['p(95)<500'],
  },
};

const BASE = __ENV.API_URL || 'http://localhost:8000/api/v1';

export default function() {
  const resp = http.get(`${BASE}/search/?q=test`, { tags: { endpoint: 'search' } });
  check(resp, { 'status < 500': (r) => r.status < 500 });
  sleep(0.5);
}
