/**
 * DatasetUploadPage Tests
 *
 * Comprehensive tests for the DatasetUploadPage component covering:
 * - File upload component rendering
 * - Drag-and-drop functionality
 * - File validation (type and size)
 * - Upload progress tracking
 * - Success handling and navigation
 * - Error handling and display
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, useNavigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { DatasetUploadPage } from '../DatasetUploadPage'
import * as datasetsApi from '@/lib/api/datasets'
import { useUploadDataset } from '@/hooks/useDatasets'

// Mock useNavigate
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

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

describe('DatasetUploadPage', () => {
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

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('should render the page with title and description', () => {
      render(
        <TestWrapper>
          <DatasetUploadPage />
        </TestWrapper>
      )

      expect(screen.getByText(/upload dataset/i)).toBeInTheDocument()
      expect(
        screen.getByText(/upload a dataset file to create a new dataset/i)
      ).toBeInTheDocument()
    })

    it('should render the file upload component', () => {
      render(
        <TestWrapper>
          <DatasetUploadPage />
        </TestWrapper>
      )

      expect(screen.getByText(/drag and drop a file here/i)).toBeInTheDocument()
      expect(screen.getByText(/or click to browse/i)).toBeInTheDocument()
    })

    it('should show accepted file types', () => {
      render(
        <TestWrapper>
          <DatasetUploadPage />
        </TestWrapper>
      )

      expect(screen.getByText(/accepted:.*\.csv.*\.json.*\.parquet/i)).toBeInTheDocument()
    })

    it('should show maximum file size', () => {
      render(
        <TestWrapper>
          <DatasetUploadPage />
        </TestWrapper>
      )

      expect(screen.getByText(/max size:.*500.*mb/i)).toBeInTheDocument()
    })
  })

  describe('File Validation', () => {
    it('should reject files with invalid extensions', async () => {
      render(
        <TestWrapper>
          <DatasetUploadPage />
        </TestWrapper>
      )

      const fileInput = screen.getByLabelText(/file upload/i) || document.querySelector('input[type="file"]')

      if (fileInput) {
        const invalidFile = new File(['content'], 'test.txt', { type: 'text/plain' })
        Object.defineProperty(fileInput, 'files', {
          value: [invalidFile],
          writable: false,
        })

        fireEvent.change(fileInput)

        await waitFor(() => {
          expect(screen.getByText(/invalid file type/i)).toBeInTheDocument()
        })
      }
    })

    it('should reject files exceeding size limit', async () => {
      render(
        <TestWrapper>
          <DatasetUploadPage />
        </TestWrapper>
      )

      const fileInput = screen.getByLabelText(/file upload/i) || document.querySelector('input[type="file"]')

      if (fileInput) {
        // Create a file larger than 500MB
        const largeFile = new File(['x'.repeat(501 * 1024 * 1024)], 'large.csv', {
          type: 'text/csv',
        })
        Object.defineProperty(fileInput, 'files', {
          value: [largeFile],
          writable: false,
        })

        fireEvent.change(fileInput)

        await waitFor(() => {
          expect(screen.getByText(/file size exceeds maximum limit/i)).toBeInTheDocument()
        })
      }
    })

    it('should accept valid CSV files', async () => {
      render(
        <TestWrapper>
          <DatasetUploadPage />
        </TestWrapper>
      )

      const fileInput = screen.getByLabelText(/file upload/i) || document.querySelector('input[type="file"]')

      if (fileInput) {
        const validFile = new File(['name,age\nJohn,30'], 'test.csv', {
          type: 'text/csv',
        })
        Object.defineProperty(fileInput, 'files', {
          value: [validFile],
          writable: false,
        })

        fireEvent.change(fileInput)

        // Should not show validation error
        await waitFor(() => {
          expect(screen.queryByText(/invalid file type/i)).not.toBeInTheDocument()
        })
      }
    })
  })

  describe('File Upload', () => {
    it('should call uploadDataset when valid file is selected', async () => {
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

      render(
        <TestWrapper>
          <DatasetUploadPage />
        </TestWrapper>
      )

      const fileInput = screen.getByLabelText(/file upload/i) || document.querySelector('input[type="file"]')

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
          expect(mockMutateAsync).toHaveBeenCalledWith({
            file: validFile,
            asset_id: null,
            onProgress: expect.any(Function),
          })
        })
      }
    })

    it('should show upload progress', async () => {
      mockMutateAsync.mockImplementation(({ onProgress }) => {
        // Simulate progress updates
        if (onProgress) {
          onProgress(25)
          onProgress(50)
          onProgress(75)
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
          <DatasetUploadPage />
        </TestWrapper>
      )

      const fileInput = screen.getByLabelText(/file upload/i) || document.querySelector('input[type="file"]')

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

  describe('Success Handling', () => {
    it('should navigate to dataset detail page on successful upload', async () => {
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

      render(
        <TestWrapper>
          <DatasetUploadPage />
        </TestWrapper>
      )

      const fileInput = screen.getByLabelText(/file upload/i) || document.querySelector('input[type="file"]')

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
          expect(mockNavigate).toHaveBeenCalledWith('/datasets/dataset-123')
        }, { timeout: 3000 })
      }
    })
  })

  describe('Error Handling', () => {
    it('should display error message when upload fails', async () => {
      const errorMessage = 'Upload failed: Network error'
      mockMutateAsync.mockRejectedValue(new Error(errorMessage))

      render(
        <TestWrapper>
          <DatasetUploadPage />
        </TestWrapper>
      )

      const fileInput = screen.getByLabelText(/file upload/i) || document.querySelector('input[type="file"]')

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
          expect(screen.getByText(/upload failed/i)).toBeInTheDocument()
        })
      }
    })

    it('should allow retry after error', async () => {
      const errorMessage = 'Upload failed: Network error'
      mockMutateAsync
        .mockRejectedValueOnce(new Error(errorMessage))
        .mockResolvedValueOnce({
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

      render(
        <TestWrapper>
          <DatasetUploadPage />
        </TestWrapper>
      )

      const fileInput = screen.getByLabelText(/file upload/i) || document.querySelector('input[type="file"]')

      if (fileInput) {
        const validFile = new File(['name,age\nJohn,30'], 'test.csv', {
          type: 'text/csv',
        })
        Object.defineProperty(fileInput, 'files', {
          value: [validFile],
          writable: false,
        })

        // First attempt - fails
        fireEvent.change(fileInput)

        await waitFor(() => {
          expect(screen.getByText(/upload failed/i)).toBeInTheDocument()
        })

        // Retry - succeeds
        fireEvent.change(fileInput)

        await waitFor(() => {
          expect(mockNavigate).toHaveBeenCalledWith('/datasets/dataset-123')
        }, { timeout: 3000 })
      }
    })
  })

  describe('Drag and Drop', () => {
    it('should handle drag and drop events', () => {
      render(
        <TestWrapper>
          <DatasetUploadPage />
        </TestWrapper>
      )

      const dropZone = screen.getByText(/drag and drop a file here/i).closest('div')

      if (dropZone) {
        const validFile = new File(['name,age\nJohn,30'], 'test.csv', {
          type: 'text/csv',
        })

        const dragOverEvent = new Event('dragover', { bubbles: true })
        Object.defineProperty(dragOverEvent, 'preventDefault', {
          value: vi.fn(),
        })
        fireEvent(dropZone, dragOverEvent)

        const dropEvent = new Event('drop', { bubbles: true })
        Object.defineProperty(dropEvent, 'preventDefault', {
          value: vi.fn(),
        })
        Object.defineProperty(dropEvent, 'dataTransfer', {
          value: {
            files: [validFile],
          },
        })
        fireEvent(dropZone, dropEvent)

        // Should trigger upload
        expect(mockMutateAsync).toHaveBeenCalled()
      }
    })
  })
})

