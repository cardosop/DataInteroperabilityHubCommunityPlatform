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

/** Empty paginated response for fallback when API returns undefined */
export function emptyPaginatedResponse<T>(): PaginatedResponse<T> {
  return {
    results: [],
    count: 0,
    page: 1,
    page_size: 100,
    total_pages: 1,
    has_next: false,
    has_previous: false,
    next_page: null,
    previous_page: null,
  };
}

export interface ApiResponse<T> {
  data: T;
  status: number;
  headers: Record<string, string>;
}

/**
 * Request configuration for the fetch-based HTTP client.
 * Replaces AxiosRequestConfig after Phase 209 axios removal.
 */
export interface RequestConfig {
  headers?: Record<string, string>;
  params?: Record<string, string | number | boolean | undefined>;
  responseType?: 'json' | 'blob' | 'text';
  timeout?: number;
  signal?: AbortSignal;
}

/**
 * HTTP client interface matching the method signatures that all 38+ service files use.
 * `getClient()` returns this type. Methods return `ApiResponse<T>` (with `data: T`)
 * so services can continue doing `response.data` unchanged — the compatibility wrapper
 * from the Phase 209 axios→fetch migration.
 */
export interface HttpClient {
  get<T = unknown>(url: string, config?: RequestConfig): Promise<ApiResponse<T>>;
  post<T = unknown>(url: string, data?: unknown, config?: RequestConfig): Promise<ApiResponse<T>>;
  put<T = unknown>(url: string, data?: unknown, config?: RequestConfig): Promise<ApiResponse<T>>;
  patch<T = unknown>(url: string, data?: unknown, config?: RequestConfig): Promise<ApiResponse<T>>;
  delete<T = unknown>(url: string, config?: RequestConfig): Promise<ApiResponse<T>>;
  head<T = unknown>(url: string, config?: RequestConfig): Promise<ApiResponse<T>>;
  defaults: { baseURL: string };
}

/**
 * Type guard for ApiError — replaces axios.isAxiosError() after Phase 209.
 * Use this instead of checking error.response?.status (axios-specific).
 */
export function isApiError(e: unknown): e is ApiError {
  return (
    typeof e === 'object' &&
    e !== null &&
    'error' in e &&
    typeof (e as ApiError).error === 'object' &&
    typeof (e as ApiError).error?.code === 'string'
  );
}
