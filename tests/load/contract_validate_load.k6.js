// 311.18 — k6 load test: contract validation (p95 < 1s)
import http from 'k6/http';
import { sleep } from 'k6';

export const options = {
  stages: [
    { duration: '2m', target: 100 },
    { duration: '2m', target: 100 },
    { duration: '1m', target: 0 },
  ],
  thresholds: {
    'http_req_duration{endpoint:contract}': ['p(95)<1000'],
  },
};

const BASE = __ENV.API_URL || 'http://localhost:8000/api/v1';

export default function() {
  http.get(`${BASE}/contracts/`, { tags: { endpoint: 'contract' } });
  sleep(0.5);
}
