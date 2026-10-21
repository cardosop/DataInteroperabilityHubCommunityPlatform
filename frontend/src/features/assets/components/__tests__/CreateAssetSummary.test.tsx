/**
 * Tests for CreateAssetSummary — shows what will be created and progress.
 * TDD: Tests written FIRST.
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { CreateAssetSummary } from '../CreateAssetSummary';

describe('CreateAssetSummary — pre-submit preview', () => {
  it('shows "Will create: Asset" when no data or contract', () => {
    render(
      <CreateAssetSummary hasDataFile={false} hasContract={false} submitting={false} />,
    );
    expect(screen.getByText(/will create.*asset/i)).toBeInTheDocument();
  });

  it('shows "Will create: Asset + Dataset" when data file present', () => {
    render(
      <CreateAssetSummary hasDataFile={true} hasContract={false} submitting={false} />,
    );
    expect(screen.getByText(/asset.*dataset/i)).toBeInTheDocument();
  });

  it('shows "Will create: Asset + Contract" when contract present', () => {
    render(
      <CreateAssetSummary hasDataFile={false} hasContract={true} submitting={false} />,
    );
    expect(screen.getByText(/asset.*contract/i)).toBeInTheDocument();
  });

  it('shows "Will create: Asset + Dataset + Contract" when both present', () => {
    render(
      <CreateAssetSummary hasDataFile={true} hasContract={true} submitting={false} />,
    );
    expect(screen.getByText(/asset.*dataset.*contract/i)).toBeInTheDocument();
  });

  it('shows detected spec type when provided', () => {
    render(
      <CreateAssetSummary
        hasDataFile={false}
        hasContract={true}
        detectedSpecType="ODPS"
        submitting={false}
      />,
    );
    expect(screen.getByText(/ODPS/)).toBeInTheDocument();
  });
});

describe('CreateAssetSummary — submitting state', () => {
  it('shows current step during submission', () => {
    render(
      <CreateAssetSummary
        hasDataFile={true}
        hasContract={true}
        submitting={true}
        currentStep="Creating asset..."
      />,
    );
    expect(screen.getByText(/creating asset/i)).toBeInTheDocument();
  });

  it('shows progress indicator when submitting', () => {
    render(
      <CreateAssetSummary
        hasDataFile={false}
        hasContract={false}
        submitting={true}
        currentStep="Creating asset..."
      />,
    );
    expect(screen.getByRole('status')).toBeInTheDocument();
  });
});
