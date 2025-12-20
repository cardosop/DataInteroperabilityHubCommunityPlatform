/**
 * APIRequestExample Tests
 *
 * Comprehensive tests for the APIRequestExample component covering:
 * - Request example display
 * - Syntax highlighting
 * - Language detection
 * - Copy functionality
 * - Formatting
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { APIRequestExample } from '../APIRequestExample'
import type { APIEndpoint } from '../../APIEndpointCard/types'

const mockEndpoint: APIEndpoint = {
  method: 'POST',
  path: '/api/v1/assets/',
  description: 'Create a new asset',
  parameters: {
    body: {
      schema: {
        name: 'string',
        description: 'string',
      },
      example: {
        name: 'My Asset',
        description: 'Asset description',
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

describe('APIRequestExample', () => {
  beforeEach(() => {
    // Mock clipboard API
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    })
  })

  describe('Rendering', () => {
    it('should render request example', async () => {
      render(<APIRequestExample endpoint={mockEndpoint} baseUrl="http://localhost:8000" />)
      await waitFor(() => {
        expect(screen.getByTestId('monaco-editor')).toBeInTheDocument()
      })
    })

    it('should display JSON request body when present', async () => {
      render(<APIRequestExample endpoint={mockEndpoint} baseUrl="http://localhost:8000" />)
      await waitFor(() => {
        const editor = screen.getByTestId('monaco-editor')
        expect(editor).toHaveAttribute('data-language', 'json')
        expect(editor.getAttribute('data-value')).toContain('My Asset')
      })
    })

    it('should display cURL example when language is curl', async () => {
      render(
        <APIRequestExample
          endpoint={mockEndpoint}
          baseUrl="http://localhost:8000"
          language="curl"
        />
      )
      await waitFor(() => {
        const editor = screen.getByTestId('monaco-editor')
        expect(editor).toHaveAttribute('data-language', 'shell')
        expect(editor.getAttribute('data-value')).toContain('curl')
      })
    })

    it('should display JavaScript example when language is javascript', async () => {
      render(
        <APIRequestExample
          endpoint={mockEndpoint}
          baseUrl="http://localhost:8000"
          language="javascript"
        />
      )
      await waitFor(() => {
        const editor = screen.getByTestId('monaco-editor')
        expect(editor).toHaveAttribute('data-language', 'javascript')
        expect(editor.getAttribute('data-value')).toContain('fetch')
      })
    })

    it('should display Python example when language is python', async () => {
      render(
        <APIRequestExample
          endpoint={mockEndpoint}
          baseUrl="http://localhost:8000"
          language="python"
        />
      )
      await waitFor(() => {
        const editor = screen.getByTestId('monaco-editor')
        expect(editor).toHaveAttribute('data-language', 'python')
        expect(editor.getAttribute('data-value')).toContain('requests')
      })
    })
  })

  describe('Copy Functionality', () => {
    it('should show copy button', async () => {
      render(<APIRequestExample endpoint={mockEndpoint} baseUrl="http://localhost:8000" />)
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /copy/i })).toBeInTheDocument()
      })
    })

    it('should copy code to clipboard when copy button is clicked', async () => {
      render(<APIRequestExample endpoint={mockEndpoint} baseUrl="http://localhost:8000" />)
      await waitFor(() => {
        const copyButton = screen.getByRole('button', { name: /copy/i })
        fireEvent.click(copyButton)
      })
      await waitFor(() => {
        expect(navigator.clipboard.writeText).toHaveBeenCalled()
      })
    })
  })

  describe('GET Request', () => {
    it('should handle GET request without body', async () => {
      const getEndpoint: APIEndpoint = {
        method: 'GET',
        path: '/api/v1/assets/',
        description: 'List assets',
        parameters: {
          query: [{ name: 'page', type: 'integer', required: false, description: 'Page number' }],
        },
        responses: [],
      }
      render(<APIRequestExample endpoint={getEndpoint} baseUrl="http://localhost:8000" />)
      await waitFor(() => {
        const editor = screen.getByTestId('monaco-editor')
        expect(editor).toBeInTheDocument()
      })
    })
  })
})

