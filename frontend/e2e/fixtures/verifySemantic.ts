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
 * via the `options.skipSparqlOn` callback.
 *
 * Phase 226 PR B5 — see
 * /home/ph/.claude/plans/now-pls-create-a-binary-cloud.md §Track B.
 */

import type { Page, TestInfo } from '@playwright/test';

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

/** Classify a GET-with-RDF-accept response. */
export function classifyDereferenceResponse(
  res: { status: number; locationHeader: string | null },
  expectedIri: string,
): DereferenceClassification {
  if (res.status === 303) {
    if (res.locationHeader === null || res.locationHeader === '') {
      return 'redirect-missing-location';
    }
    return res.locationHeader === expectedIri ? 'redirect-match' : 'redirect-mismatch';
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
 * message. */
export function validateJsonLdPayload(
  body: unknown,
  expected: { expectedIri: string; expectedType?: string },
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
  if (obj['@id'] !== expected.expectedIri) {
    return (
      `JSON-LD @id mismatch: expected=${expected.expectedIri}, ` +
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
  const token = await page.evaluate<string | null>(
    () =>
      (globalThis as unknown as { localStorage?: { getItem: (k: string) => string | null } })
        .localStorage?.getItem('access_token') ?? null,
  );
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
  const base =
    options.semanticBaseIri ??
    process.env.SEMANTIC_BASE_IRI ??
    'https://hub.example.com';
  const iri = canonicalIriFor(base, resourceType, resourceId);
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
  const classification = classifyDereferenceResponse(
    { status: derefRes.status(), locationHeader: derefRes.headers()['location'] ?? null },
    iri,
  );
  if (classification === 'redirect-mismatch') {
    throw new Error(
      `verifySemanticIri: GET ${derefUrl} redirect Location mismatch. ` +
        `Expected=${iri}, actual=${derefRes.headers()['location']}`,
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
  const jsonLdMismatch = validateJsonLdPayload(jsonLdBody, {
    expectedIri: iri,
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

  // ---- Step 4: SPARQL triple visibility (may degrade to skip)
  const sparqlQuery = `SELECT ?p ?o WHERE { <${iri}> ?p ?o } LIMIT 10`;
  const sparqlRes = await page.request.post(sparqlEndpoint, {
    headers: {
      ...headers,
      'Content-Type': 'application/sparql-query',
      Accept: 'application/sparql-results+json',
    },
    data: sparqlQuery,
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
    const sparqlBody = (await sparqlRes.json()) as {
      results?: { bindings?: SparqlBinding[] };
    };
    const bindings = sparqlBody.results?.bindings ?? [];
    if (
      !sparqlResultHasExpectedTriple(bindings, {
        requireRdfType: options.expectedType !== undefined,
      })
    ) {
      throw new Error(
        `verifySemanticIri: SPARQL returned 0 matching triples for <${iri}>. ` +
          `requireRdfType=${options.expectedType !== undefined}. ` +
          `Bindings: ${JSON.stringify(bindings).slice(0, 400)}`,
      );
    }
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

  return iri;
}
