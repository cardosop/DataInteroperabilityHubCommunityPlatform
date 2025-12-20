/**
 * APIDocumentationPage Tests
 *
 * Comprehensive tests for the APIDocumentationPage component covering:
 * - API overview display
 * - Authentication methods display
 * - REST API endpoints display
 * - GraphQL documentation display
 * - WebSocket documentation display
 * - Interactive API explorer
 * - Code snippet generation
 * - Search functionality
 * - API version selector
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, fireEvent, waitFor } from '@testing-library/react'
import { renderWithProviders } from '@/test-utils'
import { APIDocumentationPage } from '../APIDocumentationPage'

describe('APIDocumentationPage', () => {
  describe('Rendering', () => {
    it('should render API documentation page', () => {
      renderWithProviders(<APIDocumentationPage />)

      // Use getAllByText since there might be multiple instances
      const elements = screen.getAllByText(/api documentation/i)
      expect(elements.length).toBeGreaterThan(0)
    })

    it('should display API overview section', () => {
      renderWithProviders(<APIDocumentationPage />)

      // Overview tab is shown by default (activeTab === 0)
      expect(screen.getByText(/api overview/i)).toBeInTheDocument()
    })

    it('should display authentication section', () => {
      renderWithProviders(<APIDocumentationPage />)

      // Authentication section is in the Overview tab
      expect(screen.getByText(/authentication/i)).toBeInTheDocument()
      expect(screen.getByText(/jwt authentication/i)).toBeInTheDocument()
      expect(screen.getByText(/api key authentication/i)).toBeInTheDocument()
    })

    it('should display REST API section', () => {
      renderWithProviders(<APIDocumentationPage />)

      // REST API tab is available
      expect(screen.getByText(/rest api/i)).toBeInTheDocument()
    })

    it('should display GraphQL API section', () => {
      renderWithProviders(<APIDocumentationPage />)

      // GraphQL tab is available
      expect(screen.getByText(/graphql/i)).toBeInTheDocument()
    })

    it('should display WebSocket API section', () => {
      renderWithProviders(<APIDocumentationPage />)

      // WebSocket tab is available
      expect(screen.getByText(/websocket/i)).toBeInTheDocument()
    })
  })

  describe('Interactive API Explorer', () => {
    it('should display API explorer', () => {
      renderWithProviders(<APIDocumentationPage />)

      // API Explorer tab is available
      expect(screen.getByText(/api explorer/i)).toBeInTheDocument()
    })

    it('should allow selecting endpoint', async () => {
      renderWithProviders(<APIDocumentationPage />)

      // Click on REST API tab to show endpoints
      const restApiTab = screen.getByText(/rest api/i)
      fireEvent.click(restApiTab)

      // Wait for endpoints to be displayed
      await waitFor(() => {
        expect(screen.getByText(/get.*assets/i)).toBeInTheDocument()
      })
    })
  })

  describe('Code Snippet Generation', () => {
    it('should display code snippet tabs', async () => {
      renderWithProviders(<APIDocumentationPage />)

      // Click on REST API tab to show code snippets
      const restApiTab = screen.getByText(/rest api/i)
      fireEvent.click(restApiTab)

      // Wait for code snippet buttons to appear
      await waitFor(() => {
        expect(screen.getByText(/curl/i)).toBeInTheDocument()
        expect(screen.getByText(/javascript/i)).toBeInTheDocument()
        expect(screen.getByText(/python/i)).toBeInTheDocument()
      })
    })

    it('should switch between code snippet languages', async () => {
      renderWithProviders(<APIDocumentationPage />)

      // Click on REST API tab first
      const restApiTab = screen.getByText(/rest api/i)
      fireEvent.click(restApiTab)

      // Wait for code snippet buttons, then click Python
      await waitFor(() => {
        expect(screen.getByText(/python/i)).toBeInTheDocument()
      })

      const pythonButton = screen.getByText(/python/i)
      fireEvent.click(pythonButton)

      await waitFor(() => {
        expect(screen.getByText(/import requests/i)).toBeInTheDocument()
      })
    })
  })

  describe('Search Functionality', () => {
    it('should display search input', () => {
      renderWithProviders(<APIDocumentationPage />)

      expect(screen.getByPlaceholderText(/search.*api/i)).toBeInTheDocument()
    })

    it('should filter content based on search', async () => {
      renderWithProviders(<APIDocumentationPage />)

      const searchInput = screen.getByPlaceholderText(/search.*api/i)
      fireEvent.change(searchInput, { target: { value: 'assets' } })

      await waitFor(() => {
        expect(screen.getByText(/assets/i)).toBeInTheDocument()
      })
    })
  })

  describe('API Version Selector', () => {
    it('should display version selector', () => {
      renderWithProviders(<APIDocumentationPage />)

      expect(screen.getByText(/api version/i)).toBeInTheDocument()
    })

    it('should allow selecting API version', async () => {
      renderWithProviders(<APIDocumentationPage />)

      const versionSelect = screen.getByLabelText(/api version/i)
      fireEvent.mouseDown(versionSelect)

      await waitFor(() => {
        expect(screen.getByText(/v1/i)).toBeInTheDocument()
      })
    })
  })
})

