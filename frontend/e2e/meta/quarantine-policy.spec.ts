/**
 * Meta-test: validates that the @quarantine policy is wired correctly.
 *
 * If the regex in `playwright.mvp.config.ts` (`grepInvert: /@quarantine\b/`)
 * drifts or is removed, a quarantined spec would re-enter the default MVP run
 * and block `main` on every merge. This test guards that wiring by reading
 * the config on disk and asserting the filter is present.
 *
 * Runs in the default MVP run (no JOURNEY- tag, no @quarantine tag → admitted
 * by the title allowlist). Pure Node — no browser, no backend — so it's free.
 */

import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { expect, test } from '@playwright/test';

// ESM-compatible `__dirname`. The frontend package.json has `"type": "module"`
// and tsconfig `"module": "ESNext"`, so the CommonJS `__dirname` global is
// undefined at runtime — using it would throw ReferenceError before any
// assertion runs. Matches the project convention (see JOURNEY-DPO-001 and
// JOURNEY-CONTRACT-V310-LIFECYCLE).
const __currentDir = dirname(fileURLToPath(import.meta.url));

const MVP_CONFIG_PATH = resolve(__currentDir, '..', '..', 'playwright.mvp.config.ts');
const QUARANTINE_CONFIG_PATH = resolve(
  __currentDir,
  '..',
  '..',
  'playwright.mvp.quarantine.config.ts',
);

test.describe('Quarantine policy wiring', () => {
  test('default MVP config excludes @quarantine via grepInvert', () => {
    const source = readFileSync(MVP_CONFIG_PATH, 'utf8');
    // grepInvert must target the @quarantine token with a word boundary so
    // unrelated strings like "@quarantine-docs" don't accidentally match.
    expect(source).toMatch(/grepInvert:\s*\/@quarantine\\b\//);
  });

  test('dedicated quarantine config runs ONLY @quarantine-tagged specs', () => {
    const source = readFileSync(QUARANTINE_CONFIG_PATH, 'utf8');
    expect(source).toMatch(/grep:\s*\/@quarantine\\b\//);
    // The base config's grepInvert must be nullified so the quarantine run
    // is not cancelled by its own filter.
    expect(source).toMatch(/grepInvert:\s*undefined/);
  });

  test('nightly quarantine workflow exists and points at staging', () => {
    const workflowPath = resolve(
      __currentDir,
      '..',
      '..',
      '..',
      '.github',
      'workflows',
      'playwright-mvp-quarantine-nightly.yml',
    );
    const yaml = readFileSync(workflowPath, 'utf8');
    expect(yaml).toMatch(/playwright\.mvp\.quarantine\.config\.ts/);
    expect(yaml).toMatch(/staging\.meshant\.com/);
    // Advisory-only — failing quarantine runs must not block the nightly job.
    expect(yaml).toMatch(/continue-on-error:\s*true/);
  });
});
