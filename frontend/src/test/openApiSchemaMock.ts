/**
 * 313.H.4 — shared test fixture: a FULL-mode OpenAPI schema mock.
 *
 * Shell tests (Sidebar / AppShell / CommandPalette) assert MVP- and
 * capability-gating behaviour. Their real variable under test is the
 * FILTER, so the capabilities service must resolve every capability as
 * available — otherwise requiredCapability items disappear for the wrong
 * reason (an empty schema) and the assertions conflate two concerns.
 *
 * Built from CAPABILITY_DEFINITIONS.samplePaths so a newly registered
 * capability key is automatically included here.
 */
import { CAPABILITY_DEFINITIONS } from '../features/capabilities/services/capabilitiesService';

/** Minimal full-mode OpenAPI payload: every capability path present. */
export function fullModeOpenApiSchema(): { paths: Record<string, object> } {
  return {
    paths: Object.fromEntries(
      CAPABILITY_DEFINITIONS.flatMap((def) =>
        def.samplePaths.map((p) => [p, { get: {}, patch: {} }]),
      ),
    ),
  };
}

/** The apiClient URL matchers the shell mocks must special-case. */
export function isOpenApiUrl(url: string): boolean {
  return url.includes('/openapi.json') || url === '/openapi.json';
}
