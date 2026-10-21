/** Emergency report-a-breach form (Phase 232.3.13). */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { Button } from '../../../shared/components/Button';
import { useTranslation } from '../../../shared/i18n/useTranslation';
import { breachService } from '../services/breachService';

export function ReportBreachPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [title, setTitle] = useState('');
  const [summary, setSummary] = useState('');
  const [regimes, setRegimes] = useState('GDPR');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const discoveredAt = new Date().toISOString();
      const created = await breachService.createIncident({
        title,
        summary,
        regimes: regimes.split(/[\s,]+/).filter(Boolean),
        discovered_at: discoveredAt,
      });
      navigate(`/governance/breach/${created.id}`);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="p-4">
      <h1 className="text-2xl font-semibold">
        {t('governance.breach.report_title', 'Report a personal data breach')}
      </h1>
      <p className="mt-2 max-w-xl text-sm text-gray-600">
        {t(
          'governance.breach.report_intro',
          'Creates an incident record, starts the supervisory notification clock, and generates draft notifications per regulation_policies + YAML routing.',
        )}
      </p>
      {error ? <ErrorDisplay error={error} /> : null}
      <form onSubmit={submit} className="mt-6 flex max-w-lg flex-col gap-3">
        <label className="block">
          <span className="mb-1 block font-medium">{t('governance.breach.field_title', 'Title')}</span>
          <input
            className="w-full rounded border px-3 py-2"
            value={title}
            onChange={(ev) => setTitle(ev.target.value)}
            required
          />
        </label>
        <label className="block">
          <span className="mb-1 block font-medium">
            {t('governance.breach.field_summary', 'Summary (no unnecessary personal data)')}
          </span>
          <textarea
            className="w-full rounded border px-3 py-2"
            rows={4}
            value={summary}
            onChange={(ev) => setSummary(ev.target.value)}
          />
        </label>
        <label className="block">
          <span className="mb-1 block font-medium">
            {t('governance.breach.field_regimes', 'Regimes (comma-separated)')}
          </span>
          <input
            className="w-full rounded border px-3 py-2"
            value={regimes}
            onChange={(ev) => setRegimes(ev.target.value)}
          />
        </label>
        <Button type="submit" disabled={busy}>
          {busy
            ? t('governance.breach.submitting', 'Submitting…')
            : t('governance.breach.submit', 'Open incident')}
        </Button>
      </form>
    </div>
  );
}
