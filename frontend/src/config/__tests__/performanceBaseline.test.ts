/**
 * Performance Baseline Configuration Tests
 *
 * Comprehensive tests for performance baseline configuration covering:
 * - Budget checking
 * - Alert threshold checking
 * - Baseline values
 */

import { describe, it, expect } from 'vitest'
import {
  PERFORMANCE_BASELINE,
  PERFORMANCE_BUDGET,
  exceedsBudget,
  exceedsAlertThreshold,
} from '../performanceBaseline'

describe('performanceBaseline configuration', () => {
  describe('PERFORMANCE_BASELINE', () => {
    it('should have correct Web Vitals baselines', () => {
      expect(PERFORMANCE_BASELINE.webVitals.FCP.target).toBe(1800)
      expect(PERFORMANCE_BASELINE.webVitals.LCP.target).toBe(2500)
      expect(PERFORMANCE_BASELINE.webVitals.CLS.target).toBe(0.1)
      expect(PERFORMANCE_BASELINE.webVitals.TTFB.target).toBe(800)
      expect(PERFORMANCE_BASELINE.webVitals.INP.target).toBe(200)
    })

    it('should have correct component render baselines', () => {
      expect(PERFORMANCE_BASELINE.componentRender.target).toBe(16)
      expect(PERFORMANCE_BASELINE.componentRender.acceptable).toBe(50)
      expect(PERFORMANCE_BASELINE.componentRender.critical).toBe(100)
    })

    it('should have correct API response baselines', () => {
      expect(PERFORMANCE_BASELINE.apiResponse.target).toBe(200)
      expect(PERFORMANCE_BASELINE.apiResponse.acceptable).toBe(500)
      expect(PERFORMANCE_BASELINE.apiResponse.critical).toBe(1000)
    })

    it('should have correct bundle size baselines', () => {
      expect(PERFORMANCE_BASELINE.bundleSize.target).toBe(200 * 1024)
      expect(PERFORMANCE_BASELINE.bundleSize.acceptable).toBe(500 * 1024)
      expect(PERFORMANCE_BASELINE.bundleSize.critical).toBe(1000 * 1024)
    })
  })

  describe('exceedsBudget', () => {
    it('should return true when Web Vital exceeds budget', () => {
      expect(exceedsBudget('webVitals', 'FCP', 3500)).toBe(true)
      expect(exceedsBudget('webVitals', 'FCP', 2000)).toBe(false)
    })

    it('should return true when component render time exceeds budget', () => {
      expect(exceedsBudget('componentRender', 'Component', 60)).toBe(true)
      expect(exceedsBudget('componentRender', 'Component', 40)).toBe(false)
    })

    it('should return true when API response time exceeds budget', () => {
      expect(exceedsBudget('apiResponse', '/api/endpoint', 600)).toBe(true)
      expect(exceedsBudget('apiResponse', '/api/endpoint', 400)).toBe(false)
    })

    it('should return true when bundle size exceeds budget', () => {
      expect(exceedsBudget('bundleSize', 'main', 600 * 1024)).toBe(true)
      expect(exceedsBudget('bundleSize', 'main', 400 * 1024)).toBe(false)
    })
  })

  describe('exceedsAlertThreshold', () => {
    it('should return true when Web Vital exceeds alert threshold', () => {
      expect(exceedsAlertThreshold('webVitals', 'FCP', 4500)).toBe(true)
      expect(exceedsAlertThreshold('webVitals', 'FCP', 3500)).toBe(false)
    })

    it('should return true when component render time exceeds alert threshold', () => {
      expect(exceedsAlertThreshold('componentRender', 'Component', 110)).toBe(true)
      expect(exceedsAlertThreshold('componentRender', 'Component', 90)).toBe(false)
    })
  })
})

