/**
 * `guardedTest` — Playwright test.extend wrapper that installs global page
 * listeners for three classes of hidden failures and fails the test at
 * teardown if any are caught.
 *
 *   * page.on('pageerror')   — uncaught JS exceptions in the browser
 *   * page.on('console')     — console.error entries (filtered through
 *                              fixtures/console-utils.ts::isBenignConsoleError
 *                              so known-benign noise stays quiet)
 *   * page.on('response')    — server responses with HTTP 5xx
 *
 * Landed in PR 2 unused. Tier-1 specs swap their `import { test } from
 * '@playwright/test'` to `from '../fixtures/guardedTest'` in PR 7a-7d.
 *
 * Design note — retry-proof artifact logging
 * --------------------------------------------
 * Playwright is configured with `retries: 2` in CI. If the guard threw only
 * via `throw new Error(...)` in teardown, a flaky retry could pass without
 * the original caught error being visible in the job outcome. To prevent
 * that, each caught error is additionally appended to a JSONL artifact at
 * `${testInfo.project.outputDir}/../guard-failures/guard-failures.jsonl`.
 * A post-run CI step (added in PR 8's strict workflow) fails the job when
 * that file is non-empty, regardless of per-test retry success.
 *
 * Design note — annotation timing
 * --------------------------------------------
 * `testInfo.annotations` is populated as the test body runs, not at fixture
 * setup. The opt-out check MUST happen after `await use(g)`, not before.
 * Tests that legitimately exercise transient 5xx (e.g. failure-path specs
 * that assert on 500 responses) annotate themselves as:
 *
 *     test.info().annotations.push({ type: 'allow-transient-5xx',
 *                                    description: 'why' });
 *
 * The guard reads that annotation during teardown and skips the 5xx check.
 */

import { test as base, expect } from '@playwright/test';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { randomBytes } from 'node:crypto';

import { isBenignConsoleError } from './console-utils';
import {
  createRegistry as createCreatedResourcesRegistry,
  type CreatedResourcesRegistry,
} from './createdResources';

type ServerError = { url: string; status: number };

export type GuardBuffer = {
  pageErrors: Error[];
  consoleErrors: string[];
  serverErrors: ServerError[];
};

export interface EvaluateGuardOptions {
  allowTransient5xx: boolean;
}

// ------------------------- correlation-ID guard (Phase 226 B4) -------------
//
// Platform guarantee: every **backend API** response echoes back the
// request's `X-Correlation-ID` so incident forensics can join request →
// response → audit → log. The guard generates a fresh ID per test (set
// via setExtraHTTPHeaders so every outbound request carries it), observes
// every API response, and flags mismatches + missing echoes. Runs on
// every spec using `guardedTest`. Env-var kill switch
// `E2E_DISABLE_CORRELATION_GUARD=true` disables the whole guard without
// reverting the fixture.
//
// Scope: the listener is filtered to API responses (paths starting with
// `/api/v1/`). Static assets (Vite-built `/static/*` JS/CSS), third-party
// CDN (Google Fonts), SPA HTML route shells (`/login`, `/register`), and
// the unprefixed `/health/` liveness probe physically cannot echo a custom
// request header — checking them would dominate the buffer with false
// positives without surfacing real backend bugs. The guard's invariant is
// about the Django API, so the URL filter narrows to that surface.

const CORRELATION_HEADER = 'x-correlation-id';

/**
 * True when `url` is a backend API response that the correlation-id
 * platform guarantee applies to. Match by pathname so the helper works
 * across the local proxied path (`https://localhost:5173/api/v1/...`),
 * the staging direct path (`https://api.stagingmeshant-internal.example.com/api/v1/...`),
 * and the staging frontend-proxied path (`https://stagingmeshant-internal.example.com/api/v1/...`).
 * Static asset paths (`/static/...`), HTML routes (`/login`, `/register`),
 * and third-party origins (Google Fonts) all return false.
 */
export function isApiUrlForCorrelationGuard(url: string): boolean {
  try {
    const parsed = new URL(url);
    return parsed.pathname.startsWith('/api/v1/');
  } catch {
    return false;
  }
}

export type CorrelationMismatch = { url: string; sent: string; echoed: string };
export type CorrelationMissing = { url: string; sent: string };

export type CorrelationBuffer = {
  mismatches: CorrelationMismatch[];
  missing: CorrelationMissing[];
};

