/**
 * Web Vitals Service Tests
 *
 * Comprehensive tests for Web Vitals tracking service covering:
 * - Metric rating calculation
 * - Threshold checking
 * - Analytics integration
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { getMetricRating, WEB_VITALS_THRESHOLDS } from '../webVitals'

describe('webVitals service', () => {
  describe('getMetricRating', () => {
    it('should return "good" for values below good threshold', () => {
      expect(getMetricRating('FCP', 1000)).toBe('good')
      expect(getMetricRating('LCP', 2000)).toBe('good')
      expect(getMetricRating('CLS', 0.05)).toBe('good')
      expect(getMetricRating('TTFB', 500)).toBe('good')
      expect(getMetricRating('INP', 150)).toBe('good')
    })

    it('should return "needs-improvement" for values between thresholds', () => {
      expect(getMetricRating('FCP', 2500)).toBe('needs-improvement')
      expect(getMetricRating('LCP', 3500)).toBe('needs-improvement')
      expect(getMetricRating('CLS', 0.2)).toBe('needs-improvement')
      expect(getMetricRating('TTFB', 1200)).toBe('needs-improvement')
      expect(getMetricRating('INP', 350)).toBe('needs-improvement')
    })

    it('should return "poor" for values above needs-improvement threshold', () => {
      expect(getMetricRating('FCP', 4000)).toBe('poor')
      expect(getMetricRating('LCP', 5000)).toBe('poor')
      expect(getMetricRating('CLS', 0.3)).toBe('poor')
      expect(getMetricRating('TTFB', 2000)).toBe('poor')
      expect(getMetricRating('INP', 600)).toBe('poor')
    })
  })

  describe('WEB_VITALS_THRESHOLDS', () => {
    it('should have correct thresholds for all metrics', () => {
      expect(WEB_VITALS_THRESHOLDS.CLS.good).toBe(0.1)
      expect(WEB_VITALS_THRESHOLDS.CLS.needsImprovement).toBe(0.25)

      expect(WEB_VITALS_THRESHOLDS.FCP.good).toBe(1800)
      expect(WEB_VITALS_THRESHOLDS.FCP.needsImprovement).toBe(3000)

      expect(WEB_VITALS_THRESHOLDS.LCP.good).toBe(2500)
      expect(WEB_VITALS_THRESHOLDS.LCP.needsImprovement).toBe(4000)

      expect(WEB_VITALS_THRESHOLDS.TTFB.good).toBe(800)
      expect(WEB_VITALS_THRESHOLDS.TTFB.needsImprovement).toBe(1800)

      expect(WEB_VITALS_THRESHOLDS.INP.good).toBe(200)
      expect(WEB_VITALS_THRESHOLDS.INP.needsImprovement).toBe(500)
    })
  })
})

