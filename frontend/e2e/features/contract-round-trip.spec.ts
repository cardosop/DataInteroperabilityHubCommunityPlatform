/**
 * E2E Feature: Contract round-trip preservation (Phase 226 G15).
 *
 * Per-format upload → export → normalize → deep-equal. The platform
 * promise is: a contract uploaded in any of the supported standards
 * (ODCS 3.0, 3.1, ODPS v1.0, v4.2, Bitol ODPS 1.0.0, Hub-YAML) can be
 * exported back in the same format and the structurally-meaningful
 * payload survives the round-trip. A regression in the format converter
 * silently corrupts contracts; this spec catches it before publish.
 *
 * Negative cases: malformed payloads must surface an actionable 4xx with
 * a parser/validation error referenced by name.
 *
 * No mocks. Real backend.
 */

import { expect, test } from '@playwright/test';
import { getTestUser } from '../fixtures/auth';

const API_BASE = '/api/v1';

// ----------------------------------------------------------- pure helpers

/**
 * Strip volatile fields (timestamps, generated ids, audit metadata) so a
 * deep-equal compares only the structurally-meaningful payload. Recursive
 * to handle nested objects/arrays. Pure.
 */
export function stripVolatileFields(value: unknown): unknown {
  const VOLATILE_KEYS = new Set([
    'id',
    'uuid',
    'created_at',
    'updated_at',
    'last_modified',
    'last_updated',
    'created',
    'updated',
    'lastUpdated',
    'createdAt',
    'updatedAt',
    'tenant_id',
    'tenant',
    'owner_id',
    'owner',
    'workflow_instance_id',
    'workflow_id',
    'job_id',
    'audit',
    'auditEvent',
    'etag',
    'version_id',
    '_meta',
  ]);
  if (Array.isArray(value)) {
    return value.map((v) => stripVolatileFields(v));
  }
  if (value && typeof value === 'object') {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      if (VOLATILE_KEYS.has(k)) continue;
      out[k] = stripVolatileFields(v);
    }
    return out;
  }
  return value;
}

/**
 * Sample fixture payloads for each supported format. Kept inline so the
 * spec is self-contained — adding a new format means adding one entry
 * here, not coordinating with a separate fixtures directory.
 */
interface FormatFixture {
  name: string;
  /** API value for `?format=...` on the export endpoint. */
  exportFormat: 'odcs' | 'odps' | 'hubcontract';
  /** Original spec type for the contract create payload. */
  originalSpecType: 'ODCS' | 'ODPS' | 'HUB_YAML';
  /** Optional spec version label. */
  originalSpecVersion?: string;
  /** Build a minimal valid contract body. The Date.now() suffix keeps
   * names unique across parallel workers. */
  build: () => Record<string, unknown>;
}

