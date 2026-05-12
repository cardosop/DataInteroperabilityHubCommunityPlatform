/**
 * Phase 276.B.114 — Global 429 retry pattern.
 *
 * Returns a retry function with exponential backoff. Reads the
 * Retry-After header from 429 responses and waits before retrying.
 */
import { useCallback, useRef } from 'react';

export function useRetryAfter() {
  const controllerRef = useRef<AbortController | null>(null);

  const retry = useCallback(
    async (
      fn: (signal: AbortSignal) => Promise<Response>,
      maxRetries = 3,
    ): Promise<Response> => {
      controllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;

      let lastResponse: Response | undefined;

      for (let attempt = 0; attempt <= maxRetries; attempt++) {
        if (controller.signal.aborted) break;

        const response = await fn(controller.signal);
        lastResponse = response;

        if (response.status !== 429) return response;

        const retryAfter = parseInt(response.headers.get('Retry-After') || '5', 10);
        const delay = Math.min(retryAfter * 1000 * Math.pow(2, attempt), 60000);

        await new Promise((resolve) => setTimeout(resolve, delay));
      }

      return lastResponse!;
    },
    [],
  );

  return retry;
}
