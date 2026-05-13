/**
 * Records API Service
 *
 * Phase 277.B.048 — client for GET /api/v1/datasets/{id}/rows/
 * with StandardCursorPagination cursor support.
 */

import { apiClient } from '../../../shared/api/client';

const DATASETS_BASE_PATH = 'datasets';

export interface CursorPaginatedRows {
  results: Record<string, unknown>[][];
  columns: string[];
  count: number;
  next_cursor: string | null;
  previous_cursor: string | null;
  page_size: number;
}

export interface RecordsQueryParams {
  limit?: number;
  cursor?: string | null;
}

export const recordsApiService = {
  /**
   * Fetch paginated dataset rows via cursor-based pagination.
   *
   * GET /api/v1/datasets/{id}/rows/?limit=100&cursor=<encoded>
   *
   * @param datasetId - Dataset UUID
   * @param params - Pagination params (limit, cursor)
   * @returns CursorPaginatedRows with results, columns, count, next_cursor, previous_cursor
   */
  async getRows(
    datasetId: string,
    params: RecordsQueryParams = {},
  ): Promise<CursorPaginatedRows> {
    const searchParams = new URLSearchParams();
    searchParams.set('limit', String(params.limit ?? 100));

    if (params.cursor) {
      searchParams.set('cursor', params.cursor);
    }

    const response = await apiClient
      .getClient()
      .get<CursorPaginatedRows>(
        `${DATASETS_BASE_PATH}/${datasetId}/rows/?${searchParams.toString()}`,
      );

    return response.data;
  },
};
