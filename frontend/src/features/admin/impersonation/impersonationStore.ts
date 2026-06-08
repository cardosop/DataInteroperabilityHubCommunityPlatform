/**
 * Phase 235.4 — Impersonation client-side session state.
 *
 * Tracks the active impersonation session (if any) so the
 * ``ImpersonationBanner`` can render at the top of every page while
 * the operator is impersonating.
 *
 * Cross-cutting concerns (correctness contract)
 * =============================================
 *
 * 1. **JWT persistence across reload** — the impersonation Bearer
 *    token MUST survive a page reload, or the SPA silently reverts
 *    to the operator's identity mid-investigation. Persistence
 *    lives in two places that MUST agree:
 *
 *    * ``apiClient.setImpersonationToken`` — writes the token to
 *      ``localStorage['impersonation_access_token']`` so the
 *      ``_buildHeaders`` path picks it up on the very first request
 *      after reload.
 *    * ``useImpersonationStore`` (this file) — persists the session
 *      metadata under ``localStorage['impersonation_session']`` so
 *      the banner can render without an additional round-trip.
 *
 *    The store is responsible for keeping the two in sync — every
 *    ``setSession`` call ALSO updates the apiClient token, and every
 *    ``clearSession`` clears it. Component code MUST NOT call
 *    ``apiClient.setImpersonationToken`` directly to avoid the two
 *    halves drifting.
 *
 * 2. **Separation from authStore** — the impersonation lifecycle is
 *    independent of the underlying user / tenant: a single browser
 *    session can start and end multiple impersonations without ever
 *    logging out. The banner must NOT trigger an authStore refresh
 *    on mount, so coupling the two risks an "infinite refresh" loop
 *    if a future authStore action re-fetches the user on every
 *    banner mount.
 */

import { create } from 'zustand';

import { apiClient } from '../../../shared/api/client';
import type { AdminImpersonateSession } from '../services/adminService';

const SESSION_STORAGE_KEY = 'impersonation_session';

interface PersistedSession {
  session: AdminImpersonateSession;
  impersonator_email: string;
}

function readPersisted(): PersistedSession | null {
  try {
    const raw = localStorage.getItem(SESSION_STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as PersistedSession;
  } catch {
    return null;
  }
}

function writePersisted(value: PersistedSession | null): void {
  try {
    if (value === null) {
      localStorage.removeItem(SESSION_STORAGE_KEY);
    } else {
      localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(value));
    }
  } catch {
    /* localStorage unavailable — banner just doesn't survive reload. */
  }
}

interface ImpersonationState {
  session: AdminImpersonateSession | null;
  impersonatorEmail: string | null;
  /**
   * Open a session: persists the access token in apiClient, persists
   * the session metadata in localStorage, and updates store state in
   * one atomic call. The three writes are ordered: token first (so
   * any concurrent in-flight request that happens to read the new
   * apiClient state picks up the bearer), then localStorage, then
   * the in-memory Zustand state.
   */
  startSession: (
    session: AdminImpersonateSession,
    accessToken: string,
    impersonatorEmail: string,
  ) => void;
  /**
   * Close the active session: reverses ``startSession`` in the
   * opposite order — Zustand first (so banner unmounts immediately),
   * then localStorage, then apiClient token.
   */
  clearSession: () => void;
}

const initialPersisted = readPersisted();

export const useImpersonationStore = create<ImpersonationState>((set) => ({
  session: initialPersisted?.session ?? null,
  impersonatorEmail: initialPersisted?.impersonator_email ?? null,
  startSession: (session, accessToken, impersonatorEmail) => {
    // Order matters — see contract docstring above.
    apiClient.setImpersonationToken(accessToken);
    writePersisted({ session, impersonator_email: impersonatorEmail });
    set({ session, impersonatorEmail });
  },
  clearSession: () => {
    set({ session: null, impersonatorEmail: null });
    writePersisted(null);
    apiClient.setImpersonationToken(null);
  },
}));
