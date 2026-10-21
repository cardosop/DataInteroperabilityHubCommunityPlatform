/**
 * TENANT_ADMIN / DPO / LEGAL_ADMIN queue — Phase 232.2.15 (statutory clock + TZ).
 */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { ListPageSkeleton } from '../../../shared/components/skeletons/ListPageSkeleton';
import { Button } from '../../../shared/components/Button';
import { useTranslation } from '../../../shared/i18n/useTranslation';
import { countdownToUtcDeadline, formatUtcInTimeZone } from '../utils/deadlineDisplay';
import { dsarService } from '../services/dsarService';
import type { DsarListRow } from '../services/dsarService';

const TICK_MS = 30000;

export function DsarQueuePage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [rows, setRows] = useState<DsarListRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [nowTick, setNowTick] = useState(() => Date.now());

  const headline = t('governance.dsar.queue_title');

  useEffect(() => {
    const id = setInterval(() => setNowTick(Date.now()), TICK_MS);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    void (async () => {
      try {
        setLoading(true);
        setRows(await dsarService.listRequests());
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
      <h1 className="text-2xl font-semibold">{headline}</h1>
      {error ? <ErrorDisplay error={error} /> : null}
      <table className="mt-6 w-full max-w-6xl border-collapse text-sm" aria-describedby="dsar-queue-intro">
        <caption id="dsar-queue-intro" className="sr-only">
          {headline}
        </caption>
        <thead className="bg-gray-100 text-left">
          <tr>
            <th scope="col" className="p-2">
              {t('governance.dsar.col_type')}
            </th>
            <th scope="col" className="p-2">
              {t('governance.dsar.col_subject')}
            </th>
            <th scope="col" className="p-2">
              {t('governance.dsar.col_status')}
            </th>
            <th scope="col" className="p-2">
              {t('governance.dsar.col_sla_scan')}
            </th>
            <th scope="col" className="p-2">
              {t('governance.dsar.col_fulfil_detail')}
            </th>
            <th scope="col" className="p-2">
              {t('governance.dsar.col_action')}
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const iso = r.statutory_fulfil_deadline_utc ?? undefined;
            const subjTz = r.subject_timezone ?? 'UTC';
            const regTz = r.regulator_timezone ?? 'UTC';
            return (
              <tr key={r.id} className="border-t">
                <td className="p-2 font-mono text-xs">{r.request_type}</td>
                <td className="p-2">{r.subject_email}</td>
                <td className="p-2">{r.status}</td>
                <td className="p-2 font-mono text-xs">{r.last_sla_level ?? '—'}</td>
                <td className="p-2 align-top text-xs leading-snug text-gray-800">
                  <div>
                    <span className="font-medium text-gray-600">{t('governance.dsar.col_deadline')}: </span>
                    {iso ? (
                      <time dateTime={iso} className="font-mono">
                        {iso}
                      </time>
                    ) : (
                      '—'
                    )}
                  </div>
                  <div className="mt-1" aria-label={t('governance.dsar.countdown_prefix')}>
                    <span className="text-gray-600">{t('governance.dsar.countdown_prefix')}: </span>
                    <span className="font-semibold text-blue-950">
                      {countdownToUtcDeadline(iso, nowTick, t('governance.dsar.countdown_overdue'))}
                    </span>
                  </div>
                  <div className="mt-1 text-gray-700">
                    <span className="font-medium">{t('governance.dsar.subject_tz_label')}: </span>
                    {formatUtcInTimeZone(iso, subjTz)}
                    <span className="ml-1 font-mono text-[10px] text-gray-500">({subjTz})</span>
                  </div>
                  <div className="text-gray-700">
                    <span className="font-medium">{t('governance.dsar.regulator_tz_label')}: </span>
                    {formatUtcInTimeZone(iso, regTz)}
                    <span className="ml-1 font-mono text-[10px] text-gray-500">({regTz})</span>
                  </div>
                </td>
                <td className="p-2">
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => navigate(`/governance/dsar-requests/${r.id}`)}
                  >
                    {t('governance.dsar.open')}
                  </Button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {!rows.length && !error ? (
        <p className="mt-6 text-gray-600">{t('governance.dsar.empty')}</p>
      ) : null}
    </div>
  );
}
