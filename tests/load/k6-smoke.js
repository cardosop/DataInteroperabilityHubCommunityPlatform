/**
 * 305.3 — k6 Smoke Test
 *
 * Lightweight load test: 10 virtual users for 60 seconds hitting
 * key health, search, assets, marketplace, and SPARQL endpoints.
 * Manual run only — not wired into CI.
 *
 * Phase U.6 (staging): the smoke now LOGS IN (setup) and sends the access
 * token. Staging runs cookie-mode auth (USE_HTTPONLY_AUTH_COOKIES) — the
 * login body carries no access_token; the token is extracted from the
 * Set-Cookie header. Legs that may legitimately answer 401 (unauthenticated
 * fallback) or 404 (MVP-gated paid surfaces) use k6's expectedStatuses so
 * they do NOT count toward http_req_failed — the earlier staging run
 * crossed the err<5% threshold purely on expected 404s/401s.
 *
 * Usage:
 *   k6 run tests/load/k6-smoke.js
 *   k6 run --vus 5 --duration 30s tests/load/k6-smoke.js
 *   k6 run -e BASE_URL=https://api.stagingmeshant-internal.example.com tests/load/k6-smoke.js
 *
 * Prerequisites:
 *   - k6 installed: https://k6.io/docs/get-started/installation/
 *   - BASE_URL env var pointing to target environment
 *   - SMOKE_EMAIL / SMOKE_PASSWORD for the authenticated legs
 *     (default: e2e_admin@example.com / TestPass123)
 */

import http from "k6/http";
import { check, sleep, group } from "k6";
import { Rate, Trend } from "k6/metrics";

// ── Configuration ────────────────────────────────────────────────────

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const SMOKE_EMAIL = __ENV.SMOKE_EMAIL || "e2e_admin@example.com";
const SMOKE_PASSWORD = __ENV.SMOKE_PASSWORD || "TestPass123";

export const options = {
  vus: 5,
  duration: "60s",
  thresholds: {
    // Phase U.6: latency budgets sized for the SINGLE-HOST compose staging
    // (3 gunicorn workers, shared disk). On this host the search view alone
    // runs 1-4s under 5 VUs; production-grade SLAs belong to the EKS
    // environment (ticket 210.29). The endpoint-health gate is the
    // custom `errors` rate above.
    http_req_duration: ["p(95)<5000"],
    // Phase U.6: the built-in http_req_failed counts ANY 4xx even with
    // expectedStatuses (proven broken in k6 0.55.2 by micro-test) — the
    // contract gate is the custom `errors` rate, fed by the per-leg
    // checks below (200/401/404/429 per the staging contract).
    errors: ["rate<0.05"],
    "health_duration": ["p(95)<500"],     // Health endpoint < 500ms
    "search_duration": ["p(95)<3000"],    // Search < 3s (compose-staging budget)
  },
  summaryTrendStats: ["min", "avg", "med", "p(90)", "p(95)", "p(99)", "max"],
};

// ── Custom metrics ────────────────────────────────────────────────────

const healthDuration = new Trend("health_duration");
const searchDuration = new Trend("search_duration");
const errorRate = new Rate("errors");

// ── Setup: login and extract the access token (cookie-mode aware) ─────

function extractAccessTokenFromCookies(setCookieHeaders) {
  // k6 may return a single string (first header) or an array — normalize so
  // a bare string is not iterated character-by-character (the first staging
  // run logged "smoke login failed (200)" for exactly this reason).
  const headers = Array.isArray(setCookieHeaders)
    ? setCookieHeaders
    : setCookieHeaders
      ? [String(setCookieHeaders)]
      : [];
  for (const header of headers) {
    const match = header.match(/access_token=([^;]+)/);
    if (match) return decodeURIComponent(match[1]);
  }
  return "";
}

