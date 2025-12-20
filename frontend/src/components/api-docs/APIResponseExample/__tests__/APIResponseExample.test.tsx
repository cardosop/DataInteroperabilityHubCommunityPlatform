/**
 * APIResponseExample Tests
 *
 * Comprehensive tests for the APIResponseExample component covering:
 * - Response example display
 * - Syntax highlighting
 * - Status code display
 * - Copy functionality
 * - Multiple response examples
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { APIResponseExample } from '../APIResponseExample'
import type { APIResponse } from '../../APIEndpointCard/types'

const mockResponse: APIResponse = {
  status: 200,
  description: 'Success',
  example: {
    id: '123',
    name: 'Test Asset',
    status: 'ACTIVE',
  },
}

// Mock Monaco Editor
vi.mock('@monaco-editor/react', () => ({
  default: ({ value, language }: { value: string; language: string }) => (
    <div data-testid="monaco-editor" data-value={value} data-language={language}>
      {value}
    </div>
  ),
}))

describe('APIResponseExample', () => {
  beforeEach(() => {
    // Mock clipboard API
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    })
  })

  describe('Rendering', () => {
    it('should render response example', async () => {
      render(<APIResponseExample response={mockResponse} />)
      await waitFor(() => {
        expect(screen.getByTestId('monaco-editor')).toBeInTheDocument()
      })
    })

    it('should display status code', () => {
      render(<APIResponseExample response={mockResponse} />)
      expect(screen.getByText('200')).toBeInTheDocument()
    })

    it('should display response description', () => {
      render(<APIResponseExample response={mockResponse} />)
      expect(screen.getByText('Success')).toBeInTheDocument()
    })

    it('should display JSON response example', async () => {
      render(<APIResponseExample response={mockResponse} />)
      await waitFor(() => {
        const editor = screen.getByTestId('monaco-editor')
        expect(editor).toHaveAttribute('data-language', 'json')
        expect(editor.getAttribute('data-value')).toContain('Test Asset')
      })
    })

    it('should handle response without example', async () => {
      const responseWithoutExample: APIResponse = {
        status: 204,
        description: 'No Content',
      }
      render(<APIResponseExample response={responseWithoutExample} />)
      await waitFor(() => {
        const editor = screen.getByTestId('monaco-editor')
        expect(editor.getAttribute('data-value')).toBe('')
      })
    })
  })

  describe('Status Code Colors', () => {
    it('should use success color for 2xx status codes', () => {
      const { container } = render(<APIResponseExample response={mockResponse} />)
      const chip = container.querySelector('.MuiChip-colorSuccess')
      expect(chip).toBeInTheDocument()
    })

    it('should use error color for 4xx status codes', () => {
      const errorResponse: APIResponse = {
        status: 404,
        description: 'Not Found',
      }
      const { container } = render(<APIResponseExample response={errorResponse} />)
      const chip = container.querySelector('.MuiChip-colorError')
      expect(chip).toBeInTheDocument()
    })

    it('should use error color for 5xx status codes', () => {
      const serverErrorResponse: APIResponse = {
        status: 500,
        description: 'Internal Server Error',
      }
      const { container } = render(<APIResponseExample response={serverErrorResponse} />)
      const chip = container.querySelector('.MuiChip-colorError')
      expect(chip).toBeInTheDocument()
    })
  })

  describe('Copy Functionality', () => {
    it('should show copy button', async () => {
      render(<APIResponseExample response={mockResponse} />)
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /copy/i })).toBeInTheDocument()
      })
    })

    it('should copy code to clipboard when copy button is clicked', async () => {
      render(<APIResponseExample response={mockResponse} />)
      await waitFor(() => {
        const copyButton = screen.getByRole('button', { name: /copy/i })
        copyButton.click()
      })
      await waitFor(() => {
        expect(navigator.clipboard.writeText).toHaveBeenCalled()
      })
    })
  })
})

