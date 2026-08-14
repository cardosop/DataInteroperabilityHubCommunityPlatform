/**
 * Environment-gated debug logger — no raw console.* in production feature code.
 *
 * In production builds console calls are stripped by this gate.
 * Errors should route through Sentry via ErrorBoundary / captureException.
 * Debug and informational messages are only emitted in non-production environments.
 */
const isProduction = import.meta.env.VITE_ENVIRONMENT === 'production';

export const debugLogger = {
  error: (...args: unknown[]): void => {
    if (!isProduction) console.error(...args);
  },
  warn: (...args: unknown[]): void => {
    if (!isProduction) console.warn(...args);
  },
  info: (...args: unknown[]): void => {
    if (!isProduction) console.info(...args);
  },
  debug: (...args: unknown[]): void => {
    if (!isProduction) console.debug(...args);
  },
};
