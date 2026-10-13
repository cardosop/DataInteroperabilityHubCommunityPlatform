/**
 * TR.P.1 — ProtectedRoute authentication tests (split from ProtectedRoute.test.tsx).
 *
 * Covers basic auth scenarios: authenticated, loading state, login redirect,
 * empty localStorage redirect.  Role-based tests are in ProtectedRoute-roles.test.tsx.
 *
 * Split reduces per-file memory to avoid OOM in vitest worker threads.
 */
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
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

    // The production router ALWAYS has a /login route — rendering the
    // component directly with no /login match makes the unauthenticated
    // branch's <Navigate to="/login" /> loop forever (each navigation
    // re-renders the still-unauthenticated route → infinite
    // render/navigate cycle → worker OOM). Mount it as a route with the
    // login stub so the redirect LANDS.
    render(
      <MemoryRouter initialEntries={["/protected"]}>
        <Routes>
          <Route
            path="/protected"
            element={
              <ProtectedRoute>
                <div>Protected Content</div>
              </ProtectedRoute>
            }
          />
          <Route path="/login" element={<div>Login page</div>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.queryByText("Protected Content")).not.toBeInTheDocument();
    expect(screen.getByText("Login page")).toBeInTheDocument();
  });

  it("empty localStorage redirects to /login on first render", () => {
    mockUseAuthStore.mockReturnValue({
      isAuthenticated: false, user: null, isLoading: false,
    } as never);

    render(
      <MemoryRouter initialEntries={["/admin"]}>
        <Routes>
          <Route
            path="/admin"
            element={
              <ProtectedRoute requiredRole={["TENANT_ADMIN"]}>
                <div>Admin Content</div>
              </ProtectedRoute>
            }
          />
          <Route path="/login" element={<div>Login page</div>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.queryByText("Loading...")).not.toBeInTheDocument();
    expect(screen.queryByText("Admin Content")).not.toBeInTheDocument();
    expect(screen.getByText("Login page")).toBeInTheDocument();
  });
});