export interface CorrelationEvaluateOptions {
  /** If true, suppress "response did not echo the header" problems. Mismatch
   * problems are NOT suppressed — an incorrect echo is a different bug
   * class than no echo at all. */
  allowMissing: boolean;
  /** If true (kill switch), suppress every problem. */
  guardDisabled: boolean;
}

/** Pure problem-generator. Branches covered by `_guards.spec.ts`. */
export function evaluateCorrelationProblems(
  buffer: CorrelationBuffer,
  options: CorrelationEvaluateOptions,
): string[] {
  if (options.guardDisabled) return [];
  const out: string[] = [];
  for (const m of buffer.mismatches) {
    out.push(
      `correlation-id mismatch on ${m.url}: sent=${m.sent}, echoed=${m.echoed}`,
    );
  }
  if (!options.allowMissing) {
    for (const m of buffer.missing) {
      out.push(`correlation-id missing on response from ${m.url}: sent=${m.sent}`);
    }
  }
  return out;
}

/** Env-var kill switch check. Accepts "true" or "1" (case-insensitive). */
export function isCorrelationGuardDisabled(
  env: Record<string, string | undefined>,
): boolean {
  const raw = env['E2E_DISABLE_CORRELATION_GUARD'];
  if (!raw) return false;
  const normalized = raw.trim().toLowerCase();
  return normalized === 'true' || normalized === '1';
}

/** Generate a test-scoped correlation ID. Prefix + 16 random hex chars. */
export function generateCorrelationId(): string {
  return `e2e-${randomBytes(8).toString('hex')}`;
}

/** Header-name-insensitive lookup. Playwright lowercases header keys but
 * callers sometimes pass objects with original-case keys; normalize both. */
function findHeaderCaseInsensitive(
  headers: Record<string, string> | undefined,
  name: string,
): string | undefined {
  if (!headers) return undefined;
  const target = name.toLowerCase();
  for (const [k, v] of Object.entries(headers)) {
    if (k.toLowerCase() === target) return v;
  }
  return undefined;
}

/**
 * Pure function that maps a populated GuardBuffer + options into a list of
 * human-readable problem strings. Factored out of the fixture body so the
 * self-test suite can verify the branch logic without spinning up a browser.
 */
export function evaluateGuard(
  buffer: GuardBuffer,
  options: EvaluateGuardOptions,
): string[] {
  return [
    ...buffer.pageErrors.map((e) => `pageerror: ${e.message}`),
    ...buffer.consoleErrors.map((s) => `console.error: ${s}`),
    ...(options.allowTransient5xx
      ? []
      : buffer.serverErrors.map((s) => `HTTP ${s.status}: ${s.url}`)),
  ];
}

const GUARD_FAILURES_DIR_NAME = 'guard-failures';
const GUARD_FAILURES_FILE_NAME = 'guard-failures.jsonl';

function appendFailureArtifact(params: {
  outputDir: string;
  testFile: string;
  testTitle: string;
  testRetry: number;
  problems: string[];
}): void {
  // Writing sibling-of-project-outputDir so the CI post-step can find it with
  // a single glob regardless of which project/browser produced the failure.
  const dir = path.resolve(params.outputDir, '..', GUARD_FAILURES_DIR_NAME);
  try {
    fs.mkdirSync(dir, { recursive: true });
    const record = {
      test: params.testTitle,
      file: params.testFile,
      retry: params.testRetry,
      problems: params.problems,
      when: new Date().toISOString(),
    };
    fs.appendFileSync(
      path.join(dir, GUARD_FAILURES_FILE_NAME),
      JSON.stringify(record) + '\n',
      { encoding: 'utf8' },
    );
  } catch (err) {
    // We intentionally swallow the write failure — if we can't persist the
    // artifact, throwing in teardown is still the primary signal. Don't want
    // the test harness itself to break because the runner filesystem is
    // read-only, etc. (`no-console` rule not currently enabled in the e2e
    // config; the prior eslint-disable comment was flagged as unused.)
    console.warn(
      `[guardedTest] Could not persist failure artifact: ${(err as Error).message}`,
    );
  }
}

