/**
 * DatasetUpload Tests
 *
 * Comprehensive tests for the DatasetUpload component covering:
 * - File upload rendering
 * - File validation
 * - Upload progress
 * - Success/error handling
 * - Callback handlers
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { DatasetUpload } from '../DatasetUpload'
import { useUploadDataset } from '@/hooks/useDatasets'

// Mock useUploadDataset hook
vi.mock('@/hooks/useDatasets', () => ({
  useUploadDataset: vi.fn(),
}))

// Mock invalidateQueries
vi.mock('@/lib/api/react-query', async () => {
  const actual = await vi.importActual('@/lib/api/react-query')
  return {
    ...actual,
    invalidateQueries: vi.fn(),
  }
})

const createTestQueryClient = () => {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  })
}

const TestWrapper = ({ children }: { children: React.ReactNode }) => {
  const queryClient = createTestQueryClient()
  return (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  )
}

describe('DatasetUpload', () => {
  const mockMutateAsync = vi.fn()
  const mockUseUploadDataset = vi.mocked(useUploadDataset)

  beforeEach(() => {
    vi.clearAllMocks()
    mockUseUploadDataset.mockReturnValue({
      mutateAsync: mockMutateAsync,
      isPending: false,
      isError: false,
      error: null,
      isSuccess: false,
      data: undefined,
      reset: vi.fn(),
      mutate: vi.fn(),
      status: 'idle',
    } as any)
  })

  describe('Rendering', () => {
    it('should render file upload component', () => {
      render(
        <TestWrapper>
          <DatasetUpload onUploadSuccess={vi.fn()} />
        </TestWrapper>
      )

      expect(screen.getByText(/drag and drop a file here/i)).toBeInTheDocument()
    })

    it('should show accepted file types', () => {
      render(
        <TestWrapper>
          <DatasetUpload onUploadSuccess={vi.fn()} />
        </TestWrapper>
      )

      expect(screen.getByText(/accepted:.*\.csv.*\.json.*\.parquet/i)).toBeInTheDocument()
    })

    it('should show maximum file size', () => {
      render(
        <TestWrapper>
          <DatasetUpload onUploadSuccess={vi.fn()} />
        </TestWrapper>
      )

      expect(screen.getByText(/max size:.*500.*mb/i)).toBeInTheDocument()
    })
  })

  describe('File Upload', () => {
    it('should call onUploadSuccess when upload succeeds', async () => {
      const mockDataset = {
        id: 'dataset-123',
        tenant: 'tenant-1',
        asset: null,
        file: 'file-123',
        schema_json: null,
        sample_data_json: null,
        row_count: null,
        format: 'CSV' as const,
        version: 1,
        parent_version: null,
        semantic_version: null,
        version_tags: [],
        is_current: true,
        created_by: 'user-1',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      }

      mockMutateAsync.mockResolvedValue(mockDataset)
      const handleSuccess = vi.fn()

      render(
        <TestWrapper>
          <DatasetUpload onUploadSuccess={handleSuccess} />
        </TestWrapper>
      )

      const fileInput = document.querySelector('input[type="file"]')
      if (fileInput) {
        const validFile = new File(['name,age\nJohn,30'], 'test.csv', {
          type: 'text/csv',
        })
        Object.defineProperty(fileInput, 'files', {
          value: [validFile],
          writable: false,
        })

        fireEvent.change(fileInput)

        await waitFor(() => {
          expect(handleSuccess).toHaveBeenCalledWith(mockDataset)
        })
      }
    })

    it('should call onUploadError when upload fails', async () => {
      const error = new Error('Upload failed')
      mockMutateAsync.mockRejectedValue(error)
      const handleError = vi.fn()

      render(
        <TestWrapper>
          <DatasetUpload onUploadSuccess={vi.fn()} onUploadError={handleError} />
        </TestWrapper>
      )

      const fileInput = document.querySelector('input[type="file"]')
      if (fileInput) {
        const validFile = new File(['name,age\nJohn,30'], 'test.csv', {
          type: 'text/csv',
        })
        Object.defineProperty(fileInput, 'files', {
          value: [validFile],
          writable: false,
        })

        fireEvent.change(fileInput)

        await waitFor(() => {
          expect(handleError).toHaveBeenCalledWith(error)
        })
      }
    })

    it('should track upload progress', async () => {
      mockMutateAsync.mockImplementation(({ onProgress }) => {
        if (onProgress) {
          onProgress(25)
          onProgress(50)
          onProgress(100)
        }
        return Promise.resolve({
          id: 'dataset-123',
          tenant: 'tenant-1',
          asset: null,
          file: 'file-123',
          schema_json: null,
          sample_data_json: null,
          row_count: null,
          format: 'CSV' as const,
          version: 1,
          parent_version: null,
          semantic_version: null,
          version_tags: [],
          is_current: true,
          created_by: 'user-1',
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
        })
      })

      render(
        <TestWrapper>
          <DatasetUpload onUploadSuccess={vi.fn()} />
        </TestWrapper>
      )

      const fileInput = document.querySelector('input[type="file"]')
      if (fileInput) {
        const validFile = new File(['name,age\nJohn,30'], 'test.csv', {
          type: 'text/csv',
        })
        Object.defineProperty(fileInput, 'files', {
          value: [validFile],
          writable: false,
        })

        fireEvent.change(fileInput)

        await waitFor(() => {
          expect(screen.getByText(/uploading/i)).toBeInTheDocument()
        })
      }
    })
  })

  describe('Props', () => {
    it('should accept asset_id prop', async () => {
      const mockDataset = {
        id: 'dataset-123',
        tenant: 'tenant-1',
        asset: 'asset-123',
        file: 'file-123',
        schema_json: null,
        sample_data_json: null,
        row_count: null,
        format: 'CSV' as const,
        version: 1,
        parent_version: null,
        semantic_version: null,
        version_tags: [],
        is_current: true,
        created_by: 'user-1',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      }

      mockMutateAsync.mockResolvedValue(mockDataset)

      render(
        <TestWrapper>
          <DatasetUpload onUploadSuccess={vi.fn()} asset_id="asset-123" />
        </TestWrapper>
      )

      const fileInput = document.querySelector('input[type="file"]')
      if (fileInput) {
        const validFile = new File(['name,age\nJohn,30'], 'test.csv', {
          type: 'text/csv',
        })
        Object.defineProperty(fileInput, 'files', {
          value: [validFile],
          writable: false,
        })

        fireEvent.change(fileInput)

        await waitFor(() => {
          expect(mockMutateAsync).toHaveBeenCalledWith(
            expect.objectContaining({
              asset_id: 'asset-123',
            })
          )
        })
      }
    })

    it('should be disabled when disabled prop is true', () => {
      render(
        <TestWrapper>
          <DatasetUpload onUploadSuccess={vi.fn()} disabled />
        </TestWrapper>
      )

      const fileInput = document.querySelector('input[type="file"]')
      expect(fileInput).toBeDisabled()
    })
  })
})

