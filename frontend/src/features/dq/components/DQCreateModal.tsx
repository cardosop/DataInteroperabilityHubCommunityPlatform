/**
 * DQ Create Modal — extracted from DQRunListPage in Track B PR 6.
 *
 * State ownership: modal-local. Closing the modal discards in-progress
 * form input (name/dataset/file/profile selections). This matches typical
 * modal UX and is the deliberate trade-off documented in the plan; if
 * user feedback shows people want to recover dismissed forms, hoist
 * state to the list-page parent and pass as props.
 *
 * Why extracted: the previous in-place renderCreateModal() helper was
 * defined inside the list-page render body, so every parent re-render
 * (status filter change, list refetch) recreated the inline arrow
 * functions passed as picker onChange. The picker components received
 * fresh prop references each time, which can interfere with their
 * internal blur-vs-select race. With the modal as a stable component,
 * useCallback can lock down the change handlers permanently.
 */
import { useCallback, useState } from 'react';
import { AssetPicker } from '../../../shared/components/pickers/AssetPicker';
import { DatasetPicker } from '../../../shared/components/pickers/DatasetPicker';
import { FilePicker } from '../../../shared/components/pickers/FilePicker';
import { Button } from '../../../shared/components/Button';
import { useToast } from '../../../shared/components/Toast';
import { normalizeError } from '../../../shared/utils/errorUtils';
import { useCreateDQRun } from '../hooks/useDQ';

const VALID_PROFILE_KEYS = ['intake_basic_gx', 'intake_basic_soda'];

interface DQCreateModalProps {
  /** Callback fired when the user dismisses the modal without creating. */
  onClose: () => void;
  /** Callback fired with the newly-created DQ run ID after a successful submit. */
  onCreated: (dqRunId: string) => void;
}

interface DQCreateForm {
  asset_id: string;
  dataset_id: string;
  file_id: string;
  profile_key: string;
}

const EMPTY_FORM: DQCreateForm = {
  asset_id: '',
  dataset_id: '',
  file_id: '',
  profile_key: '',
};

export function DQCreateModal({ onClose, onCreated }: DQCreateModalProps) {
  const toast = useToast();
  const createMutation = useCreateDQRun();
  const [createForm, setCreateForm] = useState<DQCreateForm>(EMPTY_FORM);
  const [createError, setCreateError] = useState<string | null>(null);

  // useCallback handlers so picker prop identity is stable across renders —
  // prevents the picker's internal effects from re-firing on every parent render.
  const handleAssetChange = useCallback((id: string | null) => {
    setCreateForm((prev) => ({ ...prev, asset_id: id ?? '' }));
  }, []);
  const handleDatasetChange = useCallback((id: string | null) => {
    setCreateForm((prev) => ({ ...prev, dataset_id: id ?? '' }));
  }, []);
  const handleFileChange = useCallback((id: string | null) => {
    setCreateForm((prev) => ({ ...prev, file_id: id ?? '' }));
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError(null);
    const assetId = createForm.asset_id.trim() || undefined;
    const datasetId = createForm.dataset_id.trim() || undefined;
    const fileId = createForm.file_id.trim() || undefined;
    if (!assetId && !datasetId && !fileId) {
      setCreateError('Provide at least one of: Asset, Dataset, or File');
      return;
    }
    try {
      const run = await createMutation.mutateAsync({
        asset_id: assetId,
        dataset_id: datasetId,
        file_id: fileId,
        profile_key: createForm.profile_key.trim() || undefined,
      });
      toast.success('DQ run created successfully.');
      onCreated(run.id);
    } catch (err: unknown) {
      const msg = normalizeError(err).error.message || 'Failed to create DQ run';
      setCreateError(msg);
      toast.error(msg);
    }
  };

  return (
    <div
      className="dq-create-modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="dq-create-modal-title"
    >
      <div className="dq-create-modal">
        <h2 id="dq-create-modal-title">Create DQ run</h2>
        <form onSubmit={handleSubmit} className="dq-create-form">
          <div className="form-group">
            <label htmlFor="dq-create-asset_id">Asset (optional)</label>
            <AssetPicker
              value={createForm.asset_id || null}
              onChange={handleAssetChange}
              placeholder="Search and select an asset..."
              data-testid="dq-create-asset-picker"
            />
          </div>
          <div className="form-group">
            <label htmlFor="dq-create-dataset_id">Dataset (optional)</label>
            <DatasetPicker
              value={createForm.dataset_id || null}
              onChange={handleDatasetChange}
              assetId={createForm.asset_id || undefined}
              placeholder="Search and select a dataset..."
              data-testid="dq-create-dataset-picker"
            />
          </div>
          <div className="form-group">
            <label htmlFor="dq-create-file_id">File (optional)</label>
            <FilePicker
              value={createForm.file_id || null}
              onChange={handleFileChange}
              assetId={createForm.asset_id || undefined}
              datasetId={createForm.dataset_id || undefined}
              placeholder="Search and select a file..."
              data-testid="dq-create-file-picker"
            />
          </div>
          <div className="form-group">
            <label htmlFor="dq-create-profile_key">Profile key (optional)</label>
            <select
              id="dq-create-profile_key"
              value={createForm.profile_key}
              onChange={(e) =>
                setCreateForm((prev) => ({ ...prev, profile_key: e.target.value }))
              }
            >
              <option value="">Default</option>
              {VALID_PROFILE_KEYS.map((key) => (
                <option key={key} value={key}>
                  {key}
                </option>
              ))}
            </select>
          </div>
          {createError && (
            <p className="dq-create-error" role="alert">
              {createError}
            </p>
          )}
          <div className="dq-create-modal-actions">
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" loading={createMutation.isPending}>
              Create
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
