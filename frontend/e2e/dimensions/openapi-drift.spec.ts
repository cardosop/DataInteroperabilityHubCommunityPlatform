/**
 * E2E dimension test: OpenAPI Drift.
 *
 * Phase 226.F4. Fetches the live OpenAPI document from the deployed
 * backend, extracts a stable shape (paths × methods × parameters ×
 * components — see fixtures/openapiDrift.ts), hashes it, and compares
 * the hash to the committed snapshot at
 * `e2e/dimensions/__snapshots__/openapi-drift.snapshot.json`.
 *
 * What this catches at PR time:
 *   - Removing or renaming a path / operation
 *   - Changing a parameter's type or required-ness
 *   - Removing a property from a response/request schema
 *   - Adding a newly-required property (clients break)
 *
 * What this DOES NOT catch (by design — extractSchemaShape strips them):
 *   - Description / summary / example edits (doc-only changes)
 *   - Server URL changes between staging vs prod
 *   - Tag re-grouping
 *
 * To bump the snapshot intentionally (i.e. an API change is deliberate),
 * re-run with `UPDATE_OPENAPI_SNAPSHOT=1` and commit the new file. The
 * commit's diff serves as a structured changelog of API-shape changes
 * for that PR.
 *
 * No mocks: the test hits the real backend at the resolved API base URL.
 */

import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import { expect, test } from '@playwright/test';
import {
  classifyDiff,
  diffShapes,
  extractSchemaShape,
  hashCanonical,
  type OpenAPISchema,
} from '../fixtures/openapiDrift';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const SNAPSHOT_PATH = path.resolve(
  __dirname,
  '__snapshots__',
  'openapi-drift.snapshot.json',
);

interface DriftSnapshot {
  capturedAt: string;
  source: string;
  apiVersion: string | null;
  openapi: string;
  totals: { paths: number; operations: number; components: number };
  shapeHash: string;
  /**
   * Optional: when populated, the spec also surfaces the previous
   * shape so a future enhancement can run `diffShapes(prev, current)`
   * for full structural diagnostics. Today we keep snapshots small
   * by storing only the hash + totals.
   */
  shape?: ReturnType<typeof extractSchemaShape>;
}

/**
 * Resolve the API base URL the same way the auth fixtures do — see
 * fixtures/auth.ts for the canonical chain. Re-implemented inline so
 * this dimension spec has zero dependency on auth state.
 */
function resolveApiBase(): string {
  const explicit = process.env.E2E_API_BASE_URL;
  if (explicit) return explicit.replace(/\/$/, '');
  const proxy = process.env.VITE_PROXY_TARGET;
  if (proxy) return `${proxy.replace(/\/$/, '')}/api/v1`;
  const viteAbs = process.env.VITE_API_BASE_URL;
  if (viteAbs && viteAbs.startsWith('http')) return viteAbs.replace(/\/$/, '');
  const port = process.env.E2E_WEB_PORT ? '8001' : '8000';
  return `http://localhost:${port}/api/v1`;
}

