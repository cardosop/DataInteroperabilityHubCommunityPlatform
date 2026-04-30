/**
 * Phase 227 Wave 1 (227.L7.2) — Schema-editor telemetry client.
 *
 * Posts metric events to ``/api/v1/contracts/schema-editor/metrics``;
 * the backend increments OTel counters / histograms server-side. We
 * deliberately don't embed an OTLP exporter in the SPA bundle — a
 * thin POST through the shared ``apiClient`` is ~1KB while
 * ``@opentelemetry/sdk-metrics`` would add ~200KB to the gzipped
 * frontend.
 *
 * Uses the shared ``apiClient`` (not bare ``fetch``) so:
 *
 *   1. CSRF token is automatically read from the ``csrftoken`` cookie
 *      and attached as ``X-CSRFToken`` (Django session-auth requirement
 *      for unsafe methods — verified by
 *      ``frontend/src/shared/api/__tests__/csrf-interceptor.test.ts``).
 *   2. Authentication headers / cookies are attached uniformly with the
 *      rest of the SPA's API calls.
 *   3. Error-normalisation and tenant-id forwarding match the rest of
 *      the codebase, avoiding subtle inconsistencies if a future
 *      middleware adds a header.
 *
 * Failures are silent (``console.debug`` only) — telemetry MUST NOT
 * break the editor's primary save flow.
 */
import { apiClient } from '../../../shared/api/client';

const ENDPOINT = '/contracts/schema-editor/metrics';

export type SchemaEditorSpec = 'ODCS' | 'ODPS';
export type SchemaEditorSaveOutcome =
  | 'success'
  | 'conflict'
  | 'validation_error'
  | 'error';

interface OpenedEvent {
  event: 'opened';
  spec_type: SchemaEditorSpec | string;
}

interface SaveEvent {
  event: 'save';
  spec_type: SchemaEditorSpec | string;
  outcome: SchemaEditorSaveOutcome;
  /** Wall-clock seconds between FIRST tab-mount and FIRST successful
   * save. Only set when ``outcome === 'success'`` and this is the
   * caller's first success in the session. */
  time_to_first_save_seconds?: number;
}

type Event = OpenedEvent | SaveEvent;

async function emit(event: Event): Promise<void> {
  try {
    await apiClient.post(ENDPOINT, event);
  } catch (err) {
    if (import.meta.env?.DEV) {
      // eslint-disable-next-line no-console
      console.debug('[schema-editor-metrics] emission failed', err);
    }
  }
}

export function recordSchemaEditorOpened(
  specType: SchemaEditorSpec | string,
): void {
  void emit({ event: 'opened', spec_type: specType });
}

export function recordSchemaEditorSave(args: {
  specType: SchemaEditorSpec | string;
  outcome: SchemaEditorSaveOutcome;
  timeToFirstSaveSeconds?: number;
}): void {
  void emit({
    event: 'save',
    spec_type: args.specType,
    outcome: args.outcome,
    ...(args.timeToFirstSaveSeconds !== undefined
      ? { time_to_first_save_seconds: args.timeToFirstSaveSeconds }
      : {}),
  });
}
