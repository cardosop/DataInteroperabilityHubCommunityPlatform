#!/usr/bin/env node
// Phase 226 OQ2 — staging SPARQL reachability + determinism check.
//
// Asserts that the deployed Fuseki triplestore is reachable through the
// platform API gateway and answers a deterministic query before semantic
// E2E specs (`verifySemanticIri` step 4, `semantic-sparql-ui.spec.ts`)
// run against the same target. Without this gate, a Fuseki StatefulSet
// restart loop or a misconfigured semantic-service env produces 503s
// that surface as flaky individual specs rather than as a clean
// infrastructure signal.
//
// Pure, dependency-free. Uses node's built-in fetch (≥ Node 18).
//
// Usage:
//   node scripts/check_sparql_health.cjs --base-url=https://api.stagingmeshant-internal.example.com
//
// IMPORTANT: the canonical staging API host is `api.stagingmeshant-internal.example.com`
// (with the `.hub.` subdomain). Apex `meshant-internal.example.com` does NOT resolve.
//
// Exit codes:
//   0  — SPARQL endpoint reachable + returns a well-formed JSON response.
//   1  — endpoint unreachable, non-2xx, or response shape unexpected.
//   2  — bad CLI usage.
//
// Environment variables honoured:
//   E2E_TEST_SECRET   when set, sent as `X-E2E-Token` so the check works
//                     against environments with hardened admin endpoints.
//
// Determinism contract documented in docs/runbooks/sparql-determinism.md
// (added in the same PR). Summary: each tenant has its own named graph;
// per-test pollution within a tenant is the only remaining threat and
// is mitigated by the disposable-tenant fixture (OQ4).

'use strict';

// Pure: returns either { ok: true, args } or { ok: false, exitCode, message }.
// Keeps `require()`-time side-effect-free so unit tests can import the script
// without triggering CLI exits. The CLI wrapper at the bottom of the file
// turns the failure shape into a process.stderr.write + process.exit pair.
function parseArgs(argv) {
  const args = { baseUrl: '', timeoutMs: 15_000 };
  for (const a of argv) {
    if (a.startsWith('--base-url=')) args.baseUrl = a.slice(11).replace(/\/+$/, '');
    else if (a.startsWith('--timeout-ms=')) {
      const n = Number.parseInt(a.slice(13), 10);
      if (!Number.isFinite(n) || n <= 0) {
        return { ok: false, exitCode: 2, message: 'check_sparql_health: --timeout-ms must be a positive integer' };
      }
      args.timeoutMs = n;
    } else {
      return { ok: false, exitCode: 2, message: `check_sparql_health: unknown argument ${a}` };
    }
  }
  if (!args.baseUrl) {
    return { ok: false, exitCode: 2, message: 'check_sparql_health: --base-url=URL is required' };
  }
  return { ok: true, args };
}

/** Pure helper — build the SPARQL probe query. ASK is the cheapest
 * possible query that still proves the engine parsed + dispatched.
 * Exposed for unit testability. */
function buildProbeQuery() {
  return 'ASK { ?s ?p ?o }';
}

/** Pure helper — validate the shape of a SPARQL ASK response.
 * SPARQL 1.1 spec defines the JSON binding format
 * (https://www.w3.org/TR/sparql11-results-json/). Exposed for tests. */
function validateAskResponse(body) {
  if (!body || typeof body !== 'object') {
    return { ok: false, reason: 'response is not an object' };
  }
  if (typeof body.boolean !== 'boolean') {
    return { ok: false, reason: 'response missing `boolean` field (not a SPARQL ASK result)' };
  }
  return { ok: true };
}

async function main() {
  const parsed = parseArgs(process.argv.slice(2));
  if (!parsed.ok) {
    process.stderr.write(`${parsed.message}\n`);
    return parsed.exitCode;
  }
  const args = parsed.args;
  const url = `${args.baseUrl}/api/v1/semantic/sparql`;
  const headers = {
    'Accept': 'application/sparql-results+json',
    'Content-Type': 'application/sparql-query',
  };
  const secret = process.env.E2E_TEST_SECRET;
  if (secret) headers['X-E2E-Token'] = secret;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), args.timeoutMs);

  try {
    const res = await fetch(url, {
      method: 'POST',
      headers,
      body: buildProbeQuery(),
      signal: controller.signal,
    });
    if (!res.ok) {
      process.stderr.write(
        `check_sparql_health: ${url} returned ${res.status}. Body preview: ${
          (await res.text().catch(() => '')).slice(0, 300)
        }\n`,
      );
      return 1;
    }
    let body;
    try {
      body = await res.json();
    } catch (err) {
      process.stderr.write(
        `check_sparql_health: ${url} returned 2xx but non-JSON body: ${err.message}\n`,
      );
      return 1;
    }
    const v = validateAskResponse(body);
    if (!v.ok) {
      process.stderr.write(`check_sparql_health: invalid response shape — ${v.reason}\n`);
      return 1;
    }
    process.stdout.write(
      `check_sparql_health: ${url} OK (boolean=${body.boolean}). Fuseki reachable.\n`,
    );
    return 0;
  } catch (err) {
    process.stderr.write(
      `check_sparql_health: request to ${url} failed: ${err.message}\n`,
    );
    return 1;
  } finally {
    clearTimeout(timer);
  }
}

module.exports = { buildProbeQuery, validateAskResponse, parseArgs };

if (require.main === module) {
  main().then((code) => process.exit(code));
}
