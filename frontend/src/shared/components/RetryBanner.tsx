/**
 * RetryBanner — countdown retry for 503 / connection errors (278.D.4).
 *
 * Shows "We couldn't reach the server. Retrying in Ns… [Retry now]"
 * with an auto-countdown. Fires ``onRetry`` when the countdown reaches
 * zero OR the user clicks "Retry now".
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import './RetryBanner.css';

export interface RetryBannerProps {
  /** Seconds between auto-retries. */
  intervalSeconds?: number;
  /** Called on each retry attempt. */
  onRetry: () => void;
  /** Called after maxRetries exhausted. */
  onGiveUp?: () => void;
  /** Maximum auto-retry attempts (default 5). */
  maxRetries?: number;
  /** Custom message — the banner shows this with a countdown. */
  message?: string;
}

export function RetryBanner({
  intervalSeconds = 5,
  onRetry,
  onGiveUp,
  maxRetries = 5,
  message = "We couldn't reach the server.",
}: RetryBannerProps) {
  const [countdown, setCountdown] = useState(intervalSeconds);
  const [attempt, setAttempt] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const onRetryRef = useRef(onRetry);
  onRetryRef.current = onRetry;

  const doRetry = useCallback(() => {
    if (attempt >= maxRetries) {
      if (timerRef.current) clearInterval(timerRef.current);
      onGiveUp?.();
      return;
    }
    setAttempt((a) => a + 1);
    setCountdown(intervalSeconds);
    onRetryRef.current();
  }, [attempt, maxRetries, intervalSeconds, onGiveUp]);

  useEffect(() => {
    timerRef.current = setInterval(() => {
      setCountdown((c) => {
        if (c <= 1) {
          // Will retry on next tick — clear first to avoid double-fire
          return 0;
        }
        return c - 1;
      });
    }, 1000);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  // Auto-retry when countdown reaches 0
  useEffect(() => {
    if (countdown === 0) {
      doRetry();
    }
  }, [countdown, doRetry]);

  if (attempt >= maxRetries) {
    return (
      <div className="retry-banner retry-banner--exhausted" role="alert" data-testid="retry-banner-exhausted">
        <p className="retry-banner__text">
          Still unable to reach the server after {maxRetries} attempts. Please check your connection and try again later.
        </p>
      </div>
    );
  }

  return (
    <div className="retry-banner" role="alert" aria-live="polite" data-testid="retry-banner">
      <span className="retry-banner__text">
        {message} Retrying in {countdown}s…
      </span>
      <button
        type="button"
        className="retry-banner__action"
        onClick={doRetry}
      >
        Retry now
      </button>
    </div>
  );
}
