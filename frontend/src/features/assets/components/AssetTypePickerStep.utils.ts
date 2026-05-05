/** Pure helper used by route-level callers to skip the picker via query string. */
export function shouldSkipTypePicker(search: string): boolean {
  if (!search) return false;
  // Strip leading `?` so callers can pass either `location.search` or a bare query string.
  const cleaned = search.startsWith('?') ? search.slice(1) : search;
  if (!cleaned) return false;
  const params = new URLSearchParams(cleaned);
  return params.get('skip') === 'picker';
}
