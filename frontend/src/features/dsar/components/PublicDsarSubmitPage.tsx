import { Helmet } from 'react-helmet-async';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { APP_NAME } from '../../../shared/constants/brand';
import { useTranslation } from '../../../shared/i18n/useTranslation';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

/** Public DSAR form (Phase 232.2.14) — WCAG: labels tied to controls, errors in live region */
export function PublicDsarSubmitPage() {
  const { t } = useTranslation();
  const [tenantId, setTenantId] = useState('');
  const [email, setEmail] = useState('');
  const [requestType, setRequestType] = useState('ACCESS');
  const [regimes, setRegimes] = useState('GDPR');
  const [hcaptchaToken, setHcaptchaToken] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<{
    id: string;
    public_reference_token: string;
    status: string;
  } | null>(null);
  const [otp, setOtp] = useState('');
  const [subjectTimezone, setSubjectTimezone] = useState('UTC');
  const [regulatorTimezone, setRegulatorTimezone] = useState('UTC');

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const regimesList = regimes
        .split(',')
        .map((s) => s.trim().toUpperCase())
        .filter(Boolean);
      const body = {
        tenant_id: tenantId.trim(),
        request_type: requestType,
        subject_email: email.trim(),
        regimes: regimesList.length ? regimesList : ['GDPR'],
        hcaptcha_response: hcaptchaToken.trim(),
        subject_timezone: subjectTimezone.trim() || 'UTC',
        regulator_timezone: regulatorTimezone.trim() || 'UTC',
      };
      const res = await fetch(`${API_BASE}/public/dsar-requests/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(body),
      });
      const data = (await res.json()) as Record<string, unknown>;
      if (!res.ok) {
        const detail = Array.isArray(data.detail)
          ? (data.detail as string[]).join(' ')
          : typeof data.detail === 'string'
            ? data.detail
            : JSON.stringify(data);
        setError(detail);
        return;
      }
      setCreated({
        id: String(data.id),
        public_reference_token: String(data.public_reference_token),
        status: String(data.status),
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const verifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!created) return;
    setError(null);
    setBusy(true);
    try {
      const res = await fetch(`${API_BASE}/public/dsar-requests/${created.id}/verify-otp/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ code: otp.trim() }),
      });
      const data = (await res.json()) as { detail?: unknown; status?: string };
      if (!res.ok) {
        setError(typeof data.detail === 'string' ? data.detail : JSON.stringify(data));
        return;
      }
      setCreated((prev) => (prev ? { ...prev, status: String(data.status) } : null));
      setOtp('');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Helmet>
        <title>
          {APP_NAME} — {t('public.legal.dsar.title')}
        </title>
      </Helmet>
      <h2 className="text-xl font-semibold text-blue-950">{t('public.legal.dsar.heading')}</h2>
      <p className="mt-2 text-gray-700" id="dsar-intro">
        {t('public.legal.dsar.intro')}
      </p>
      <p className="mt-2 text-sm text-gray-600">{t('public.legal.dsar.captcha_notice')}</p>

      <div role="alert" aria-live="polite" className="mt-2 min-h-[1.5rem] text-red-800">
        {error}
      </div>

      {!created ? (
        <form className="mt-6 flex max-w-lg flex-col gap-4" onSubmit={submit} aria-labelledby="dsar-intro">
          <datalist id="dsar-common-tz">
            <option value="UTC" />
            <option value="America/New_York" />
            <option value="America/Sao_Paulo" />
            <option value="Europe/London" />
            <option value="Europe/Berlin" />
            <option value="Asia/Tokyo" />
            <option value="Australia/Sydney" />
          </datalist>
          <div>
            <label htmlFor="dsar-tenant-id" className="mb-1 block font-medium">
              {t('public.legal.dsar.field_tenant_id')}
            </label>
            <input
              id="dsar-tenant-id"
              required
              className="w-full rounded border px-3 py-2"
              autoComplete="off"
              aria-required="true"
              value={tenantId}
              onChange={(ev) => setTenantId(ev.target.value)}
            />
          </div>
          <div>
            <label htmlFor="dsar-email" className="mb-1 block font-medium">
              {t('public.legal.dsar.field_email')}
            </label>
            <input
              id="dsar-email"
              required
              type="email"
              className="w-full rounded border px-3 py-2"
              autoComplete="email"
              aria-required="true"
              value={email}
              onChange={(ev) => setEmail(ev.target.value)}
            />
          </div>
          <div>
            <label htmlFor="dsar-type" className="mb-1 block font-medium">
              {t('public.legal.dsar.field_type')}
            </label>
            <select
              id="dsar-type"
              className="w-full rounded border px-3 py-2"
              aria-required="true"
              value={requestType}
              onChange={(ev) => setRequestType(ev.target.value)}
            >
              <option value="ACCESS">ACCESS</option>
              <option value="ERASURE">ERASURE</option>
              <option value="RECTIFICATION">RECTIFICATION</option>
              <option value="PORTABILITY">PORTABILITY</option>
              <option value="RESTRICTION">RESTRICTION</option>
              <option value="OBJECTION">OBJECTION</option>
              <option value="AUTOMATED_DECISION_REVIEW">AUTOMATED_DECISION_REVIEW</option>
            </select>
          </div>
          <div>
            <label htmlFor="dsar-regimes" className="mb-1 block font-medium">
              {t('public.legal.dsar.field_regimes')}
            </label>
            <input
              id="dsar-regimes"
              className="w-full rounded border px-3 py-2"
              placeholder="GDPR, LGPD"
              value={regimes}
              onChange={(ev) => setRegimes(ev.target.value)}
              aria-describedby="dsar-regimes-help"
            />
            <p id="dsar-regimes-help" className="mt-1 text-sm text-gray-600">
              {t('public.legal.dsar.regimes_help')}
            </p>
          </div>
          <div>
            <label htmlFor="dsar-subject-tz" className="mb-1 block font-medium">
              {t('public.legal.dsar.field_subject_tz')}
            </label>
            <input
              id="dsar-subject-tz"
              className="w-full rounded border px-3 py-2 font-mono text-sm"
              list="dsar-common-tz"
              autoComplete="off"
              aria-describedby="dsar-tz-help"
              value={subjectTimezone}
              onChange={(ev) => setSubjectTimezone(ev.target.value)}
            />
          </div>
          <div>
            <label htmlFor="dsar-regulator-tz" className="mb-1 block font-medium">
              {t('public.legal.dsar.field_regulator_tz')}
            </label>
            <input
              id="dsar-regulator-tz"
              className="w-full rounded border px-3 py-2 font-mono text-sm"
              list="dsar-common-tz"
              autoComplete="off"
              aria-describedby="dsar-tz-help"
              value={regulatorTimezone}
              onChange={(ev) => setRegulatorTimezone(ev.target.value)}
            />
            <p id="dsar-tz-help" className="mt-1 text-sm text-gray-600">
              {t('public.legal.dsar.tz_help')}
            </p>
          </div>
          <div>
            <label htmlFor="dsar-hcaptcha" className="mb-1 block font-medium">
              {t('public.legal.dsar.field_hcaptcha')}
            </label>
            <input
              id="dsar-hcaptcha"
              required
              className="w-full rounded border px-3 py-2"
              autoComplete="off"
              aria-required="true"
              value={hcaptchaToken}
              onChange={(ev) => setHcaptchaToken(ev.target.value)}
            />
          </div>
          <button
            type="submit"
            disabled={busy}
            className="rounded bg-blue-800 px-4 py-2 font-medium text-white hover:bg-blue-900 disabled:opacity-50"
          >
            {busy ? t('public.legal.dsar.submitting') : t('public.legal.dsar.submit')}
          </button>
        </form>
      ) : (
        <div className="mt-6 space-y-4">
          <p className="text-gray-800">{t('public.legal.dsar.created_blurb')}</p>
          <ul className="list-inside list-disc text-sm text-gray-700">
            <li>
              {t('public.legal.dsar.reference')}:{' '}
              <Link className="font-mono underline" to={`/legal/dsar/status/${created.public_reference_token}`}>
                {created.public_reference_token}
              </Link>
            </li>
            <li>
              {t('public.legal.dsar.status_label')}: {created.status}
            </li>
          </ul>
          <form onSubmit={verifyOtp} className="flex max-w-md flex-col gap-2">
            <label htmlFor="dsar-otp" className="font-medium">
              {t('public.legal.dsar.otp_label')}
            </label>
            <input
              id="dsar-otp"
              className="rounded border px-3 py-2"
              autoComplete="one-time-code"
              inputMode="numeric"
              aria-describedby="dsar-intro"
              value={otp}
              onChange={(ev) => setOtp(ev.target.value)}
            />
            <button
              type="submit"
              disabled={busy}
              className="rounded bg-emerald-800 px-4 py-2 text-white hover:bg-emerald-900 disabled:opacity-50"
            >
              {t('public.legal.dsar.verify')}
            </button>
          </form>
        </div>
      )}
    </>
  );
}
