/**
 * `verifySemanticIri` — five-step dual-channel helper for the semantic-layer
 * guarantee that every Linked Data resource is dereferenceable as JSON-LD
 * and visible in SPARQL.
 *
 * Steps:
 *   1. 303 dereference: GET `/api/v1/semantic/id/<type>/<id>` with
 *      `Accept: application/rdf+xml` returns 303 + `Location` header matching
 *      the canonical IRI (`{SEMANTIC_BASE_IRI}/id/<type>/<id>`).
 *   2. JSON-LD payload: follow the redirect (or GET again with
 *      `Accept: application/ld+json`) and assert `@context`, `@id`,
 *      optionally `@type`.
 *   3. JSON-LD context doc: `GET /api/v1/semantic/context.jsonld` resolves
 *      (skipped by default; opt-in via `expectContextDoc`).
 *   4. SPARQL triple: `SELECT ?p ?o WHERE { <iri> ?p ?o }` returns at least
 *      one binding (the new resource is visible to the triple store).
 *   5. Negative: `/api/v1/semantic/id/<type>/<bogus-uuid>` returns 404, so
 *      we know the dereferencer isn't a stub that returns 303 for anything.
 *
 * Pure logic split out for `_guards.spec.ts`:
 *   - canonicalIriFor(base, type, id) — IRI construction.
 *   - classifyDereferenceResponse({ status, locationHeader }, expectedIri) —
 *     branch that picks between redirect-match / redirect-mismatch / direct /
 *     not-found / server-error.
 *   - validateJsonLdPayload(body, { expectedIri, expectedType? }) — shape
 *     check returning null or a mismatch message.
 *   - sparqlResultHasExpectedTriple(bindings, options) — triple presence.
 *
 * SPARQL is a hard dependency of staging infra; if the endpoint is flaky
 * (Open Question §7) the SPARQL step degrades to `test.skip(cond, reason)`
 * via the `options.skipSparqlOn` callback. W16: in CI a degraded SPARQL
 * endpoint announces itself via `environmentSkipGuard` instead of skipping.
 *
 * Phase 226 PR B5 — see
 * /home/ph/.claude/plans/now-pls-create-a-binary-cloud.md §Track B.
 */

import type { Page, TestInfo } from '@playwright/test';
import { environmentSkipGuard } from './envPolicy.cjs';

export type SemanticResourceType =
  | 'asset'
  | 'dataset'
  | 'contract'
  | 'semantic_resource'
  // Allow free-form for future resource types without TS friction.
  | (string & {});

export interface VerifySemanticIriOptions {
  /** If provided, the SPARQL step asserts an `@type` triple equal to this
   * value. Also passed to the JSON-LD payload check. */
  expectedType?: string;
  /** If true, additionally fetch `/api/v1/semantic/context.jsonld` and
   * assert it resolves. Default false — the context doc is a stable, shared
   * resource that doesn't need per-spec verification. */
  expectContextDoc?: boolean;
  /** Override the semantic base IRI. Default: read from `process.env.SEMANTIC_BASE_IRI`
   * (must match the backend's `SEMANTIC_BASE_IRI` setting). Falls back to
   * `https://hub.example.com` to match backend's own fallback. */
  semanticBaseIri?: string;
  /** Override the API base path for dereferencing. Default
   * `/api/v1/semantic/id`. */
  derefEndpointBase?: string;
  /** Override the SPARQL endpoint. Default `/api/v1/semantic/sparql`. */
  sparqlEndpoint?: string;
  /** Override the JSON-LD context endpoint. Default
   * `/api/v1/semantic/context.jsonld`. */
  contextEndpoint?: string;
  /** Override the auth extraction. Rarely needed. */
  authHeaderOverride?: Record<string, string>;
  /** Opt-in hook to degrade the SPARQL step to a test.skip when the endpoint
   * is unavailable on the current env. If returns true, the step is skipped
   * (not failed). */
  skipSparqlOn?: (res: { status: number; bodyPreview: string }) => boolean;
  /** When false, the SPARQL triple-visibility assertion is skipped entirely
   * (dereference + JSON-LD steps still run). Use for resource types the
   * semantic index does NOT ingest — contracts are never indexed (the
   * product-creation workflow has no semantic-mapping task for them), so
   * the triple check is a false guarantee there. Default true. */
  expectSparqlTriple?: boolean;
  /** Test info used to emit degradation skips. When present, SPARQL
   * unavailability becomes a skip rather than a failure. */
  testInfo?: TestInfo;
}

