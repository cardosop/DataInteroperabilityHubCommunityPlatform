/**
 * useDebouncedValue Hook
 * Returns a debounced version of the given value.
 * Useful for search inputs to reduce API calls.
 */

import { useEffect, useState } from 'react';

/**
 * Debounce a value by the specified delay.
 *
 * @param value - The value to debounce
 * @param delayMs - Delay in milliseconds
 * @returns The debounced value
 */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);

  return debouncedValue;
}
