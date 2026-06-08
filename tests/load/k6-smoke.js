/**
 * 305.3 — k6 Smoke Test
 *
 * Lightweight load test: 10 virtual users for 60 seconds hitting
 * key health, search, assets, marketplace, and SPARQL endpoints.
 * Manual run only — not wired into CI.
 *
 * Usage:
 *   k6 run tests/load/k6-smoke.js
 *   k6 run --vus 5 --duration 30s tests/load/k6-smoke.js
 *   k6 run -e BASE_URL=https://api.stagingmeshant-internal.example.com tests/load/k6-smoke.js
 *
 * Prerequisites:
 *   - k6 installed: https://k6.io/docs/get-started/installation/
 *   - BASE_URL env var pointing to target environment
 *   - API_TOKEN env var for authenticated endpoints (optional; unauthenticated requests tested otherwise)
 */

import http from "k6/http";
import { check, sleep, group } from "k6";
import { Rate, Trend } from "k6/metrics";

// ── Configuration ────────────────────────────────────────────────────

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const API_TOKEN = __ENV.API_TOKEN || "";

export const options = {
  vus: 10,
  duration: "60s",
  thresholds: {
    http_req_duration: ["p(95)<2000"],   // 95% of requests < 2s
    http_req_failed: ["rate<0.05"],       // <5% failure rate
    "health_duration": ["p(95)<500"],     // Health endpoint < 500ms
    "search_duration": ["p(95)<1000"],    // Search < 1s
  },
  summaryTrendStats: ["min", "avg", "med", "p(90)", "p(95)", "p(99)", "max"],
};

// ── Custom metrics ────────────────────────────────────────────────────

const healthDuration = new Trend("health_duration");
const searchDuration = new Trend("search_duration");
const errorRate = new Rate("errors");

// ── Default headers ───────────────────────────────────────────────────

function authHeaders() {
  if (API_TOKEN) {
    return { Authorization: `Bearer ${API_TOKEN}` };
  }
  return {};
}

// ── Endpoint groups ───────────────────────────────────────────────────

export default function () {
  // 1. Health check
  group("health", () => {
    const res = http.get(`${BASE_URL}/api/v1/health/`, {
      headers: { ...authHeaders() },
      tags: { endpoint: "health" },
    });
    healthDuration.add(res.timings.duration);
    check(res, {
      "health status 200": (r) => r.status === 200,
    }) || errorRate.add(1);
  });

  sleep(1);

  // 2. Search
  group("search", () => {
    const queries = ["data", "contract", "asset", "pipeline", "report"];
    const q = queries[Math.floor(Math.random() * queries.length)];
    const res = http.get(`${BASE_URL}/api/v1/search/?q=${q}`, {
      headers: { ...authHeaders() },
      tags: { endpoint: "search" },
    });
    searchDuration.add(res.timings.duration);
    check(res, {
      "search status 200": (r) => r.status === 200,
    }) || errorRate.add(1);
  });

  sleep(1);

  // 3. Assets list
  group("assets", () => {
    const res = http.get(`${BASE_URL}/api/v1/assets/?limit=10`, {
      headers: { ...authHeaders() },
      tags: { endpoint: "assets" },
    });
    check(res, {
      "assets status 200 or 401": (r) => r.status === 200 || r.status === 401,
    }) || errorRate.add(1);
  });

  sleep(1);

  // 4. Marketplace listings
  group("marketplace", () => {
    const res = http.get(`${BASE_URL}/api/v1/marketplace/listings/?limit=10`, {
      headers: { ...authHeaders() },
      tags: { endpoint: "marketplace" },
    });
    check(res, {
      "marketplace status 200": (r) => r.status === 200,
    }) || errorRate.add(1);
  });

  sleep(1);

  // 5. SPARQL query
  group("sparql", () => {
    const sparqlQuery = encodeURIComponent(
      "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 1"
    );
    const res = http.get(
      `${BASE_URL}/api/v1/semantic/sparql/?query=${sparqlQuery}`,
      { headers: { ...authHeaders() }, tags: { endpoint: "sparql" } }
    );
    check(res, {
      "sparql status 200 or 401": (r) => r.status === 200 || r.status === 401,
    }) || errorRate.add(1);
  });

  sleep(1);
}

// ── Lifecycle hooks ───────────────────────────────────────────────────

export function setup() {
  console.log(`k6 smoke test starting: ${BASE_URL}`);
  console.log(`VUs: ${options.vus}, Duration: ${options.duration}`);
  return {};
}

export function teardown(data) {
  console.log("k6 smoke test complete.");
}

export function handleSummary(data) {
  const summary = {
    timestamp: new Date().toISOString(),
    base_url: BASE_URL,
    vus: options.vus,
    duration: options.duration,
    total_requests: data.metrics.http_reqs?.values?.count || 0,
    failed_requests: data.metrics.http_req_failed?.values?.fails || 0,
    p95_duration_ms: Math.round(
      data.metrics.http_req_duration?.values?.["p(95)"] || 0
    ),
    endpoints: {},
  };

  // Per-endpoint summary
  for (const [name, metric] of Object.entries(data.metrics)) {
    if (name.endsWith("_duration") && name !== "http_req_duration") {
      summary.endpoints[name.replace("_duration", "")] = {
        p95_ms: Math.round(metric.values?.["p(95)"] || 0),
        avg_ms: Math.round(metric.values?.avg || 0),
      };
    }
  }

  return {
    "stdout": JSON.stringify(summary, null, 2),
    "tests/load/k6-smoke-summary.json": JSON.stringify(summary),
  };
}