// ---------------------------------------------------------------- pure helpers

/** Build the canonical IRI for a resource. Strips trailing slash from base. */
export function canonicalIriFor(
  base: string,
  resourceType: string,
  resourceId: string,
): string {
  if (!resourceType) throw new Error('canonicalIriFor: resourceType is required');
  if (!resourceId) throw new Error('canonicalIriFor: resourceId is required');
  const cleanBase = base.replace(/\/+$/, '');
  return `${cleanBase}/id/${resourceType}/${resourceId}`;
}

export type DereferenceClassification =
  | 'redirect-match'
  | 'redirect-mismatch'
  | 'redirect-missing-location'
  | 'direct-payload'
  | 'not-found'
  | 'server-error'
  | 'unexpected';

/** Classify a GET-with-RDF-accept response.
 *
 * When `expectedIri` is null (no base pinned by the caller or env), the
 * redirect is validated by PATH SUFFIX instead: the Location must end with
 * `expectedIriSuffix` (the canonical `/id/<type>/<id>` resource path). The
 * backend derives the IRI origin from HUB_DOMAIN (test.hub.example.com on
 * the test stack), which the E2E runner cannot hardcode without drift. */
export function classifyDereferenceResponse(
  res: { status: number; locationHeader: string | null },
  expectedIri: string | null,
  expectedIriSuffix?: string,
): DereferenceClassification {
  if (res.status === 303) {
    if (res.locationHeader === null || res.locationHeader === '') {
      return 'redirect-missing-location';
    }
    const matches = expectedIri !== null
      ? res.locationHeader === expectedIri
      : expectedIriSuffix !== undefined && res.locationHeader.endsWith(expectedIriSuffix);
    return matches ? 'redirect-match' : 'redirect-mismatch';
  }
  if (res.status >= 200 && res.status < 300) return 'direct-payload';
  if (res.status === 404) return 'not-found';
  if (res.status >= 500) return 'server-error';
  return 'unexpected';
}

/** Type guard — is the value an array? */
function isArray(x: unknown): x is unknown[] {
  return Array.isArray(x);
}

/** Check JSON-LD payload shape against expectations. Returns null or a mismatch
 * message.
 *
 * Exactly one of `expectedIri` (exact @id match — use when a base is pinned)
 * or `expectedIriSuffix` (canonical `/id/<type>/<id>` path match — use when
 * the IRI origin is env-derived, see classifyDereferenceResponse) must be
 * provided. */
export function validateJsonLdPayload(
  body: unknown,
  expected: { expectedIri?: string; expectedIriSuffix?: string; expectedType?: string },
): string | null {
  if (!body || typeof body !== 'object') {
    return `JSON-LD payload is not an object: ${JSON.stringify(body)}`;
  }
  const obj = body as Record<string, unknown>;

  if (!('@context' in obj)) {
    return `JSON-LD payload missing @context. Keys: ${JSON.stringify(Object.keys(obj))}`;
  }

  if (!('@id' in obj)) {
    return `JSON-LD payload missing @id. Keys: ${JSON.stringify(Object.keys(obj))}`;
  }
  const actualId = typeof obj['@id'] === 'string' ? obj['@id'] : JSON.stringify(obj['@id']);
  const idMismatch =
    expected.expectedIri !== undefined
      ? actualId !== expected.expectedIri
      : expected.expectedIriSuffix !== undefined
        ? !actualId.endsWith(expected.expectedIriSuffix)
        : true;
  if (idMismatch) {
    return (
      `JSON-LD @id mismatch: expected=${expected.expectedIri ?? `*${expected.expectedIriSuffix}`}, ` +
      `actual=${JSON.stringify(obj['@id'])}`
    );
  }

  if (expected.expectedType !== undefined) {
    const rawType = obj['@type'];
    const types = isArray(rawType) ? rawType : [rawType];
    if (!types.includes(expected.expectedType)) {
      return (
        `JSON-LD @type mismatch: expected=${expected.expectedType}, ` +
        `actual=${JSON.stringify(rawType)}`
      );
    }
  }

  return null;
}

