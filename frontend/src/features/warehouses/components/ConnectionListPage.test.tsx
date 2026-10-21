/**
 * W5.4 (MEDIUM-8) — the warehouse connection list swallowed load
 * failures to console (page stuck on a spinner) and a failed delete
 * escaped as an unhandled rejection. Pins: both surfaces render an
 * error toast; a failed load also renders an inline error state.
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ToastProvider } from '../../../shared/components/Toast';
import { ConnectionListPage } from './ConnectionListPage';

vi.mock('../services/warehouseService', () => ({
  listConnections: vi.fn(),
  testConnection: vi.fn(),
  deleteConnection: vi.fn(),
}));

import { deleteConnection, listConnections } from '../services/warehouseService';

function renderPage() {
  return render(
    <ToastProvider>
      <ConnectionListPage />
    </ToastProvider>,
  );
}

describe('ConnectionListPage failure surfacing (MEDIUM-8)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('surfaces a failed list load instead of a silent eternal spinner', async () => {
    vi.mocked(listConnections).mockRejectedValue(new Error('list rejected'));
    renderPage();

    await waitFor(() => {
      const toast = screen.getByTestId('toast');
      expect(toast).toHaveClass('toast-error');
      expect(toast).toHaveTextContent(/list rejected/i);
    });
    // The page must not stay stuck on the loading state.
    expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
  });

  it('surfaces a failed delete with an error toast', async () => {
    vi.mocked(listConnections).mockResolvedValue([
      {
        id: 'c1',
        name: 'Snowflake prod',
        warehouse_type: 'SNOWFLAKE',
        is_active: true,
      },
    ]);
    vi.mocked(deleteConnection).mockRejectedValue(new Error('delete rejected'));
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const user = userEvent.setup();
    renderPage();

    const deleteBtn = await screen.findByRole('button', { name: /delete/i });
    await user.click(deleteBtn);

    await waitFor(() => {
      const toast = screen.getByTestId('toast');
      expect(toast).toHaveClass('toast-error');
      expect(toast).toHaveTextContent(/delete rejected/i);
    });
  });
});
