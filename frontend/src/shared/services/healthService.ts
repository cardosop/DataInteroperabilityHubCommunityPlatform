/**
 * Health Service
 * Fetches health status from Django /health/ endpoint
 */

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
   * Get aggregate health status from Django health endpoint
   * Uses /health/ (Django root) which exists; /api/v1/health is not implemented
   */
  async getAggregateHealth(): Promise<HealthStatus> {
    try {
      return await this.getHealth();
    } catch {
      // Graceful degradation when health check fails
      return {
        status: 'degraded',
        service: 'unknown',
      };
    }
  },
};
