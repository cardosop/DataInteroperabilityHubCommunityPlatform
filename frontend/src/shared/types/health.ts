/**
 * Health Types
 * Based on backend health endpoint responses
 */

export interface HealthStatus {
  status: 'healthy' | 'unhealthy' | 'degraded';
  database?: string;
  redis?: {
    cache?: string;
    queue?: string;
    events?: string;
    channels?: string;
  };
  service?: string;
  version?: string;
  backend_services?: Record<
    string,
    {
      status: 'healthy' | 'unhealthy';
      status_code: number;
      url: string;
      health_url: string;
      error?: string;
    }
  >;
  unhealthy_services?: number;
  timestamp?: string;
}
