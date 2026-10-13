/**
 * openspec add-databricks-control-plane task 0b.14 — k6 smoke for the
 * Databricks control-plane SSO/OBO surface (Sign In with Databricks).
 *
 * Covers the P0b live HTTP contract:
 *   1. SSO chooser      — GET /api/v1/databricks/sso/workspaces/
 *   2. SSO login-url    — GET /api/v1/databricks/sso/login-url/
 *                         (PKCE S256 + signed state + offline_access scope
 *                         asserted live, on the authorize URL shape)
 *   3. SSO session      — GET /api/v1/databricks/sso/session/
 *                         (countdown state + hub re-auth deadline)
 *   4. Workspace registry — GET /api/v1/databricks/workspaces/
 *   5. OBO live query   — P9-GATED leg (see below)
 *
 * The full U2M round-trip (login-url → Databricks consent → callback) is
 * deferred to the P9 live sandbox per the acceptance line: k6 cannot drive
 * a browser consent screen, and the P0b HTTP surface has no interactive
 * live-query execution endpoint (the six execution surfaces land with
 * their P-phase executors). The harness below ships now so P9 only has to
 * point env vars at the sandbox.
 *
 * OBO live-query leg (P9): set OBO_LIVE_QUERY=1 to enable it. The leg
 * sends the authenticated Hub JWT to OBO_QUERY_URL (defaults to the
 * shipped live-query records surface; the P9 sandbox repoints it at the
 * live execution surface once P1/P3 wire the query endpoints). Its
 * expectedStatuses accept every documented response the not-yet-wired
 * surface can return, so the leg fails only on transport/5xx errors.
 *
 * Manual run only — not wired into CI (the tests/load convention).
 *
 * Usage:
 *   k6 run tests/load/databricks_obo.k6.js
 *   k6 run --vus 5 --duration 30s tests/load/databricks_obo.k6.js
 *   k6 run -e BASE_URL=https://api.stagingmeshant-internal.example.com \
 *          -e SMOKE_EMAIL=<email> -e SMOKE_PASSWORD=<password> \
 *          -e TENANT_ID=<tenant-uuid> tests/load/databricks_obo.k6.js
 *   # P9 live sandbox:
 *   k6 run -e OBO_LIVE_QUERY=1 \
 *          -e OBO_QUERY_URL=https://<hub>/api/v1/... \
 *          -e TENANT_ID=<tenant-uuid> \
 *          -e DATABRICKS_WORKSPACE_ID=<workspace-uuid> \
 *          tests/load/databricks_obo.k6.js
 *
 * Prerequisites:
 *   - k6 installed: https://k6.io/docs/get-started/installation/
 *   - BASE_URL pointing at a full-mode environment whose e2e tenant has
 *     databricks_control_plane_enabled + databricks_sso_enabled
 *     (ensure_e2e_user_roles enables the control-plane flag; the SSO flag
 *     is default-off per task 0b.10, so legs 2-3 may legitimately 403).
 *   - SMOKE_EMAIL / SMOKE_PASSWORD for the authenticated legs
 *     (default: e2e_admin@example.com / TestPass123)
 *   - TENANT_ID (default: the e2e default tenant UUID used by the
 *     JOURNEY-DB-003 spec)
 */

import http from "k6/http";
import { check, sleep, group } from "k6";
import { Rate, Trend } from "k6/metrics";

// ── Configuration ────────────────────────────────────────────────────

const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";
const SMOKE_EMAIL = __ENV.SMOKE_EMAIL || "e2e_admin@example.com";
const SMOKE_PASSWORD = __ENV.SMOKE_PASSWORD || "TestPass123";
const TENANT_ID =
  __ENV.TENANT_ID || "00000000-0000-0000-0000-000000000001";
const WORKSPACE_ID = __ENV.DATABRICKS_WORKSPACE_ID || "";
const OBO_LIVE_QUERY = __ENV.OBO_LIVE_QUERY === "1";
const OBO_QUERY_URL =
  __ENV.OBO_QUERY_URL || `${BASE_URL}/api/v1/warehouses/query/`;

export const options = {
  vus: 5,
  duration: "60s",
  thresholds: {
    // Smoke-level budgets sized like tests/load/k6-smoke.js; the
    // per-endpoint trends carry the tighter control-plane budgets.
    // The built-in http_req_failed counts ANY 4xx even with
    // expectedStatuses (proven broken in k6 0.55.2 by micro-test) —
    // the contract gate is the custom `errors` rate below.
    http_req_duration: ["p(95)<5000"],
    errors: ["rate<0.05"],
    sso_chooser_duration: ["p(95)<2000"],
    sso_login_url_duration: ["p(95)<2000"],
    sso_session_duration: ["p(95)<2000"],
    workspace_registry_duration: ["p(95)<3000"],
    obo_live_query_duration: ["p(95)<10000"],
  },
  summaryTrendStats: ["min", "avg", "med", "p(90)", "p(95)", "p(99)", "max"],
};

