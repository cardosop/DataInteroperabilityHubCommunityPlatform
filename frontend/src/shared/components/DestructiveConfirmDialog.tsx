/**
 * DestructiveConfirmDialog — typed-name confirmation for dangerous actions (278.C.3).
 *
 * In PRODUCTION, requires the user to type the resource name before the
 * confirm button becomes enabled. In non-production environments a standard
 * confirmation dialog is shown (can be overridden via ``requireConfirmation``).
 */
import { type ReactNode, useState } from 'react';
import { ConfirmDialog } from './ConfirmDialog';
import type { ConfirmDialogVariant } from './ConfirmDialog';
import './DestructiveConfirmDialog.css';

export interface DestructiveConfirmDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  resourceName: string;
  resourceType: string;
  requireConfirmation?: boolean;
  title?: string;
  message?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: ConfirmDialogVariant;
  children?: ReactNode;
}

function isProductionEnvironment(): boolean {
  try {
    if (typeof import.meta !== 'undefined') {
      const env = (import.meta as unknown as { env: Record<string, string> }).env;
      const v = (env?.VITE_ENVIRONMENT ?? '').toLowerCase();
      if (v === 'production' || v === 'prod') return true;
      if (env?.PROD) return true;
    }
  } catch { /* SSR */ }
  return false;
}

export function DestructiveConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  resourceName,
  resourceType,
  requireConfirmation,
  title,
  message,
  confirmLabel = 'Delete',
  cancelLabel = 'Cancel',
  variant = 'danger',
  children,
}: DestructiveConfirmDialogProps) {
  const [typedName, setTypedName] = useState('');
  const needsConfirmation = requireConfirmation ?? isProductionEnvironment();
  const match = typedName.trim() === resourceName.trim();
  const canConfirm = !needsConfirmation || match;

  const defaultTitle = `Delete ${resourceType}`;
  const defaultMessage = needsConfirmation
    ? `This will permanently delete "${resourceName}". Type the ${resourceType} name to confirm.`
    : `Are you sure you want to delete "${resourceName}"? This cannot be undone.`;

  const handleClose = () => {
    setTypedName('');
    onClose();
  };

  const handleConfirm = () => {
    setTypedName('');
    onConfirm();
  };

  return (
    <ConfirmDialog
      isOpen={isOpen}
      onClose={handleClose}
      onConfirm={handleConfirm}
      title={title ?? defaultTitle}
      message={message ?? defaultMessage}
      confirmLabel={confirmLabel}
      cancelLabel={cancelLabel}
      variant={variant}
      confirmDisabled={needsConfirmation && !canConfirm}
    >
      {needsConfirmation && (
        <div className="destructive-confirm-input">
          <label htmlFor="destructive-confirm-name" className="destructive-confirm-label">
            Type <strong>{resourceName}</strong> to confirm:
          </label>
          <input
            id="destructive-confirm-name"
            type="text"
            className="destructive-confirm-field"
            value={typedName}
            onChange={(e) => setTypedName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && canConfirm) {
                e.preventDefault();
                handleConfirm();
              }
            }}
            placeholder={resourceName}
            autoComplete="off"
            spellCheck={false}
            data-testid="destructive-confirm-input"
          />
          {typedName.length > 0 && !match && (
            <p className="destructive-confirm-error" role="alert">
              Name does not match.
            </p>
          )}
        </div>
      )}
      {children}
    </ConfirmDialog>
  );
}
