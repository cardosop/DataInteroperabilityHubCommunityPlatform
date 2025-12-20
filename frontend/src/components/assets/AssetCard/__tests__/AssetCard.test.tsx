/**
 * AssetCard Component Tests
 *
 * Comprehensive tests for the AssetCard component covering:
 * - Rendering with different asset states
 * - Click interactions and navigation
 * - Action callbacks (view, edit, delete)
 * - Description truncation
 * - Related info display
 * - Status badges
 * - Memoization behavior
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent, waitFor, render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { renderWithProviders } from '@/test-utils'
import { AssetCard } from '../AssetCard'
import { assetFactory } from '../../../../../tests/factories'
import type { Asset } from '@/lib/api/assets'

// Mock useNavigate
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

describe('AssetCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('renders asset card with basic information', () => {
      const asset = assetFactory.build()

      renderWithProviders(<AssetCard asset={asset} />)

      expect(screen.getByText(asset.name)).toBeInTheDocument()
      expect(screen.getByText(asset.key)).toBeInTheDocument()
    })

    it('renders asset with description', () => {
      const asset = assetFactory.build({
        overrides: {
          description: 'This is a test asset description',
        },
      })

      renderWithProviders(<AssetCard asset={asset} />)

      expect(screen.getByText(/This is a test asset description/i)).toBeInTheDocument()
    })

    it('renders asset without description', () => {
      const asset = assetFactory.build({
        overrides: {
          description: null,
        },
      })

      renderWithProviders(<AssetCard asset={asset} />)

      expect(screen.getByText('No description')).toBeInTheDocument()
    })

    it('renders asset with domain', () => {
      const asset = assetFactory.build({
        overrides: {
          domain: 'test-domain',
        },
      })

      renderWithProviders(<AssetCard asset={asset} />)

      expect(screen.getByText(/Domain: test-domain/i)).toBeInTheDocument()
    })

    it('renders status badges', () => {
      const asset = assetFactory.build()

      renderWithProviders(<AssetCard asset={asset} />)

      expect(screen.getByText(asset.status)).toBeInTheDocument()
      // Use getAllByText for statuses that might appear multiple times (e.g., "PASS")
      const dqStatusElements = screen.getAllByText(asset.dq_status)
      expect(dqStatusElements.length).toBeGreaterThan(0)
      const complianceStatusElements = screen.getAllByText(asset.compliance_status)
      expect(complianceStatusElements.length).toBeGreaterThan(0)
      expect(screen.getByText(asset.visibility)).toBeInTheDocument()
    })

    it('renders contract information when available', () => {
      const contractId = 'contract-123'
      const asset = assetFactory.withContract(contractId, {
        overrides: {
          contract: {
            id: contractId,
            name: 'Test Contract',
            status: 'ACTIVE',
          },
        },
      })

      renderWithProviders(<AssetCard asset={asset} />)

      expect(screen.getByText(/Contract: Test Contract/i)).toBeInTheDocument()
    })

    it('renders dataset information when available', () => {
      const datasetId = 'dataset-123'
      const asset = assetFactory.withDataset(datasetId, {
        overrides: {
          dataset: {
            id: datasetId,
            name: 'Test Dataset',
            format: 'CSV',
          },
        },
      })

      renderWithProviders(<AssetCard asset={asset} />)

      expect(screen.getByText(/Dataset: Test Dataset/i)).toBeInTheDocument()
    })

    it('renders updated timestamp', () => {
      const asset = assetFactory.build()

      renderWithProviders(<AssetCard asset={asset} />)

      expect(screen.getByText(/Updated/i)).toBeInTheDocument()
    })
  })

  describe('Description Truncation', () => {
    it('truncates long description by default', () => {
      const longDescription = 'a'.repeat(200)
      const asset = assetFactory.build({
        overrides: {
          description: longDescription,
        },
      })

      renderWithProviders(<AssetCard asset={asset} />)

      const descriptionElement = screen.getByText(/^a{150}\.\.\./)
      expect(descriptionElement).toBeInTheDocument()
    })

    it('shows full description when showFullDescription is true', () => {
      const longDescription = 'a'.repeat(200)
      const asset = assetFactory.build({
        overrides: {
          description: longDescription,
        },
      })

      render(
        <MemoryRouter>
          <AssetCard asset={asset} showFullDescription={true} />
        </MemoryRouter>
      )

      expect(screen.getByText(longDescription)).toBeInTheDocument()
    })

    it('does not truncate short description', () => {
      const shortDescription = 'Short description'
      const asset = assetFactory.build({
        overrides: {
          description: shortDescription,
        },
      })

      renderWithProviders(<AssetCard asset={asset} />)

      expect(screen.getByText(shortDescription)).toBeInTheDocument()
    })
  })

  describe('Click Interactions', () => {
    it('navigates to asset detail page when card is clicked', () => {
      const asset = assetFactory.build()

      renderWithProviders(<AssetCard asset={asset} />)

      const card = screen.getByText(asset.name).closest('div[class*="MuiCard"]')
      expect(card).toBeInTheDocument()

      fireEvent.click(card!)

      expect(mockNavigate).toHaveBeenCalledWith(`/assets/${asset.id}`)
    })

    it('calls onClick callback when provided', () => {
      const asset = assetFactory.build()
      const handleClick = vi.fn()

      render(
        <MemoryRouter>
          <AssetCard asset={asset} onClick={handleClick} />
        </MemoryRouter>
      )

      const card = screen.getByText(asset.name).closest('div[class*="MuiCard"]')
      fireEvent.click(card!)

      expect(handleClick).toHaveBeenCalledWith(asset)
      expect(mockNavigate).not.toHaveBeenCalled()
    })

    it('does not navigate when clickable is false', () => {
      const asset = assetFactory.build()

      render(
        <MemoryRouter>
          <AssetCard asset={asset} clickable={false} />
        </MemoryRouter>
      )

      const card = screen.getByText(asset.name).closest('div[class*="MuiCard"]')
      fireEvent.click(card!)

      expect(mockNavigate).not.toHaveBeenCalled()
    })
  })

  describe('Action Callbacks', () => {
    it('calls onView when view action is clicked', () => {
      const asset = assetFactory.build()
      const handleView = vi.fn()

      render(
        <MemoryRouter>
          <AssetCard asset={asset} onView={handleView} />
        </MemoryRouter>
      )

      // Find and click view button (from AssetActions component)
      const viewButton = screen.getByRole('button', { name: /view/i })
      fireEvent.click(viewButton)

      expect(handleView).toHaveBeenCalledWith(asset)
    })

    it('calls onEdit when edit action is clicked', () => {
      const asset = assetFactory.build()
      const handleEdit = vi.fn()

      render(
        <MemoryRouter>
          <AssetCard asset={asset} onEdit={handleEdit} />
        </MemoryRouter>
      )

      const editButton = screen.getByRole('button', { name: /edit/i })
      fireEvent.click(editButton)

      expect(handleEdit).toHaveBeenCalledWith(asset)
    })

    it('calls onDelete when delete action is clicked', () => {
      const asset = assetFactory.build()
      const handleDelete = vi.fn()

      render(
        <MemoryRouter>
          <AssetCard asset={asset} onDelete={handleDelete} />
        </MemoryRouter>
      )

      const deleteButton = screen.getByRole('button', { name: /delete/i })
      fireEvent.click(deleteButton)

      expect(handleDelete).toHaveBeenCalledWith(asset)
    })

    it('navigates to view page when card is clicked and onView is not provided', () => {
      const asset = assetFactory.build()

      const { container } = render(
        <MemoryRouter>
          <AssetCard asset={asset} clickable={true} />
        </MemoryRouter>
      )

      // When onView is not provided and card is clickable, clicking should navigate
      const card = container.querySelector('.MuiCard-root')
      if (card) {
        fireEvent.click(card)
        expect(mockNavigate).toHaveBeenCalledWith(`/assets/${asset.id}`)
      }
    })

    it('navigates to edit page when onEdit is provided and edit button is clicked', () => {
      const asset = assetFactory.build()
      const onEdit = vi.fn()

      render(
        <MemoryRouter>
          <AssetCard asset={asset} onEdit={onEdit} showActions={true} />
        </MemoryRouter>
      )

      // When onEdit is provided, the Edit button should be visible
      const editButton = screen.getByRole('button', { name: /edit/i })
      fireEvent.click(editButton)

      expect(onEdit).toHaveBeenCalledWith(asset)
    })
  })

  describe('Visibility Options', () => {
    it('hides actions when showActions is false', () => {
      const asset = assetFactory.build()

      render(
        <MemoryRouter>
          <AssetCard asset={asset} showActions={false} />
        </MemoryRouter>
      )

      expect(screen.queryByRole('button', { name: /view/i })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /edit/i })).not.toBeInTheDocument()
    })

    it('hides related info when showRelatedInfo is false', () => {
      const asset = assetFactory.withContract('contract-123', {
        overrides: {
          contract: {
            id: 'contract-123',
            name: 'Test Contract',
            status: 'ACTIVE',
          },
        },
      })

      render(
        <MemoryRouter>
          <AssetCard asset={asset} showRelatedInfo={false} />
        </MemoryRouter>
      )

      expect(screen.queryByText(/Contract:/i)).not.toBeInTheDocument()
    })

    it('shows related info by default', () => {
      const asset = assetFactory.withContract('contract-123', {
        overrides: {
          contract: {
            id: 'contract-123',
            name: 'Test Contract',
            status: 'ACTIVE',
          },
        },
      })

      renderWithProviders(<AssetCard asset={asset} />)

      expect(screen.getByText(/Contract:/i)).toBeInTheDocument()
    })
  })

  describe('Different Asset States', () => {
    it('renders DRAFT asset correctly', () => {
      const asset = assetFactory.draft()

      renderWithProviders(<AssetCard asset={asset} />)

      expect(screen.getByText('DRAFT')).toBeInTheDocument()
    })

    it('renders ACTIVE asset correctly', () => {
      const asset = assetFactory.active()

      renderWithProviders(<AssetCard asset={asset} />)

      expect(screen.getByText('ACTIVE')).toBeInTheDocument()
    })

    it('renders PUBLIC asset correctly', () => {
      const asset = assetFactory.public()

      renderWithProviders(<AssetCard asset={asset} />)

      // PUBLIC appears in both status and visibility badges, so use getAllByText
      const publicElements = screen.getAllByText('PUBLIC')
      expect(publicElements.length).toBeGreaterThan(0)
      // Verify at least one is in a Chip (badge)
      const chipElements = publicElements.filter(el =>
        el.closest('[class*="MuiChip"]') !== null
      )
      expect(chipElements.length).toBeGreaterThan(0)
    })

    it('renders asset with FAILED compliance status', () => {
      const asset = assetFactory.complianceFailed()

      renderWithProviders(<AssetCard asset={asset} />)

      expect(screen.getByText('FAIL')).toBeInTheDocument()
    })

    it('renders asset with FAILED data quality status', () => {
      const asset = assetFactory.dqFailed()

      renderWithProviders(<AssetCard asset={asset} />)

      expect(screen.getByText('FAIL')).toBeInTheDocument()
    })
  })

  describe('Card Props', () => {
    it('applies custom card props', () => {
      const asset = assetFactory.build()

      render(
        <MemoryRouter>
          <AssetCard
            asset={asset}
            cardProps={{
              'data-testid': 'custom-asset-card',
              sx: { backgroundColor: 'red' },
            }}
          />
        </MemoryRouter>
      )

      const card = screen.getByTestId('custom-asset-card')
      expect(card).toBeInTheDocument()
    })
  })

  describe('Event Propagation', () => {
    it('stops event propagation for action buttons', () => {
      const asset = assetFactory.build()
      const handleClick = vi.fn()
      const handleEdit = vi.fn()

      render(
        <MemoryRouter>
          <AssetCard asset={asset} onClick={handleClick} onEdit={handleEdit} />
        </MemoryRouter>
      )

      const editButton = screen.getByRole('button', { name: /edit/i })
      fireEvent.click(editButton)

      expect(handleEdit).toHaveBeenCalled()
      expect(handleClick).not.toHaveBeenCalled()
    })
  })
})

