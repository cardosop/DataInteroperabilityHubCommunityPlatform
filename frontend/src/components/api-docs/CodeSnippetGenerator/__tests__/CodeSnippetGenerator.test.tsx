/**
 * CodeSnippetGenerator Tests
 *
 * Comprehensive tests for the CodeSnippetGenerator component covering:
 * - Language selection
 * - Code snippet generation
 * - Tab switching
 * - Copy functionality
 * - Multiple language support
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { CodeSnippetGenerator } from '../CodeSnippetGenerator'
import type { APIEndpoint } from '../../APIEndpointCard/types'

const mockEndpoint: APIEndpoint = {
  method: 'POST',
  path: '/api/v1/assets/',
  description: 'Create a new asset',
  parameters: {
    body: {
      schema: {
        name: 'string',
      },
      example: {
        name: 'My Asset',
      },
    },
  },
  responses: [],
}

// Mock Monaco Editor
vi.mock('@monaco-editor/react', () => ({
  default: ({ value, language }: { value: string; language: string }) => (
    <div data-testid="monaco-editor" data-value={value} data-language={language}>
      {value}
    </div>
  ),
}))

describe('CodeSnippetGenerator', () => {
  beforeEach(() => {
    // Mock clipboard API
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    })
  })

  describe('Rendering', () => {
    it('should render code snippet generator', () => {
      render(
        <CodeSnippetGenerator endpoint={mockEndpoint} baseUrl="http://localhost:8000" />
      )
      expect(screen.getByText(/code example/i)).toBeInTheDocument()
    })

    it('should display language tabs', () => {
      render(
        <CodeSnippetGenerator endpoint={mockEndpoint} baseUrl="http://localhost:8000" />
      )
      expect(screen.getByText(/curl/i)).toBeInTheDocument()
      expect(screen.getByText(/javascript/i)).toBeInTheDocument()
      expect(screen.getByText(/python/i)).toBeInTheDocument()
    })

    it('should default to curl language', async () => {
      render(
        <CodeSnippetGenerator endpoint={mockEndpoint} baseUrl="http://localhost:8000" />
      )
      await waitFor(() => {
        const editor = screen.getByTestId('monaco-editor')
        expect(editor).toHaveAttribute('data-language', 'shell')
        expect(editor.getAttribute('data-value')).toContain('curl')
      })
    })
  })

  describe('Language Switching', () => {
    it('should switch to JavaScript when JavaScript tab is clicked', async () => {
      render(
        <CodeSnippetGenerator endpoint={mockEndpoint} baseUrl="http://localhost:8000" />
      )
      const jsTab = screen.getByText(/javascript/i)
      fireEvent.click(jsTab)

      await waitFor(() => {
        const editor = screen.getByTestId('monaco-editor')
        expect(editor).toHaveAttribute('data-language', 'javascript')
        expect(editor.getAttribute('data-value')).toContain('fetch')
      })
    })

    it('should switch to Python when Python tab is clicked', async () => {
      render(
        <CodeSnippetGenerator endpoint={mockEndpoint} baseUrl="http://localhost:8000" />
      )
      const pythonTab = screen.getByText(/python/i)
      fireEvent.click(pythonTab)

      await waitFor(() => {
        const editor = screen.getByTestId('monaco-editor')
        expect(editor).toHaveAttribute('data-language', 'python')
        expect(editor.getAttribute('data-value')).toContain('requests')
      })
    })

    it('should switch back to cURL when cURL tab is clicked', async () => {
      render(
        <CodeSnippetGenerator endpoint={mockEndpoint} baseUrl="http://localhost:8000" />
      )
      // Switch to JavaScript first
      const jsTab = screen.getByText(/javascript/i)
      fireEvent.click(jsTab)

      // Then switch back to cURL
      const curlTab = screen.getByText(/curl/i)
      fireEvent.click(curlTab)

      await waitFor(() => {
        const editor = screen.getByTestId('monaco-editor')
        expect(editor).toHaveAttribute('data-language', 'shell')
        expect(editor.getAttribute('data-value')).toContain('curl')
      })
    })
  })

  describe('Copy Functionality', () => {
    it('should show copy button', async () => {
      render(
        <CodeSnippetGenerator endpoint={mockEndpoint} baseUrl="http://localhost:8000" />
      )
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /copy/i })).toBeInTheDocument()
      })
    })

    it('should copy current language code to clipboard', async () => {
      render(
        <CodeSnippetGenerator endpoint={mockEndpoint} baseUrl="http://localhost:8000" />
      )
      await waitFor(() => {
        const copyButton = screen.getByRole('button', { name: /copy/i })
        fireEvent.click(copyButton)
      })
      await waitFor(() => {
        expect(navigator.clipboard.writeText).toHaveBeenCalled()
      })
    })
  })

  describe('Custom Languages', () => {
    it('should support custom language list', () => {
      render(
        <CodeSnippetGenerator
          endpoint={mockEndpoint}
          baseUrl="http://localhost:8000"
          languages={['curl', 'javascript']}
        />
      )
      expect(screen.getByText(/curl/i)).toBeInTheDocument()
      expect(screen.getByText(/javascript/i)).toBeInTheDocument()
      expect(screen.queryByText(/python/i)).not.toBeInTheDocument()
    })
  })
})