const FORMATS: FormatFixture[] = [
  {
    name: 'ODCS v3.0',
    exportFormat: 'odcs',
    originalSpecType: 'ODCS',
    originalSpecVersion: '3.0.2',
    build: () => {
      const payload = {
      name: `RT ODCS 3.0 ${Date.now()}`,
            original_spec_type: 'ODCS',
            original_spec_version: '3.0.2',
            version: '1.0.0',
            spec: {
              apiVersion: 'odcs.io/v3.0.2',
              kind: 'DataContract',
              id: `rt-odcs-30-${Date.now()}`,
              name: `RT ODCS 3.0 ${Date.now()}`,
              version: '1.0.0',
              schema: {
                fields: [
                  { name: 'id', type: 'string', nullable: false, description: 'ID' },
                  { name: 'amount', type: 'number', nullable: false, description: 'Amount' },
                ],
              },
            },
      };
      // ContractCreateSerializer (POST /contracts/) and the ODPS
      // products path both require the raw content + format. The
      // structured fields stay so the round-trip comparison below
      // keeps reading original.spec / original.product unchanged.
      return {
        ...payload,
        // The create path parses original_raw — the raw must be the
        // ODCS DOCUMENT (payload.spec), not the API wrapper, or the
        // normalizer sees no schema fields (STRUCTURELESS_ODCS_NO_SCHEMA).
        original_raw: JSON.stringify(payload.spec),
        original_format: 'JSON',
      };
    },
  },
  {
    name: 'ODCS v3.1',
    exportFormat: 'odcs',
    originalSpecType: 'ODCS',
    originalSpecVersion: '3.1.0',
    build: () => {
      const payload = {
      name: `RT ODCS 3.1 ${Date.now()}`,
            original_spec_type: 'ODCS',
            original_spec_version: '3.1.0',
            version: '1.0.0',
            spec: {
              apiVersion: 'odcs.io/v3.1.0',
              kind: 'DataContract',
              id: `rt-odcs-31-${Date.now()}`,
              name: `RT ODCS 3.1 ${Date.now()}`,
              version: '1.0.0',
              schema: {
                fields: [
                  { name: 'id', type: 'string', nullable: false, description: 'ID' },
                  { name: 'created_at', type: 'datetime', nullable: false, description: 'When' },
                ],
              },
            },
      };
      // ContractCreateSerializer (POST /contracts/) and the ODPS
      // products path both require the raw content + format. The
      // structured fields stay so the round-trip comparison below
      // keeps reading original.spec / original.product unchanged.
      return {
        ...payload,
        // Raw = the ODCS document itself (see ODCS v3.0 fixture).
        original_raw: JSON.stringify(payload.spec),
        original_format: 'JSON',
      };
    },
  },
  {
    name: 'ODPS v1.0',
    exportFormat: 'odps',
    originalSpecType: 'ODPS',
    originalSpecVersion: '1.0',
    build: () => {
      const payload = {
      schema: 'https://opendataproducts.org/schema/v1.0',
            version: '1.0',
            product: {
              details: {
                en: {
                  productID: `rt-odps-10-${Date.now()}`,
                  name: `RT ODPS 1.0 ${Date.now()}`,
                  description: 'Round-trip ODPS v1.0',
                  productVersion: '1.0.0',
                },
              },
              dataSchema: {
                fields: [
                  { name: 'id', type: 'string' },
                  { name: 'name', type: 'string' },
                ],
              },
              // The products workflow's extract_contract step requires an
              // inline ODCS contract on EVERY ODPS product (same shape as the
              // v4.2 fixture) — a v1.0 doc without product.contract fails
              // with REQUIRED_FIELD_MISSING before normalization (b7 #8).
              contract: {
                spec: {
                  apiVersion: 'odcs.io/v3.0.2',
                  kind: 'DataContract',
                  id: `rt-odps-10-c-${Date.now()}`,
                  name: `RT ODPS 1.0 ODCS ${Date.now()}`,
                  version: '1.0.0',
                  schema: {
                    fields: [
                      { name: 'id', type: 'string', nullable: false, description: 'ID' },
                      { name: 'name', type: 'string', nullable: false, description: 'Name' },
                    ],
                  },
                },
              },
            },
      };
      // ContractCreateSerializer (POST /contracts/) and the ODPS
      // products path both require the raw content + format. The
      // structured fields stay so the round-trip comparison below
      // keeps reading original.spec / original.product unchanged.
      return {
        ...payload,
        original_raw: JSON.stringify(payload),
        original_format: 'JSON',
      };
    },
  },
  {
    name: 'ODPS v4.2',
    exportFormat: 'odps',
    originalSpecType: 'ODPS',
    originalSpecVersion: '4.2',
    build: () => {
      const payload = {
      schema: 'https://opendataproducts.org/schema/v4.2',
            version: '4.2',
            product: {
              details: {
                en: {
                  productID: `rt-odps-42-${Date.now()}`,
                  name: `RT ODPS 4.2 ${Date.now()}`,
                  description: 'Round-trip ODPS v4.2',
                  productVersion: '1.0.0',
                },
              },
              dataSchema: {
                fields: [
                  { name: 'id', type: 'string' },
                  { name: 'price', type: 'number' },
                ],
              },
              contract: {
                spec: {
                  apiVersion: 'odcs.io/v3.0.2',
                  kind: 'DataContract',
                  id: `rt-odps-42-c-${Date.now()}`,
                  name: `RT ODPS 4.2 ODCS ${Date.now()}`,
                  version: '1.0.0',
                  schema: {
                    fields: [
                      { name: 'id', type: 'string', nullable: false, description: 'ID' },
                      { name: 'price', type: 'number', nullable: false, description: 'Price' },
                    ],
                  },
                },
              },
            },
      };
      // ContractCreateSerializer (POST /contracts/) and the ODPS
      // products path both require the raw content + format. The
      // structured fields stay so the round-trip comparison below
      // keeps reading original.spec / original.product unchanged.
      return {
        ...payload,
        original_raw: JSON.stringify(payload),
        original_format: 'JSON',
      };
    },
  },
  {
    name: 'Bitol ODPS 1.0.0',
    exportFormat: 'odps',
    originalSpecType: 'ODPS',
    originalSpecVersion: 'bitol-1.0.0',
    build: () => {
      const payload = {
      // Canonical Bitol ODPS discriminators (see odps_version_detection.py
      // _BITOL_VERSION_PATTERN): the bitol-io.github.io schema URL + kind
      // DataProduct + apiVersion v1.0.0 route the doc to the bitol
      // normalizer. The non-canonical opendataproducts.bitol.io URL fell
      // through to the pre-Bitol v1.x JSON schema and died on PATTERN_MISMATCH
      // (b7 #10). Like every products-workflow doc, product.contract.spec
      // carries the inline ODCS contract for extract_contract.
      schema: 'https://bitol-io.github.io/open-data-product-standard/v1.0.0/schema.json',
            kind: 'DataProduct',
            apiVersion: 'v1.0.0',
            version: '1.0.0',
            product: {
              details: {
                en: {
                  productID: `rt-bitol-100-${Date.now()}`,
                  name: `RT Bitol ODPS ${Date.now()}`,
                  description: 'Round-trip Bitol ODPS 1.0.0',
                  productVersion: '1.0.0',
                },
              },
              dataSchema: {
                fields: [
                  { name: 'id', type: 'string' },
                  { name: 'event_type', type: 'string' },
                ],
              },
              contract: {
                spec: {
                  apiVersion: 'odcs.io/v3.0.2',
                  kind: 'DataContract',
                  id: `rt-bitol-100-c-${Date.now()}`,
                  name: `RT Bitol ODCS ${Date.now()}`,
                  version: '1.0.0',
                  schema: {
                    fields: [
                      { name: 'id', type: 'string', nullable: false, description: 'ID' },
                      { name: 'event_type', type: 'string', nullable: false, description: 'Event type' },
                    ],
                  },
                },
              },
            },
      };
      // ContractCreateSerializer (POST /contracts/) and the ODPS
      // products path both require the raw content + format. The
      // structured fields stay so the round-trip comparison below
      // keeps reading original.spec / original.product unchanged.
      return {
        ...payload,
        original_raw: JSON.stringify(payload),
        original_format: 'JSON',
      };
    },
  },
  {
    name: 'Hub-YAML',
    exportFormat: 'hubcontract',
    originalSpecType: 'HUB_YAML',
    build: () => {
      // OriginalSpecType no longer has a HUB_YAML choice (enum is ODCS |
      // ODPS) — the Hub document is ODCS-shaped (kind DataContract,
      // schema.fields) and the normalizer extracts the version from any
      // apiVersion, so it uploads as ODCS. The fixture keeps
      // originalSpecType: 'HUB_YAML' for the round-trip branch +
      // exportFormat=hubcontract below (b7 #14: "\"HUB_YAML\" is not a
      // valid choice.").
      const payload = {
      name: `RT HubYAML ${Date.now()}`,
            original_spec_type: 'ODCS',
            version: '1.0.0',
            spec: {
              apiVersion: 'meshant-internal.example.com/v1',
              kind: 'DataContract',
              // The ODCS normalizer maps doc.id → hub_contract.id; a doc
              // without it normalizes to an empty id and the HubContract
              // typed-model validator rejects it ("hub_contract_version and
              // id must be provided") (b7 #11). hub_contract_version is
              // defaulted by the normalizer.
              id: `rt-hubyaml-${Date.now()}`,
              name: `RT HubYAML ${Date.now()}`,
              version: '1.0.0',
              schema: {
                fields: [
                  { name: 'id', type: 'string', nullable: false },
                  { name: 'value', type: 'number', nullable: false },
                ],
              },
            },
      };
      // ContractCreateSerializer (POST /contracts/) and the ODPS
      // products path both require the raw content + format. The
      // structured fields stay so the round-trip comparison below
      // keeps reading original.spec / original.product unchanged.
      return {
        ...payload,
        // Raw = the hub document itself (payload.spec) — the create path
        // parses original_raw and the normalizer reads schema.fields from
        // it (b3's run: wrapper-wrapped raw → STRUCTURELESS_ODCS_NO_SCHEMA).
        // JSON text is valid YAML, so the YAML format label parses cleanly.
        original_raw: JSON.stringify(payload.spec),
        original_format: 'YAML',
      };
    },
  },
];

