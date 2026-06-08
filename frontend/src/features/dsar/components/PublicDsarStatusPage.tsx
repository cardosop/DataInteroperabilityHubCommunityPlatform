import { Helmet } from 'react-helmet-async';
import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { APP_NAME } from '../../../shared/constants/brand';
import { useTranslation } from '../../../shared/i18n/useTranslation';
import { countdownToUtcDeadline } from '../utils/deadlineDisplay';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';
const TICK_MS = 30000;

export function PublicDsarStatusPage() {
  const { referenceToken } = useParams<{ referenceToken: string }>();
  const { t } = useTranslation();
  const [payload, setPayload] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [nowTick, setNowTick] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNowTick(Date.now()), TICK_MS);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (!referenceToken) return;
    void (async () => {
      setError(null);
      try {
        const res = await fetch(
          `${API_BASE}/public/dsar-requests/status/${referenceToken}/`,
          {
            credentials: 'include',
          },
        );
        const data = (await res.json()) as Record<string, unknown>;
        if (!res.ok) {
          setError(typeof data.detail === 'string' ? data.detail : JSON.stringify(data));
          return;
        }
        setPayload(data);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : String(e));
      }
    })();
  }, [referenceToken]);

  const fulfilUtc = payload?.statutory_fulfil_deadline_utc;
  const fulfilIso = typeof fulfilUtc === 'string' ? fulfilUtc : null;

  return (
    <>
      <Helmet>
        <title>
          {APP_NAME} — {t('public.legal.dsar.status.title')}
        </title>
      </Helmet>
      <h2 className="text-xl font-semibold text-blue-950">{t('public.legal.dsar.status.title')}</h2>
      <div role="status" aria-live="polite" className="mt-4">
        {error && <p className="text-red-800">{error}</p>}
        {payload && !error && (
          <dl className="grid max-w-xl grid-cols-1 gap-2 text-gray-800 sm:grid-cols-2">
            <dt className="font-medium">{t('public.legal.dsar.status.labels.status')}</dt>
            <dd>{String(payload.status)}</dd>
            <dt className="font-medium">{t('public.legal.dsar.status.labels.type')}</dt>
            <dd>{String(payload.request_type)}</dd>
            <dt className="font-medium">{t('public.legal.dsar.status.labels.ack_deadline')}</dt>
            <dd>{payload.statutory_ack_deadline_utc ? String(payload.statutory_ack_deadline_utc) : '—'}</dd>
            <dt className="font-medium">{t('public.legal.dsar.status.labels.fulfil_deadline')}</dt>
            <dd>
              <time dateTime={fulfilIso ?? undefined}>{fulfilIso ?? '—'}</time>
            </dd>
            <dt className="font-medium">{t('public.legal.dsar.status.labels.countdown')}</dt>
            <dd className="font-semibold text-blue-950">
              {countdownToUtcDeadline(fulfilIso, nowTick, t('governance.dsar.countdown_overdue'))}
            </dd>
            <dt className="font-medium">{t('public.legal.dsar.status.labels.subject_local')}</dt>
            <dd className="font-mono text-sm">
              {payload.statutory_fulfil_deadline_subject_local
                ? String(payload.statutory_fulfil_deadline_subject_local)
                : '—'}
            </dd>
            <dt className="font-medium">{t('public.legal.dsar.status.labels.regulator_local')}</dt>
            <dd className="font-mono text-sm">
              {payload.statutory_fulfil_deadline_regulator_local
                ? String(payload.statutory_fulfil_deadline_regulator_local)
                : '—'}
            </dd>
          </dl>
        )}
      </div>
    </>
  );
}
