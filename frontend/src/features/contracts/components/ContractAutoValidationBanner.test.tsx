/**
 * ContractAutoValidationBanner — 222.5 tests.
 *
 * Renders an inline banner reflecting the result of the dry-run validation
 * performed by useAutoValidateContract. Real Banner/hook — only apiClient
 * is auto-mocked.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../../../shared/api/client');

import { apiClient } from '../../../shared/api/client';
import type { DraftValidationResult } from '../../../shared/types/contracts';
import { ContractAutoValidationBanner } from './ContractAutoValidationBanner';

function wrap(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

const baseContract = {
  id: 'c-1',
  original_raw: '{"id":"x"}',
  original_format: 'JSON' as const,
};

const valid: DraftValidationResult = {
  valid: true,
  detected_spec_type: 'ODCS',
  detected_spec_version: '3.0.0',
  normalization_status: 'NORMALIZED_OK',
  normalization_errors: [],
  normalization_warnings: [],
};

const warn: DraftValidationResult = {
  ...valid,
  normalization_status: 'NORMALIZED_WITH_WARNINGS',
  normalization_warnings: ['deprecated `spec.version`', 'field ignored'],
};

const invalid: DraftValidationResult = {
  ...valid,
  valid: false,
  normalization_status: 'NORMALIZATION_FAILED',
  normalization_errors: ['missing `id`', 'invalid `schema`'],
};

describe('ContractAutoValidationBanner', () => {
  let queryClient: QueryClient;
  beforeEach(() => {
    vi.clearAllMocks();
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
  });

  it('renders nothing while idle (no contract)', () => {
    const { container } = render(<ContractAutoValidationBanner contract={null} />, {
      wrapper: wrap(queryClient),
    });
    expect(container.textContent).toBe('');
  });

  it('renders a green "Contract valid" banner when dry-run succeeds clean', async () => {
    vi.mocked(apiClient.getClient().post).mockResolvedValue({ data: valid } as never);
    render(<ContractAutoValidationBanner contract={baseContract} />, {
      wrapper: wrap(queryClient),
    });
    await waitFor(() => {
      expect(screen.getByTestId('contract-auto-validation-banner')).toHaveTextContent(
        /contract valid/i,
      );
    });
    const banner = screen.getByTestId('contract-auto-validation-banner');
    expect(banner.querySelector('.banner--success')).not.toBeNull();
  });

  it('renders a yellow "Validation warnings" banner with the count', async () => {
    vi.mocked(apiClient.getClient().post).mockResolvedValue({ data: warn } as never);
    render(<ContractAutoValidationBanner contract={baseContract} />, {
      wrapper: wrap(queryClient),
    });
    await waitFor(() => {
      expect(screen.getByTestId('contract-auto-validation-banner')).toHaveTextContent(
        /validation warnings:\s*2/i,
      );
    });
    const banner = screen.getByTestId('contract-auto-validation-banner');
    expect(banner.querySelector('.banner--warning')).not.toBeNull();
  });

  it('renders a red "Validation failed" banner with a summary', async () => {
    vi.mocked(apiClient.getClient().post).mockResolvedValue({ data: invalid } as never);
    render(<ContractAutoValidationBanner contract={baseContract} />, {
      wrapper: wrap(queryClient),
    });
    await waitFor(() => {
      expect(screen.getByTestId('contract-auto-validation-banner')).toHaveTextContent(
        /validation failed/i,
      );
    });
    expect(screen.getByTestId('contract-auto-validation-banner')).toHaveTextContent(
      /missing `id`/,
    );
    const banner = screen.getByTestId('contract-auto-validation-banner');
    expect(banner.querySelector('.banner--error')).not.toBeNull();
  });
});
