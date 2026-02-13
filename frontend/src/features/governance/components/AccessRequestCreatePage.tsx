/**
 * Access Request Create Page
 * Form: reason, asset_id/dataset_id/file_id (at least one), requested_access_type
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { AccessRequestCreateRequest } from '../../../shared/types/governance';
import { useCreateAccessRequest } from '../hooks/useGovernance';
import './AccessRequestCreatePage.css';

const INITIAL_FORM: AccessRequestCreateRequest & {
  asset_id: string;
  dataset_id: string;
  file_id: string;
} = {
  reason: '',
  asset_id: '',
  dataset_id: '',
  file_id: '',
  requested_access_type: 'READ',
};

export function AccessRequestCreatePage() {
  const navigate = useNavigate();
  const [form, setForm] = useState(INITIAL_FORM);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const createMutation = useCreateAccessRequest();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);
    const asset_id = form.asset_id.trim() || undefined;
    const dataset_id = form.dataset_id.trim() || undefined;
    const file_id = form.file_id.trim() || undefined;
    if (!asset_id && !dataset_id && !file_id) {
      setSubmitError('Provide at least one of: Asset ID, Dataset ID, or File ID');
      return;
    }
    if (!form.reason.trim()) {
      setSubmitError('Reason is required');
      return;
    }
    try {
      const created = await createMutation.mutateAsync({
        reason: form.reason.trim(),
        asset_id,
        dataset_id,
        file_id,
        requested_access_type: form.requested_access_type,
      });
      navigate(`/governance/access-requests/${created.id}`);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Failed to create access request');
    }
  };

  return (
    <div className="governance-create-page">
      <button type="button" className="btn-back" onClick={() => navigate('/governance')}>
        ← Back to Access Requests
      </button>
      <h1>Create access request</h1>

      <form className="governance-create-form" onSubmit={handleSubmit}>
        {submitError && (
          <div className="form-error" role="alert">
            {submitError}
          </div>
        )}
        <div className="form-group">
          <label htmlFor="create-reason">Reason (required)</label>
          <textarea
            id="create-reason"
            value={form.reason}
            onChange={(e) => setForm({ ...form, reason: e.target.value })}
            required
            placeholder="Why do you need access?"
          />
        </div>
        <div className="form-group">
          <label htmlFor="create-asset_id">Asset ID (optional)</label>
          <input
            id="create-asset_id"
            type="text"
            value={form.asset_id}
            onChange={(e) => setForm({ ...form, asset_id: e.target.value })}
            placeholder="UUID"
          />
        </div>
        <div className="form-group">
          <label htmlFor="create-dataset_id">Dataset ID (optional)</label>
          <input
            id="create-dataset_id"
            type="text"
            value={form.dataset_id}
            onChange={(e) => setForm({ ...form, dataset_id: e.target.value })}
            placeholder="UUID"
          />
        </div>
        <div className="form-group">
          <label htmlFor="create-file_id">File ID (optional)</label>
          <input
            id="create-file_id"
            type="text"
            value={form.file_id}
            onChange={(e) => setForm({ ...form, file_id: e.target.value })}
            placeholder="UUID"
          />
        </div>
        <div className="form-group">
          <label htmlFor="create-type">Requested access type</label>
          <select
            id="create-type"
            value={form.requested_access_type}
            onChange={(e) => setForm({ ...form, requested_access_type: e.target.value })}
          >
            <option value="READ">READ</option>
            <option value="WRITE">WRITE</option>
            <option value="DOWNLOAD">DOWNLOAD</option>
          </select>
        </div>
        <div className="form-actions">
          <button type="button" className="btn-secondary" onClick={() => navigate('/governance')}>
            Cancel
          </button>
          <button type="submit" className="btn-primary" disabled={createMutation.isPending}>
            {createMutation.isPending ? 'Creating…' : 'Create'}
          </button>
        </div>
      </form>
    </div>
  );
}
