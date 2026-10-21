/**
 * WhatsNewModal — user-facing release notes on first visit after update (278.M.6).
 *
 * Shows on first login after a version bump. Dismissed state is persisted
 * in localStorage keyed by version, so the modal only appears once per release.
 */
import { type FC, useCallback, useEffect, useState } from 'react';
import { Modal } from './Modal';
import './WhatsNewModal.css';

export interface ReleaseNote {
  title: string;
  description: string;
  emoji?: string;
}

export interface WhatsNewModalProps {
  /** Version string for dismissal tracking (e.g. "2.4.0"). */
  version: string;
  /** Release notes to show. */
  notes: ReleaseNote[];
  /** Callback after modal is dismissed. */
  onDismiss?: () => void;
}

const STORAGE_KEY_PREFIX = 'meshant_whats_new_dismissed_';

function isDismissed(version: string): boolean {
  try {
    return localStorage.getItem(`${STORAGE_KEY_PREFIX}${version}`) === '1';
  } catch {
    return false;
  }
}

function markDismissed(version: string): void {
  try {
    localStorage.setItem(`${STORAGE_KEY_PREFIX}${version}`, '1');
    // Prune old keys (keep only current + 1 previous)
    const keys: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i);
      if (k?.startsWith(STORAGE_KEY_PREFIX)) keys.push(k);
    }
    keys.sort().reverse();
    keys.slice(2).forEach((k) => localStorage.removeItem(k));
  } catch { /* localStorage unavailable */ }
}

export const WhatsNewModal: FC<WhatsNewModalProps> = ({
  version,
  notes,
  onDismiss,
}) => {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!isDismissed(version)) {
      // Delay slightly so the page renders behind the modal
      const timer = setTimeout(() => setOpen(true), 800);
      return () => clearTimeout(timer);
    }
  }, [version]);

  const handleClose = useCallback(() => {
    markDismissed(version);
    setOpen(false);
    onDismiss?.();
  }, [version, onDismiss]);

  return (
    <Modal isOpen={open} onClose={handleClose} title="What's New">
      <div className="whats-new-modal" data-testid="whats-new-modal">
        <p className="whats-new-modal__version">
          Version {version}
        </p>
        <ul className="whats-new-modal__list">
          {notes.map((note) => (
            <li key={note.title} className="whats-new-modal__item">
              <span className="whats-new-modal__emoji" aria-hidden="true">
                {note.emoji ?? '✨'}
              </span>
              <div className="whats-new-modal__item-body">
                <strong className="whats-new-modal__item-title">{note.title}</strong>
                <p className="whats-new-modal__item-desc">{note.description}</p>
              </div>
            </li>
          ))}
        </ul>
        <div className="whats-new-modal__actions">
          <button
            type="button"
            className="whats-new-modal__dismiss"
            onClick={handleClose}
          >
            Got it
          </button>
        </div>
      </div>
    </Modal>
  );
};
