import { useEffect, useRef, type RefObject } from 'react';

/**
 * Stores the latest value in a ref so effects/callbacks can read the
 * current value without re-running when the parent passes inline
 * functions.
 *
 * The assignment lives in an effect (NOT during render) — the
 * react-hooks/refs compiler rule forbids render-time ref writes, and
 * the deferred write is equivalent for every consumer (the ref is only
 * ever read from effects or event handlers, never during render).
 */
export function useLatestRef<T>(value: T): RefObject<T> {
  const ref = useRef(value);
  useEffect(() => {
    ref.current = value;
  }, [value]);
  return ref;
}