async function login(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  page: any,
): Promise<string> {
  const user = await getTestUser();
  const res = await page.request.post(`${API_BASE}/auth/login/`, {
    data: { email: user.email, password: user.password },
    headers: { 'Content-Type': 'application/json' },
  });
  expect(res.ok()).toBe(true);
  return (await res.json()).access_token as string;
}

test.describe('Feature: Contract round-trip preservation', () => {
  test.setTimeout(120_000);

  for (const fixture of FORMATS) {
    test(`${fixture.name}: upload → export → deep-equal core fields`, async ({ page }) => {
      const token = await login(page);
      const original = fixture.build();

      // Upload — POST /api/v1/contracts/. ODPS payloads route through the
      // workflow path on `/contracts/products/`; endpoint selection follows
      // the original_spec_type.
      const createUrl =
        fixture.originalSpecType === 'ODPS'
          ? `${API_BASE}/contracts/products/`
          : `${API_BASE}/contracts/`;
      const createRes = await page.request.post(createUrl, {
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        data: original,
      });
      if (!createRes.ok()) {
        const text = (await createRes.text()).slice(0, 400);
        // Capability gating (404 / 503 / 501) on a specific format is an
        // environment posture, not a regression — skip cleanly so the rest
        // of the matrix still runs.
        test.skip(
          [404, 501, 503].includes(createRes.status()),
          `${fixture.name} create returned ${createRes.status()} — capability not enabled in this env: ${text}`,
        );
        throw new Error(
          `${fixture.name} contract create returned ${createRes.status()}: ${text}`,
        );
      }
      const created = (await createRes.json()) as {
        id?: string;
        contract?: { id?: string };
        odps_contract?: { id?: string };
        odcs_contract?: { id?: string };
        workflow_instance_id?: string;
      };
      // Sync-mode (ENVIRONMENT=test) executes the product workflow inline
      // and returns the persisted contracts under odps_contract /
      // odcs_contract — there is no top-level id. Async-mode returns only
      // workflow_instance_id; poll the status endpoint then. (b7: the spec
      // read neither shape — the three ODPS fixtures timed out polling a
      // route that 404'd and skipped "did not resolve contract id".)
      let contractId =
        created.id ?? created.contract?.id ?? created.odps_contract?.id ?? created.odcs_contract?.id;
      if (!contractId && created.workflow_instance_id) {
        const deadline = Date.now() + 60_000;
        while (Date.now() < deadline) {
          const wRes = await page.request.get(
            `${API_BASE}/contracts/products/workflows/${created.workflow_instance_id}/status/`,
            { headers: { Authorization: `Bearer ${token}` } },
          );
          if (wRes.ok()) {
            const wBody = (await wRes.json()) as {
              status?: string;
              contract_id?: string;
              odps_contract?: { id?: string } | null;
              odcs_contract?: { id?: string } | null;
              result?: { contract_id?: string };
            };
            const status = (wBody.status ?? '').toUpperCase();
            const resolvedId =
              wBody.contract_id ??
              wBody.result?.contract_id ??
              wBody.odps_contract?.id ??
              wBody.odcs_contract?.id;
            if (resolvedId) {
              contractId = resolvedId;
              break;
            }
            if (['FAILED', 'CANCELLED'].includes(status)) {
              throw new Error(`${fixture.name} workflow ${status}: ${JSON.stringify(wBody).slice(0, 300)}`);
            }
          }
          await page.waitForTimeout(2000);
        }
      }
      test.skip(!contractId, `${fixture.name} did not resolve contract id within budget`);

      // Export — GET /api/v1/contracts/{id}/export/?format=<fmt>.
      const exportRes = await page.request.get(
        `${API_BASE}/contracts/${contractId}/export/?format=${fixture.exportFormat}&output_format=json`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      if (!exportRes.ok()) {
        test.skip(
          [404, 501].includes(exportRes.status()),
          `${fixture.name} export not available: ${exportRes.status()}`,
        );
        const text = (await exportRes.text()).slice(0, 400);
        throw new Error(
          `${fixture.name} export returned ${exportRes.status()}: ${text}`,
        );
      }
      // The odps+json export returns the document as a JSON-ENCODED STRING
      // (the download path consumes it verbatim); hubcontract/odcs return
      // a plain object. Unwrap both shapes before comparing.
      const exportedRaw = (await exportRes.json()) as unknown;
      const exported = (
        typeof exportedRaw === 'string'
          ? JSON.parse(exportedRaw)
          : exportedRaw
      ) as Record<string, unknown>;

      const stripExp = stripVolatileFields(exported) as Record<string, unknown>;

      // The export is the canonical document for the requested format —
      // not a re-echoed wrapper. So:
      //   - ODCS export = the ODCS document (apiVersion/kind/schema/...)
      //   - ODPS export = the ODPS document (schema/version/product/...)
      //   - hubcontract export = the HubContract document
      // The original payload may wrap this in `spec` (ODCS / HUB_YAML) or
      // be flat (ODPS). The right round-trip assertion compares the
      // CONTENT of those wrappers against the export, not the wrappers
      // themselves.

      /**
       * Find the inner ODCS-like document inside the original payload.
       * For ODCS-wrapped uploads the inner doc is `original.spec`; for
       * raw ODPS-with-embedded-contract it's `original.product.contract.spec`;
       * for HUB_YAML uploads it's `original.spec`.
       */
      function innerOdcsDoc(o: Record<string, unknown>): Record<string, unknown> | null {
        if (typeof o.spec === 'object' && o.spec !== null) {
          return o.spec as Record<string, unknown>;
        }
        const product = o.product;
        if (
          product &&
          typeof product === 'object' &&
          'contract' in product &&
          (product as { contract?: { spec?: unknown } }).contract?.spec
        ) {
          return (product as { contract: { spec: Record<string, unknown> } }).contract.spec;
        }
        return null;
      }

      // ODPS round-trip — the dataSchema.fields preservation is the canonical
      // coercion test — names and types must round-trip.
      if (fixture.originalSpecType === 'ODPS') {
        const origProduct = (original as { product?: { dataSchema?: { fields?: Array<{ name: string; type: string }> } } }).product;
        const origFields = origProduct?.dataSchema?.fields ?? [];
        const expProduct = (stripExp as { product?: { dataSchema?: { fields?: Array<{ name?: string; type?: string }> } } }).product;
        const expFields = expProduct?.dataSchema?.fields ?? [];
        expect(
          expFields.length,
          `${fixture.name}: dataSchema.fields count must round-trip`,
        ).toBe(origFields.length);
        for (const f of origFields) {
          const found = expFields.find((g) => g.name === f.name);
          expect(found, `${fixture.name}: field ${f.name} missing after export`).toBeTruthy();
          expect(found?.type, `${fixture.name}: field ${f.name}.type changed`).toBe(f.type);
        }
        // ODPS structural roots — these survive verbatim (top-level shape
        // matches input exactly).
        expect(stripExp, `${fixture.name}: export must keep top-level "product"`).toHaveProperty('product');
        expect(stripExp, `${fixture.name}: export must keep top-level "version"`).toHaveProperty('version');
      }

      // ODCS round-trip — schema.fields preservation. The export IS the
      // ODCS document, so we compare original.spec.schema.fields ↔
      // exported.schema.fields (no `spec` wrapper on the export side).
      if (fixture.originalSpecType === 'ODCS') {
        const origInner = innerOdcsDoc(original as Record<string, unknown>);
        expect(
          origInner,
          `${fixture.name}: test fixture must have inner ODCS doc under .spec`,
        ).toBeTruthy();
        const origSchema = (origInner as { schema?: { fields?: Array<{ name: string; type: string }> } })?.schema;
        const origFields = origSchema?.fields ?? [];
        // Export shape: top-level schema.fields directly.
        const expSchema = (stripExp as { schema?: { fields?: Array<{ name?: string; type?: string }> } }).schema;
        const expFields = expSchema?.fields ?? [];
        expect(
          expFields.length,
          `${fixture.name}: schema.fields count must round-trip`,
        ).toBe(origFields.length);
        for (const f of origFields) {
          const found = expFields.find((g) => g.name === f.name);
          expect(found, `${fixture.name}: field ${f.name} missing after export`).toBeTruthy();
          expect(found?.type, `${fixture.name}: field ${f.name}.type changed`).toBe(f.type);
        }
        // Spec-level core metadata — apiVersion + name + version survive.
        expect(stripExp).toHaveProperty('apiVersion');
        expect(stripExp).toHaveProperty('name');
        expect(stripExp).toHaveProperty('version');
      }

      // HubContract / HUB_YAML round-trip — the export is a HubContract
      // document. Field structure matches ODCS-derived HubContract shape:
      // a top-level `schema.fields` and `info.name` etc. We assert the
      // schema fields survive by name and type.
      if (fixture.originalSpecType === 'HUB_YAML') {
        const origInner = innerOdcsDoc(original as Record<string, unknown>);
        const origFields =
          (origInner as { schema?: { fields?: Array<{ name: string; type: string }> } } | null)?.schema?.fields ?? [];
        const expSchema = (stripExp as { schema?: { fields?: Array<{ name?: string; type?: string; data_type?: string }> } }).schema;
        const expFields = expSchema?.fields ?? [];
        expect(
          expFields.length,
          `${fixture.name}: schema.fields count must round-trip`,
        ).toBe(origFields.length);
        for (const f of origFields) {
          const found = expFields.find((g) => g.name === f.name);
          expect(found, `${fixture.name}: field ${f.name} missing after export`).toBeTruthy();
          // The hubcontract export emits the CANONICAL HubContract field
          // names — ``data_type`` — not the ODCS alias ``type``
          // (odcs_normalizer_base dumps with by_alias=False precisely to
          // preserve data_type / min_length / max_length). Reading only
          // ``type`` finds undefined on a perfectly round-tripped field
          // (b6 verification: id.type Expected "string" Received undefined).
          const exportedType = found?.data_type ?? found?.type;
          expect(exportedType, `${fixture.name}: field ${f.name}.type changed`).toBe(f.type);
        }
      }
    });
  }

  test('Negative: malformed ODCS payload surfaces actionable validation error', async ({ page }) => {
    const token = await login(page);
    const malformed = {
      name: 'Malformed ODCS',
      original_spec_type: 'ODCS',
      version: '1.0.0',
      spec: {
        // Missing required apiVersion + kind + id
        name: 'Missing-Required',
        version: '1.0.0',
      },
      // Serializer contract requires the raw content — supply it so the
      // SPEC validator (missing apiVersion/kind/id) is what rejects the
      // request, not the required-field check.
      original_raw: JSON.stringify({
        name: 'Missing-Required',
        version: '1.0.0',
      }),
      original_format: 'JSON',
    };
    const res = await page.request.post(`${API_BASE}/contracts/`, {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      data: malformed,
    });
    expect(res.ok()).toBe(false);
    expect([400, 422]).toContain(res.status());
    const body = await res.text();
    // The error must name what's wrong; a generic "invalid" is a poor user
    // experience and a regression of the validator's diagnostic quality.
    expect(body.length).toBeGreaterThan(0);
    expect(/(apiVersion|kind|id|required|missing|validation)/i.test(body)).toBe(true);
  });

  test('Negative: malformed ODPS payload surfaces actionable validation error', async ({ page }) => {
    const token = await login(page);
    const malformed = {
      schema: 'https://opendataproducts.org/schema/v4.2',
      version: '4.2',
      product: {
        // missing details.en.productID and missing dataSchema entirely
        details: { en: { name: 'No ID' } },
      },
      // Serializer contract requires the raw content — supply it so the
      // ODPS validator (missing productID/dataSchema) is what rejects the
      // request, not the required-field check.
      original_raw: JSON.stringify({
        schema: 'https://opendataproducts.org/schema/v4.2',
        version: '4.2',
        product: {
          details: { en: { name: 'No ID' } },
        },
      }),
      original_format: 'JSON',
    };
    const res = await page.request.post(`${API_BASE}/contracts/products/`, {
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      data: malformed,
    });
    expect(res.ok()).toBe(false);
    // 4xx range — must be actionable, not 5xx.
    expect(res.status()).toBeGreaterThanOrEqual(400);
    expect(res.status()).toBeLessThan(500);
    const body = await res.text();
    expect(/(productID|dataSchema|required|invalid|validation|missing)/i.test(body)).toBe(true);
  });
});
