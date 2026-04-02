/**
 * ActivationBlockerDialog Tests
 * Tests the blocker dialog shown when asset activation fails with ASSET_ACTIVATION_BLOCKED.
 * Tests both the component rendering and the extractBlockersFromError utility.
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { type ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  ActivationBlockerDialog,
  extractBlockersFromError,
  type ActivationBlockerDialogProps,
} from './ActivationBlockerDialog';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

function wrapper({ children }: { children: ReactNode }) {
  return <MemoryRouter>{children}</MemoryRouter>;
}

function renderDialog(overrides: Partial<ActivationBlockerDialogProps> = {}) {
  const defaultProps: ActivationBlockerDialogProps = {
    blockers: ['Asset must have an ACTIVE contract'],
    assetId: 'asset-001',
    onDismiss: vi.fn(),
    ...overrides,
  };
  return { ...render(<ActivationBlockerDialog {...defaultProps} />, { wrapper }), props: defaultProps };
}

describe('ActivationBlockerDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render the dialog with role=dialog', () => {
    renderDialog();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('should render the title "Activation Blocked"', () => {
    renderDialog();
    expect(screen.getByText('Activation Blocked')).toBeInTheDocument();
  });

  it('should render all blocker messages', () => {
    renderDialog({
      blockers: [
        'Asset must have an ACTIVE contract',
        'dq_status must be PASS or WARN (current: PENDING)',
      ],
    });
    expect(screen.getByTestId('blocker-item-0')).toHaveTextContent('ACTIVE contract');
    expect(screen.getByTestId('blocker-item-1')).toHaveTextContent('dq_status');
  });

  it('should render "Attach Contract" action for contract blocker', () => {
    renderDialog({ blockers: ['Asset must have an ACTIVE contract'] });
    expect(screen.getByTestId('blocker-action-0')).toHaveTextContent('Attach Contract');
  });

  it('should call onDismiss and navigate when "Attach Contract" action is clicked', async () => {
    const user = userEvent.setup();
    const onDismiss = vi.fn();
    renderDialog({ blockers: ['Asset must have an ACTIVE contract'], onDismiss });
    await user.click(screen.getByTestId('blocker-action-0'));
    expect(onDismiss).toHaveBeenCalled();
    expect(mockNavigate).toHaveBeenCalledWith('/assets/asset-001');
  });

  it('should call onDismiss when Close button is clicked', async () => {
    const user = userEvent.setup();
    const onDismiss = vi.fn();
    renderDialog({ onDismiss });
    await user.click(screen.getByTestId('blocker-dismiss'));
    expect(onDismiss).toHaveBeenCalled();
  });

  it('should call onDismiss when overlay is clicked', async () => {
    const user = userEvent.setup();
    const onDismiss = vi.fn();
    renderDialog({ onDismiss });
    const overlay = screen.getByTestId('activation-blocker-dialog');
    // Click directly on the overlay (not the dialog content inside)
    await user.click(overlay);
    expect(onDismiss).toHaveBeenCalled();
  });

  it('should not show action button for unknown blocker messages', () => {
    renderDialog({ blockers: ['Some unknown requirement'] });
    expect(screen.queryByTestId('blocker-action-0')).not.toBeInTheDocument();
  });

  it('should render action buttons for DQ and compliance blockers (scroll targets)', () => {
    renderDialog({
      blockers: [
        'dq_status must be PASS or WARN (current: PENDING)',
        'compliance_status must be PASS or WARN (current: PENDING)',
      ],
    });
    expect(screen.getByTestId('blocker-action-0')).toHaveTextContent('Run DQ Check');
    expect(screen.getByTestId('blocker-action-1')).toHaveTextContent('Run Compliance Check');
  });

  it('should render action buttons for validation/normalization blockers (scroll targets)', () => {
    renderDialog({
      blockers: [
        'Contract validation_status must be VALID or WARNING_ONLY (current: INVALID)',
        'Contract normalization_status must be NORMALIZED_OK (current: NOT_NORMALIZED)',
      ],
    });
    expect(screen.getByTestId('blocker-action-0')).toHaveTextContent('Validate Contract');
    expect(screen.getByTestId('blocker-action-1')).toHaveTextContent('View Contract');
  });

  it('should scroll to element when DQ blocker action is clicked', async () => {
    const user = userEvent.setup();
    const onDismiss = vi.fn();
    Element.prototype.scrollIntoView = vi.fn();
    renderDialog({ blockers: ['dq_status must be PASS or WARN (current: PENDING)'], onDismiss });
    await user.click(screen.getByTestId('blocker-action-0'));
    expect(onDismiss).toHaveBeenCalled();
  });
});

describe('extractBlockersFromError', () => {
  it('should return null for null/undefined input', () => {
    expect(extractBlockersFromError(null)).toBeNull();
    expect(extractBlockersFromError(undefined)).toBeNull();
  });

  it('should return null for non-ASSET_ACTIVATION_BLOCKED errors', () => {
    const err = { error: { code: 'SOME_OTHER_ERROR', message: 'fail' } };
    expect(extractBlockersFromError(err)).toBeNull();
  });

  it('should extract blockers from normalized ApiError shape (array details)', () => {
    const err = {
      error: {
        code: 'ASSET_ACTIVATION_BLOCKED',
        message: 'Cannot activate',
        details: ['Asset must have an ACTIVE contract', 'dq_status must be PASS'],
      },
    };
    const result = extractBlockersFromError(err);
    expect(result).toEqual(['Asset must have an ACTIVE contract', 'dq_status must be PASS']);
  });

  it('should extract blockers from normalized ApiError shape (object details)', () => {
    const err = {
      error: {
        code: 'ASSET_ACTIVATION_BLOCKED',
        message: 'Cannot activate',
        details: { contract: ['Missing contract'], dq: ['DQ failed'] },
      },
    };
    const result = extractBlockersFromError(err);
    expect(result).toEqual(['Missing contract', 'DQ failed']);
  });

  it('should return code as single blocker when no details array', () => {
    const err = {
      error: {
        code: 'ASSET_ACTIVATION_BLOCKED',
        message: 'Cannot activate',
      },
    };
    const result = extractBlockersFromError(err);
    expect(result).toEqual(['ASSET_ACTIVATION_BLOCKED']);
  });

  it('should extract blockers from raw API error response shape', () => {
    const err = {
      response: {
        data: {
          code: 'ASSET_ACTIVATION_BLOCKED',
          error: 'Cannot activate',
          details: ['Missing contract'],
        },
      },
    };
    const result = extractBlockersFromError(err);
    expect(result).toEqual(['Missing contract']);
  });

  it('should return null for non-object input', () => {
    expect(extractBlockersFromError('string error')).toBeNull();
    expect(extractBlockersFromError(42)).toBeNull();
  });
});
