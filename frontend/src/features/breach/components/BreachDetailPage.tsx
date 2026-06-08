/** Breach incident detail + notification actions (Phase 232.3). */
import { useCallback, useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { ListPageSkeleton } from '../../../shared/components/skeletons/ListPageSkeleton';
import { Button } from '../../../shared/components/Button';
import { useTranslation } from '../../../shared/i18n/useTranslation';
import { countdownToUtcDeadline } from '../../dsar/utils/deadlineDisplay';
import { breachService } from '../services/breachService';
import type { BreachIncidentDetail } from '../services/breachService';

export function BreachDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { t } = useTranslation();
  const [row, setRow] = useState<BreachIncidentDetail | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [nowTick, setNowTick] = useState(() => Date.now());

  useEffect(() => {
    const tick = setInterval(() => setNowTick(Date.now()), 30_000);
    return () => clearInterval(tick);
  }, []);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      setRow(await breachService.getIncident(id));
      setError(null);
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  async function markSent(nid: string) {
    const ref =
      window.prompt(t('governance.breach.prompt_outbound_ref', 'Outbound reference (ticket id)')) ||
      '';
    if (!ref.trim()) return;
    await breachService.markNotificationSent(nid, { outbound_reference: ref.trim() });
    await load();
  }

  async function patchStatus(next: string) {
    if (!id) return;
    await breachService.patchIncidentStatus(id, { status: next, notes: '' });
    await load();
  }

  if (loading) return <ListPageSkeleton />;
  if (!row) return <p className="p-4">{t('governance.breach.not_found', 'Not found')}</p>;

  return (
    <div className="p-4">
      <h1 className="text-xl font-semibold">{row.title}</h1>
      <p className="mt-2 whitespace-pre-wrap text-sm text-gray-700">{row.summary}</p>
      <p className="mt-2 text-xs text-gray-600">
        {t('governance.breach.col_status', 'Status')}:{' '}
        <span className="font-mono">{row.status}</span> ·{' '}
        {t('governance.breach.col_deadline', 'Supervisory deadline')}:{' '}
        <span className="font-mono">{row.statutory_authority_deadline_utc}</span>
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button type="button" onClick={() => patchStatus('CONTAINED')}>
          {t('governance.breach.btn_contained', 'Mark contained')}
        </Button>
        <Button type="button" onClick={() => patchStatus('NOTIFIED')}>
          {t('governance.breach.btn_notified', 'Mark notified')}
        </Button>
        <Button type="button" onClick={() => patchStatus('CLOSED')}>
          {t('governance.breach.btn_closed', 'Close')}
        </Button>
      </div>
      {error ? <ErrorDisplay error={error} /> : null}
      <h2 className="mt-6 font-semibold">{t('governance.breach.notifications', 'Notifications')}</h2>
      <ul className="mt-2 space-y-2 text-sm">
        {row.notifications.map((n) => (
          <li key={n.id} className="rounded border p-2">
            <div className="font-mono text-xs">
              {n.regime} / {n.supervisory_authority_id || '—'} · {n.status}
            </div>
            <div className="mt-1 text-xs text-gray-700">
              {t('governance.breach.notif_due', 'Regime supervisory due (UTC)')}:{' '}
              <span className="font-mono">{n.statutory_due_at_utc}</span>
              {' · '}
              <span className="font-semibold text-blue-950">
                {countdownToUtcDeadline(
                  n.statutory_due_at_utc,
                  nowTick,
                  t('governance.breach.countdown_overdue', 'OVERDUE'),
                )}
              </span>
            </div>
            {n.status === 'PENDING' ? (
              <Button className="mt-2" type="button" onClick={() => markSent(n.id)}>
                {t('governance.breach.btn_mark_sent', 'Record as sent + proof')}
              </Button>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
