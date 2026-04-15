/**
 * exportUtils tests — 223.4.3.
 *
 * Covers CSV generation correctness (headers, RFC-4180 escaping, null
 * handling, explicit column ordering) and the Blob-based download
 * mechanics (URL.createObjectURL, anchor click, URL.revokeObjectURL
 * cleanup). jsdom provides DOM APIs but we shim the URL lifecycle so
 * we can assert on the MIME type and object-URL churn.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  buildCSV,
  exportToCSV,
  exportToJSON,
} from './exportUtils';

describe('buildCSV', () => {
  it('emits a header row plus one row per object', () => {
    const csv = buildCSV([
      { id: '1', name: 'Alpha' },
      { id: '2', name: 'Beta' },
    ]);
    expect(csv).toBe('id,name\r\n1,Alpha\r\n2,Beta');
  });

  it('quotes values containing commas', () => {
    const csv = buildCSV([{ name: 'Smith, John' }]);
    expect(csv).toBe('name\r\n"Smith, John"');
  });

  it('escapes embedded double-quotes by doubling them (RFC 4180)', () => {
    const csv = buildCSV([{ name: 'He said "hi"' }]);
    expect(csv).toBe('name\r\n"He said ""hi"""');
  });

  it('quotes values containing newlines', () => {
    const csv = buildCSV([{ body: 'line1\nline2' }]);
    expect(csv).toBe('body\r\n"line1\nline2"');
  });

  it('serialises null and undefined to empty cells', () => {
    const csv = buildCSV([{ a: null, b: undefined, c: 'x' }]);
    expect(csv).toBe('a,b,c\r\n,,x');
  });

  it('stringifies numbers and booleans losslessly', () => {
    const csv = buildCSV([{ n: 0, f: 1.5, b: true, t: false }]);
    expect(csv).toBe('n,f,b,t\r\n0,1.5,true,false');
  });

  it('honours explicit columns in order (and drops un-listed keys)', () => {
    const csv = buildCSV(
      [{ a: 1, b: 2, c: 3 }],
      { columns: [{ key: 'c' }, { key: 'a' }] },
    );
    expect(csv).toBe('c,a\r\n3,1');
  });

  it('uses column labels in the header row', () => {
    const csv = buildCSV(
      [{ a: 1 }],
      { columns: [{ key: 'a', label: 'Alpha' }] },
    );
    expect(csv).toBe('Alpha\r\n1');
  });

  it('accepts a custom accessor function', () => {
    const csv = buildCSV(
      [{ first: 'Ada', last: 'Lovelace' }],
      {
        columns: [
          {
            key: 'full',
            label: 'Full Name',
            accessor: (row: { first: string; last: string }) =>
              `${row.first} ${row.last}`,
          },
        ],
      },
    );
    expect(csv).toBe('Full Name\r\nAda Lovelace');
  });

  it('returns just a header when data is empty and columns are given', () => {
    const csv = buildCSV([], { columns: [{ key: 'a' }] });
    expect(csv).toBe('a');
  });

  it('returns an empty string when data is empty and no columns are given', () => {
    expect(buildCSV([])).toBe('');
  });
});

describe('exportToCSV / exportToJSON download mechanics', () => {
  const originalCreate = URL.createObjectURL;
  const originalRevoke = URL.revokeObjectURL;
  let created: Blob[];
  let revoked: string[];

  beforeEach(() => {
    created = [];
    revoked = [];
    (URL as unknown as { createObjectURL: (b: Blob) => string }).createObjectURL =
      (blob: Blob) => {
        created.push(blob);
        return `blob:mock/${created.length}`;
      };
    (URL as unknown as { revokeObjectURL: (u: string) => void }).revokeObjectURL =
      (url: string) => {
        revoked.push(url);
      };
  });

  afterEach(() => {
    URL.createObjectURL = originalCreate;
    URL.revokeObjectURL = originalRevoke;
    vi.restoreAllMocks();
  });

  it('exportToCSV creates a Blob with text/csv MIME and triggers a click', async () => {
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});

    exportToCSV([{ a: 1 }], 'rows.csv');

    expect(clickSpy).toHaveBeenCalledTimes(1);
    expect(created).toHaveLength(1);
    expect(created[0].type).toMatch(/text\/csv/);
    const text = await created[0].text();
    // Blob is prefixed with a UTF-8 BOM so Excel opens UTF-8 CSV
    // files with the correct encoding. Strip it before asserting.
    expect(text.replace(/^\uFEFF/, '')).toBe('a\r\n1');

    // Revocation is scheduled via microtask/setTimeout; flush it.
    await new Promise((r) => setTimeout(r, 0));
    expect(revoked).toHaveLength(1);
  });

  it('exportToCSV appends .csv if the filename lacks it', () => {
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    const anchorSpy = vi.spyOn(document, 'createElement');
    exportToCSV([{ a: 1 }], 'rows');
    const call = anchorSpy.mock.results.find(
      (r) => (r.value as HTMLElement).tagName === 'A',
    );
    expect((call?.value as HTMLAnchorElement).download).toBe('rows.csv');
  });

  it('exportToJSON creates a Blob with application/json MIME and pretty-prints', async () => {
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    exportToJSON([{ a: 1, b: 'x' }], 'data.json');
    expect(created[0].type).toMatch(/application\/json/);
    const text = await created[0].text();
    expect(text).toContain('"a": 1');
    expect(text).toContain('"b": "x"');
  });
});
