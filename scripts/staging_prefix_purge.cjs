#!/usr/bin/env node
// Phase 226 E2 — Nightly staging-side prefix-purge cron (safety net).
//
// `createdResources` (the per-test fixture) tears down resources after
// each spec, but a hard test crash (process killed, runner OOM) can leave
// rows behind. The prefix-purge cron is the safety net: it queries the
// staging API for any e2e-prefixed resource older than the configured
// age and bulk-cancels / soft-deletes them.
//
// Why a separate script (not a Django management command): we want this
// runnable from a GitHub Actions cron with nothing more than `node` and
// the staging API key — no Django bootstrap, no SSH into the cluster, no
// per-pod kubectl exec. The script is self-contained and idempotent.
//
// Resource families purged (must mirror createdResources teardownRequestFor):
//   - asset    → DELETE  (soft to RETIRED)
//   - contract → DELETE  (soft to RETIRED)
//   - listing  → DELETE  (soft to DELETED)
//   - dataset  → DELETE  (HARD)
//   - order    → POST cancel (soft to CANCELLED)
//   - user     → DELETE (conditional soft/hard; backend-resolved)
//
// CLI:
//   node scripts/staging_prefix_purge.cjs
//        --base=URL                   (required: staging API base, e.g. https://api.stagingmeshant-internal.example.com/api/v1)
//        --token=TOKEN                (required: bearer token of an admin user)
//        --prefix=STR                 (default: "e2e-")
//        --older-than-minutes=N       (default: 60; rows newer than this are skipped — never delete in-flight test data)
//        --max-per-type=N             (default: 500; safety cap per family per run)
//        [--dry-run]                  (list candidates without mutating)
//        [--json]                     (machine-readable output)
//
// Exit codes:
//   0  — purge completed (with or without leftovers; always idempotent-on-rerun)
//   1  — at least one resource family hit a non-recoverable error (e.g. 401)
//   2  — config error (missing required flag, malformed URL, etc.)

'use strict';

const DEFAULT_PREFIX = 'e2e-';
const DEFAULT_OLDER_THAN_MIN = 60;
const DEFAULT_MAX_PER_TYPE = 500;

// Resource families. Order matches `createdResources` TEARDOWN_ORDER —
// purge children before parents so cascade-delete on a parent doesn't
// 404 the child mid-list.
const FAMILIES = [
  { type: 'order',    listPath: '/marketplace/orders/',  deletePath: (id) => `/marketplace/orders/${id}/cancel/`, method: 'POST' },
  { type: 'dataset',  listPath: '/datasets/',            deletePath: (id) => `/datasets/${id}/`,                  method: 'DELETE' },
  { type: 'listing',  listPath: '/marketplace/listings/', deletePath: (id) => `/marketplace/listings/${id}/`,     method: 'DELETE' },
  { type: 'contract', listPath: '/contracts/',           deletePath: (id) => `/contracts/${id}/`,                 method: 'DELETE' },
  { type: 'asset',    listPath: '/assets/',              deletePath: (id) => `/assets/${id}/`,                    method: 'DELETE' },
  { type: 'user',     listPath: '/users/',               deletePath: (id) => `/users/${id}/`,                     method: 'DELETE' },
];

// ---------------------------------------------------- pure logic

/** Coerce a `--older-than-minutes=N` flag against `now` into an ISO cutoff. */
function cutoffIsoFor(now, minutes) {
  const cutoff = new Date(now.getTime() - minutes * 60 * 1000);
  return cutoff.toISOString();
}

/**
 * A row is purgeable when:
 *   * its name (or title or username, depending on shape) starts with prefix
 *   * its created_at is older than the cutoff (so we never delete in-flight
 *     test data from a still-running spec)
 *   * its status is NOT already a tombstone (RETIRED / DELETED / DISABLED /
 *     CANCELLED) — those rows are already gone; deleting them again is a
 *     wasted call.
 *
 * Returns `true` for purge, `false` for skip. Pure & deterministic so the
 * unit suite can pin every branch.
 */