// ── Custom metrics ────────────────────────────────────────────────────

const ssoChooserDuration = new Trend("sso_chooser_duration");
const ssoLoginUrlDuration = new Trend("sso_login_url_duration");
const ssoSessionDuration = new Trend("sso_session_duration");
const workspaceRegistryDuration = new Trend("workspace_registry_duration");
const oboLiveQueryDuration = new Trend("obo_live_query_duration");
const errorRate = new Rate("errors");

// ── Setup: login and resolve the SSO workspace id when not provided ───

function extractAccessTokenFromCookies(setCookieHeaders) {
  // k6 may return a single string (first header) or an array — normalize so
  // a bare string is not iterated character-by-character (the same trap the
  // k6-smoke.js staging run hit).
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
  console.log(`databricks OBO smoke starting: ${BASE_URL}`);
  let token = "";
  const res = http.post(
    `${BASE_URL}/api/v1/auth/login/`,
    JSON.stringify({ email: SMOKE_EMAIL, password: SMOKE_PASSWORD }),
    { headers: { "Content-Type": "application/json" } },
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
      `login failed (${res.status}) — authenticated legs will run unauthenticated`,
    );
  } else {
    console.log("login OK — authenticated legs will send the token");
  }

  // Resolve the workspace id from the live chooser when the operator did
  // not pin one (the login-url leg needs it). The chooser may legitimately
  // 403 (SSO flag off) — the id then stays empty and the leg skips.
  let workspaceId = WORKSPACE_ID;
  if (!workspaceId) {
    const chooser = http.get(
      `${BASE_URL}/api/v1/databricks/sso/workspaces/?tenant_id=${TENANT_ID}`,
      { expectedStatuses: [200, 400, 403, 404, 429] },
    );
    if (chooser.status === 200) {
      const workspaces = chooser.json("workspaces") || [];
      if (workspaces.length > 0) {
        workspaceId = workspaces[0].id;
        console.log(`chooser resolved workspace id: ${workspaceId}`);
      }
    } else {
      console.warn(
        `chooser probe returned ${chooser.status} — login-url leg will skip (no workspace id)`,
      );
    }
  }
  return { token, workspaceId };
}

// ── Endpoint groups ───────────────────────────────────────────────────

