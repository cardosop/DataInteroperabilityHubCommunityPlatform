/**
 * Breach response dashboard (Phase 232.3.14) — timers to supervisory deadline.
 */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { ListPageSkeleton } from '../../../shared/components/skeletons/ListPageSkeleton';
import { useTranslation } from '../../../shared/i18n/useTranslation';
import { countdownToUtcDeadline } from '../../dsar/utils/deadlineDisplay';
import { breachService } from '../services/breachService';
import type { BreachDashboardPayload } from '../services/breachService';

const TICK_MS = 30000;

export function BreachDashboardPage() {
  const { t } = useTranslation();
  const [data, setData] = useState<BreachDashboardPayload | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [nowTick, setNowTick] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNowTick(Date.now()), TICK_MS);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    void (async () => {
      try {
        setLoading(true);
        setData(await breachService.getDashboard());
        setError(null);
      } catch (e) {
        setError(e);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <ListPageSkeleton />;

  return (
    <div className="p-4">
      <h1 className="text-2xl font-semibold">
        {t('governance.breach.dashboard_title', 'Breach response dashboard')}
      </h1>
      <p className="mt-2 text-sm text-gray-600">
        {t(
          'governance.breach.dashboard_intro',
          'Open incidents and pending supervisory notifications with statutory deadlines (UTC).',
        )}
      </p>
      {error ? <ErrorDisplay error={error} /> : null}
      {data ? (
        <div className="mt-4 flex flex-wrap gap-6 text-sm">
          <div>
            <span className="text-gray-600">{t('governance.breach.open_count', 'Open incidents')}: </span>
            <span className="font-semibold">{data.open_incidents_count}</span>
          </div>
          <div>
            <span className="text-gray-600">
              {t('governance.breach.pending_notifications', 'Pending notifications')}:{' '}
            </span>
            <span className="font-semibold">{data.pending_notifications_count}</span>
          </div>
        </div>
      ) : null}
      <table className="mt-6 w-full max-w-5xl border-collapse text-sm">
        <thead className="bg-gray-100 text-left">
          <tr>
            <th className="p-2">{t('governance.breach.col_title', 'Title')}</th>
            <th className="p-2">{t('governance.breach.col_status', 'Status')}</th>
            <th className="p-2">{t('governance.breach.col_deadline', 'Supervisory deadline (UTC)')}</th>
            <th className="p-2">{t('governance.breach.col_countdown', 'Countdown')}</th>
            <th className="p-2">{t('governance.breach.col_action', 'Action')}</th>
          </tr>
        </thead>
        <tbody>
          {(data?.incidents ?? []).map((row) => {
            const iso = row.statutory_authority_deadline_utc ?? undefined;
            return (
              <tr key={row.id} className="border-t">
                <td className="p-2">{row.title}</td>
                <td className="p-2 font-mono text-xs">{row.status}</td>
                <td className="p-2 font-mono text-xs">{iso ?? '—'}</td>
                <td className="p-2 font-semibold text-blue-950">
                  {countdownToUtcDeadline(
                    iso,
                    nowTick,
                    t('governance.breach.countdown_overdue', 'OVERDUE'),
                  )}
                </td>
                <td className="p-2">
                  <Link className="text-blue-700 underline" to={`/governance/breach/${row.id}`}>
                    {t('governance.breach.view', 'View')}
                  </Link>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
