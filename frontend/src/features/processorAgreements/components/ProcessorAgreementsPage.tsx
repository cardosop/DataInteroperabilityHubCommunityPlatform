/** Tenant admin processor + agreement inventory (Phase 232.6.11). */
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { apiClient } from '../../../shared/api/client';
import { ErrorDisplay } from '../../../shared/components/ErrorDisplay';
import { ListPageSkeleton } from '../../../shared/components/skeletons/ListPageSkeleton';
import { Button } from '../../../shared/components/Button';
import { useTranslation } from '../../../shared/i18n/useTranslation';

type Paged<T> = { results?: T[] };

function unwrapResults<T>(data: Paged<T> | T[] | undefined): T[] {
  if (!data) return [];
  if (Array.isArray(data)) return data;
  return data.results ?? [];
}

interface ProcessorRow {
  id: string;
  name: string;
  legal_name?: string;
}

const AGREEMENT_TYPES = ['DPA', 'BAA', 'SCC', 'BCR'] as const;

interface AgreementRow {
  id: string;
  processor: string;
  processor_name?: string;
  agreement_type: string;
  document_uri: string;
  document_hash: string;
  effective_from: string;
  expires_on: string | null;
  status: string;
  transfer_mechanism_summary?: string;
  registration_reference?: string;
  jurisdiction_region?: string;
}