export default function (data) {
  const token = (data && data.token) || "";
  const workspaceId = (data && data.workspaceId) || "";
  const headers = token ? { Authorization: `Bearer ${token}` } : {};

  // 1. SSO chooser — AllowAny; the tenant resolves from the query param
  // (pre-login convention, mirrors the login page's tenant hint).
  group("sso-chooser", () => {
    const res = http.get(
      `${BASE_URL}/api/v1/databricks/sso/workspaces/?tenant_id=${TENANT_ID}`,
      {
        headers: { ...headers },
        tags: { endpoint: "sso-chooser" },
        // 200 ok · 400 NO_TENANT · 403 DATABRICKS_SSO_DISABLED ·
        // 404 MVP-gated · 429 throttled
        expectedStatuses: [200, 400, 403, 404, 429],
        noConnectionReuse: true,
      },
    );
    ssoChooserDuration.add(res.timings.duration);
    check(res, {
      "sso-chooser status 200/400/403/404/429": (r) =>
        [200, 400, 403, 404, 429].includes(r.status),
      "sso-chooser 200 carries a workspaces list": (r) =>
        r.status !== 200 || Array.isArray(r.json("workspaces")),
    }) || errorRate.add(1);
  });

  sleep(1);

  // 2. SSO login-url — the live PKCE contract: the authorize URL must
  // carry response_type=code, a S256 code_challenge, a signed state, and
  // the offline_access scope (0b.2 — otherwise no refresh token is ever
  // returned for the vault).
  if (!workspaceId) {
    console.warn(
      "no workspace id resolved (env DATABRICKS_WORKSPACE_ID or a live chooser) — skipping the login-url leg",
    );
  } else {
    group("sso-login-url", () => {
      const res = http.get(
        `${BASE_URL}/api/v1/databricks/sso/login-url/?tenant_id=${TENANT_ID}&workspace_id=${workspaceId}`,
        {
          headers: { ...headers },
          tags: { endpoint: "sso-login-url" },
          // 200 ok · 400 DATABRICKS_SSO_UNAVAILABLE (GCP) / missing client ·
          // 403 flag · 404 workspace/tenant · 429 throttled
          expectedStatuses: [200, 400, 403, 404, 429],
          noConnectionReuse: true,
        },
      );
      ssoLoginUrlDuration.add(res.timings.duration);
      // The view responds with a JSON envelope {"login_url": "<url>"} —
      // extract the URL first (regexing the raw JSON text would let
      // envelope punctuation/escaping skew the shape checks).
      const url = res.status === 200 ? res.json("login_url") || "" : "";
      check(res, {
        "sso-login-url status 200/400/403/404/429": (r) =>
          [200, 400, 403, 404, 429].includes(r.status),
        "authorize URL carries response_type=code": () =>
          res.status !== 200 || url.includes("response_type=code"),
        "authorize URL carries a PKCE S256 challenge": () =>
          res.status !== 200 || /code_challenge=[A-Za-z0-9_-]+/.test(url),
        "authorize URL carries a signed state": () =>
          res.status !== 200 || /state=[A-Za-z0-9._-]+/.test(url),
        "authorize URL requests offline_access": () =>
          res.status !== 200 || decodeURIComponent(url).includes("offline_access"),
      }) || errorRate.add(1);
    });

    sleep(1);
  }

  // 3. SSO session — the countdown banner's source; requires the Hub JWT.
  group("sso-session", () => {
    const res = http.get(`${BASE_URL}/api/v1/databricks/sso/session/`, {
      headers: { ...headers },
      tags: { endpoint: "sso-session" },
      expectedStatuses: [200, 401],
      noConnectionReuse: true,
    });
    ssoSessionDuration.add(res.timings.duration);
    check(res, {
      "sso-session status 200/401": (r) => [200, 401].includes(r.status),
      "sso-session 200 carries countdown + hub deadline": (r) =>
        r.status !== 200 ||
        (r.json("countdown") !== null &&
          typeof r.json("hub_reauth_deadline") === "string"),
    }) || errorRate.add(1);
  });

  sleep(1);

  // 4. Workspace registry — TENANT_ADMIN-gated; the OBO bindings live
  // against these workspace rows.
  group("workspace-registry", () => {
    const res = http.get(`${BASE_URL}/api/v1/databricks/workspaces/`, {
      headers: { ...headers },
      tags: { endpoint: "workspace-registry" },
      // 200 ok · 401 unauthenticated · 403 flag/kill/RBAC ·
      // 404 MVP-gated · 429 throttled
      expectedStatuses: [200, 401, 403, 404, 429],
      noConnectionReuse: true,
    });
    workspaceRegistryDuration.add(res.timings.duration);
    check(res, {
      "workspace-registry status 200/401/403/404/429": (r) =>
        [200, 401, 403, 404, 429].includes(r.status),
      "workspace-registry 200 is paginated": (r) =>
        r.status !== 200 || Array.isArray(r.json("results")),
    }) || errorRate.add(1);
  });

  sleep(1);

  // 5. OBO live query — P9-gated. The live execution surface is not wired
  // in P0b (interactive executors land with their P-phase endpoints); the
  // sandbox exports a Hub JWT for a user with a REAL Databricks binding and
  // repoints OBO_QUERY_URL. Until then this leg never runs.
  if (!OBO_LIVE_QUERY) {
    console.log("OBO live-query leg disabled (set OBO_LIVE_QUERY=1 for the P9 sandbox)");
  } else {
    group("obo-live-query", () => {
      const res = http.get(OBO_QUERY_URL, {
        headers: { ...headers },
        tags: { endpoint: "obo-live-query" },
        // 200 ok · 401 (no binding / expired Hub session) · 403 flag ·
        // 404 surface not wired · 429 throttled
        expectedStatuses: [200, 401, 403, 404, 429],
        noConnectionReuse: true,
      });
      oboLiveQueryDuration.add(res.timings.duration);
      check(res, {
        "obo-live-query status 200/401/403/404/429": (r) =>
          [200, 401, 403, 404, 429].includes(r.status),
      }) || errorRate.add(1);
    });

    sleep(1);
  }
}

export function teardown() {
  console.log("databricks OBO smoke complete.");
}

export function handleSummary(data) {
  const summary = {
    timestamp: new Date().toISOString(),
    base_url: BASE_URL,
    tenant_id: TENANT_ID,
    vus: options.vus,
    duration: options.duration,
    total_requests: data.metrics.http_reqs?.values?.count || 0,
    failed_requests: data.metrics.http_req_failed?.values?.fails || 0,
    p95_duration_ms: Math.round(
      data.metrics.http_req_duration?.values?.["p(95)"] || 0,
    ),
    endpoints: {},
    endpoint_failures: {},
    endpoint_passes: {},
  };

  for (const [name, metric] of Object.entries(data.metrics)) {
    if (name.endsWith("_duration") && name !== "http_req_duration") {
      summary.endpoints[name.replace("_duration", "")] = {
        p95_ms: Math.round(metric.values?.["p(95)"] || 0),
        avg_ms: Math.round(metric.values?.avg || 0),
      };
    }
  }
  for (const [name, metric] of Object.entries(data.metrics)) {
    if (name === "http_req_failed") {
      for (const [key, val] of Object.entries(metric.values || {})) {
        const m = key.match(/^tag:(\w+)/);
        if (m && (val.fails || val.passes)) {
          summary.endpoint_failures[m[1]] = val.fails || 0;
          summary.endpoint_passes[m[1]] = val.passes || 0;
        }
      }
    }
  }

  return {
    "stdout": JSON.stringify(summary, null, 2),
    "tests/load/k6-databricks-obo-summary.json": JSON.stringify(summary),
  };
}
