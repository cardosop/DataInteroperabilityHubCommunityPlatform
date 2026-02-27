/**
 * Performance Metrics Service
 * Collects Web Vitals and custom performance metrics
 */

export interface PerformanceMetric {
  name: string;
  value: number;
  timestamp: number;
  correlationId?: string;
  url: string;
}

class PerformanceMetricsService {
  private metrics: PerformanceMetric[] = [];
  private maxMetrics = 100;

  /**
   * Record a performance metric
   */
  recordMetric(name: string, value: number, correlationId?: string): void {
    const metric: PerformanceMetric = {
      name,
      value,
      timestamp: Date.now(),
      correlationId,
      url: window.location.href,
    };

    this.metrics.push(metric);
    if (this.metrics.length > this.maxMetrics) {
      this.metrics.shift();
    }

    // Log in dev mode
    if (import.meta.env.DEV) {
      console.debug(`[Performance] ${name}: ${value.toFixed(2)}ms`, {
        correlationId,
        url: metric.url,
      });
    }
  }

  /**
   * Measure route load time
   */
  measureRouteLoad(routeName: string, startTime: number, correlationId?: string): void {
    const loadTime = performance.now() - startTime;
    this.recordMetric(`route_load_${routeName}`, loadTime, correlationId);
  }

  /**
   * Measure API call duration
   */
  measureAPICall(endpoint: string, duration: number, correlationId?: string): void {
    this.recordMetric(`api_call_${endpoint}`, duration, correlationId);
  }

  /**
   * Get Web Vitals
   */
  async collectWebVitals(): Promise<void> {
    if (typeof window === 'undefined' || !('PerformanceObserver' in window)) {
      return;
    }

    try {
      // Largest Contentful Paint (LCP)
      const lcpObserver = new PerformanceObserver((list) => {
        const entries = list.getEntries();
        const lastEntry = entries[entries.length - 1] as PerformanceEntry & {
          renderTime?: number;
          loadTime?: number;
        };
        const lcp = lastEntry.renderTime || lastEntry.loadTime || 0;
        this.recordMetric('web_vital_lcp', lcp);
      });
      lcpObserver.observe({ entryTypes: ['largest-contentful-paint'] });

      // First Input Delay (FID)
      const fidObserver = new PerformanceObserver((list) => {
        const entries = list.getEntries();
        entries.forEach((entry) => {
          const fid = (entry as PerformanceEventTiming).processingStart - entry.startTime;
          this.recordMetric('web_vital_fid', fid);
        });
      });
      fidObserver.observe({ entryTypes: ['first-input'] });

      // Cumulative Layout Shift (CLS)
      let clsValue = 0;
      const clsObserver = new PerformanceObserver((list) => {
        const entries = list.getEntries();
        entries.forEach((entry) => {
          const ls = entry as { hadRecentInput?: boolean; value?: number };
          if (!ls.hadRecentInput) {
            clsValue += ls.value ?? 0;
          }
        });
        this.recordMetric('web_vital_cls', clsValue);
      });
      clsObserver.observe({ entryTypes: ['layout-shift'] });
    } catch (error) {
      // Performance Observer not supported or error
      console.debug('[Performance] Web Vitals collection not available:', error);
    }
  }

  /**
   * Get recent metrics
   */
  getRecentMetrics(limit = 20): PerformanceMetric[] {
    return this.metrics.slice(-limit);
  }

  /**
   * Get metrics by name
   */
  getMetricsByName(name: string): PerformanceMetric[] {
    return this.metrics.filter((m) => m.name === name);
  }

  /**
   * Clear metrics
   */
  clearMetrics(): void {
    this.metrics = [];
  }
}

export const performanceMetricsService = new PerformanceMetricsService();

// Start collecting Web Vitals on load
if (typeof window !== 'undefined') {
  window.addEventListener('load', () => {
    performanceMetricsService.collectWebVitals();
  });
}
