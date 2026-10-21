/**
 * W5.4 (MEDIUM-8) — the warehouse connection detail page swallowed load
 * failures to console (stuck on "Loading...") and test/reflect actions
 * escaped as unhandled rejections. Pins: failures surface via toast +
 * visible error state, and the actions never reject unhandled.
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ToastProvider } from '../../../shared/components/Toast';
import { ConnectionDetailPage } from './ConnectionDetailPage';

vi.mock('../services/warehouseService', () => ({
  getConnection: vi.fn(),
  testConnection: vi.fn(),
  reflectSchema: vi.fn(),
}));

import { getConnection, reflectSchema, testConnection } from '../services/warehouseService';

function renderPage() {
  return render(
    <ToastProvider>
      <ConnectionDetailPage connectionId="c1" />
    </ToastProvider>,
  );
}

describe('ConnectionDetailPage failure surfacing (MEDIUM-8)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('surfaces a failed load with a toast and a visible error state', async () => {
    vi.mocked(getConnection).mockRejectedValue(new Error('load rejected'));
    renderPage();

    await waitFor(() => {
      const toast = screen.getByTestId('toast');
      expect(toast).toHaveClass('toast-error');
      expect(toast).toHaveTextContent(/load rejected/i);
    });
    expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
  });

  it('surfaces a failed test-connection action with an error toast', async () => {
    vi.mocked(getConnection).mockResolvedValue({
      id: 'c1',
      name: 'Snowflake prod',
      warehouse_type: 'SNOWFLAKE',
      is_active: true,
    });
    vi.mocked(testConnection).mockRejectedValue(new Error('test rejected'));
    const user = userEvent.setup();
    renderPage();

    const testBtn = await screen.findByRole('button', { name: /test/i });
    await user.click(testBtn);

    await waitFor(() => {
      const toast = screen.getByTestId('toast');
      expect(toast).toHaveClass('toast-error');
      expect(toast).toHaveTextContent(/test rejected/i);
    });
  });

  it('surfaces a failed schema reflect with an error toast', async () => {
    vi.mocked(getConnection).mockResolvedValue({
      id: 'c1',
      name: 'Snowflake prod',
      warehouse_type: 'SNOWFLAKE',
      is_active: true,
    });
    vi.mocked(reflectSchema).mockRejectedValue(new Error('reflect rejected'));
    const user = userEvent.setup();
    renderPage();

    await user.type(await screen.findByRole('textbox'), 'orders');
    const reflectBtn = await screen.findByRole('button', { name: /reflect|load schema/i });
    await user.click(reflectBtn);

    await waitFor(() => {
      const toast = screen.getByTestId('toast');
      expect(toast).toHaveClass('toast-error');
      expect(toast).toHaveTextContent(/reflect rejected/i);
    });
  });
});