function shouldPurge(row, prefix, cutoffIso) {
  if (!row || typeof row !== 'object') return false;
  const name = row.name ?? row.title ?? row.username ?? row.email ?? '';
  if (typeof name !== 'string' || !name.startsWith(prefix)) return false;
  const createdAt = row.created_at ?? row.created ?? row.date_joined ?? null;
  if (typeof createdAt === 'string' && createdAt > cutoffIso) return false;
  const status = (row.status ?? '').toString().toUpperCase();
  if (['RETIRED', 'DELETED', 'DISABLED', 'CANCELLED'].includes(status)) return false;
  return true;
}

/** Extract candidate ids from a list-endpoint response. The serializer
 * shape is paginated: `{ count, next, previous, results: [...] }`. We
 * also accept a bare array for forwards-compat. */
function extractCandidates(payload, prefix, cutoffIso) {
  const rows = Array.isArray(payload)
    ? payload
    : Array.isArray(payload?.results) ? payload.results : [];
  return rows.filter((row) => shouldPurge(row, prefix, cutoffIso))
             .map((row) => row.id)
             .filter((id) => id != null);
}

// ---------------------------------------------------- argv parsing

function parseArgs(argv) {
  const args = {
    base: null,
    token: null,
    prefix: DEFAULT_PREFIX,
    olderThanMinutes: DEFAULT_OLDER_THAN_MIN,
    maxPerType: DEFAULT_MAX_PER_TYPE,
    dryRun: false,
    json: false,
  };
  for (const a of argv.slice(2)) {
    if (a.startsWith('--base=')) args.base = a.slice('--base='.length);
    else if (a.startsWith('--token=')) args.token = a.slice('--token='.length);
    else if (a.startsWith('--prefix=')) args.prefix = a.slice('--prefix='.length);
    else if (a.startsWith('--older-than-minutes=')) args.olderThanMinutes = Number(a.slice('--older-than-minutes='.length));
    else if (a.startsWith('--max-per-type=')) args.maxPerType = Number(a.slice('--max-per-type='.length));
    else if (a === '--dry-run') args.dryRun = true;
    else if (a === '--json') args.json = true;
    else throw new Error(`unknown arg: ${a}`);
  }
  return args;
}

function validateArgs(args) {
  if (!args.base) return 'missing required --base=URL';
  if (!args.token && !args.dryRun) return 'missing required --token=TOKEN (or pass --dry-run)';
  if (!Number.isFinite(args.olderThanMinutes) || args.olderThanMinutes < 0) {
    return `invalid --older-than-minutes: ${args.olderThanMinutes}`;
  }
  if (!Number.isFinite(args.maxPerType) || args.maxPerType < 1) {
    return `invalid --max-per-type: ${args.maxPerType}`;
  }
  try {
    // eslint-disable-next-line no-new
    new URL(args.base);
  } catch (e) {
    return `invalid --base URL: ${args.base}`;
  }
  return null;
}

// ---------------------------------------------------- HTTP loop