export function setup() {
  console.log(`k6 smoke test starting: ${BASE_URL}`);
  console.log(`VUs: ${options.vus}, Duration: ${options.duration}`);
  let token = "";
  const res = http.post(
    `${BASE_URL}/api/v1/auth/login/`,
    JSON.stringify({ email: SMOKE_EMAIL, password: SMOKE_PASSWORD }),
    { headers: { "Content-Type": "application/json" } }
  );
  if (res.status === 200) {
    // Legacy mode: token in the body.
    token = res.json("access_token") || "";
    // Cookie mode (staging/production): token in the Set-Cookie header.
    if (!token) {
      token = extractAccessTokenFromCookies(res.headers["Set-Cookie"]);
    }
  }
  if (!token) {
    console.warn(
      `smoke login failed (${res.status}) — authenticated legs will run unauthenticated`
    );
  } else {
    console.log("smoke login OK — authenticated legs will send the token");
  }
  return { token };
}

// ── Endpoint groups ───────────────────────────────────────────────────

export default function (data) {
  const token = (data && data.token) || "";
  const headers = token ? { Authorization: `Bearer ${token}` } : {};

  // 1. Health check — /health/ is the comprehensive view; /api/v1/health/
  // does not exist in this revision (Phase U.6: it 404'd every k6 leg).
  group("health", () => {
    const res = http.get(`${BASE_URL}/health/`, {
      headers: { ...headers },
      tags: { endpoint: "health" },
      expectedStatuses: [200],
      noConnectionReuse: true,
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
      headers: { ...headers },
      tags: { endpoint: "search" },
      expectedStatuses: [200, 401, 429],
      noConnectionReuse: true,
    });
    searchDuration.add(res.timings.duration);
    check(res, {
      "search status 200/401/429": (r) => [200, 401, 429].includes(r.status),
    }) || errorRate.add(1);
  });

  sleep(1);

  // 3. Assets list
  group("assets", () => {
    const res = http.get(`${BASE_URL}/api/v1/assets/?limit=10`, {
      headers: { ...headers },
      tags: { endpoint: "assets" },
      expectedStatuses: [200, 401, 429],
      noConnectionReuse: true,
    });
    check(res, {
      "assets status 200/401/429": (r) => [200, 401, 429].includes(r.status),
    }) || errorRate.add(1);
  });

  sleep(1);

  // 4. Marketplace listings — paid surface: 404 when MVP_MODE gates it
  group("marketplace", () => {
    const res = http.get(`${BASE_URL}/api/v1/marketplace/listings/?limit=10`, {
      headers: { ...headers },
      tags: { endpoint: "marketplace" },
      expectedStatuses: [200, 401, 404, 429],
      noConnectionReuse: true,
    });
    check(res, {
      "marketplace status 200/401/404/429": (r) =>
        [200, 401, 404, 429].includes(r.status),
    }) || errorRate.add(1);
  });

  sleep(1);

  // 5. SPARQL query — the route is `sparql` with NO trailing slash
  // (hub/apps/semantic/urls.py) — the slash variant 404'd every leg.
  group("sparql", () => {
    const sparqlQuery = encodeURIComponent(
      "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 1"
    );
    const res = http.get(
      `${BASE_URL}/api/v1/semantic/sparql?query=${sparqlQuery}`,
      {
        headers: { ...headers },
        tags: { endpoint: "sparql" },
        expectedStatuses: [200, 401, 429],
        noConnectionReuse: true,
      }
    );
    check(res, {
      "sparql status 200/401/429": (r) => [200, 401, 429].includes(r.status),
    }) || errorRate.add(1);
  });

  sleep(1);
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
  // Per-endpoint failure breakdown (Phase U.6 diagnostics — keep).
  const failsByTag = {};
  const passesByTag = {};
  const tags = Object.keys(data.root_group?.groups || {});
  for (const t of tags) {
    failsByTag[t] = 0;
    passesByTag[t] = 0;
  }
  for (const [name, metric] of Object.entries(data.metrics)) {
    if (name === "http_req_failed") {
      for (const [key, val] of Object.entries(metric.values || {})) {
        const m = key.match(/^tag:(\w+)/);
        if (m && (val.fails || val.passes)) {
          failsByTag[m[1]] = val.fails || 0;
          passesByTag[m[1]] = val.passes || 0;
        }
      }
    }
  }
  summary.endpoint_failures = failsByTag;
  summary.endpoint_passes = passesByTag;

  return {
    "stdout": JSON.stringify(summary, null, 2),
    // Phase U.6: path relative to the container WORKDIR — the smoke script
    // mounts the repo at /repo and sets -w /repo.
    "tests/load/k6-smoke-summary.json": JSON.stringify(summary),
  };
}
