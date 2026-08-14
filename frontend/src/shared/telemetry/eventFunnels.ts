/**
 * UI Event Funnel Tracking (281.A.11.3).
 *
 * Emits structured telemetry events for workflow completions,
 * feature discovery paths, and adoption scoring. Events are
 * batched and sent via navigator.sendBeacon on page unload.
 */
const ENDPOINT = '/api/v1/analytics/events/';
const BATCH_SIZE = 10;
const FLUSH_INTERVAL_MS = 5000;

interface TelemetryEvent {
  event: string;
  category: 'workflow' | 'discovery' | 'adoption';
  screen_id: string;
  tenant_id?: string;
  metadata?: Record<string, string | number | boolean>;
  timestamp: number;
}

let eventQueue: TelemetryEvent[] = [];
let flushTimer: ReturnType<typeof setTimeout> | null = null;

function flush(): void {
  if (eventQueue.length === 0) return;
  const batch = eventQueue.splice(0, BATCH_SIZE);

  const payload = JSON.stringify({ events: batch });
  if (navigator.sendBeacon) {
    navigator.sendBeacon(ENDPOINT, new Blob([payload], { type: 'application/json' }));
  } else {
    fetch(ENDPOINT, {
      method: 'POST',
      body: payload,
      headers: { 'Content-Type': 'application/json' },
      keepalive: true,
    }).catch(() => { /* non-critical */ });
  }
}

function scheduleFlush(): void {
  if (flushTimer) return;
  flushTimer = setTimeout(() => {
    flushTimer = null;
    flush();
  }, FLUSH_INTERVAL_MS);
}

/** Emit a telemetry event. Batched — not sent immediately. */
export function trackEvent(
  event: string,
  category: TelemetryEvent['category'],
  screenId: string,
  metadata?: TelemetryEvent['metadata'],
): void {
  eventQueue.push({
    event,
    category,
    screen_id: screenId,
    timestamp: Date.now(),
    metadata,
  });
  scheduleFlush();

  // Flush immediately if batch is full
  if (eventQueue.length >= BATCH_SIZE) {
    if (flushTimer) { clearTimeout(flushTimer); flushTimer = null; }
    flush();
  }
}

// ── Pre-built funnel helpers ────────────────────────────────────────

/** Track a workflow step completion. */
export function trackWorkflowStep(
  workflow: string,
  step: string,
  screenId: string,
  metadata?: Record<string, string | number>,
): void {
  trackEvent(`${workflow}.${step}`, 'workflow', screenId, {
    ...metadata,
    workflow,
    step,
  });
}

/** Track a feature discovery path (e.g., sidebar → marketplace → listing detail). */
export function trackFeatureDiscovery(
  feature: string,
  path: string[],
  screenId: string,
): void {
  trackEvent(`discovery.${feature}`, 'discovery', screenId, {
    feature,
    path: path.join(' → '),
    path_length: path.length,
  });
}

/** Track adoption score metrics. */
export function trackAdoption(
  feature: string,
  action: 'enabled' | 'used' | 'retained' | 'churned',
  tenantId?: string,
): void {
  trackEvent(`adoption.${feature}.${action}`, 'adoption', 'telemetry', {
    ...(tenantId !== undefined ? { tenant_id: tenantId } : {}),
    feature,
    action,
  });
}

// Flush any remaining events on page unload
if (typeof window !== 'undefined') {
  window.addEventListener('beforeunload', () => flush());
  window.addEventListener('pagehide', () => flush());
}