async function purgeFamily(family, args, deps) {
  const fetchImpl = deps.fetchImpl || fetch;
  const cutoffIso = cutoffIsoFor(deps.now || new Date(), args.olderThanMinutes);
  const headers = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${args.token}`,
  };
  const base = args.base.replace(/\/$/, '');
  const listUrl = `${base}${family.listPath}?page_size=${args.maxPerType}`;
  let listRes;
  try {
    listRes = await fetchImpl(listUrl, { headers });
  } catch (err) {
    return { type: family.type, fatal: true, error: `list-fetch threw: ${err.message}`, attempted: 0, succeeded: 0, failures: [] };
  }
  if (listRes.status === 401 || listRes.status === 403) {
    return { type: family.type, fatal: true, error: `list ${listRes.status}`, attempted: 0, succeeded: 0, failures: [] };
  }
  if (!listRes.ok) {
    // intentional: best-effort body read for diagnostic context — the failure is the non-OK status, not the read.
    const body = await listRes.text().catch(() => '');
    return { type: family.type, fatal: false, error: `list ${listRes.status} ${body.slice(0, 200)}`, attempted: 0, succeeded: 0, failures: [] };
  }
  // intentional: best-effort json parse; bad payload is not the cron's pass/fail decision — we report it and move on.
  const payload = await listRes.json().catch(() => null);
  const candidates = extractCandidates(payload, args.prefix, cutoffIso);
  let attempted = 0;
  let succeeded = 0;
  const failures = [];
  if (args.dryRun) {
    return { type: family.type, fatal: false, error: null, attempted: candidates.length, succeeded: 0, failures: [], candidates };
  }
  for (const id of candidates) {
    attempted++;
    const url = `${base}${family.deletePath(id)}`;
    try {
      const res = await fetchImpl(url, { method: family.method, headers });
      if (res.ok || res.status === 404) {
        succeeded++;
        continue;
      }
      // intentional: best-effort body read for diagnostic context only.
      const body = await res.text().catch(() => '');
      failures.push(`${family.type}/${id} → ${res.status} ${body.slice(0, 200)}`);
    } catch (err) {
      failures.push(`${family.type}/${id} threw: ${err.message}`);
    }
  }
  return { type: family.type, fatal: false, error: null, attempted, succeeded, failures };
}

async function run(argv, deps = {}) {
  let args;
  try {
    args = parseArgs(argv);
  } catch (err) {
    return { exitCode: 2, error: err.message, result: null };
  }
  const configErr = validateArgs(args);
  if (configErr) return { exitCode: 2, error: configErr, result: null };

  const familyResults = [];
  let anyFatal = false;
  for (const family of FAMILIES) {
    const r = await purgeFamily(family, args, deps);
    familyResults.push(r);
    if (r.fatal) anyFatal = true;
  }
  const totals = familyResults.reduce(
    (acc, r) => ({
      attempted: acc.attempted + r.attempted,
      succeeded: acc.succeeded + r.succeeded,
      failures: acc.failures + r.failures.length,
    }),
    { attempted: 0, succeeded: 0, failures: 0 },
  );
  return {
    exitCode: anyFatal ? 1 : 0,
    error: null,
    result: { args: { ...args, token: args.token ? '***' : null }, families: familyResults, totals },
  };
}

// ---------------------------------------------------- CLI entry

if (require.main === module) {
  (async () => {
    const outcome = await run(process.argv);
    if (outcome.error) {
      process.stderr.write(`staging_prefix_purge: ${outcome.error}\n`);
      process.exit(outcome.exitCode);
    }
    const args = parseArgs(process.argv);
    if (args.json) {
      process.stdout.write(JSON.stringify(outcome.result, null, 2) + '\n');
    } else {
      const r = outcome.result;
      process.stdout.write(
        `staging_prefix_purge: ${args.dryRun ? 'DRY-RUN' : 'PURGE'} ` +
        `attempted=${r.totals.attempted} succeeded=${r.totals.succeeded} failures=${r.totals.failures}\n`,
      );
      for (const f of r.families) {
        if (f.fatal) {
          process.stdout.write(`  ${f.type}: FATAL ${f.error}\n`);
        } else {
          process.stdout.write(`  ${f.type}: attempted=${f.attempted} succeeded=${f.succeeded}${f.failures.length ? ` failures=${f.failures.length}` : ''}\n`);
        }
      }
    }
    process.exit(outcome.exitCode);
  })();
}

module.exports = {
  cutoffIsoFor,
  shouldPurge,
  extractCandidates,
  parseArgs,
  validateArgs,
  purgeFamily,
  run,
  FAMILIES,
};
