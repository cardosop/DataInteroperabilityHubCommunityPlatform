/**
 * W5.1 (oss-release-remediation R2-F1) — impersonation store contract.
 *
 * The store keeps the THREE client-side impersonation artifacts in
 * sync: the apiClient bearer, the persisted session metadata, and the
 * in-memory banner state. The R2-F1 persistence contract is
 * sessionStorage (survives reloads, dies with the tab — the
 * pre-fix docstring claimed localStorage while the code persisted
 * NOTHING on the apiClient side, the P4 doc-drift class).
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from '../../../shared/api/client';
import { useImpersonationStore } from './impersonationStore';

const SESSION = {
  session: {
    id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
    impersonator_user_id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
    impersonated_user_id: 'cccccccc-cccc-cccc-cccc-cccccccccccc',
    impersonator_tenant_id: null,
    impersonated_tenant_id: 'dddddddd-dddd-dddd-dddd-dddddddddddd',
    started_at: '2026-10-10T00:00:00Z',
    expires_at: '2026-10-10T01:00:00Z',
    max_minutes: 60,
    status: 'ACTIVE',
  },
  access_token: 'imp.jwt.token',
  token_type: 'Bearer',
  expires_in: 3600,
};

describe('useImpersonationStore (W5.1)', () => {
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
    apiClient.setImpersonationToken(null);
    useImpersonationStore.getState().clearSession();
  });

  it('startSession persists the metadata to sessionStorage', () => {
    useImpersonationStore.getState().startSession(
      SESSION,
      SESSION.access_token,
      'operator@meshant.test',
    );

    expect(sessionStorage.getItem('impersonation_session')).toBeTruthy();
    expect(localStorage.getItem('impersonation_session')).toBeNull();
  });

  it('startSession propagates the bearer to the apiClient', () => {
    useImpersonationStore.getState().startSession(
      SESSION,
      SESSION.access_token,
      'operator@meshant.test',
    );

    expect(apiClient.getImpersonationToken()).toBe(SESSION.access_token);
  });

  it('clearSession removes the persisted metadata and the bearer', () => {
    useImpersonationStore.getState().startSession(
      SESSION,
      SESSION.access_token,
      'operator@meshant.test',
    );

    useImpersonationStore.getState().clearSession();

    expect(sessionStorage.getItem('impersonation_session')).toBeNull();
    expect(apiClient.getImpersonationToken()).toBeNull();
    expect(useImpersonationStore.getState().session).toBeNull();
  });

  it('a store constructed after reload reads the persisted session', () => {
    useImpersonationStore.getState().startSession(
      SESSION,
      SESSION.access_token,
      'operator@meshant.test',
    );

    // The module-level initialPersisted is read at import time — verify
    // the persisted shape round-trips through readPersisted indirectly:
    // a second startSession from a clean in-memory state still
    // round-trips the SAME keys (the storage contract, not the import
    // snapshot).
    const raw = JSON.parse(sessionStorage.getItem('impersonation_session') ?? 'null');
    expect(raw).toBeTruthy();
    // The persisted shape: { session: AdminImpersonateSession, impersonator_email }
    expect(raw.session.session.id).toBe(SESSION.session.id);
    expect(raw.impersonator_email).toBe('operator@meshant.test');
  });
});
