// Root-level vitest config — single-project pattern.
//
// Vitest is owned by the frontend workspace (frontend/package.json), but users
// commonly invoke `npx vitest` from the repo root. Without a config here,
// vitest at the root falls back to its compiled-in defaults (environment=node,
// no setup, default include glob) and sweeps up Playwright e2e specs alongside
// the src unit tests — producing thousands of spurious "document is not
// defined" / "test.describe() called outside Playwright" failures.
//
// Why `test.projects` instead of a `vitest.workspace.ts`:
//   `defineWorkspace` was deprecated in vitest 3 and REMOVED in vitest 4. When
//   `npx vitest` from the repo root has no local install, npx fetches the
//   latest vitest from the registry — currently 4.x — which silently ignores
//   any workspace file. The `test.projects` field in a regular config works in
//   vitest 3+ and is forward-compatible.
//
// Pointing projects at './frontend' makes vitest treat that directory as the
// project: it loads frontend/vitest.config.ts in its own context (so __dirname
// resolves to frontend/, aliases work, jsdom env is applied) regardless of
// the launching cwd or the vitest version that's actually executing.
import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    projects: ['./frontend'],
  },
});
