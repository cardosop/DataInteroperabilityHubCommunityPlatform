/**
 * exportUtils — 223.4.1.
 *
 * Client-side CSV / JSON download helpers that serialise an array of
 * row objects to a Blob, create an object-URL, and trigger a synthetic
 * anchor click. No server round-trip — suitable for "export this page"
 * buttons on list / detail views. CSV follows RFC 4180 escaping rules
 * (CRLF line endings, double-quote wrapping, embedded-quote doubling)
 * so the output opens cleanly in Excel, Numbers, Sheets, and pandas.
 */

export interface CSVColumn<T> {
  /** Property key on each row; also the default header label. */
  key: string;
  /** Optional human-readable header; defaults to `key`. */
  label?: string;
  /** Optional custom value extractor; defaults to `row[key]`. */
  accessor?: (row: T) => unknown;
}

export interface BuildCSVOptions<T> {
  /**
   * Explicit column definitions — when provided, locks header ordering
   * and drops any un-listed keys. When omitted, the header is derived
   * from the union of keys on the first row (sufficient for ad-hoc
   * exports where the row shape is homogeneous).
   */
  columns?: Array<CSVColumn<T>>;
}

const QUOTE_SENTINEL = /[",\r\n]/;

/**
 * Serialise a single cell value into a CSV-safe string per RFC 4180.
 * - `null` / `undefined` collapse to an empty string.
 * - Objects and arrays are JSON-stringified (users can override via
 *   `accessor` when they want a flat representation).
 * - Strings with comma, quote, CR, or LF get wrapped in double-quotes;
 *   interior quotes are doubled.
 */
function formatCell(value: unknown): string {
  if (value === null || value === undefined) return '';
  let raw: string;
  if (typeof value === 'string') {
    raw = value;
  } else if (typeof value === 'number' || typeof value === 'boolean') {
    raw = String(value);
  } else if (value instanceof Date) {
    raw = value.toISOString();
  } else {
    raw = JSON.stringify(value);
  }
  if (QUOTE_SENTINEL.test(raw)) {
    return `"${raw.replace(/"/g, '""')}"`;
  }
  return raw;
}

/**
 * Build the CSV text body for `data`. Pure function — no DOM side
 * effects — so it's testable in isolation and reusable for upload
 * flows (e.g. posting the CSV back to the API).
 */
export function buildCSV<T extends Record<string, unknown>>(
  data: T[],
  options: BuildCSVOptions<T> = {},
): string {
  const columns: Array<CSVColumn<T>> =
    options.columns ??
    (data.length > 0
      ? Object.keys(data[0] as object).map((key) => ({ key }))
      : []);

  if (columns.length === 0) return '';

  const header = columns
    .map((col) => formatCell(col.label ?? col.key))
    .join(',');

  if (data.length === 0) return header;

  const rows = data.map((row) =>
    columns
      .map((col) => {
        const value = col.accessor
          ? col.accessor(row)
          : (row as Record<string, unknown>)[col.key];
        return formatCell(value);
      })
      .join(','),
  );

  return [header, ...rows].join('\r\n');
}

/**
 * Shared download-trigger plumbing — creates a Blob, wraps it in an
 * object URL, synthesises an `<a>` click, then revokes the URL on the
 * next tick so memory is released even if the user cancels the save
 * dialog. Uses `document.body.appendChild` so Firefox (which ignores
 * programmatic clicks on un-parented anchors) fires the download.
 */
function triggerDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = 'noopener';
  anchor.style.display = 'none';
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  // Revoke on next tick so the browser has a chance to start the download.
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

function ensureExtension(filename: string, ext: string): string {
  const suffix = ext.startsWith('.') ? ext : `.${ext}`;
  return filename.toLowerCase().endsWith(suffix.toLowerCase())
    ? filename
    : `${filename}${suffix}`;
}

export function exportToCSV<T extends Record<string, unknown>>(
  data: T[],
  filename: string,
  options: BuildCSVOptions<T> = {},
): void {
  const csv = buildCSV(data, options);
  // BOM makes Excel open UTF-8 CSVs with correct character encoding.
  const blob = new Blob(['\uFEFF', csv], { type: 'text/csv;charset=utf-8' });
  triggerDownload(blob, ensureExtension(filename, '.csv'));
}

export function exportToJSON(data: unknown, filename: string): void {
  const body = JSON.stringify(data, null, 2);
  const blob = new Blob([body], { type: 'application/json;charset=utf-8' });
  triggerDownload(blob, ensureExtension(filename, '.json'));
}
