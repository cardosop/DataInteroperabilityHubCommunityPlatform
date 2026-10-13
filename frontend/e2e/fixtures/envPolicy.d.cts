/**
 * Declaration for envPolicy.cjs — the W16 (Phase T.4) environment policy.
 *
 * The module is CommonJS so both the TS specs (esbuild resolves .cjs
 * imports) and the Node-side harness (scripts/tests) can require it
 * unchanged. See envPolicy.cjs for the policy contract.
 */

/** True when the run is a CI run (GitHub Actions sets CI=true). */
export function isCi(): boolean;

/**
 * The policy: call at every environment-dependent branch BEFORE the local
 * skip/fallback. In CI this throws (the environment failure announces
 * itself); locally it is a no-op and the caller proceeds to skip.
 */
export function environmentSkipGuard(detail: string): void;
