/**
 * TR.P.1 — ProtectedRoute role-based access tests (split from ProtectedRoute.test.tsx).
 *
 * Covers role scenarios: role check, required roles match, role mismatch → 403,
 * store re-evaluation on role change. Auth scenarios are in ProtectedRoute-auth.test.tsx.
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

describe("ProtectedRoute — Role-Based Access", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("redirects to 403 when user lacks required role", () => {
    mockUseAuthStore.mockReturnValue({
      isAuthenticated: true,
      user: { id: "1", email: "test@example.com", name: "Test", tenant_id: "t1", roles: ["USER"] },
      isLoading: false,
    } as never);

    render(
      <MemoryRouter initialEntries={["/admin"]}>
        <ProtectedRoute requiredRole={["ADMIN"]}>
          <div>Admin Content</div>
        </ProtectedRoute>
      </MemoryRouter>,
    );

    expect(screen.queryByText("Admin Content")).not.toBeInTheDocument();
  });

  it("renders children when user has required role", () => {
    mockUseAuthStore.mockReturnValue({
      isAuthenticated: true,
      user: { id: "1", email: "admin@example.com", name: "Admin", tenant_id: "t1", roles: ["USER", "ADMIN"] },
      isLoading: false,
    } as never);

    render(
      <MemoryRouter>
        <ProtectedRoute requiredRole={["ADMIN"]}>
          <div>Admin Content</div>
        </ProtectedRoute>
      </MemoryRouter>,
    );

    expect(screen.getByText("Admin Content")).toBeInTheDocument();
  });

  it("hydrated DE user redirects to /403 on first render (no loading)", () => {
    mockUseAuthStore.mockReturnValue({
      isAuthenticated: true,
      user: { id: "1", email: "de@example.com", name: "Data Engineer", tenant_id: "t1", roles: ["DATA_ENGINEER"] },
      isLoading: false,
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

  it("hydrated TENANT_ADMIN renders children synchronously", () => {
    mockUseAuthStore.mockReturnValue({
      isAuthenticated: true,
      user: { id: "1", email: "admin@example.com", name: "Admin", tenant_id: "t1", roles: ["USER", "TENANT_ADMIN"] },
      isLoading: false,
    } as never);

    render(
      <MemoryRouter>
        <ProtectedRoute requiredRole={["TENANT_ADMIN"]}>
          <div>Admin Content</div>
        </ProtectedRoute>
      </MemoryRouter>,
    );

    expect(screen.getByText("Admin Content")).toBeInTheDocument();
  });

  it("re-evaluates on store update: revoked role triggers redirect", () => {
    mockUseAuthStore.mockReturnValue({
      isAuthenticated: true,
      user: { id: "1", email: "admin@example.com", name: "Admin", tenant_id: "t1", roles: ["USER", "TENANT_ADMIN"] },
      isLoading: false,
    } as never);

    const { rerender } = render(
      <MemoryRouter initialEntries={["/admin"]}>
        <ProtectedRoute requiredRole={["TENANT_ADMIN"]}>
          <div>Admin Content</div>
        </ProtectedRoute>
      </MemoryRouter>,
    );

    expect(screen.getByText("Admin Content")).toBeInTheDocument();

    // Background refresh returns updated roles WITHOUT TENANT_ADMIN
    mockUseAuthStore.mockReturnValue({
      isAuthenticated: true,
      user: { id: "1", email: "admin@example.com", name: "Admin", tenant_id: "t1", roles: ["USER"] },
      isLoading: false,
    } as never);

    rerender(
      <MemoryRouter initialEntries={["/admin"]}>
        <ProtectedRoute requiredRole={["TENANT_ADMIN"]}>
          <div>Admin Content</div>
        </ProtectedRoute>
      </MemoryRouter>,
    );

    expect(screen.queryByText("Admin Content")).not.toBeInTheDocument();
  });
});
