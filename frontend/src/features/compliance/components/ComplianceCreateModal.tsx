/**
 * Compliance Create Modal — extracted from ComplianceRunListPage in
 * Track B PR 6. See DQCreateModal.tsx for the rationale (state ownership
 * choice, why useCallback handlers matter for picker prop stability).
 */
import { useCallback, useState } from 'react';
import { AssetPicker } from '../../../shared/components/pickers/AssetPicker';
import { DatasetPicker } from '../../../shared/components/pickers/DatasetPicker';
import { FilePicker } from '../../../shared/components/pickers/FilePicker';
import { Button } from '../../../shared/components/Button';
import { useToast } from '../../../shared/components/Toast';
import { normalizeError } from '../../../shared/utils/errorUtils';
import { useCreateComplianceRun } from '../hooks/useCompliance';

interface ComplianceCreateModalProps {
  onClose: () => void;
  onCreated: (complianceRunId: string) => void;
}

interface ComplianceCreateForm {
  asset_id: string;
  dataset_id: string;
  file_id: string;
  scan_mode: 'internal' | 'external';
  applicable_regulations: string;
}

const EMPTY_FORM: ComplianceCreateForm = {
  asset_id: '',
  dataset_id: '',
  file_id: '',
  scan_mode: 'internal',
  applicable_regulations: '',
};

export function ComplianceCreateModal({
  onClose,
  onCreated,
}: ComplianceCreateModalProps) {
  const toast = useToast();
  const createMutation = useCreateComplianceRun();
  const [createForm, setCreateForm] = useState<ComplianceCreateForm>(EMPTY_FORM);
  const [createError, setCreateError] = useState<string | null>(null);

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
    const regs = createForm.applicable_regulations
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    try {
      const run = await createMutation.mutateAsync({
        asset_id: assetId,
        dataset_id: datasetId,
        file_id: fileId,
        scan_mode: createForm.scan_mode,
        applicable_regulations: regs.length ? regs : undefined,
      });
      toast.success('Compliance run created successfully.');
      onCreated(run.id);
    } catch (err: unknown) {
      const msg =
        normalizeError(err).error.message || 'Failed to create compliance run';
      setCreateError(msg);
      toast.error(msg);
    }
  };

  return (
    <div
      className="compliance-create-modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="compliance-create-modal-title"
    >
      <div className="compliance-create-modal">
        <h2 id="compliance-create-modal-title">Create compliance run</h2>
        <form onSubmit={handleSubmit} className="compliance-create-form">
          <div className="form-group">
            <label htmlFor="compliance-create-asset_id">Asset (optional)</label>
            <AssetPicker
              value={createForm.asset_id || null}
              onChange={handleAssetChange}
              placeholder="Search and select an asset..."
              data-testid="compliance-create-asset-picker"
            />
          </div>
          <div className="form-group">
            <label htmlFor="compliance-create-dataset_id">Dataset (optional)</label>
            <DatasetPicker
              value={createForm.dataset_id || null}
              onChange={handleDatasetChange}
              assetId={createForm.asset_id || undefined}
              placeholder="Search and select a dataset..."
              data-testid="compliance-create-dataset-picker"
            />
          </div>
          <div className="form-group">
            <label htmlFor="compliance-create-file_id">File (optional)</label>
            <FilePicker
              value={createForm.file_id || null}
              onChange={handleFileChange}
              assetId={createForm.asset_id || undefined}
              datasetId={createForm.dataset_id || undefined}
              placeholder="Search and select a file..."
              data-testid="compliance-create-file-picker"
            />
          </div>
          <div className="form-group">
            <label htmlFor="compliance-create-scan_mode">Scan mode</label>
            <select
              id="compliance-create-scan_mode"
              value={createForm.scan_mode}
              onChange={(e) =>
                setCreateForm((prev) => ({
                  ...prev,
                  scan_mode: e.target.value as 'internal' | 'external',
                }))
              }
            >
              <option value="internal">Internal</option>
              <option value="external">External</option>
            </select>
          </div>
          <div className="form-group">
            <label htmlFor="compliance-create-regulations">
              Applicable regulations (comma-separated, optional)
            </label>
            <input
              id="compliance-create-regulations"
              type="text"
              value={createForm.applicable_regulations}
              onChange={(e) =>
                setCreateForm((prev) => ({
                  ...prev,
                  applicable_regulations: e.target.value,
                }))
              }
              placeholder="e.g. GDPR, HIPAA"
            />
          </div>
          {createError && (
            <p className="compliance-create-error" role="alert">
              {createError}
            </p>
          )}
          <div className="compliance-create-modal-actions">
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
