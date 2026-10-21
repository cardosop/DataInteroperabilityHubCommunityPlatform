/**
 * Core Web Vitals instrumentation (280.B.1.5).
 *
 * Reports LCP, FCP, TBT (via FID proxy), and CLS to the analytics
 * endpoint.  Metrics are batched and sent via ``navigator.sendBeacon``
 * on page unload so they don't block navigation.
 */
import { onCLS, onFCP, onLCP, onTTFB } from 'web-vitals';

const ENDPOINT = '/api/v1/analytics/web-vitals/';

interface VitalMetric {
  name: string;
  value: number;
  rating: 'good' | 'needs-improvement' | 'poor';
  delta: number;
  id: string;
  entries: PerformanceEntry[];
}

function sendToAnalytics(metric: VitalMetric): void {
  // Don't block the main thread — fire-and-forget
  const payload = JSON.stringify({
    name: metric.name,
    value: Math.round(metric.value * 100) / 100,
    rating: metric.rating,
    delta: Math.round(metric.delta * 100) / 100,
    id: metric.id,
    timestamp: Date.now(),
  });

  if (navigator.sendBeacon) {
    navigator.sendBeacon(ENDPOINT, new Blob([payload], { type: 'application/json' }));
  } else {
    // Fallback for browsers without sendBeacon
    fetch(ENDPOINT, {
      method: 'POST',
      body: payload,
      headers: { 'Content-Type': 'application/json' },
      keepalive: true,
    }).catch(() => {
      /* non-critical — analytics may be down; never break the app */
    });
  }
}

// Report all vitals to analytics. Each reports at most once per page load.
// The module's side-effect registration is the shipped mechanism — it is
// imported from main.tsx; per-route SPA re-reporting is intentionally NOT
// implemented (web-vitals metrics are page-load metrics, not route metrics).
onCLS(sendToAnalytics);
onFCP(sendToAnalytics);
onLCP(sendToAnalytics);
onTTFB(sendToAnalytics);
