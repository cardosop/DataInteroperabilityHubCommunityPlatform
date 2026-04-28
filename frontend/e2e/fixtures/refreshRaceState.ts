/**
 * Refresh-race state machine — pure-logic model of the apiClient's
 * singleton-refresh contract (see frontend/src/shared/api/client.ts —
 * `_refreshAccessToken` at L325). Phase 226.F3.
 *
 * Why this exists:
 *   The production apiClient guards against concurrent 401s by holding
 *   a single in-flight refresh promise (`_refreshPromise`). Every
 *   concurrent caller attaches to the *same* promise; on success they
 *   all receive the new token, on failure they all see the rejection.
 *   The token endpoint is never called more than once per cycle.
 *
 *   That contract is the only thing standing between two parallel
 *   fetches and a refresh-token-burning storm under load. Modelling
 *   it as a pure helper lets the e2e refresh-race spec assert the
 *   invariants it depends on without depending on a particular
 *   browser-side timing model.
 *
 * The class wraps an injected `refresh: () => Promise<T>` so tests can
 * supply a counted / failing / delayed refresher and observe what the
 * state machine does. Production code does the same shape inline; this
 * helper is intentionally a one-to-one mirror.
 */

export type Refresher<T> = () => Promise<T>;

export class RefreshRaceState<T> {
  private inFlight: Promise<T> | null = null;
  private _callCount = 0;
  private _failureCount = 0;
  private _successCount = 0;

  constructor(private readonly refresh: Refresher<T>) {}

  /**
   * Run the refresh, sharing the in-flight promise with any concurrent
   * caller. The first caller after settle starts a new refresh — the
   * promise field is cleared in `finally`.
   */
  async run(): Promise<T> {
    if (this.inFlight) {
      return this.inFlight;
    }
    this._callCount++;
    this.inFlight = (async () => {
      try {
        const out = await this.refresh();
        this._successCount++;
        return out;
      } catch (err) {
        this._failureCount++;
        throw err;
      } finally {
        this.inFlight = null;
      }
    })();
    return this.inFlight;
  }

  /** How many times the underlying refresher was invoked. */
  get refreshInvocations(): number {
    return this._callCount;
  }
  /** How many invocations resolved successfully. */
  get successCount(): number {
    return this._successCount;
  }
  /** How many invocations rejected. */
  get failureCount(): number {
    return this._failureCount;
  }
  /** Snapshot — not a promise; useful for assertions about idle state. */
  get isInFlight(): boolean {
    return this.inFlight !== null;
  }
}

/**
 * Describes the post-401 outcome the apiClient drives, modelled as a
 * pure decision so the spec + the production logic can be cross-checked.
 *
 * Inputs (what the apiClient knows when it gets a 401):
 *   - canRefresh: can the client even try? (cookie mode ALWAYS, or
 *     legacy mode with a refresh_token in memory)
 *   - refreshOk:  did the refresh round-trip succeed?
 *
 * Outputs (the legal post-401 state):
 *   - retry:       retry the original request with the new access token
 *   - clearTokens: wipe local tokens (cookie mode: server clears its cookie)
 *   - redirect:    push the browser to /login
 */
export type Post401Action =
  | { kind: 'retry' }
  | { kind: 'redirect-to-login'; clearTokens: true };

export function decidePost401(input: {
  canRefresh: boolean;
  refreshOk: boolean;
}): Post401Action {
  if (!input.canRefresh) {
    return { kind: 'redirect-to-login', clearTokens: true };
  }
  if (input.refreshOk) {
    return { kind: 'retry' };
  }
  return { kind: 'redirect-to-login', clearTokens: true };
}
