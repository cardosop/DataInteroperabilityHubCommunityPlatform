/**
 * Phase 228 (REQ-LIN-005, 228.0.16) — lineage E2E fixture helpers.
 *
 * The ``seedLineageDag(page, n=3)`` helper seeds an N-contract DAG via
 * the contract-create API: ``root → mid → leaf`` (n=3) by default.
 * Each contract carries a ``lineage.contracts[]`` reference so the
 * post-save signal handler maintains the relational ``LineageEdge``
 * index — both the JSON-fallback read path and the relational read
 * path return the same shape, so the E2E spec can assert content
 * exactly without branching on read-path internals.
 *
 * The helper is **strict by default** — any non-2xx from the API
 * raises so the E2E test fails fast at setup rather than producing a
 * misleading "0 nodes rendered" assertion.
 */
import type { Page } from '@playwright/test';

const API_BASE = process.env.PLAYWRIGHT_API_BASE || '/api/v1';

export interface LineageDagResult {
  rootId: string;
  midId: string;
  leafId: string;
  /** Every contract id created, ordered root → … → leaf. */
  ids: string[];
}

/** Build a minimal valid ODCS YAML body. The ``lineage`` key is the
 *  Meshant extension that the engine reads into ``hub_contract_json.lineage``
 *  on save. */
function buildOdcsYaml(opts: {
  id: string;
  name: string;
  upstreamContractIds?: string[];
}): string {
  const lineage =
    (opts.upstreamContractIds ?? []).length === 0
      ? ''
      : `\n  lineage:\n    contracts:\n${(opts.upstreamContractIds ?? [])
          .map(
            (cid) =>
              `      - source_contract: ${cid}\n        target_contract: self\n        edge_type: reference`,
          )
          .join('\n')}`;
  return [
    'kind: DataContract',
    'apiVersion: v3.0.2',
    `id: ${opts.id}`,
    `name: ${opts.name}`,
    'version: 1.0.0',
    'status: active',
    'schema:',
    `  - name: ${opts.name}`,
    '    fields:',
    '      - name: id',
    '        type: string',
    `info:${lineage}`,
  ].join('\n');
}

async function postContract(
  page: Page,
  body: string,
  authHeaders: Record<string, string>,
): Promise<string> {
  const res = await page.request.post(`${API_BASE}/contracts/`, {
    headers: { 'Content-Type': 'application/json', ...authHeaders },
    data: {
      original_raw: body,
      original_spec_type: 'ODCS',
      original_format: 'YAML',
    },
  });
  if (!res.ok()) {
    const text = await res.text().catch(() => '');
    throw new Error(
      `seedLineageDag: POST ${API_BASE}/contracts/ failed ${res.status()}. ` +
        `Body: ${text.slice(0, 400)}.`,
    );
  }
  const data = (await res.json()) as { id?: string };
  if (!data.id) {
    throw new Error(
      `seedLineageDag: POST returned 2xx with no id; body=${JSON.stringify(data).slice(0, 200)}.`,
    );
  }
  return data.id;
}

/**
 * Seed an N-contract linear DAG (``c0 → c1 → … → cN-1``) via the
 * contract-create API and return their ids in topological order.
 *
 * Default ``n=3`` produces the canonical ``root → mid → leaf`` shape
 * the ``REQ-LIN-005`` spec asserts in the strict-content test.
 *
 * Auth: extracts the access token from the page's existing storage
 * state — the test must call ``loginUser(page, user)`` BEFORE this
 * fixture so the cookies / Bearer header are populated.
 */
export async function seedLineageDag(
  page: Page,
  n: number = 3,
  opts: { accessToken?: string } = {},
): Promise<LineageDagResult> {
  if (n < 2) {
    throw new Error(`seedLineageDag: n must be >= 2; got ${n}`);
  }

  const authHeaders: Record<string, string> = {};
  if (opts.accessToken) {
    authHeaders.Authorization = `Bearer ${opts.accessToken}`;
  }

  // Build a unique id-prefix per run so reruns of the spec on a shared
  // staging DB do not collide with each other.
  const runStamp = Date.now().toString(36);

  const ids: string[] = [];
  for (let i = 0; i < n; i++) {
    const idPrefix = `e2e-lin-${runStamp}-${i}`;
    const body = buildOdcsYaml({
      id: idPrefix,
      name: idPrefix,
      upstreamContractIds: i === 0 ? [] : [ids[i - 1]],
    });
    ids.push(await postContract(page, body, authHeaders));
  }

  return {
    rootId: ids[0],
    midId: ids[Math.floor(n / 2)],
    leafId: ids[n - 1],
    ids,
  };
}
