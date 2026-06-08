// 311.18 — k6 load test: SPARQL latency SLO (p95 < 2s)
import http from 'k6/http';
import { sleep } from 'k6';

export const options = {
  stages: [
    { duration: '2m', target: 100 },
    { duration: '2m', target: 100 },
    { duration: '1m', target: 0 },
  ],
  thresholds: {
    'http_req_duration{endpoint:sparql}': ['p(95)<2000'],
  },
};

const BASE = __ENV.API_URL || 'http://localhost:8000/api/v1';

export default function() {
  http.get(`${BASE}/semantic/sparql/?query=SELECT%20*%20WHERE%20{?s%20?p%20?o}%20LIMIT%201`, { tags: { endpoint: 'sparql' } });
  sleep(0.5);
}
