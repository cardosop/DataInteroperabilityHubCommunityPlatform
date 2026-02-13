/**
 * API Types
 * Based on OpenAPI schema and backend API contracts
 */

export interface ApiError {
  error: {
    code: string;
    message: string;
    http_status: number;
    request_id: string;
    timestamp: string;
    details?: Record<string, unknown>;
    field_errors?: Array<{
      field: string;
      message: string;
      code: string;
    }>;
  };
}

export interface PaginatedResponse<T> {
  count: number;
  page: number;
  page_size: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
  next_page: number | null;
  previous_page: number | null;
  results: T[];
}

export interface ApiResponse<T> {
  data: T;
  status: number;
  headers: Record<string, string>;
}
