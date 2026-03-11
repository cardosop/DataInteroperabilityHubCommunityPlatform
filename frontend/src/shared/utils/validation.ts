/**
 * Validation Utilities
 * Shared validation helpers for forms
 */

const UUID_REGEX =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

/**
 * Validates that a string is a valid UUID v4 format.
 *
 * @param str - String to validate
 * @returns true if valid UUID format, false otherwise
 */
export function isValidUUID(str: string | null | undefined): boolean {
  if (str == null || typeof str !== 'string') return false;
  const trimmed = str.trim();
  if (trimmed === '') return false;
  return UUID_REGEX.test(trimmed);
}