test.describe('OpenAPI drift @dimension', () => {
  test.setTimeout(120_000);

  test('live schema shape-hash matches committed snapshot', async ({ request }) => {
    const apiBase = resolveApiBase();
    // Two probe paths — the server moved from `/schema/` (drf-spectacular
    // default) to `/openapi.json` at some point. Try the canonical first
    // and fall back so the test stays robust to either configuration.
    const candidates = [`${apiBase}/openapi.json`, `${apiBase}/schema/`];
    let body: OpenAPISchema | null = null;
    const triedUrls: string[] = [];
    for (const url of candidates) {
      triedUrls.push(url);
      const res = await request.get(url, {
        headers: { Accept: 'application/json' },
        timeout: 60_000,
      });
      if (!res.ok()) continue;
      const text = await res.text();
      try {
        const parsed = JSON.parse(text) as OpenAPISchema;
        if (parsed && typeof parsed === 'object' && parsed.paths) {
          body = parsed;
          break;
        }
      } catch {
        // intentional: non-JSON response from one candidate is a hard miss for that URL — fall through to the next candidate so the spec exhausts both /openapi.json and /schema/ before failing.
      }
    }
    expect(
      body,
      `Could not fetch a JSON OpenAPI document from any of: ${triedUrls.join(
        ', ',
      )}. Drift gate cannot run without the live schema.`,
    ).not.toBeNull();
    if (body === null) return;

    const shape = extractSchemaShape(body);
    const liveHash = hashCanonical(shape);

    const updateMode = process.env.UPDATE_OPENAPI_SNAPSHOT === '1';

    if (!fs.existsSync(SNAPSHOT_PATH)) {
      // Bootstrap the snapshot on first run — also acts as the "yes,
      // create this from scratch" path. Fail loudly so a missing file
      // can't silently pass in CI.
      const fresh: DriftSnapshot = {
        capturedAt: new Date().toISOString(),
        source: candidates[0],
        apiVersion: shape.apiVersion ?? null,
        openapi: shape.openapi,
        totals: shape.totals,
        shapeHash: liveHash,
      };
      if (updateMode) {
        fs.mkdirSync(path.dirname(SNAPSHOT_PATH), { recursive: true });
        fs.writeFileSync(SNAPSHOT_PATH, JSON.stringify(fresh, null, 2) + '\n');
        console.log(
          `[openapi-drift] snapshot bootstrapped at ${SNAPSHOT_PATH} (UPDATE_OPENAPI_SNAPSHOT=1).`,
        );
        return;
      }
      throw new Error(
        `[openapi-drift] snapshot missing at ${SNAPSHOT_PATH}. Run with ` +
          `UPDATE_OPENAPI_SNAPSHOT=1 to bootstrap. Live shapeHash=${liveHash}.`,
      );
    }

    const snapshot = JSON.parse(fs.readFileSync(SNAPSHOT_PATH, 'utf8')) as DriftSnapshot;
    expect(
      snapshot.shapeHash,
      'Snapshot file is missing shapeHash; the file is likely corrupt — re-run with UPDATE_OPENAPI_SNAPSHOT=1 to repair.',
    ).toMatch(/^[0-9a-f]{64}$/);

    if (snapshot.shapeHash === liveHash) {
      // Green path. Sanity-check totals didn't drift accidentally —
      // a hash collision is astronomically unlikely but we keep
      // an extra cardinality assertion as a cheap belt-and-braces.
      expect(shape.totals.paths).toBe(snapshot.totals.paths);
      expect(shape.totals.operations).toBe(snapshot.totals.operations);
      expect(shape.totals.components).toBe(snapshot.totals.components);
      return;
    }

    // ---- drift detected ----
    const summary: string[] = [
      `[openapi-drift] shape changed since the last snapshot was committed.`,
      `Snapshot: ${snapshot.shapeHash} (captured ${snapshot.capturedAt})`,
      `Live:     ${liveHash}`,
      `Totals:   prev paths=${snapshot.totals.paths}, ops=${snapshot.totals.operations}, components=${snapshot.totals.components}`,
      `          live paths=${shape.totals.paths}, ops=${shape.totals.operations}, components=${shape.totals.components}`,
    ];

    if (snapshot.shape) {
      // Detailed diff is only possible when the previous full shape was
      // committed. The default snapshot keeps only the hash to keep the
      // file small; a future enhancement can opt into the full shape
      // (totals × bytes ~= a few hundred kB).
      const diff = diffShapes(snapshot.shape, shape);
      const { breaking, nonBreaking } = classifyDiff(diff);
      summary.push('');
      summary.push(`Breaking changes (${breaking.length}):`);
      breaking.slice(0, 50).forEach((entry) => summary.push(`  - ${entry}`));
      if (breaking.length > 50) summary.push(`  …and ${breaking.length - 50} more.`);
      summary.push('');
      summary.push(`Non-breaking changes (${nonBreaking.length}):`);
      nonBreaking.slice(0, 25).forEach((entry) => summary.push(`  - ${entry}`));
      if (nonBreaking.length > 25) summary.push(`  …and ${nonBreaking.length - 25} more.`);
    }

    summary.push('');
    summary.push(
      `If this drift is intentional, re-run with UPDATE_OPENAPI_SNAPSHOT=1 ` +
        `and commit the updated snapshot.`,
    );

    if (updateMode) {
      const fresh: DriftSnapshot = {
        capturedAt: new Date().toISOString(),
        source: candidates[0],
        apiVersion: shape.apiVersion ?? null,
        openapi: shape.openapi,
        totals: shape.totals,
        shapeHash: liveHash,
      };
      fs.writeFileSync(SNAPSHOT_PATH, JSON.stringify(fresh, null, 2) + '\n');
      console.log(
        `[openapi-drift] snapshot updated (UPDATE_OPENAPI_SNAPSHOT=1).\n${summary.join('\n')}`,
      );
      return;
    }

    throw new Error(summary.join('\n'));
  });
});
