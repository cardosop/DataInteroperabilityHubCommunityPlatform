/**
 * Access Request Create Page
 * Form: reason, asset_id/dataset_id/file_id (at least one), requested_access_type
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { AccessRequestCreateRequest } from '../../../shared/types/governance';
import { AssetPicker } from '../../../shared/components/pickers/AssetPicker';
import { DatasetPicker } from '../../../shared/components/pickers/DatasetPicker';
import { FilePicker } from '../../../shared/components/pickers/FilePicker';
import { normalizeError } from '../../../shared/utils/errorUtils';
import { useCreateAccessRequest } from '../hooks/useGovernance';
import './AccessRequestCreatePage.css';
import { Button } from '../../../shared/components/Button';

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
      setSubmitError('Provide at least one of: Asset, Dataset, or File');
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
    } catch (err: unknown) {
      const msg = normalizeError(err).error.message || 'Failed to create access request';
      setSubmitError(msg);
    }
  };

  return (
    <div className="governance-create-page">
      <Button variant="ghost" onClick={() => navigate('/governance')}>
        ← Back to Access Requests
      </Button>
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
            onChange={(e) => setForm((prev) => ({ ...prev, reason: e.target.value }))}
            required
            placeholder="Why do you need access?"
          />
        </div>
        <div className="form-group">
          <label htmlFor="create-asset_id">Asset (optional)</label>
          <AssetPicker
            value={form.asset_id || null}
            onChange={(id) => setForm((prev) => ({ ...prev, asset_id: id ?? '' }))}
            placeholder="Search and select an asset..."
            data-testid="access-request-asset-picker"
          />
        </div>
        <div className="form-group">
          <label htmlFor="create-dataset_id">Dataset (optional)</label>
          <DatasetPicker
            value={form.dataset_id || null}
            onChange={(id) => setForm((prev) => ({ ...prev, dataset_id: id ?? '' }))}
            assetId={form.asset_id || undefined}
            placeholder="Search and select a dataset..."
            data-testid="access-request-dataset-picker"
          />
        </div>
        <div className="form-group">
          <label htmlFor="create-file_id">File (optional)</label>
          <FilePicker
            value={form.file_id || null}
            onChange={(id) => setForm((prev) => ({ ...prev, file_id: id ?? '' }))}
            assetId={form.asset_id || undefined}
            datasetId={form.dataset_id || undefined}
            placeholder="Search and select a file..."
            data-testid="access-request-file-picker"
          />
        </div>
        <div className="form-group">
          <label htmlFor="create-type">Requested access type</label>
          <select
            id="create-type"
            value={form.requested_access_type}
            onChange={(e) => setForm((prev) => ({ ...prev, requested_access_type: e.target.value }))}
          >
            <option value="READ">READ</option>
            <option value="WRITE">WRITE</option>
            <option value="DOWNLOAD">DOWNLOAD</option>
          </select>
        </div>
        <div className="form-actions">
          <Button variant="secondary" onClick={() => navigate('/governance')}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" loading={createMutation.isPending}>
            Create
          </Button>
        </div>
      </form>
    </div>
  );
}