// ----------------------- security-header guard (Phase 226 G16) -------------
//
// Platform guarantee: every HTML/document response from the frontend tier
// MUST carry a complete set of security headers (CSP, X-Frame-Options,
// X-Content-Type-Options, Referrer-Policy; HSTS additionally on HTTPS).
// A regression in nginx config or a CDN that strips headers becomes
// invisible to functional specs but is the most common production
// security hole.
//
// Evidence-based enforcement
// --------------------------
// The guard observes every HTML/document response, but only fails the
// test when there is *evidence* the env emits security headers in the
// first place — i.e. at least one observed response had at least one
// of the required headers. If NO observed response carried any of the
// required headers, the env is "headers not enforced here" (Vite dev,
// CI without nginx) and the guard skips silently with an annotation.
//
// This auto-detect avoids the obvious anti-pattern where a strict guard
// breaks every test on Vite dev mode. nginx + staging emit ≥ 1 header
// on the first / probe → guard activates. Vite dev emits zero → guard
// stays passive.
//
// Scope: HTML/SPA-shell responses only — JSON API responses do not need
// CSP (and don't get it from nginx). The match heuristic looks for a
// document-like content-type ("text/html") OR for the explicit absence
// of Content-Type combined with a 2xx response on a route path
// (some test stacks return HTML without Content-Type).
//
// Env-var kill switch: `E2E_DISABLE_SECURITY_HEADER_GUARD=true` — disables
// the guard entirely (auto-detect + enforcement). Per-test opt-out:
// annotation `allow-missing-security-headers`.

const REQUIRED_SECURITY_HEADERS = [
  'content-security-policy',
  'x-content-type-options',
  'x-frame-options',
  'referrer-policy',
] as const;

/** Headers that, if present on any HTML response, prove the env enforces
 * security headers and the guard should activate. CSP alone is a strong
 * enough signal — every nginx config we ship emits all four together
 * but a partially-rolled-out config might emit only some, and we want
 * to catch that mid-rollout state. */
const SECURITY_HEADER_PRESENCE_SIGNALS = [
  'content-security-policy',
  'content-security-policy-report-only',
  'x-frame-options',
  'strict-transport-security',
] as const;

export type SecurityHeaderProblem = {
  url: string;
  reason:
    | 'missing-header'
    | 'csp-report-only'
    | 'csp-allows-unsafe-eval'
    | 'csp-allows-unsafe-inline-script'
    | 'x-content-type-options-not-nosniff'
    | 'x-frame-options-not-deny-or-sameorigin';
  detail: string;
};

export type SecurityHeaderBuffer = {
  problems: SecurityHeaderProblem[];
  /** True when at least one observed HTML response carried at least one
   * security header. Drives the activate-or-skip decision at teardown. */
  evidenceObserved: boolean;
  /** Number of HTML responses observed (used for the "no responses at
   * all → no decision" branch). */
  htmlResponsesObserved: number;
};

/** True when `url` and the response Content-Type indicate a document/SPA
 * shell that the security-header guard applies to. Static assets, JSON
 * APIs, and third-party CDN responses all return false. */
export function isDocumentResponseForSecurityGuard(
  url: string,
  contentType: string | undefined,
): boolean {
  // Content-Type wins when present.
  if (contentType !== undefined) {
    return /text\/html/i.test(contentType);
  }
  // No Content-Type: only treat as document when the URL is plausibly a
  // route/shell (no extension after the last slash). Static-asset URLs
  // typically end in .js/.css/.png/etc — those are NOT in scope.
  try {
    const parsed = new URL(url);
    const path = parsed.pathname;
    const lastSeg = path.split('/').pop() ?? '';
    if (lastSeg === '' || !lastSeg.includes('.')) return true;
    return false;
  } catch {
    return false;
  }
}

/**
 * Returns true if `headers` contains at least one of the
 * `SECURITY_HEADER_PRESENCE_SIGNALS`. Pure helper — used by the auto-
 * fixture to flip `evidenceObserved` to true.
 */
export function hasSecurityHeaderEvidence(headers: Record<string, string>): boolean {
  const lower: Record<string, string> = {};
  for (const [k, v] of Object.entries(headers)) lower[k.toLowerCase()] = v;
  for (const signal of SECURITY_HEADER_PRESENCE_SIGNALS) {
    if (lower[signal] !== undefined && lower[signal] !== '') return true;
  }
  return false;
}

/** Pure security-header validator. Walks the headers map and produces a
 * list of problems (or an empty list if the response is fully
 * compliant). Branches are unit-testable without a browser.
 *
 * NB: this is an "absolute" validator — it does NOT consult evidence.
 * The auto-fixture combines it with the `evidenceObserved` flag so a
 * Vite dev server (no headers anywhere) does not fail every test. */
