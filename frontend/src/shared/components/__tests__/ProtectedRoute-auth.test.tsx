/**
 * TR.P.1 — ProtectedRoute authentication tests (split from ProtectedRoute.test.tsx).
 *
 * Covers basic auth scenarios: authenticated, loading state, login redirect,
 * empty localStorage redirect.  Role-based tests are in ProtectedRoute-roles.test.tsx.
 *
 * Split reduces per-file memory to avoid OOM in vitest worker threads.
 */
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ProtectedRoute } from "../ProtectedRoute";

vi.mock("../../../features/auth/store/authStore", () => ({
  useAuthStore: vi.fn(),
}));

import { useAuthStore } from "../../../features/auth/store/authStore";

const mockUseAuthStore = vi.mocked(useAuthStore);

describe("ProtectedRoute — Authentication", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders children when user is authenticated", () => {
    mockUseAuthStore.mockReturnValue({
      isAuthenticated: true,
      user: { id: "1", email: "test@example.com", name: "Test", tenant_id: "t1", roles: ["USER"] },
      isLoading: false,
    } as never);

    render(
      <MemoryRouter>
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>
      </MemoryRouter>,
    );

    expect(screen.getByText("Protected Content")).toBeInTheDocument();
  });

  it("shows LoadingSpinner when isLoading is true", () => {
    mockUseAuthStore.mockReturnValue({
      isAuthenticated: false, user: null, isLoading: true,
    } as never);

    render(
      <MemoryRouter>
        <ProtectedRoute><div>Protected Content</div></ProtectedRoute>
      </MemoryRouter>,
    );

    expect(screen.getByText("Loading...")).toBeInTheDocument();
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(screen.queryByText("Protected Content")).not.toBeInTheDocument();
  });

  it("redirects to login when user is not authenticated", () => {
    mockUseAuthStore.mockReturnValue({
      isAuthenticated: false, user: null, isLoading: false,
    } as never);

    render(
      <MemoryRouter initialEntries={["/protected"]}>
        <ProtectedRoute><div>Protected Content</div></ProtectedRoute>
      </MemoryRouter>,
    );

    expect(screen.queryByText("Protected Content")).not.toBeInTheDocument();
  });

  it("empty localStorage redirects to /login on first render", () => {
    mockUseAuthStore.mockReturnValue({
      isAuthenticated: false, user: null, isLoading: false,
    } as never);

    render(
      <MemoryRouter initialEntries={["/admin"]}>
        <ProtectedRoute requiredRole={["TENANT_ADMIN"]}>
          <div>Admin Content</div>
        </ProtectedRoute>
      </MemoryRouter>,
    );

    expect(screen.queryByText("Loading...")).not.toBeInTheDocument();
    expect(screen.queryByText("Admin Content")).not.toBeInTheDocument();
  });
});
