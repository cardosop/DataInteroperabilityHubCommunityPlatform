/**
 * Accessible Modal Component
 * WCAG 2.1 AA compliant modal with focus management
 */

import { useEffect } from 'react';
import { useFocusTrap } from '../hooks/useFocusManagement';
import './Modal.css';

export interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  'aria-describedby'?: string;
}

export function Modal({
  isOpen,
  onClose,
  title,
  children,
  'aria-describedby': ariaDescribedBy,
}: ModalProps) {
  const containerRef = useFocusTrap(isOpen);

  // Handle Escape key
  useEffect(() => {
    if (!isOpen) {
      return;
    }

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isOpen, onClose]);

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }

    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  if (!isOpen) {
    return null;
  }

  return (
    // Phase 226.F1.b — testids on overlay/content/close so e2e specs can
    // open-close modals without `.locator('.modal-overlay')`.
    <div
      className="modal-overlay"
      data-testid="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
      aria-describedby={ariaDescribedBy}
      onClick={(e) => {
        // Close on overlay click
        if (e.target === e.currentTarget) {
          onClose();
        }
      }}
    >
      <div
        className="modal-content"
        data-testid="modal-content"
        ref={containerRef as React.RefObject<HTMLDivElement>}
      >
        <div className="modal-header">
          <h2 id="modal-title">{title}</h2>
          <button
            type="button"
            className="modal-close"
            onClick={onClose}
            aria-label="Close dialog"
            data-testid="modal-close"
          >
            ×
          </button>
        </div>
        <div className="modal-body" data-testid="modal-body">
          {children}
        </div>
      </div>
    </div>
  );
}