export function evaluateSecurityHeaders(
  url: string,
  headers: Record<string, string>,
  isHttps: boolean,
): SecurityHeaderProblem[] {
  const problems: SecurityHeaderProblem[] = [];
  const lower = (h: string) => h.toLowerCase();
  const hdr: Record<string, string> = {};
  for (const [k, v] of Object.entries(headers)) hdr[lower(k)] = v;

  // Explicit Report-Only check first — present-with-wrong-mode is a
  // distinct failure class from missing.
  if (hdr['content-security-policy-report-only'] && !hdr['content-security-policy']) {
    problems.push({
      url,
      reason: 'csp-report-only',
      detail: 'Content-Security-Policy-Report-Only present without enforce header',
    });
  }

  for (const required of REQUIRED_SECURITY_HEADERS) {
    if (hdr[required] === undefined || hdr[required] === '') {
      problems.push({
        url,
        reason: 'missing-header',
        detail: `Required header "${required}" missing on ${url}`,
      });
    }
  }

  if (isHttps && (hdr['strict-transport-security'] === undefined || hdr['strict-transport-security'] === '')) {
    problems.push({
      url,
      reason: 'missing-header',
      detail: `Required header "strict-transport-security" missing on HTTPS response ${url}`,
    });
  }

  const csp = hdr['content-security-policy'];
  if (csp) {
    const scriptSrcMatch = csp.match(/script-src\s+([^;]+)/i);
    const scriptSrcValue = scriptSrcMatch?.[1] ?? '';
    if (/'unsafe-eval'/.test(scriptSrcValue)) {
      problems.push({
        url,
        reason: 'csp-allows-unsafe-eval',
        detail: `script-src contains 'unsafe-eval' on ${url}`,
      });
    }
    if (/'unsafe-inline'/.test(scriptSrcValue)) {
      problems.push({
        url,
        reason: 'csp-allows-unsafe-inline-script',
        detail: `script-src contains 'unsafe-inline' on ${url}`,
      });
    }
  }

  const xcto = hdr['x-content-type-options'];
  if (xcto !== undefined && xcto.toLowerCase() !== 'nosniff') {
    problems.push({
      url,
      reason: 'x-content-type-options-not-nosniff',
      detail: `X-Content-Type-Options is "${xcto}" (must be nosniff)`,
    });
  }

  const xfo = hdr['x-frame-options'];
  if (xfo !== undefined && !/^(DENY|SAMEORIGIN)$/i.test(xfo)) {
    problems.push({
      url,
      reason: 'x-frame-options-not-deny-or-sameorigin',
      detail: `X-Frame-Options is "${xfo}" (must be DENY or SAMEORIGIN)`,
    });
  }

  return problems;
}

/** Env-var kill switch check for the security-header guard. */
export function isSecurityHeaderGuardDisabled(
  env: Record<string, string | undefined>,
): boolean {
  const raw = env['E2E_DISABLE_SECURITY_HEADER_GUARD'];
  if (!raw) return false;
  const normalized = raw.trim().toLowerCase();
  return normalized === 'true' || normalized === '1';
}

