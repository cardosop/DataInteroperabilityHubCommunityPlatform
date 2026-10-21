// 311.18 — k6 load test: marketplace browse
import http from 'k6/http';
import { sleep } from 'k6';

export const options = {
  stages: [
    { duration: '2m', target: 100 },
    { duration: '2m', target: 100 },
    { duration: '1m', target: 0 },
  ],
};

const BASE = __ENV.API_URL || 'http://localhost:8000/api/v1';

export default function() {
  http.get(`${BASE}/marketplace/listings/`, { tags: { endpoint: 'marketplace' } });
  sleep(0.5);
}
