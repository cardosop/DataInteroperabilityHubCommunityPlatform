/**
 * Phase 260.4.A.2 — dataset retire confirmation modal.
 *
 * Pass-2 P2-1 contract (unit-tested in DatasetRetireConfirmModal.test.tsx
 * and pinned by frontend/e2e/features/dataset-retire.spec.ts):
 *   - explicit consequences copy (irreversible + retention window +
 *     hard-deletion) and the dataset name
 *   - "I understand" acknowledge checkbox
 *     ``data-testid="dataset-retire-confirm-acknowledge"``
 *   - destructive confirm CTA ``data-testid="dataset-retire-confirm-cta"``,
 *     disabled until the checkbox is ticked (and while ``isPending``)
 *   - container ``data-testid="dataset-retire-confirm-modal"`` with
 *     role="dialog", aria-modal="true", aria-labelledby
 *   - Cancel (``dataset-retire-confirm-cancel``) and Esc both call
 *     ``onCancel`` and never ``onConfirm``
 */
import { useEffect, useState } from 'react';
import { Button } from '../../../shared/components/Button';
import { useDialogA11y } from '../../../shared/hooks/useFocusManagement';

interface DatasetRetireConfirmModalProps {
  open: boolean;
  datasetName: string;
  /** Tenant retention window (days) — surfaced in the consequences copy. */
  retentionDays: number;
  onConfirm: () => void;
  onCancel: () => void;
  isPending?: boolean;
}

export function DatasetRetireConfirmModal({
  open,
  datasetName,
  retentionDays,
  onConfirm,
  onCancel,
  isPending = false,
}: DatasetRetireConfirmModalProps) {
  const [acknowledged, setAcknowledged] = useState(false);

  // Reset the acknowledge gate whenever the modal (re)opens.
  useEffect(() => {
    if (open) setAcknowledged(false);
  }, [open]);

  // W5.4 (R2-F5) — focus trap + initial focus + restore + Escape
  // (replaces the inline Escape-only listener).
  const modalRef = useDialogA11y(open, onCancel);

  if (!open) return null;

  return (
    <div
      ref={modalRef}
      className="modal-overlay"
      data-testid="dataset-retire-confirm-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="dataset-retire-modal-title"
    >
      <div className="modal-content">
        <h2 id="dataset-retire-modal-title">Retire dataset</h2>
        <p>
          Retiring <strong>{datasetName}</strong> is irreversible. Retired
          datasets stay readable for {retentionDays} days and are then
          hard-deleted. This cannot be undone.
        </p>
        <label className="dataset-retire-acknowledge">
          <input
            type="checkbox"
            data-testid="dataset-retire-confirm-acknowledge"
            checked={acknowledged}
            onChange={(e) => setAcknowledged(e.target.checked)}
          />
          I understand this dataset will be retired.
        </label>
        <div className="modal-actions">
          <Button
            variant="secondary"
            data-testid="dataset-retire-confirm-cancel"
            onClick={onCancel}
            disabled={isPending}
          >
            Cancel
          </Button>
          <Button
            variant="danger"
            data-testid="dataset-retire-confirm-cta"
            disabled={!acknowledged || isPending}
            loading={isPending}
            onClick={onConfirm}
          >
            Retire dataset
          </Button>
        </div>
      </div>
    </div>
  );
}
