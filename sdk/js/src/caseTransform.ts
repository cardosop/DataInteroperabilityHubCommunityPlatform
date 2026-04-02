/**
 * Case Transform Utilities — Phase 118C (D60)
 *
 * Deep key transforms for request/response interceptors:
 * - camelToSnake: JS client → Python API (request bodies)
 * - snakeToCamel: Python API → JS client (response bodies)
 */

/**
 * Convert a single camelCase string to snake_case.
 *
 * "firstName" → "first_name"
 * "alreadySnake" → "already_snake"
 * "myURL" → "my_url"
 *
 * Note: consecutive uppercase runs like "HTMLParser" become
 * "htmlparser" (no split).  This is intentional — the API
 * uses standard camelCase keys, not acronym-heavy names.
 */
export function camelToSnakeKey(key: string): string {
  return key.replace(/([a-z0-9])([A-Z])/g, '$1_$2').toLowerCase();
}

/**
 * Convert a single snake_case string to camelCase.
 *
 * "first_name" → "firstName"
 * "already_camel" → "alreadyCamel"
 */
export function snakeToCamelKey(key: string): string {
  return key.replace(/_([a-z0-9])/g, (_, char) => char.toUpperCase());
}

/**
 * Deep-convert all object keys from camelCase to snake_case.
 *
 * Recursively handles nested objects and arrays.
 * Primitives pass through unchanged.
 */
export function camelToSnake(data: any): any {
  if (data === null || data === undefined) return data;
  if (typeof data !== 'object') return data;
  if (Array.isArray(data)) return data.map(camelToSnake);
  if (data instanceof Date) return data;
  if (data instanceof FormData) return data;

  const result: Record<string, any> = {};
  for (const [key, value] of Object.entries(data)) {
    result[camelToSnakeKey(key)] = camelToSnake(value);
  }
  return result;
}

/**
 * Deep-convert all object keys from snake_case to camelCase.
 *
 * Recursively handles nested objects and arrays.
 * Primitives pass through unchanged.
 */
export function snakeToCamel(data: any): any {
  if (data === null || data === undefined) return data;
  if (typeof data !== 'object') return data;
  if (Array.isArray(data)) return data.map(snakeToCamel);
  if (data instanceof Date) return data;

  const result: Record<string, any> = {};
  for (const [key, value] of Object.entries(data)) {
    result[snakeToCamelKey(key)] = snakeToCamel(value);
  }
  return result;
}
