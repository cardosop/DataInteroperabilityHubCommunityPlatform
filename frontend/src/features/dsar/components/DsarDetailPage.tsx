/**
 * Handler response packaging UI — Phase 232.2.16
 */
import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { Button } from '../../../shared/components/Button';
import { useTranslation } from '../../../shared/i18n/useTranslation';
import { countdownToUtcDeadline, formatUtcInTimeZone } from '../utils/deadlineDisplay';
import { dsarService } from '../services/dsarService';
import type { DsarDetail } from '../services/dsarService';

export function DsarDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { t } = useTranslation();
  const [detail, setDetail] = useState<DsarDetail | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [downloadPayload, setDownloadPayload] = useState<unknown>(null);
  const [nowTick, setNowTick] = useState(() => Date.now());

  useEffect(() => {
    const iv = setInterval(() => setNowTick(Date.now()), 30000);
    return () => clearInterval(iv);
  }, []);

  const reload = async () => {
    if (!id) return;
    setDetail(await dsarService.getRequest(id));
  };

  useEffect(() => {
    void (async () => {
      try {
        await reload();
      } catch (e) {
        setError(e);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- stable id from route
  }, [id]);

  const wrap = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError(null);
    setDownloadPayload(null);
    try {
      await fn();
      await reload();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  const materialize = async () => {
    if (!id) return;
    await wrap(() => dsarService.materializePackage(id));
  };

  const rejectCase = async () => {
    if (!id) return;
    const reason = window.prompt(t('governance.dsar.prompt_reject')) || '';
    if (!reason.trim()) return;
    await wrap(() => dsarService.rejectRequest(id, { reason }));
  };

  const hold = async () => {
    if (!id) return;
    const reason = window.prompt(t('governance.dsar.prompt_hold_reason')) || '';
    await wrap(() => dsarService.setLegalHold(id, { active: true, reason }));
  };

  const issueDl = async () => {
    if (!id) return;
    await wrap(async () => {
      setDownloadPayload(await dsarService.issueDownloadUrl(id));
    });
  };

  if (!detail && !error) {
    return <p className="p-4 text-gray-600">{t('governance.dsar.loading')}</p>;
  }

  const fulfilIso =
    detail && typeof detail.statutory_fulfil_deadline_utc === 'string'
      ? detail.statutory_fulfil_deadline_utc
      : null;
  const subTz =
    detail && typeof detail.subject_timezone === 'string' ? detail.subject_timezone : 'UTC';
  const regTz =
    detail && typeof detail.regulator_timezone === 'string'
      ? detail.regulator_timezone
      : 'UTC';

  return (
    <div className="flex flex-col gap-4 p-4">
      <h1 className="text-xl font-semibold">{t('governance.dsar.detail_title')}</h1>
      {error ? <ErrorDisplay error={error} /> : null}
      {detail ? (
        <section
          className="rounded border border-slate-200 bg-slate-50 p-4 text-sm shadow-sm"
          aria-label={t('governance.dsar.col_fulfil_detail')}
        >
          <h2 className="mb-2 font-semibold text-slate-900">{t('governance.dsar.col_fulfil_detail')}</h2>
          <p>
            <span className="text-slate-600">{t('governance.dsar.col_deadline')}: </span>
            <time className="font-mono text-slate-900" dateTime={fulfilIso ?? undefined}>
              {fulfilIso ?? '—'}
            </time>
          </p>
          <p className="mt-1">
            <span className="text-slate-600">{t('governance.dsar.countdown_prefix')}: </span>
            <span className="font-semibold text-blue-950">
              {countdownToUtcDeadline(fulfilIso, nowTick, t('governance.dsar.countdown_overdue'))}
            </span>
          </p>
          <p className="mt-1">
            <span className="font-medium">{t('governance.dsar.subject_tz_label')}: </span>
            {formatUtcInTimeZone(fulfilIso, subTz)}
            <span className="ml-1 font-mono text-xs text-slate-500">({subTz})</span>
          </p>
          <p>
            <span className="font-medium">{t('governance.dsar.regulator_tz_label')}: </span>
            {formatUtcInTimeZone(fulfilIso, regTz)}
            <span className="ml-1 font-mono text-xs text-slate-500">({regTz})</span>
          </p>
        </section>
      ) : null}
      <pre className="max-h-72 overflow-auto rounded bg-gray-100 p-4 text-xs" aria-live="polite">
        {JSON.stringify(detail, null, 2)}
      </pre>
      <div className="flex flex-wrap gap-2">
        <Button type="button" disabled={busy} onClick={materialize}>
          {t('governance.dsar.btn_materialize')}
        </Button>
        <Button type="button" disabled={busy} variant="danger" onClick={rejectCase}>
          {t('governance.dsar.btn_reject')}
        </Button>
        <Button type="button" disabled={busy} variant="secondary" onClick={hold}>
          {t('governance.dsar.btn_legal_hold')}
        </Button>
        <Button type="button" disabled={busy} variant="ghost" onClick={issueDl}>
          {t('governance.dsar.btn_download')}
        </Button>
      </div>
      {downloadPayload ? (
        <div className="rounded border border-emerald-200 bg-emerald-50 p-3 text-sm" role="region">
          <p className="font-medium">{t('governance.dsar.download_ready')}</p>
          <p className="break-all">{String((downloadPayload as { download_url?: string }).download_url ?? '')}</p>
        </div>
      ) : null}
    </div>
  );
}
