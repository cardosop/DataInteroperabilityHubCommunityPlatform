/**
 * close-test-coverage-gaps 3.0 — TenantSignupPage contract.
 *
 * Checkpoint 3.0 verified the backend `admin/tenants/` permission contract:
 * org creation is PLATFORM_ADMIN-only, and POST /api/v1/admin/tenants/
 * accepts EXACTLY `{slug, display_name, jurisdiction, admin_email,
 * plan_slug?}` (AdminTenantCreateSerializer). The previous page posted a
 * self-service-shaped payload (`name`, `admin_name`, no jurisdiction) that
 * 400'd even for platform admins. This suite pins the reworked contract:
 *
 * - posts `{slug, display_name, jurisdiction, admin_email, plan_slug}` to
 *   `admin/tenants/`;
 * - jurisdiction is a REQUIRED select from the regime registry mirrored
 *   from `hub.apps.tenants.validators.VALID_COMPLIANCE_REGIMES` (no public
 *   listing endpoint exists — the list is a pinned mirror);
 * - success renders the invitation copy + workspace ID from
 *   `response.data.tenant.id`;
 * - DRF error shapes are parsed: 400 field errors, 422
 *   TENANT_SLUG_DUPLICATE / ADMIN_EMAIL_DUPLICATE, 401/403.
 *
 * Pattern: CpoCostOverviewPage.test.tsx — only the API client is mocked.
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { TenantSignupPage } from '../TenantSignupPage';

const mockPost = vi.fn();

vi.mock('../../../../shared/api/client', () => ({
  apiClient: { getClient: () => ({ post: mockPost }) },
}));

function renderPage() {
  return render(<TenantSignupPage />);
}

const VALID_FORM = {
  companyName: 'Acme Corp',
  tenantSlug: 'acme-corp',
  jurisdiction: 'GDPR',
  adminEmail: 'admin@acme.example.com',
};

async function fillDetails(user: ReturnType<typeof userEvent.setup>) {
  // plan step → details step
  await user.click(screen.getByTestId('plan-free'));
  await user.click(screen.getByTestId('plan-continue'));
  await user.type(screen.getByLabelText(/company name/i), VALID_FORM.companyName);
  await user.type(screen.getByLabelText(/workspace url/i), VALID_FORM.tenantSlug);
  await user.selectOptions(screen.getByLabelText(/jurisdiction/i), VALID_FORM.jurisdiction);
  await user.type(screen.getByLabelText(/work email/i), VALID_FORM.adminEmail);
}

const EXPECTED_PAYLOAD = {
  slug: 'acme-corp',
  display_name: 'Acme Corp',
  jurisdiction: 'GDPR',
  admin_email: 'admin@acme.example.com',
  plan_slug: 'free',
};

describe('TenantSignupPage (close-test-coverage-gaps 3.0 contract)', () => {
  beforeEach(() => {
    mockPost.mockReset();
  });

  it('renders the plan step with the three seeded plan slugs', async () => {
    renderPage();
    expect(screen.getByTestId('tenant-signup-page')).toBeDefined();
    expect(screen.getByTestId('plan-free')).toBeDefined();
    expect(screen.getByTestId('plan-pro')).toBeDefined();
    expect(screen.getByTestId('plan-enterprise')).toBeDefined();
    // plan slugs mirror the seeded TenantPlan rows (seed_default_plans)
    expect(screen.getByTestId('plan-free').getAttribute('data-plan-slug')).toBe('free');
  });

  it('posts the AdminTenantCreateSerializer wire shape to admin/tenants/', async () => {
    const user = userEvent.setup();
    mockPost.mockResolvedValue({
      data: {
        tenant: { id: 't-123', slug: 'acme-corp', name: 'Acme Corp' },
        admin_user: { id: 'u-1', email: VALID_FORM.adminEmail, status: 'INVITED' },
      },
    });
    renderPage();
    await fillDetails(user);
    await user.click(screen.getByTestId('signup-submit'));

    await waitFor(() => {
      expect(mockPost).toHaveBeenCalledTimes(1);
    });
    expect(mockPost).toHaveBeenCalledWith('admin/tenants/', EXPECTED_PAYLOAD);
  });

  it('requires jurisdiction — no POST without it', async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByTestId('plan-free'));
    await user.click(screen.getByTestId('plan-continue'));
    await user.type(screen.getByLabelText(/company name/i), VALID_FORM.companyName);
    await user.type(screen.getByLabelText(/workspace url/i), VALID_FORM.tenantSlug);
    await user.type(screen.getByLabelText(/work email/i), VALID_FORM.adminEmail);
    await user.click(screen.getByTestId('signup-submit'));

    expect(screen.getByText(/jurisdiction is required/i)).toBeDefined();
    expect(mockPost).not.toHaveBeenCalled();
  });

  it('mirrors the backend regime registry (pinned drift guard)', async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByTestId('plan-free'));
    await user.click(screen.getByTestId('plan-continue'));
    const select = screen.getByLabelText(/jurisdiction/i) as HTMLSelectElement;
    const options = Array.from(select.options).map((o) => o.value);
    // VALID_COMPLIANCE_REGIMES (hub/apps/tenants/validators.py) has 32
    // entries — a backend addition/removal must sync here (no public
    // listing endpoint exists yet).
    expect(options).toHaveLength(32);
    expect(options).toContain('GDPR');
    expect(options).toContain('LGPD');
    expect(options).toContain('CCPA');
    expect(options).toContain('PIPL_CN');
    expect(options).toContain('PCI_DSS');
  });

  it('renders the invitation success copy with the workspace ID', async () => {
    const user = userEvent.setup();
    mockPost.mockResolvedValue({
      data: {
        tenant: { id: 't-123', slug: 'acme-corp', name: 'Acme Corp' },
        admin_user: { id: 'u-1', email: VALID_FORM.adminEmail, status: 'INVITED' },
      },
    });
    renderPage();
    await fillDetails(user);
    await user.click(screen.getByTestId('signup-submit'));

    await waitFor(() => {
      expect(screen.getByTestId('tenant-signup-done')).toBeDefined();
    });
    expect(screen.getByText(/admin@acme\.example\.com/)).toBeDefined();
    expect(screen.getByText(/t-123/)).toBeDefined();
  });

  it('surfaces 400 field errors from the platform envelope', async () => {
    const user = userEvent.setup();
    // REAL wire shape (hub/apps/api/exceptions.py): the exception
    // handler wraps 400s in the error envelope AND preserves field
    // errors at the TOP level as plain strings — never arrays, never
    // a raw-DRF {detail} key.
    mockPost.mockRejectedValue({
      response: {
        status: 400,
        data: {
          error: {
            code: 'VALIDATION_ERROR',
            message: 'Validation failed.',
            http_status: 400,
          },
          display_name: 'This field is required.',
        },
      },
    });
    renderPage();
    await fillDetails(user);
    await user.click(screen.getByTestId('signup-submit'));

    await waitFor(() => {
      expect(screen.getByText(/Company name: This field is required\./i)).toBeDefined();
    });
  });

  it('maps 422 TENANT_SLUG_DUPLICATE to a friendly message', async () => {
    const user = userEvent.setup();
    mockPost.mockRejectedValue({
      response: {
        status: 422,
        data: { code: 'TENANT_SLUG_DUPLICATE', detail: "A tenant with slug 'acme-corp' already exists." },
      },
    });
    renderPage();
    await fillDetails(user);
    await user.click(screen.getByTestId('signup-submit'));

    await waitFor(() => {
      expect(screen.getByText(/already taken/i)).toBeDefined();
    });
  });

  it('maps 422 ADMIN_EMAIL_DUPLICATE to a friendly message', async () => {
    const user = userEvent.setup();
    mockPost.mockRejectedValue({
      response: {
        status: 422,
        data: { code: 'ADMIN_EMAIL_DUPLICATE', detail: 'A user with this email already exists.' },
      },
    });
    renderPage();
    await fillDetails(user);
    await user.click(screen.getByTestId('signup-submit'));

    await waitFor(() => {
      expect(screen.getByText(/already registered/i)).toBeDefined();
    });
  });

  it('maps 403 to the platform-admin-only message (real envelope)', async () => {
    const user = userEvent.setup();
    // REAL wire shape: the platform envelope carries error.code
    // AUTH_FORBIDDEN — there is no raw-DRF {detail} key on the wire.
    mockPost.mockRejectedValue({
      response: {
        status: 403,
        data: {
          error: {
            code: 'AUTH_FORBIDDEN',
            message: 'You do not have permission to perform this action.',
            http_status: 403,
          },
        },
      },
    });
    renderPage();
    await fillDetails(user);
    await user.click(screen.getByTestId('signup-submit'));

    await waitFor(() => {
      expect(screen.getByText('Only platform administrators can create workspaces.')).toBeDefined();
    });
  });

  it('maps 401 to the sign-in message (real envelope)', async () => {
    const user = userEvent.setup();
    mockPost.mockRejectedValue({
      response: {
        status: 401,
        data: {
          error: {
            code: 'AUTH_REQUIRED',
            message: 'Authentication credentials were not provided.',
            http_status: 401,
          },
        },
      },
    });
    renderPage();
    await fillDetails(user);
    await user.click(screen.getByTestId('signup-submit'));

    await waitFor(() => {
      expect(screen.getByText('You must be signed in as a platform administrator.')).toBeDefined();
    });
  });
});
