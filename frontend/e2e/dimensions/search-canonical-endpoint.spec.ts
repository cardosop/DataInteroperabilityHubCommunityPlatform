/**
 * Phase 273.1.6 — Search canonical endpoint drift guard.
 *
 * Asserts that no frontend bundle references the deprecated
 * ``/api/v1/search/`` prefix. All search traffic must route through
 * the canonical UnifiedSearchView at ``/api/search/``.
 *
 * This spec is a dimension test (not a journey) — it runs in CI
 * on every PR touching search/semantic code and fails if the
 * deprecated endpoint reference regresses.
 */
import { test, expect } from '@playwright/test';
import * as fs from 'node:fs';
import * as path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const FRONTEND_SRC = path.resolve(__dirname, '../../src');

/** Recursively collect .ts and .tsx files under a directory. */
function collectSourceFiles(dir: string): string[] {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const files: string[] = [];
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory() && entry.name !== '__pycache__' && entry.name !== 'node_modules') {
      files.push(...collectSourceFiles(full));
    } else if (entry.name.endsWith('.ts') || entry.name.endsWith('.tsx')) {
      files.push(full);
    }
  }
  return files;
}

test.describe('Search canonical endpoint drift', () => {
  const DEPRECATED = '/api/v1/search/';
  const CANONICAL = '/api/search/';

  test('no frontend source references deprecated /api/v1/search/', () => {
    const files = collectSourceFiles(FRONTEND_SRC);
    const violations: { file: string; line: string }[] = [];

    for (const file of files) {
      const content = fs.readFileSync(file, 'utf-8');
      const lines = content.split('\n');
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        // Skip comments and test files that deliberately reference
        // the deprecated endpoint for migration validation.
        if (line.trim().startsWith('//') || line.trim().startsWith('*')) continue;
        if (line.includes(DEPRECATED)) {
          // Allow the searchService.ts migration comment and this spec itself.
          if (file.includes('searchService.ts') && line.includes('formerly called')) continue;
          if (file.includes('search-canonical-endpoint.spec.ts')) continue;
          violations.push({ file, line: `${i + 1}: ${line.trim()}` });
        }
      }
    }

    expect(violations).toEqual([]);
  });

  test('searchService uses canonical /api/search/ endpoint', () => {
    const servicePath = path.join(
      FRONTEND_SRC,
      'features/search/services/searchService.ts',
    );
    expect(fs.existsSync(servicePath)).toBeTruthy();
    const content = fs.readFileSync(servicePath, 'utf-8');
    expect(content).toContain(CANONICAL);
    // The deprecated path must not appear outside of the migration comment.
    const nonCommentLines = content
      .split('\n')
      .filter((l) => !l.trim().startsWith('//') && !l.trim().startsWith('*'));
    for (const line of nonCommentLines) {
      expect(line).not.toContain(DEPRECATED);
    }
  });
});
