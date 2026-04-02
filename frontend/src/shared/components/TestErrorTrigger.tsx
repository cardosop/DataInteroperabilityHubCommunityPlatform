/**
 * TestErrorTrigger — E2E test utility component.
 *
 * This component unconditionally throws during render so that
 * FeatureErrorBoundary can be exercised in Playwright tests without
 * requiring a real feature to crash.
 *
 * Only reachable via the /test/error-boundary route which is compiled in
 * exclusively when VITE_E2E_TEST=true (tree-shaken in production builds).
 */
export default function TestErrorTrigger(): never {
  throw new Error(
    '__E2E_TEST_ERROR__: Intentional render error for FeatureErrorBoundary test'
  );
}
