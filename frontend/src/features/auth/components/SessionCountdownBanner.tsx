/**
 * Session countdown banner (task 0b.12 — JOURNEY-DB-004 step 4).
 *
 * Polls the SSO session endpoint and shows a non-blocking countdown when
 * the workspace's absolute session lifetime is within the window. The Hub
 * session itself is unaffected (the banner prompts a Databricks
 * re-sign-in, never a Hub logout).
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import { useTranslation } from '../../../shared/i18n/useTranslation';
import { useAuthStore } from '../store/authStore';
import { ssoSession } from '../../databricks/services/databricksSsoService';

const POLL_MS = 30_000;

export function SessionCountdownBanner(): React.ReactElement | null {
  const { t } = useTranslation();
  const isAuthenticated = useAuthStore((s) => Boolean(s.accessToken));
  const [secondsRemaining, setSecondsRemaining] = useState<number | null>(null);
  const timerRef = useRef<number | null>(null);

  const poll = useCallback(async () => {
    try {
      const state = await ssoSession();
      if (state.countdown.active && state.countdown.seconds_remaining !== null) {
        setSecondsRemaining(state.countdown.seconds_remaining);
      } else {
        setSecondsRemaining(null);
      }
    } catch {
      // Best-effort polling — a transient failure hides the banner, never
      // the session.
      setSecondsRemaining(null);
    }
  }, []);

  useEffect(() => {
    if (!isAuthenticated) {
      setSecondsRemaining(null);
      return;
    }
    void poll();
    timerRef.current = window.setInterval(() => void poll(), POLL_MS);
    return () => {
      if (timerRef.current !== null) {
        window.clearInterval(timerRef.current);
      }
    };
  }, [isAuthenticated, poll]);

  if (secondsRemaining === null) {
    return null;
  }

  return (
    <div
      role="status"
      data-testid="databricks-countdown-banner"
      className="countdown-banner"
    >
      {t('databricks.sso.countdown_body', 'Databricks access needs re-verification soon.')}{' '}
      <strong data-testid="databricks-countdown-seconds">
        {Math.max(0, Math.ceil(secondsRemaining / 60))}
      </strong>{' '}
      {t('databricks.sso.countdown_minutes', 'min remaining')}
    </div>
  );
}