export interface SparqlBinding {
  [variable: string]: { type: string; value: string };
}

/** Check a SPARQL `SELECT ?p ?o WHERE { <iri> ?p ?o }` result for the
 * expected triple presence. Options:
 *   - `requireRdfType`: only accept a binding whose `?p` is `rdf:type`. */
export function sparqlResultHasExpectedTriple(
  bindings: readonly SparqlBinding[],
  options: { requireRdfType?: boolean } = {},
): boolean {
  if (bindings.length === 0) return false;
  if (!options.requireRdfType) return true;

  const RDF_TYPE = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type';
  return bindings.some((b) => b.p?.value === RDF_TYPE);
}

// ------------------------------------------------------------ browser-facing

async function extractBearerHeaders(
  page: Page,
  override?: Record<string, string>,
): Promise<Record<string, string>> {
  if (override !== undefined) return override;
  // Phase 11.1 — the access_token lives in JS module memory; localStorage
  // holds it only transiently (the E2E injection helper writes it, and every
  // SPA-side refresh rotation removes it in the same tick). Reading
  // localStorage only made long flows fail with a bare 401 the moment the
  // SPA rotated the token (batch3 contract/dataset-create). The sanctioned
  // probe is window.__getAccessToken (client.ts) — read it first, fall back
  // to localStorage for pages that predate the hook.
  const token = await page.evaluate<string | null>(() => {
    const w = globalThis as unknown as {
      localStorage?: { getItem: (k: string) => string | null };
      __getAccessToken?: () => string | null;
    };
    if (typeof w.__getAccessToken === 'function') {
      return w.__getAccessToken();
    }
    return w.localStorage?.getItem('access_token') ?? null;
  });
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

/**
 * Run the five-step chain. Returns the canonical IRI so callers can chain
 * further assertions.
 *
 * Steps 3, 4 can be degraded (skipped) via `options.skipSparqlOn` and
 * `options.expectContextDoc` respectively.
 */
export async function verifySemanticIri(
  page: Page,
  resourceType: SemanticResourceType,
  resourceId: string,
  options: VerifySemanticIriOptions = {},
): Promise<string> {
  // When no base is pinned (caller option or SEMANTIC_BASE_IRI env), learn the
  // canonical IRI from the dereference's own 303 Location and verify the
  // resource PATH suffix. The IRI origin is backend-derived (HUB_DOMAIN,
  // docker-compose.test.yml → test.hub.example.com on the test stack), so a
  // hardcoded runner-side fallback drifts — the old 'https://hub.example.com'
  // fallback made batch3's dataset-create fail with a @id mismatch.
  const pinnedBase = options.semanticBaseIri ?? process.env.SEMANTIC_BASE_IRI ?? null;
  const canonicalPath = `/id/${resourceType}/${resourceId}`;
  const pinnedIri = pinnedBase
    ? canonicalIriFor(pinnedBase, resourceType, resourceId)
    : null;
  const derefBase = options.derefEndpointBase ?? '/api/v1/semantic/id';
  const sparqlEndpoint = options.sparqlEndpoint ?? '/api/v1/semantic/sparql';
  const contextEndpoint = options.contextEndpoint ?? '/api/v1/semantic/context.jsonld';
  const headers = await extractBearerHeaders(page, options.authHeaderOverride);

  // ---- Step 1: 303 dereference
  const derefUrl = `${derefBase}/${resourceType}/${resourceId}`;
  const derefRes = await page.request.get(derefUrl, {
    headers: { ...headers, Accept: 'application/rdf+xml' },
    maxRedirects: 0,
  });
  const redirectLocation = derefRes.headers()['location'] ?? null;
  const classification = classifyDereferenceResponse(
    { status: derefRes.status(), locationHeader: redirectLocation },
    pinnedIri,
    pinnedIri === null ? canonicalPath : undefined,
  );
  if (classification === 'redirect-mismatch') {
    throw new Error(
      `verifySemanticIri: GET ${derefUrl} redirect Location mismatch. ` +
        `Expected=${pinnedIri ?? `*${canonicalPath}`}, actual=${redirectLocation}`,
    );
  }
  if (classification === 'redirect-missing-location') {
    throw new Error(
      `verifySemanticIri: GET ${derefUrl} returned 303 with no Location header`,
    );
  }
  if (classification === 'not-found' || classification === 'server-error' || classification === 'unexpected') {
    throw new Error(
      `verifySemanticIri: GET ${derefUrl} returned ${derefRes.status()} (${classification})`,
    );
  }

  // ---- Step 2: JSON-LD payload (either from redirect or direct)
  const jsonLdRes = await page.request.get(derefUrl, {
    headers: { ...headers, Accept: 'application/ld+json' },
  });
  if (!jsonLdRes.ok()) {
    let preview = '';
    try {
      preview = (await jsonLdRes.text()).slice(0, 400);
    } catch {
      // intentional: verifySemantic's degrade-to-skip paths are documented in the fixture header — SPARQL endpoint and context-doc fetches are best-effort because some staging configurations don't expose them yet.
      /* ignore */
    }
    throw new Error(
      `verifySemanticIri: JSON-LD fetch ${derefUrl} returned ${jsonLdRes.status()}. Body preview: ${preview}`,
    );
  }
  const jsonLdBody = await jsonLdRes.json();
  // Effective IRI for downstream steps: the pinned value, or the value the
  // backend itself declared (redirect Location, falling back to the
  // payload's own @id when the deref serves the document directly).
  const effectiveIri =
    pinnedIri ??
    redirectLocation ??
    (typeof (jsonLdBody as Record<string, unknown>)?.['@id'] === 'string'
      ? ((jsonLdBody as Record<string, unknown>)['@id'] as string)
      : '');
  const jsonLdMismatch = validateJsonLdPayload(jsonLdBody, {
    ...(pinnedIri !== null
      ? { expectedIri: pinnedIri }
      : { expectedIriSuffix: canonicalPath }),
    expectedType: options.expectedType,
  });
  if (jsonLdMismatch !== null) {
    throw new Error(`verifySemanticIri: ${jsonLdMismatch}`);
  }

  // ---- Step 3: JSON-LD context doc (opt-in)
  if (options.expectContextDoc) {
    const ctxRes = await page.request.get(contextEndpoint, { headers });
    if (!ctxRes.ok()) {
      throw new Error(
        `verifySemanticIri: context fetch ${contextEndpoint} returned ${ctxRes.status()}`,
      );
    }
  }

  // ---- Step 4: SPARQL triple visibility (may degrade to skip, or be
  // opted out entirely for resource types the index never ingests)
  if (options.expectSparqlTriple === false) {
    return effectiveIri;
  }
  const sparqlQuery = `SELECT ?p ?o WHERE { <${effectiveIri}> ?p ?o } LIMIT 10`;
  // SPARQL endpoint contract (semantic/views.py sparql_query): POST a JSON
  // body {"query": ..., "format": ..., "timeout": ...} — the legacy raw
  // `application/sparql-query` content-type is rejected by the API's
  // JSON-only POST middleware (400 INVALID_FORMAT).
  let sparqlRes = await page.request.post(sparqlEndpoint, {
    headers: {
      ...headers,
      'Content-Type': 'application/json',
      Accept: 'application/sparql-results+json',
    },
    data: { query: sparqlQuery, format: 'json' },
  });

  if (!sparqlRes.ok()) {
    let preview = '';
    try {
      preview = (await sparqlRes.text()).slice(0, 400);
    } catch {
      // intentional: verifySemantic's degrade-to-skip paths are documented in the fixture header — SPARQL endpoint and context-doc fetches are best-effort because some staging configurations don't expose them yet.
      /* ignore */
    }
    if (options.skipSparqlOn?.({ status: sparqlRes.status(), bodyPreview: preview })) {
      // W16 — in CI a SPARQL-outage skip is an environment failure and must
      // announce itself; local runs keep the documented degrade-to-skip.
      environmentSkipGuard(
        `SPARQL verification degraded: status=${sparqlRes.status()} ` +
          `preview=${preview.slice(0, 120)}`,
      );
      options.testInfo?.annotations.push({
        type: 'sparql-endpoint-unavailable',
        description: `status=${sparqlRes.status()} preview=${preview.slice(0, 120)}`,
      });
    } else {
      throw new Error(
        `verifySemanticIri: SPARQL query returned ${sparqlRes.status()}. Body preview: ${preview}`,
      );
    }
  } else {
    // The semantic index ingests asynchronously — a freshly created
    // resource can return 0 bindings for seconds after its row is
    // visible elsewhere (contract-create failed exactly this: 200 with
    // Bindings: []). Retry the query with a short bounded budget before
    // declaring the triple missing.
    // Ingestion lag under batch load measured beyond 20s (dataset-create
    // and asset-activation both exhausted 20s with the triple appearing
    // later) — 45s covers the batch-restart cold path.
    const SPARQL_INDEX_BUDGET_MS = 45_000;
    const SPARQL_RETRY_DELAY_MS = 5_000;
    const sparqlDeadline = Date.now() + SPARQL_INDEX_BUDGET_MS;
    let bindings: SparqlBinding[] = [];
    let lastSparqlBody: { results?: { bindings?: SparqlBinding[] } } | null = null;
    while (true) {
      const sparqlBody = (await sparqlRes.json()) as {
        results?: { bindings?: SparqlBinding[] };
      };
      lastSparqlBody = sparqlBody;
      bindings = sparqlBody.results?.bindings ?? [];
      if (sparqlResultHasExpectedTriple(bindings, {
        requireRdfType: options.expectedType !== undefined,
      })) {
        break;
      }
      if (Date.now() >= sparqlDeadline) break;
      await new Promise((r) => setTimeout(r, SPARQL_RETRY_DELAY_MS));
      // Re-run the query — the previous response body is consumed.
      sparqlRes = await page.request.post(sparqlEndpoint, {
        headers: {
          ...headers,
          'Content-Type': 'application/json',
          Accept: 'application/sparql-results+json',
        },
        data: { query: sparqlQuery, format: 'json' },
      });
      if (!sparqlRes.ok()) break;
    }
    if (
      !sparqlResultHasExpectedTriple(bindings, {
        requireRdfType: options.expectedType !== undefined,
      })
    ) {
      throw new Error(
        `verifySemanticIri: SPARQL returned 0 matching triples for <${effectiveIri}>. ` +
          `requireRdfType=${options.expectedType !== undefined}. ` +
          `Bindings: ${JSON.stringify(bindings).slice(0, 400)}`,
      );
    }
    void lastSparqlBody;
  }

  // ---- Step 5: Negative-path — bogus UUID must 404
  const bogusId = '00000000-0000-0000-0000-000000000000';
  if (bogusId !== resourceId) {
    const negUrl = `${derefBase}/${resourceType}/${bogusId}`;
    const negRes = await page.request.get(negUrl, {
      headers: { ...headers, Accept: 'application/rdf+xml' },
      maxRedirects: 0,
    });
    if (negRes.status() !== 404) {
      // Non-fatal but recorded — a 303 here would mean the dereferencer is a
      // stub that redirects everything; fail loud.
      if (negRes.status() === 303) {
        throw new Error(
          `verifySemanticIri: negative-path bogus-UUID dereferencing returned 303, ` +
            `indicating the dereferencer redirects any ID. Expected 404.`,
        );
      }
      // Other statuses (e.g. 401 from auth) are noisy but not fatal — record
      // via annotation and continue.
      options.testInfo?.annotations.push({
        type: 'semantic-negative-path-unexpected',
        description: `bogus ${negUrl} returned ${negRes.status()} (expected 404)`,
      });
    }
  }

  return effectiveIri;
}
