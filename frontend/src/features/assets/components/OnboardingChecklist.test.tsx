/**
 * OnboardingChecklist Tests
 * Tests the 6-step activation checklist for DRAFT assets.
 * Uses MemoryRouter + Routes (no router mocks).
 */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Contract } from '../../../shared/types/contracts';
import type { Dataset } from '../../../shared/types/datasets';
import { OnboardingChecklist, type OnboardingChecklistProps } from './OnboardingChecklist';

/** Shown when navigation targets /contracts/:id */
function ContractNavMarker() {
  return <div data-testid="nav-contract-detail">contract-detail</div>;
}

function renderChecklist(overrides: Partial<OnboardingChecklistProps> = {}) {
  const defaultProps: OnboardingChecklistProps = {
    contracts: [],
    datasets: [],
    dqStatus: 'PENDING',
    complianceStatus: 'PENDING',
    ...overrides,
  };
  return render(
    <MemoryRouter initialEntries={['/assets/checklist-asset']}>
      <Routes>
        <Route
          path="/assets/:assetId"
          element={<OnboardingChecklist {...defaultProps} />}
        />
        <Route path="/contracts/:id" element={<ContractNavMarker />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('OnboardingChecklist', () => {
  beforeEach(() => {
    Element.prototype.scrollIntoView = vi.fn();
  });

  it('should render the checklist container', () => {
    renderChecklist();
    expect(screen.getByTestId('onboarding-checklist')).toBeInTheDocument();
  });

  it('should render all 7 steps (6 prerequisites + Activate)', () => {
    renderChecklist();
    const steps = screen.getByTestId('onboarding-steps');
    expect(steps.children).toHaveLength(7);
    expect(screen.getByTestId('onboarding-step-activate')).toBeInTheDocument();
  });

  it('should show progress 1/6 when only asset is created (no contract, no dataset)', () => {
    renderChecklist();
    expect(screen.getByTestId('onboarding-progress')).toHaveTextContent('1/6');
  });

  it('should mark step 1 (Create Asset) as always completed', () => {
    renderChecklist();
    const step = screen.getByTestId('onboarding-step-create-asset');
    expect(step).toHaveClass('completed');
  });

  it('should mark step 2 (Attach Contract) as completed when contracts exist', () => {
    renderChecklist({ contracts: [makeContract()] });
    const step = screen.getByTestId('onboarding-step-attach-contract');
    expect(step).toHaveClass('completed');
  });

  it('should mark step 2 (Attach Contract) as pending when no contracts', () => {
    renderChecklist({ contracts: [] });
    const step = screen.getByTestId('onboarding-step-attach-contract');
    expect(step).toHaveClass('pending');
  });

  it('should show "Attach Contract" action button when no contracts', () => {
    renderChecklist({ contracts: [] });
    expect(screen.getByTestId('onboarding-action-attach-contract')).toBeInTheDocument();
  });

  it('should NOT show action button for step 2 when contracts exist', () => {
    renderChecklist({ contracts: [makeContract()] });
    expect(screen.queryByTestId('onboarding-action-attach-contract')).not.toBeInTheDocument();
  });

  it('should mark step 3 (Validate & Normalize) as completed with valid, normalized contract', () => {
    renderChecklist({
      contracts: [makeContract({ normalization_status: 'NORMALIZED_OK', validation_status: 'VALID' })],
    });
    const step = screen.getByTestId('onboarding-step-validate-contract');
    expect(step).toHaveClass('completed');
  });

  it('should mark step 3 as pending with contract that has NOT_NORMALIZED status', () => {
    renderChecklist({
      contracts: [makeContract({ normalization_status: 'NOT_NORMALIZED', validation_status: 'VALID' })],
    });
    const step = screen.getByTestId('onboarding-step-validate-contract');
    expect(step).toHaveClass('pending');
  });

  it('should navigate to contract detail when "View Contract" action is clicked', async () => {
    const user = userEvent.setup();
    renderChecklist({
      contracts: [makeContract({ id: 'c-123', normalization_status: 'NOT_NORMALIZED', validation_status: 'INVALID' })],
    });
    const action = screen.getByTestId('onboarding-action-validate-contract');
    await user.click(action);
    expect(screen.getByTestId('nav-contract-detail')).toBeInTheDocument();
  });

  it('should mark step 4 (Upload Dataset) as completed when datasets exist', () => {
    renderChecklist({ datasets: [makeDataset()] });
    const step = screen.getByTestId('onboarding-step-upload-dataset');
    expect(step).toHaveClass('completed');
  });

  it('should mark step 5 (DQ) as completed when dqStatus is PASS', () => {
    renderChecklist({ dqStatus: 'PASS', datasets: [makeDataset()] });
    const step = screen.getByTestId('onboarding-step-run-dq');
    expect(step).toHaveClass('completed');
  });

  it('should mark step 5 (DQ) as completed for contract-only asset (no dataset, has contract)', () => {
    renderChecklist({ contracts: [makeContract()], datasets: [], dqStatus: 'PENDING' });
    const step = screen.getByTestId('onboarding-step-run-dq');
    expect(step).toHaveClass('completed');
  });

  it('should mark step 6 (Compliance) as completed when complianceStatus is COMPLIANT', () => {
    renderChecklist({ complianceStatus: 'COMPLIANT', datasets: [makeDataset()] });
    const step = screen.getByTestId('onboarding-step-run-compliance');
    expect(step).toHaveClass('completed');
  });

  it('should mark step 6 (Compliance) as completed for contract-only asset', () => {
    renderChecklist({ contracts: [makeContract()], datasets: [], complianceStatus: 'PENDING' });
    const step = screen.getByTestId('onboarding-step-run-compliance');
    expect(step).toHaveClass('completed');
  });

  it('should show progress 6/6 when all steps are completed', () => {
    renderChecklist({
      contracts: [makeContract({ normalization_status: 'NORMALIZED_OK', validation_status: 'VALID' })],
      datasets: [makeDataset()],
      dqStatus: 'PASS',
      complianceStatus: 'COMPLIANT',
    });
    expect(screen.getByTestId('onboarding-progress')).toHaveTextContent('6/6');
  });

  it('should show correct progress for contract-only path (DQ/Compliance skipped as satisfied)', () => {
    renderChecklist({
      contracts: [makeContract({ normalization_status: 'NORMALIZED_OK', validation_status: 'VALID' })],
      datasets: [],
      dqStatus: 'PENDING',
      complianceStatus: 'PENDING',
    });
    expect(screen.getByTestId('onboarding-progress')).toHaveTextContent('5/6');
  });

  it('should render progress bar with correct width percentage', () => {
    renderChecklist({
      contracts: [makeContract({ normalization_status: 'NORMALIZED_OK', validation_status: 'VALID' })],
      datasets: [makeDataset()],
      dqStatus: 'PENDING',
      complianceStatus: 'PENDING',
    });
    const bar = screen.getByTestId('onboarding-progress-bar');
    expect(bar.style.width).toBe('67%');
  });

  it('should scroll to contracts section when "Attach Contract" action is clicked without assetId', async () => {
    const user = userEvent.setup();
    renderChecklist();
    const action = screen.getByTestId('onboarding-action-attach-contract');
    await user.click(action);
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled();
  });

  // ------- 222.4: required vs optional steps, Activate action, Attach-link -------

  it('marks required steps with data-required="true" and optional steps with "false"', () => {
    renderChecklist({ assetId: 'asset-req' });
    expect(
      screen.getByTestId('onboarding-step-create-asset'),
    ).toHaveAttribute('data-required', 'true');
    expect(
      screen.getByTestId('onboarding-step-attach-contract'),
    ).toHaveAttribute('data-required', 'true');
    expect(
      screen.getByTestId('onboarding-step-validate-contract'),
    ).toHaveAttribute('data-required', 'true');
    // Dataset and downstream DQ/Compliance are optional for contract-only assets.
    expect(
      screen.getByTestId('onboarding-step-upload-dataset'),
    ).toHaveAttribute('data-required', 'false');
    expect(
      screen.getByTestId('onboarding-step-run-dq'),
    ).toHaveAttribute('data-required', 'false');
    expect(
      screen.getByTestId('onboarding-step-run-compliance'),
    ).toHaveAttribute('data-required', 'false');
  });

  it('labels optional steps with an "(optional)" tag in the DOM', () => {
    renderChecklist({ assetId: 'asset-opt' });
    const upload = screen.getByTestId('onboarding-step-upload-dataset');
    expect(upload).toHaveTextContent(/\(optional\)/i);
  });

  it('Attach Contract action is a real <a> link to /contracts/create?asset_id=... when assetId present', () => {
    renderChecklist({ assetId: 'asset-abc', contracts: [] });
    const action = screen.getByTestId('onboarding-action-attach-contract');
    expect(action.tagName).toBe('A');
    expect(action).toHaveAttribute(
      'href',
      '/contracts/create?asset_id=asset-abc',
    );
  });

  it('renders Activate step and invokes onActivate when clicked (ready to activate)', async () => {
    const user = userEvent.setup();
    const onActivate = vi.fn();
    renderChecklist({
      assetId: 'asset-ready',
      contracts: [
        makeContract({ normalization_status: 'NORMALIZED_OK', validation_status: 'VALID' }),
      ],
      datasets: [makeDataset()],
      dqStatus: 'PASS',
      complianceStatus: 'COMPLIANT',
      onActivate,
    });
    const activateAction = screen.getByTestId('onboarding-action-activate');
    await user.click(activateAction);
    expect(onActivate).toHaveBeenCalledTimes(1);
  });

  it('disables Activate action while prerequisites are incomplete and does not call onActivate on click', async () => {
    const user = userEvent.setup();
    const onActivate = vi.fn();
    renderChecklist({
      assetId: 'asset-not-ready',
      contracts: [],
      datasets: [],
      onActivate,
    });
    const activateAction = screen.getByTestId('onboarding-action-activate');
    expect(activateAction).toBeDisabled();
    // user.click on a disabled button is a no-op — asserts the handler is
    // gated by the disabled attribute, not by any separate guard inside.
    await user.click(activateAction);
    expect(onActivate).not.toHaveBeenCalled();
  });

  it('disables Activate while isActivating is true even when prerequisites pass', () => {
    renderChecklist({
      assetId: 'asset-inflight',
      contracts: [
        makeContract({ normalization_status: 'NORMALIZED_OK', validation_status: 'VALID' }),
      ],
      datasets: [makeDataset()],
      dqStatus: 'PASS',
      complianceStatus: 'COMPLIANT',
      onActivate: vi.fn(),
      isActivating: true,
    });
    expect(screen.getByTestId('onboarding-action-activate')).toBeDisabled();
  });

  it('Activate is rendered but inert when onActivate is not supplied', () => {
    renderChecklist({
      assetId: 'asset-no-handler',
      contracts: [
        makeContract({ normalization_status: 'NORMALIZED_OK', validation_status: 'VALID' }),
      ],
      datasets: [makeDataset()],
      dqStatus: 'PASS',
      complianceStatus: 'COMPLIANT',
    });
    // Step row is present, but no action button is rendered when the caller
    // does not wire an activate handler — guarding against a broken link.
    expect(screen.getByTestId('onboarding-step-activate')).toBeInTheDocument();
    expect(screen.queryByTestId('onboarding-action-activate')).toBeNull();
  });
});

function makeContract(overrides: Partial<Contract> = {}): Contract {
  return {
    id: 'contract-001',
    original_raw: '{}',
    original_format: 'JSON',
    normalization_status: 'NORMALIZED_OK',
    validation_status: 'VALID',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    created_by: 'user-001',
    tenant_id: 'tenant-001',
    hub_contract_json: {},
    ...overrides,
  };
}

function makeDataset(overrides: Partial<Dataset> = {}): Dataset {
  return {
    id: 'dataset-001',
    name: 'Test Dataset',
    format: 'CSV',
    size_bytes: 1024,
    version: '1',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    tenant_id: 'tenant-001',
    ...overrides,
  };
}
