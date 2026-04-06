/**
 * Tests for ODPS → Contracts backward-compat redirects.
 *
 * TDD: Tests written FIRST.
 */

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MemoryRouter, Route, Routes, Navigate, useParams } from 'react-router-dom';

// ---------------------------------------------------------------------------
// We test the redirect behavior independently of the full router.
// This verifies the <Navigate replace> components work correctly.
// ---------------------------------------------------------------------------

/** Helper component for /odps/:id redirect (needs useParams) */
function OdpsIdRedirect() {
  const { id } = useParams<{ id: string }>();
  return <Navigate to={`/contracts/${id}`} replace />;
}

function RedirectTestHarness({ initialPath }: { initialPath: string }) {
  return (
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        {/* Redirect routes (same as routes.tsx) */}
        <Route path="/odps" element={<Navigate to="/contracts?spec_type=ODPS" replace />} />
        <Route path="/odps/upload" element={<Navigate to="/contracts/create" replace />} />
        <Route path="/odps/:id" element={<OdpsIdRedirect />} />

        {/* Target routes */}
        <Route path="/contracts" element={<div data-testid="contracts-list">Contracts List</div>} />
        <Route path="/contracts/create" element={<div data-testid="contracts-create">Create Contract</div>} />
        <Route path="/contracts/:id" element={<div data-testid="contracts-detail">Contract Detail</div>} />
      </Routes>
    </MemoryRouter>
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ODPS backward-compat redirects', () => {
  it('/odps redirects to /contracts?spec_type=ODPS', () => {
    render(<RedirectTestHarness initialPath="/odps" />);
    expect(screen.getByTestId('contracts-list')).toBeInTheDocument();
  });

  it('/odps/upload redirects to /contracts/create', () => {
    render(<RedirectTestHarness initialPath="/odps/upload" />);
    expect(screen.getByTestId('contracts-create')).toBeInTheDocument();
  });

  it('/odps/:id redirects to /contracts/:id', () => {
    render(<RedirectTestHarness initialPath="/odps/abc-123" />);
    expect(screen.getByTestId('contracts-detail')).toBeInTheDocument();
  });
});