async function sha256HexFromFile(file: File): Promise<string> {
  const buf = await file.arrayBuffer();
  const hash = await crypto.subtle.digest('SHA-256', buf);
  return Array.from(new Uint8Array(hash))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

export function ProcessorAgreementsPage() {
  const { t } = useTranslation();
  const client = apiClient.getClient();

  const [processors, setProcessors] = useState<ProcessorRow[]>([]);
  const [agreements, setAgreements] = useState<AgreementRow[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const [procName, setProcName] = useState('');
  const [procLegalName, setProcLegalName] = useState('');

  const [agrProcessorId, setAgrProcessorId] = useState('');
  const [agrType, setAgrType] = useState<(typeof AGREEMENT_TYPES)[number]>('DPA');
  const [agrDocUri, setAgrDocUri] = useState('');
  const [agrHash, setAgrHash] = useState('');
  const [agrEffective, setAgrEffective] = useState(() => new Date().toISOString().slice(0, 10));
  const [agrExpires, setAgrExpires] = useState('');
  const [agrXfer, setAgrXfer] = useState('');
  const [agrRegRef, setAgrRegRef] = useState('');
  const [agrRegion, setAgrRegion] = useState('');

  const [editing, setEditing] = useState<AgreementRow | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [pr, ar] = await Promise.all([
        client.get<Paged<ProcessorRow> | ProcessorRow[]>('governance/processors/'),
        client.get<Paged<AgreementRow> | AgreementRow[]>('governance/processor-agreements/'),
      ]);
      const prows = unwrapResults(pr.data);
      const arows = unwrapResults(ar.data);
      setProcessors(prows);
      setAgreements(arows);
      setError(null);
      setAgrProcessorId((prev) => prev || prows[0]?.id || '');
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }, [client]);

  useEffect(() => {
    void load();
  }, [load]);

  async function addProcessor() {
    if (!procName.trim()) return;
    setBusy(true);
    try {
      await client.post('governance/processors/', {
        name: procName.trim(),
        legal_name: procLegalName.trim() || '',
      });
      setProcName('');
      setProcLegalName('');
      await load();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  async function deleteProcessor(id: string, displayName: string) {
    if (!window.confirm(t('governance.processors.confirm_delete', `Delete processor “${displayName}”?`))) return;
    setBusy(true);
    try {
      await client.delete(`governance/processors/${id}/`);
      await load();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  async function onAgreementFilePick(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    try {
      setBusy(true);
      setAgrHash(await sha256HexFromFile(f));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
      e.target.value = '';
    }
  }

  async function addAgreement() {
    if (!agrProcessorId || !agrDocUri.trim() || !agrHash.trim()) return;
    setBusy(true);
    try {
      await client.post('governance/processor-agreements/', {
        processor: agrProcessorId,
        agreement_type: agrType,
        document_uri: agrDocUri.trim(),
        document_hash: agrHash.trim().toLowerCase(),
        effective_from: agrEffective,
        expires_on: agrExpires || null,
        sub_processors_declared: [],
        transfer_mechanism_summary: agrXfer.trim(),
        registration_reference: agrRegRef.trim(),
        jurisdiction_region: agrRegion.trim().toUpperCase(),
      });
      setAgrDocUri('');
      setAgrHash('');
      setAgrExpires('');
      setAgrXfer('');
      setAgrRegRef('');
      setAgrRegion('');
      await load();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  async function saveEditedAgreement() {
    if (!editing) return;
    setBusy(true);
    try {
      await client.patch(`governance/processor-agreements/${editing.id}/`, {
        expires_on: editing.expires_on || null,
        transfer_mechanism_summary: editing.transfer_mechanism_summary ?? '',
        registration_reference: editing.registration_reference ?? '',
        jurisdiction_region: editing.jurisdiction_region ?? '',
      });
      setEditing(null);
      await load();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  async function deleteAgreement(id: string) {
    if (!window.confirm(t('governance.processor_agreements.confirm_delete', 'Delete this agreement record?'))) return;
    setBusy(true);
    try {
      await client.delete(`governance/processor-agreements/${id}/`);
      if (editing?.id === id) setEditing(null);
      await load();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <ListPageSkeleton />;

  return (
    <div className="governance-processor-agreements p-4">
      <p className="text-sm">
        <Link to="/governance" className="text-primary-600 underline">
          {t('governance.back', '← Back to governance')}
        </Link>
      </p>
      <h1 className="text-2xl font-semibold">
        {t('governance.processors.title', 'Processor agreements')}
      </h1>
      <p className="mt-2 text-sm text-gray-600">
        {t(
          'governance.processors.intro',
          'Register processors (Article 28-style counterparties) and record DPA/BAA/SCC/BCR artefacts with tamper-evident hashes.',
        )}
      </p>
      {error ? <ErrorDisplay error={error} /> : null}

      <div className="mt-6 max-w-xl rounded border p-4">
        <h2 className="font-semibold">{t('governance.processors.add_processor', 'Add processor')}</h2>
        <label className="mt-2 block text-sm">
          <span className="font-medium">{t('governance.processors.name', 'Name')}</span>
          <input
            className="mt-1 w-full rounded border px-2 py-1"
            value={procName}
            onChange={(e) => setProcName(e.target.value)}
          />
        </label>
        <label className="mt-2 block text-sm">
          <span className="font-medium">{t('governance.processors.legal_name', 'Legal name (optional)')}</span>
          <input
            className="mt-1 w-full rounded border px-2 py-1"
            value={procLegalName}
            onChange={(e) => setProcLegalName(e.target.value)}
          />
        </label>
        <Button className="mt-3" type="button" disabled={busy} onClick={() => void addProcessor()}>
          {busy
            ? t('governance.processors.saving', 'Saving…')
            : t('governance.processors.save', 'Save')}
        </Button>
      </div>

      <h2 className="mt-8 font-semibold">{t('governance.processors.list', 'Processors')}</h2>
      <ul className="mt-2 space-y-2 text-sm">
        {processors.map((p) => (
          <li key={p.id} className="flex flex-wrap items-center gap-2 font-mono text-xs">
            <span>
              {p.name}
              {p.legal_name ? ` · ${p.legal_name}` : ''}
            </span>
            <Button
              type="button"
              className="!py-0 !px-2 text-xs"
              disabled={busy}
              onClick={() => void deleteProcessor(p.id, p.name)}
            >
              {t('common.delete', 'Delete')}
            </Button>
          </li>
        ))}
      </ul>

      <div className="mt-10 max-w-2xl rounded border p-4">
        <h2 className="font-semibold">
          {t('governance.processor_agreements.add', 'Register agreement')}
        </h2>
        <label className="mt-2 block text-sm">
          <span className="font-medium">{t('governance.processor_agreements.processor', 'Processor')}</span>
          <select
            className="mt-1 w-full rounded border px-2 py-1"
            value={agrProcessorId}
            onChange={(e) => setAgrProcessorId(e.target.value)}
          >
            {processors.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
        <label className="mt-2 block text-sm">
          <span className="font-medium">{t('governance.processor_agreements.type', 'Type')}</span>
          <select
            className="mt-1 w-full rounded border px-2 py-1"
            value={agrType}
            onChange={(e) => setAgrType(e.target.value as (typeof AGREEMENT_TYPES)[number])}
          >
            {AGREEMENT_TYPES.map((x) => (
              <option key={x} value={x}>
                {x}
              </option>
            ))}
          </select>
        </label>
        <label className="mt-2 block text-sm">
          <span className="font-medium">{t('governance.processor_agreements.document_uri', 'Document URL')}</span>
          <input
            className="mt-1 w-full rounded border px-2 py-1"
            value={agrDocUri}
            onChange={(e) => setAgrDocUri(e.target.value)}
            placeholder="https://…"
          />
        </label>
        <label className="mt-2 block text-sm">
          <span className="font-medium">{t('governance.processor_agreements.hash', 'SHA-256 (hex)')}</span>
          <input
            className="mt-1 w-full rounded border px-2 py-1 font-mono text-xs"
            value={agrHash}
            onChange={(e) => setAgrHash(e.target.value)}
            placeholder="64 hex chars"
          />
        </label>
        <label className="mt-2 block text-sm">
          {t('governance.processor_agreements.hash_from_file', 'Or compute hash from file')}
          <input type="file" className="mt-1 block w-full text-xs" onChange={(e) => void onAgreementFilePick(e)} />
        </label>
        <div className="mt-2 grid grid-cols-2 gap-2">
          <label className="block text-sm">
            <span className="font-medium">{t('governance.processor_agreements.effective', 'Effective from')}</span>
            <input
              type="date"
              className="mt-1 w-full rounded border px-2 py-1"
              value={agrEffective}
              onChange={(e) => setAgrEffective(e.target.value)}
            />
          </label>
          <label className="block text-sm">
            <span className="font-medium">{t('governance.processor_agreements.expires', 'Expires (optional)')}</span>
            <input
              type="date"
              className="mt-1 w-full rounded border px-2 py-1"
              value={agrExpires}
              onChange={(e) => setAgrExpires(e.target.value)}
            />
          </label>
        </div>
        <label className="mt-2 block text-sm">
          <span className="font-medium">
            {t('governance.processor_agreements.transfer_summary', 'Transfer mechanism (SCC)')}
          </span>
          <input
            className="mt-1 w-full rounded border px-2 py-1"
            value={agrXfer}
            onChange={(e) => setAgrXfer(e.target.value)}
          />
        </label>
        <label className="mt-2 block text-sm">
          <span className="font-medium">
            {t('governance.processor_agreements.reg_ref', 'Registration ref (BCR)')}
          </span>
          <input
            className="mt-1 w-full rounded border px-2 py-1"
            value={agrRegRef}
            onChange={(e) => setAgrRegRef(e.target.value)}
          />
        </label>
        <label className="mt-2 block text-sm">
          <span className="font-medium">{t('governance.processor_agreements.region', 'Region hint (BAA)')}</span>
          <input
            className="mt-1 w-full rounded border px-2 py-1"
            value={agrRegion}
            onChange={(e) => setAgrRegion(e.target.value)}
            placeholder="US"
            maxLength={8}
          />
        </label>
        <Button className="mt-3" type="button" disabled={busy} onClick={() => void addAgreement()}>
          {t('governance.processor_agreements.submit', 'Save agreement')}
        </Button>
      </div>

      <h2 className="mt-10 font-semibold">{t('governance.processor_agreements.list', 'Agreements')}</h2>
      <div className="mt-2 overflow-x-auto">
        <table className="min-w-full border-collapse text-left text-sm">
          <thead>
            <tr className="border-b">
              <th className="py-2 pr-4">{t('governance.processor_agreements.col.processor', 'Processor')}</th>
              <th className="py-2 pr-4">{t('governance.processor_agreements.col.type', 'Type')}</th>
              <th className="py-2 pr-4">{t('governance.processor_agreements.col.status', 'Status')}</th>
              <th className="py-2 pr-4">{t('governance.processor_agreements.col.expires', 'Expires')}</th>
              <th className="py-2 pr-4">{t('governance.processor_agreements.col.actions', 'Actions')}</th>
            </tr>
          </thead>
          <tbody>
            {agreements.map((a) => (
              <tr key={a.id} className="border-b border-gray-100">
                <td className="py-2 pr-4">{a.processor_name ?? a.processor}</td>
                <td className="py-2 pr-4">{a.agreement_type}</td>
                <td className="py-2 pr-4">{a.status}</td>
                <td className="py-2 pr-4">{a.expires_on ?? '—'}</td>
                <td className="space-x-2 py-2 pr-4">
                  <button
                    type="button"
                    className="text-primary-600 underline"
                    onClick={() => setEditing(a)}
                  >
                    {t('common.edit', 'Edit')}
                  </button>
                  <button
                    type="button"
                    className="text-red-700 underline"
                    onClick={() => void deleteAgreement(a.id)}
                  >
                    {t('common.delete', 'Delete')}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {editing ? (
        <div className="mt-6 max-w-xl rounded border border-amber-200 bg-amber-50 p-4">
          <h3 className="font-semibold">{t('governance.processor_agreements.edit_title', 'Edit agreement')}</h3>
          <p className="text-xs text-gray-600">
            {editing.processor_name ?? editing.processor} — {editing.agreement_type}
          </p>
          <label className="mt-2 block text-sm">
            <span className="font-medium">{t('governance.processor_agreements.expires', 'Expires')}</span>
            <input
              type="date"
              className="mt-1 w-full rounded border px-2 py-1"
              value={editing.expires_on ?? ''}
              onChange={(e) =>
                setEditing({ ...editing, expires_on: e.target.value || null })
              }
            />
          </label>
          <label className="mt-2 block text-sm">
            <span className="font-medium">{t('governance.processor_agreements.transfer_summary', 'Transfer mechanism')}</span>
            <input
              className="mt-1 w-full rounded border px-2 py-1"
              value={editing.transfer_mechanism_summary ?? ''}
              onChange={(e) =>
                setEditing({ ...editing, transfer_mechanism_summary: e.target.value })
              }
            />
          </label>
          <label className="mt-2 block text-sm">
            <span className="font-medium">{t('governance.processor_agreements.reg_ref', 'Registration ref')}</span>
            <input
              className="mt-1 w-full rounded border px-2 py-1"
              value={editing.registration_reference ?? ''}
              onChange={(e) =>
                setEditing({ ...editing, registration_reference: e.target.value })
              }
            />
          </label>
          <label className="mt-2 block text-sm">
            <span className="font-medium">{t('governance.processor_agreements.region', 'Region hint')}</span>
            <input
              className="mt-1 w-full rounded border px-2 py-1"
              value={editing.jurisdiction_region ?? ''}
              onChange={(e) =>
                setEditing({ ...editing, jurisdiction_region: e.target.value })
              }
            />
          </label>
          <div className="mt-3 flex gap-2">
            <Button type="button" disabled={busy} onClick={() => void saveEditedAgreement()}>
              {t('common.save', 'Save')}
            </Button>
            <Button type="button" variant="secondary" disabled={busy} onClick={() => setEditing(null)}>
              {t('common.cancel', 'Cancel')}
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
