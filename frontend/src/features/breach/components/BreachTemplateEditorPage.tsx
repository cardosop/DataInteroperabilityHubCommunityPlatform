/** Per-tenant breach template editor (Phase 232.3.15). */
import { useEffect, useState } from 'react';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { ListPageSkeleton } from '../../../shared/components/skeletons/ListPageSkeleton';
import { Button } from '../../../shared/components/Button';
import { useTranslation } from '../../../shared/i18n/useTranslation';
import { breachService } from '../services/breachService';
import type { BreachTemplate } from '../services/breachService';

export function BreachTemplateEditorPage() {
  const { t } = useTranslation();
  const [rows, setRows] = useState<BreachTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);
  const [regime, setRegime] = useState('GDPR');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [busy, setBusy] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const catalog = await breachService.getTemplateCatalog();
      setRows(catalog.templates);
      setError(null);
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    const row = rows.find((r) => r.regime === regime);
    if (row) {
      setSubject(row.subject_template);
      setBody(row.body_template);
    }
  }, [rows, regime]);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await breachService.upsertTemplateOverride({
        regime,
        subject_template: subject,
        body_template: body,
      });
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <ListPageSkeleton />;

  return (
    <div className="p-4">
      <h1 className="text-2xl font-semibold">
        {t('governance.breach.templates_title', 'Breach notification templates')}
      </h1>
      <p className="mt-2 max-w-2xl text-sm text-gray-600">
        {t(
          'governance.breach.templates_intro',
          'Merged view: platform defaults plus tenant overrides. Placeholders: $incident_title, $incident_summary, $authority_name, $regime, $deadline_utc.',
        )}
      </p>
      {error ? <ErrorDisplay error={error} /> : null}
      <form onSubmit={save} className="mt-6 flex max-w-3xl flex-col gap-3">
        <label className="block">
          <span className="mb-1 block font-medium">{t('governance.breach.field_regime', 'Regime')}</span>
          <select
            className="w-full rounded border px-3 py-2"
            value={regime}
            onChange={(ev) => setRegime(ev.target.value)}
          >
            {rows.map((r) => (
              <option key={r.regime} value={r.regime}>
                {r.regime} (v{r.template_version})
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block font-medium">{t('governance.breach.field_subject', 'Subject')}</span>
          <input
            className="w-full rounded border px-3 py-2 font-mono text-sm"
            value={subject}
            onChange={(ev) => setSubject(ev.target.value)}
          />
        </label>
        <label className="block">
          <span className="mb-1 block font-medium">{t('governance.breach.field_body', 'Body')}</span>
          <textarea
            className="w-full rounded border px-3 py-2 font-mono text-sm"
            rows={10}
            value={body}
            onChange={(ev) => setBody(ev.target.value)}
          />
        </label>
        <Button type="submit" disabled={busy}>
          {busy ? t('governance.breach.saving', 'Saving…') : t('governance.breach.save', 'Save tenant override')}
        </Button>
      </form>
    </div>
  );
}
