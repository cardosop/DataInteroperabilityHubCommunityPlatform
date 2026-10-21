/**
 * W5.4 (MEDIUM-8) — the workspace chooser turned a failed SSO workspace
 * load into a silently EMPTY list (the user saw zero workspaces with no
 * explanation). The pin asserts a visible error state; only the
 * ssoWorkspaces seam is stubbed.
 */

import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { WorkspaceChooserModal } from './WorkspaceChooserModal';

vi.mock('../services/databricksSsoService', () => ({
  ssoWorkspaces: vi.fn(),
}));

import { ssoWorkspaces } from '../services/databricksSsoService';

describe('WorkspaceChooserModal failure surfacing (MEDIUM-8)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders a visible error instead of a silent empty list on load failure', async () => {
    vi.mocked(ssoWorkspaces).mockRejectedValue(new Error('sso rejected'));

    render(
      <WorkspaceChooserModal tenantId="t1" onPick={() => {}} onClose={() => {}} />,
    );

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/sso rejected|failed to load/i);
    });
    // Pre-fix: the failure produced an empty <ul> with no explanation.
    expect(screen.queryByRole('list')).not.toBeInTheDocument();
  });

  it('renders the workspace list on success (regression pin)', async () => {
    vi.mocked(ssoWorkspaces).mockResolvedValue([
      { id: 'ws1', name: 'Sandbox', host: 'x.cloud.databricks.com' },
    ]);

    render(
      <WorkspaceChooserModal tenantId="t1" onPick={() => {}} onClose={() => {}} />,
    );

    await waitFor(() => {
      expect(screen.getByRole('list')).toBeInTheDocument();
      expect(screen.getByText(/Sandbox/)).toBeInTheDocument();
    });
  });
});
