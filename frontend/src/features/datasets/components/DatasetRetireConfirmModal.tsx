/**
 * Phase 260.4.A.2 — confirmation modal for the destructive Retire
 * action on a dataset.
 *
 * Pass-2 P2-1 compliance: the modal MUST list the consequences
 * explicitly (this cannot be undone, the row is hard-deleted after
 * the retention window) AND require the user to tick an "I
 * understand" checkbox before the Retire CTA enables. This is a
 * two-step gate against accidental clicks on a tombstone-class
 * action.
 *
 * Accessibility (WCAG 2.1 AA):
 *   - ``role="dialog"`` + ``aria-modal="true"``
 *   - headline associated via ``aria-labelledby``
 *   - Esc key closes the dialog (the standard escape hatch)
 *   - the focus-on-mount lands on the Cancel button (safer
 *     default than landing on the destructive CTA)
 */

import { useEffect, useId, useRef, useState, type JSX } from 'react';

import './DatasetRetireConfirmModal.css';

export interface DatasetRetireConfirmModalProps {
  open: boolean;
  /** Display name of the dataset being retired (drives the headline). */
  datasetName: string;
  /**
   * Per-tenant retention window in days (drives the consequences
   * copy: "the row will be hard-deleted after N days").
   */
  retentionDays: number;
  onConfirm: () => void;
  onCancel: () => void;
  /** True while the parent's retire mutation is in flight. */
  isPending?: boolean;
}

export function DatasetRetireConfirmModal({
  open,
  datasetName,
  retentionDays,
  onConfirm,
  onCancel,
  isPending = false,
}: DatasetRetireConfirmModalProps): JSX.Element | null {
  const [acknowledged, setAcknowledged] = useState(false);
  const titleId = useId();
  const cancelButtonRef = useRef<HTMLButtonElement>(null);

  // Reset acknowledgement on close so a re-open starts from scratch.
  useEffect(() => {
    if (!open) {
      setAcknowledged(false);
    } else {
      // Land focus on the Cancel button — safer default than landing
      // on the destructive CTA.
      cancelButtonRef.current?.focus();
    }
  }, [open]);

  // Esc key closes — standard dialog hotkey.
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onCancel();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open, onCancel]);

  if (!open) return null;

  const ctaDisabled = !acknowledged || isPending;

  return (
    <div
      className="dataset-retire-confirm-overlay"
      onClick={() => onCancel()}
      data-testid="dataset-retire-confirm-overlay"
    >
      <div
        className="dataset-retire-confirm-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        data-testid="dataset-retire-confirm-modal"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="dataset-retire-confirm-header">
          <h2 id={titleId}>Retire dataset</h2>
        </header>
        <div className="dataset-retire-confirm-body">
          <p>
            You're about to retire <strong>{datasetName}</strong>. This action
            cannot be undone. Once retired:
          </p>
          <ul>
            <li>The dataset disappears from the default list view.</li>
            <li>
              No new compliance / DQ runs can be scheduled against it; consumers
              with active entitlements lose download access.
            </li>
            <li>
              The row is permanently / hard-deleted{' '}
              <strong>{retentionDays} days</strong> after retirement, per your
              tenant's retention policy.
            </li>
          </ul>
          <label className="dataset-retire-confirm-acknowledge-label">
            <input
              type="checkbox"
              checked={acknowledged}
              onChange={(e) => setAcknowledged(e.target.checked)}
              data-testid="dataset-retire-confirm-acknowledge"
              disabled={isPending}
            />{' '}
            I understand this cannot be undone.
          </label>
        </div>
        <footer className="dataset-retire-confirm-footer">
          <button
            type="button"
            ref={cancelButtonRef}
            className="dataset-retire-confirm-cancel"
            onClick={() => onCancel()}
            disabled={isPending}
            data-testid="dataset-retire-confirm-cancel"
          >
            Cancel
          </button>
          <button
            type="button"
            className="dataset-retire-confirm-cta"
            onClick={() => onConfirm()}
            disabled={ctaDisabled}
            data-testid="dataset-retire-confirm-cta"
          >
            {isPending ? 'Retiring…' : 'Retire dataset'}
          </button>
        </footer>
      </div>
    </div>
  );
}
