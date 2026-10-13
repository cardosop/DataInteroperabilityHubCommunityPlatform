/**
 * Vitest pins for the DLT pipelines page (openspec
 * add-databricks-dlt-pipelines task 10.7).
 *
 * The service module is the sanctioned seam (the repo's frontend
 * convention — the page logic itself is real): the pins assert the
 * rendered mirror states, the flag-off banner, the machine-readable
 * error surface, and that start/stop call the service with the exact
 * args the views expect.
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { DatabricksDltPipeline } from '@/shared/types/databricks';

import { DltPipelinesPage } from './DltPipelinesPage';

import { DatabricksApiError, listDltPipelines, startDltUpdate, stopDltPipeline } from '../services/dltService';

vi.mock('../services/dltService', () => {
  class MockError extends Error {
    code?: string;
    constructor(message: string, code?: string) {
      super(message);
      this.name = 'DatabricksApiError';
      this.code = code;
    }
  }
  return {
    DatabricksApiError: MockError,
    listDltPipelines: vi.fn(),
    startDltUpdate: vi.fn(),
    stopDltPipeline: vi.fn(),
  };
});

const mockedList = vi.mocked(listDltPipelines);
const mockedStart = vi.mocked(startDltUpdate);
const mockedStop = vi.mocked(stopDltPipeline);

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/databricks/workspaces/ws-1/dlt-pipelines']}>
      <Routes>
        <Route path="/databricks/workspaces/:workspaceId/dlt-pipelines" element={<DltPipelinesPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

function row(pipelineId: string, overrides: Partial<DatabricksDltPipeline> = {}): DatabricksDltPipeline {
  return {
    id: `row-${pipelineId}`,
    pipeline_id: pipelineId,
    name: `pipeline ${pipelineId}`,
    state: 'IDLE',
    channel: 'CURRENT',
    settings: {},
    synced_at: '2026-09-14T00:00:00Z',
    latest_update_id: 'u-1',
    latest_update_state: 'COMPLETED',
    ...overrides,
  };
}

describe('DltPipelinesPage', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('renders the mirrored pipeline states and latest updates', async () => {
    mockedList.mockResolvedValue([row('p-1'), row('p-2', { state: 'ACTIVE', latest_update_state: null })]);
    renderPage();

    expect(await screen.findByText('pipeline p-1')).toBeInTheDocument();
    expect(screen.getByText('IDLE')).toBeInTheDocument();
    expect(screen.getByText('COMPLETED')).toBeInTheDocument();
    expect(screen.getByText('-')).toBeInTheDocument();
    expect(mockedList).toHaveBeenCalledWith('ws-1');
  });

  it('renders the distinct flag-off banner', async () => {
    mockedList.mockRejectedValue(
      new DatabricksApiError('disabled', 'DATABRICKS_DLT_PIPELINES_DISABLED'),
    );
    renderPage();

    expect(await screen.findByTestId('dlt-flag-banner')).toBeInTheDocument();
  });

  it('renders the machine-readable code on a failed load', async () => {
    mockedList.mockRejectedValue(new DatabricksApiError('boom', 'DATABRICKS_SERVER_ERROR'));
    renderPage();

    expect(await screen.findByTestId('dlt-error')).toHaveTextContent('DATABRICKS_SERVER_ERROR');
  });

  it('renders the empty state', async () => {
    mockedList.mockResolvedValue([]);
    renderPage();

    expect(await screen.findByTestId('dlt-empty')).toBeInTheDocument();
  });

  it('start ships the full refresh through the service', async () => {
    mockedList.mockResolvedValue([row('p-1')]);
    mockedStart.mockResolvedValue({ update_id: 'u-9' });
    renderPage();

    // The click handler is fire-and-forget async (start → busy reset →
    // reload); flush its whole promise chain inside act so the page's
    // busy/loading updates don't land after the test body ends.
    const startBtn = await screen.findByRole('button', { name: 'Start' });
    await act(async () => {
      fireEvent.click(startBtn);
    });
    await waitFor(() => expect(mockedList).toHaveBeenCalledTimes(2));

    expect(mockedStart).toHaveBeenCalledWith('ws-1', 'p-1', { full_refresh: true });
  });

  it('stop ships through the service', async () => {
    mockedList.mockResolvedValue([row('p-1')]);
    mockedStop.mockResolvedValue({ stopped: true });
    renderPage();

    const stopBtn = await screen.findByRole('button', { name: 'Stop' });
    await act(async () => {
      fireEvent.click(stopBtn);
    });
    await waitFor(() => expect(mockedList).toHaveBeenCalledTimes(2));

    expect(mockedStop).toHaveBeenCalledWith('ws-1', 'p-1');
  });

  it('a start conflict surfaces the inline action error', async () => {
    mockedList.mockResolvedValue([row('p-1')]);
    mockedStart.mockRejectedValue(
      new DatabricksApiError('active', 'DATABRICKS_DLT_UPDATE_CONFLICT'),
    );
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: 'Start' }));

    expect(await screen.findByTestId('dlt-action-error')).toHaveTextContent(
      'An update is already active',
    );
  });
});