export const test = base.extend<{
  guard: GuardBuffer;
  /** Auto-fixture: activates on every spec that imports `test` from this
   * file, even if the spec does not destructure `{ correlation }`. */
  correlation: CorrelationBuffer;
  /** Auto-fixture: every HTML response is checked for the platform-required
   * security headers. Phase 226 G16. */
  securityHeaders: SecurityHeaderBuffer;
  /**
   * Phase 226 E2 — auto-fixture per-test registry of resources created
   * by UI flows (or any code path that doesn't already use the
   * `cleanup` fixture from `test-data-cleanup.ts`). Specs call
   * `createdResources.track({ type, id, owner })` immediately after a
   * UI form submit returns the new id (e.g. parsed out of a 302
   * Location header or read from the URL after the redirect). Auto-
   * teardown after the test body completes — failures surface as
   * test annotations so they're visible in the HTML report without
   * masking the original test failure.
   */
  createdResources: CreatedResourcesRegistry;
}>({
  guard: async ({ page }, use, testInfo) => {
    const buffer: GuardBuffer = {
      pageErrors: [],
      consoleErrors: [],
      serverErrors: [],
    };

    page.on('pageerror', (err) => {
      buffer.pageErrors.push(err);
    });

    page.on('console', (msg) => {
      if (msg.type() !== 'error') return;
      const text = msg.text();
      if (isBenignConsoleError(text)) return;
      buffer.consoleErrors.push(text);
    });

    page.on('response', (res) => {
      const status = res.status();
      if (status >= 500) {
        buffer.serverErrors.push({ url: res.url(), status });
      }
    });

    // Hand control to the test body. Annotations are populated here, not
    // before — so the opt-out check MUST happen after this await.
    await use(buffer);

    const allowTransient5xx = testInfo.annotations.some(
      (a) => a.type === 'allow-transient-5xx',
    );

    const problems = evaluateGuard(buffer, { allowTransient5xx });
    if (problems.length === 0) return;

    appendFailureArtifact({
      outputDir: testInfo.project.outputDir,
      testFile: testInfo.file,
      testTitle: testInfo.titlePath.join(' > '),
      testRetry: testInfo.retry,
      problems,
    });

    throw new Error(
      `guardedTest caught ${problems.length} hidden failure${
        problems.length === 1 ? '' : 's'
      }:\n${problems.join('\n')}`,
    );
  },

  correlation: [async ({ page }, use, testInfo) => {
    const buffer: CorrelationBuffer = { mismatches: [], missing: [] };
    const disabled = isCorrelationGuardDisabled(process.env);

    // Passive-observe design. We do NOT install `page.route` interception —
    // that would break specs that register their own route handlers. Instead,
    // we seed an extra HTTP header once so every outbound request the browser
    // makes carries a known correlation-ID; then we observe responses and
    // verify the echo. Specs that need their own correlation-ID per-request
    // can override the header via `page.setExtraHTTPHeaders` before making
    // the call and opt out of the mismatch check via annotation.
    const testScopedId = generateCorrelationId();

    if (!disabled) {
      await page.setExtraHTTPHeaders({ [CORRELATION_HEADER]: testScopedId });

      page.on('response', (res) => {
        // Scope: only backend API responses. See isApiUrlForCorrelationGuard
        // — static assets and third-party CDN responses cannot echo a custom
        // request header and would otherwise dominate the buffer with false
        // positives.
        if (!isApiUrlForCorrelationGuard(res.url())) return;
        const req = res.request();
        const reqHeaders = req.headers();
        const sent = findHeaderCaseInsensitive(reqHeaders, CORRELATION_HEADER);
        if (!sent) return; // request didn't carry the header (e.g. non-fetch nav); skip
        const echoed = findHeaderCaseInsensitive(res.headers(), CORRELATION_HEADER);
        if (echoed === undefined) {
          buffer.missing.push({ url: res.url(), sent });
        } else if (echoed !== sent) {
          buffer.mismatches.push({ url: res.url(), sent, echoed });
        }
      });

      // Expose the test-scoped sent ID on test.info() so verifyAuditEvent (B3)
      // can cross-check the audit row's correlation_id.
      testInfo.annotations.push({
        type: 'correlation-id-sent',
        description: testScopedId,
      });
    }

    await use(buffer);

    const allowMissing = testInfo.annotations.some(
      (a) => a.type === 'allow-missing-correlation-id',
    );
    const problems = evaluateCorrelationProblems(buffer, {
      allowMissing,
      guardDisabled: disabled,
    });
    if (problems.length === 0) return;

    appendFailureArtifact({
      outputDir: testInfo.project.outputDir,
      testFile: testInfo.file,
      testTitle: testInfo.titlePath.join(' > '),
      testRetry: testInfo.retry,
      problems,
    });

    throw new Error(
      `guardedTest caught ${problems.length} correlation-id problem${
        problems.length === 1 ? '' : 's'
      }:\n${problems.join('\n')}`,
    );
  }, { auto: true }],

  // --------- 226.G16 — security-header auto-fixture -----------------------
  //
  // Auto-runs on every spec that imports `test` from guardedTest. Observes
  // every HTML/document response and aggregates any that is missing one
  // of the required security headers (CSP enforce, X-Frame-Options,
  // X-Content-Type-Options=nosniff, Referrer-Policy; HSTS on HTTPS).
  //
  // Evidence-based activation: the guard only fails the test if at least
  // one observed HTML response carried a security-header presence signal
  // (CSP enforce / Report-Only / X-Frame-Options / HSTS). When NO observed
  // response carried any signal the env doesn't enforce headers (Vite dev,
  // some CI configurations) and the guard skips silently with an
  // annotation. nginx + staging always emit ≥ 1 signal on the first
  // response → guard activates and fails on missing headers; a
  // partially-rolled-out config that emits some signals but misses
  // others is caught.
  //
  // Per-test opt-out:
  //   1. env var `E2E_DISABLE_SECURITY_HEADER_GUARD=true` (skips entirely)
  //   2. annotation `allow-missing-security-headers` on the test
  //
  // The guard ONLY observes — it does not assert during the test body.
  // Problems are aggregated and thrown at teardown so they don't mask the
  // primary test failure (if the test failed for a different reason).
  securityHeaders: [async ({ page }, use, testInfo) => {
    const buffer: SecurityHeaderBuffer = {
      problems: [],
      evidenceObserved: false,
      htmlResponsesObserved: 0,
    };
    const disabled = isSecurityHeaderGuardDisabled(process.env);

    if (!disabled) {
      page.on('response', (res) => {
        const url = res.url();
        const headers = res.headers();
        const contentType = headers['content-type'];
        if (!isDocumentResponseForSecurityGuard(url, contentType)) return;
        if (res.status() < 200 || res.status() >= 400) return; // skip 3xx redirects + 4xx error pages
        buffer.htmlResponsesObserved += 1;
        if (hasSecurityHeaderEvidence(headers)) {
          buffer.evidenceObserved = true;
        }
        const isHttps = url.startsWith('https://');
        const problems = evaluateSecurityHeaders(url, headers, isHttps);
        if (problems.length > 0) {
          buffer.problems.push(...problems);
        }
      });
    }

    await use(buffer);

    const allowMissing = testInfo.annotations.some(
      (a) => a.type === 'allow-missing-security-headers',
    );
    if (disabled || allowMissing) return;
    if (buffer.problems.length === 0) return;
    // Auto-detect: if no response carried evidence the env emits security
    // headers, the env doesn't enforce them (Vite dev). Annotate and skip
    // — failing here would break every spec that runs against Vite.
    if (!buffer.evidenceObserved) {
      testInfo.annotations.push({
        type: 'security-header-guard-skipped',
        description:
          `security-header guard skipped: no evidence the test environment ` +
          `emits security headers (observed ${buffer.htmlResponsesObserved} ` +
          `HTML response${buffer.htmlResponsesObserved === 1 ? '' : 's'} ` +
          `without a CSP/X-Frame-Options/HSTS signal). Set ` +
          `E2E_DISABLE_SECURITY_HEADER_GUARD=true to silence this annotation.`,
      });
      return;
    }

    // Deduplicate (url, reason) pairs so a noisy SPA shell doesn't dominate
    // the artifact with the same problem 50 times.
    const seen = new Set<string>();
    const deduped: SecurityHeaderProblem[] = [];
    for (const p of buffer.problems) {
      const key = `${p.url}::${p.reason}`;
      if (seen.has(key)) continue;
      seen.add(key);
      deduped.push(p);
    }

    const problems = deduped.map((p) => `security-header[${p.reason}]: ${p.detail}`);
    appendFailureArtifact({
      outputDir: testInfo.project.outputDir,
      testFile: testInfo.file,
      testTitle: testInfo.titlePath.join(' > '),
      testRetry: testInfo.retry,
      problems,
    });

    throw new Error(
      `guardedTest caught ${problems.length} security-header problem${
        problems.length === 1 ? '' : 's'
      }:\n${problems.join('\n')}`,
    );
  }, { auto: true }],

  // --------- 226.E2 — createdResources auto-fixture ----------------------
  //
  // Auto-flushes after the test body completes (success OR failure). A
  // teardown failure surfaces as a `cleanup-failed` annotation, NEVER as
  // a thrown error from this fixture — throwing here would mask the
  // primary failure (if the test failed) or convert a leak into a green-
  // to-red flip (if the test passed but a single resource 401'd on
  // re-login).
  createdResources: [async ({}, use, testInfo) => {
    const registry = createCreatedResourcesRegistry();
    await use(registry);
    let result;
    try {
      result = await registry.flush();
    } catch (err) {
      testInfo.annotations.push({
        type: 'cleanup-failed',
        description: `createdResources auto-flush threw: ${(err as Error).message}`,
      });
      return;
    }
    if (result.failures.length > 0) {
      testInfo.annotations.push({
        type: 'cleanup-failed',
        description:
          `createdResources teardown encountered ${result.failures.length} failure(s):\n` +
          result.failures.join('\n'),
      });
    }
  }, { auto: true }],
});

export { expect };
