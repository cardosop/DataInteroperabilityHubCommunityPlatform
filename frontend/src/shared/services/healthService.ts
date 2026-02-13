/**
 * Health Service
 * API client for health check endpoints
 */

import { apiClient } from '../api/client';
import type { HealthStatus } from '../types/health';

export const healthService = {
  /**
   * Get health status from Django app health endpoint
   * GET /health/ (via Django URLs, not under /api/v1/)
   */
  async getHealth(): Promise<HealthStatus> {
    // Use direct fetch to bypass API client (health endpoint is public, not under /api/v1/)
    // Health endpoint is at /health/ (Django root level)
    // Use relative URL to leverage Vite proxy in dev, or full URL in production
    const healthUrl = '/health/';
    const response = await fetch(healthUrl, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
      },
    });
    if (!response.ok) {
      throw new Error(`Health check failed: ${response.statusText}`);
    }
    return response.json();
  },

  /**
   * Get aggregate health status from API Gateway or Django health endpoint
   * Tries /api/v1/health first (API Gateway aggregate), falls back to /health/ (Django)
   */
  async getAggregateHealth(): Promise<HealthStatus> {
    try {
      // Try API Gateway aggregate health endpoint first
      const response = await apiClient.getClient().get<HealthStatus>('health');
      return response.data;
    } catch (error) {
      // Fallback to Django health endpoint if API Gateway endpoint fails
      try {
        return await this.getHealth();
      } catch (fallbackError) {
        // If both fail, return a degraded status (graceful degradation)
        return {
          status: 'degraded',
          service: 'unknown',
        };
      }
    }
  },
};
