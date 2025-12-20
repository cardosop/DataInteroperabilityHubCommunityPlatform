/**
 * ContractCard Component Tests
 *
 * Comprehensive tests for the ContractCard component covering:
 * - Rendering with different contract states
 * - Click interactions and navigation
 * - Action callbacks (view, edit, delete)
 * - Description truncation
 * - Related info display (tags, owners, asset)
 * - Status badges
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, fireEvent, render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { renderWithProviders } from '@/test-utils'
import { ContractCard } from '../ContractCard'
import { contractFactory } from '../../../../../tests/factories'
import type { Contract } from '@/lib/api/contracts'

// Mock useNavigate
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

describe('ContractCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('renders contract card with basic information', () => {
      const contract = contractFactory.build()

      renderWithProviders(<ContractCard contract={contract} />)

      const contractName = contract.hub_contract_json.info.name
      expect(screen.getByText(contractName)).toBeInTheDocument()
    })

    it('renders contract with description', () => {
      const contract = contractFactory.build({
        overrides: {
          hub_contract_json: {
            info: {
              name: 'Test Contract',
              description: 'This is a test contract description',
            },
          },
        },
      })

      renderWithProviders(<ContractCard contract={contract} />)

      expect(screen.getByText(/This is a test contract description/i)).toBeInTheDocument()
    })

    it('renders contract without description', () => {
      const contract = contractFactory.build({
        overrides: {
          hub_contract_json: {
            info: {
              name: 'Test Contract',
              description: undefined,
            },
          },
        },
      })

      renderWithProviders(<ContractCard contract={contract} />)

      expect(screen.getByText('No description')).toBeInTheDocument()
    })

    it('renders contract ID when available', () => {
      const contract = contractFactory.build()

      renderWithProviders(<ContractCard contract={contract} />)

      expect(screen.getByText(new RegExp(`ID: ${contract.hub_contract_json.id}`))).toBeInTheDocument()
    })

    it('renders status badges', () => {
      const contract = contractFactory.build()

      renderWithProviders(<ContractCard contract={contract} />)

      expect(screen.getByText(contract.status)).toBeInTheDocument()
      // Normalization status is formatted (underscores replaced with spaces)
      const normalizedStatusText = contract.normalization_status.replace(/_/g, ' ')
      expect(screen.getByText(normalizedStatusText)).toBeInTheDocument()
      if (contract.validation_status) {
        expect(screen.getByText(contract.validation_status)).toBeInTheDocument()
      }
    })

    it('renders tags when available', () => {
      const contract = contractFactory.build({
        overrides: {
          tags: ['tag1', 'tag2', 'tag3'],
        },
      })

      renderWithProviders(<ContractCard contract={contract} />)

      expect(screen.getByText('tag1')).toBeInTheDocument()
      expect(screen.getByText('tag2')).toBeInTheDocument()
      expect(screen.getByText('tag3')).toBeInTheDocument()
    })

    it('shows tag count when more than 3 tags', () => {
      const contract = contractFactory.build({
        overrides: {
          tags: ['tag1', 'tag2', 'tag3', 'tag4', 'tag5'],
        },
      })

      renderWithProviders(<ContractCard contract={contract} />)

      expect(screen.getByText('+2')).toBeInTheDocument()
    })

    it('renders owners when available', () => {
      const contract = contractFactory.build({
        overrides: {
          owners: [
            { name: 'Owner 1', email: 'owner1@test.com' },
            { name: 'Owner 2', email: 'owner2@test.com' },
          ],
        },
      })

      renderWithProviders(<ContractCard contract={contract} />)

      expect(screen.getByText(/Owners: Owner 1, Owner 2/i)).toBeInTheDocument()
    })

    it('renders asset ID when available', () => {
      const contract = contractFactory.withAsset('asset-123')

      renderWithProviders(<ContractCard contract={contract} />)

      // Component shows first 8 characters + "..."
      // "asset-123" -> "asset-12..."
      expect(screen.getByText(/Asset: asset-12\.\.\./i)).toBeInTheDocument()
    })

    it('renders updated timestamp', () => {
      const contract = contractFactory.build()

      renderWithProviders(<ContractCard contract={contract} />)

      expect(screen.getByText(/Updated/i)).toBeInTheDocument()
    })
  })

  describe('Description Truncation', () => {
    it('truncates long description by default', () => {
      const longDescription = 'a'.repeat(200)
      const contract = contractFactory.build({
        overrides: {
          hub_contract_json: {
            info: {
              name: 'Test Contract',
              description: longDescription,
            },
          },
        },
      })

      renderWithProviders(<ContractCard contract={contract} />)

      const descriptionElement = screen.getByText(/^a{150}\.\.\./)
      expect(descriptionElement).toBeInTheDocument()
    })

    it('shows full description when showFullDescription is true', () => {
      const longDescription = 'a'.repeat(200)
      const contract = contractFactory.build({
        overrides: {
          hub_contract_json: {
            info: {
              name: 'Test Contract',
              description: longDescription,
            },
          },
        },
      })

      render(
        <MemoryRouter>
          <ContractCard contract={contract} showFullDescription={true} />
        </MemoryRouter>
      )

      expect(screen.getByText(longDescription)).toBeInTheDocument()
    })
  })

  describe('Click Interactions', () => {
    it('navigates to contract detail page when card is clicked', () => {
      const contract = contractFactory.build()

      renderWithProviders(<ContractCard contract={contract} />)

      const card = screen.getByText(contract.hub_contract_json.info.name).closest('div[class*="MuiCard"]')
      expect(card).toBeInTheDocument()

      fireEvent.click(card!)

      expect(mockNavigate).toHaveBeenCalledWith(`/contracts/${contract.id}`)
    })

    it('calls onClick callback when provided', () => {
      const contract = contractFactory.build()
      const handleClick = vi.fn()

      render(
        <MemoryRouter>
          <ContractCard contract={contract} onClick={handleClick} />
        </MemoryRouter>
      )

      const card = screen.getByText(contract.hub_contract_json.info.name).closest('div[class*="MuiCard"]')
      fireEvent.click(card!)

      expect(handleClick).toHaveBeenCalledWith(contract)
      expect(mockNavigate).not.toHaveBeenCalled()
    })

    it('does not navigate when clickable is false', () => {
      const contract = contractFactory.build()

      render(
        <MemoryRouter>
          <ContractCard contract={contract} clickable={false} />
        </MemoryRouter>
      )

      const card = screen.getByText(contract.hub_contract_json.info.name).closest('div[class*="MuiCard"]')
      fireEvent.click(card!)

      expect(mockNavigate).not.toHaveBeenCalled()
    })
  })

  describe('Action Callbacks', () => {
    it('calls onView when view action is clicked', () => {
      const contract = contractFactory.build()
      const handleView = vi.fn()

      render(
        <MemoryRouter>
          <ContractCard contract={contract} onView={handleView} />
        </MemoryRouter>
      )

      const viewButton = screen.getByText('View')
      fireEvent.click(viewButton)

      expect(handleView).toHaveBeenCalledWith(contract)
    })

    it('calls onEdit when edit action is clicked', () => {
      const contract = contractFactory.build()
      const handleEdit = vi.fn()

      render(
        <MemoryRouter>
          <ContractCard contract={contract} onEdit={handleEdit} />
        </MemoryRouter>
      )

      const editButton = screen.getByText('Edit')
      fireEvent.click(editButton)

      expect(handleEdit).toHaveBeenCalledWith(contract)
    })

    it('calls onDelete when delete action is clicked', () => {
      const contract = contractFactory.build()
      const handleDelete = vi.fn()

      render(
        <MemoryRouter>
          <ContractCard contract={contract} onDelete={handleDelete} />
        </MemoryRouter>
      )

      const deleteButton = screen.getByText('Delete')
      fireEvent.click(deleteButton)

      expect(handleDelete).toHaveBeenCalledWith(contract)
    })

    it('navigates to view page when card is clicked and onView is not provided', () => {
      const contract = contractFactory.build()

      const { container } = render(
        <MemoryRouter>
          <ContractCard contract={contract} clickable={true} />
        </MemoryRouter>
      )

      // When onView is not provided and card is clickable, clicking should navigate
      const card = container.querySelector('.MuiCard-root')
      if (card) {
        fireEvent.click(card)
        expect(mockNavigate).toHaveBeenCalledWith(`/contracts/${contract.id}`)
      }
    })

    it('navigates to edit page when onEdit is provided and edit button is clicked', () => {
      const contract = contractFactory.build()
      const onEdit = vi.fn()

      render(
        <MemoryRouter>
          <ContractCard contract={contract} onEdit={onEdit} showActions={true} />
        </MemoryRouter>
      )

      // When onEdit is provided, the Edit button should be visible
      const editButton = screen.getByText('Edit')
      fireEvent.click(editButton)

      expect(onEdit).toHaveBeenCalledWith(contract)
    })
  })

  describe('Visibility Options', () => {
    it('hides actions when showActions is false', () => {
      const contract = contractFactory.build()

      render(
        <MemoryRouter>
          <ContractCard contract={contract} showActions={false} />
        </MemoryRouter>
      )

      expect(screen.queryByText('View')).not.toBeInTheDocument()
      expect(screen.queryByText('Edit')).not.toBeInTheDocument()
    })

    it('hides related info when showRelatedInfo is false', () => {
      const contract = contractFactory.build({
        overrides: {
          tags: ['tag1', 'tag2'],
          owners: [{ name: 'Owner', email: 'owner@test.com' }],
        },
      })

      render(
        <MemoryRouter>
          <ContractCard contract={contract} showRelatedInfo={false} />
        </MemoryRouter>
      )

      expect(screen.queryByText('tag1')).not.toBeInTheDocument()
      expect(screen.queryByText(/Owners:/i)).not.toBeInTheDocument()
    })
  })

  describe('Different Contract States', () => {
    it('renders DRAFT contract correctly', () => {
      const contract = contractFactory.draft()

      renderWithProviders(<ContractCard contract={contract} />)

      expect(screen.getByText('DRAFT')).toBeInTheDocument()
    })

    it('renders ACTIVE contract correctly', () => {
      const contract = contractFactory.build()

      renderWithProviders(<ContractCard contract={contract} />)

      expect(screen.getByText('ACTIVE')).toBeInTheDocument()
    })

    it('renders contract with INVALID validation status', () => {
      const contract = contractFactory.invalid()

      renderWithProviders(<ContractCard contract={contract} />)

      expect(screen.getByText('INVALID')).toBeInTheDocument()
    })

    it('renders contract with WARNING_ONLY validation status', () => {
      const contract = contractFactory.warning()

      renderWithProviders(<ContractCard contract={contract} />)

      expect(screen.getByText('WARNING_ONLY')).toBeInTheDocument()
    })
  })

  describe('Contract Name Extraction', () => {
    it('uses contract name from hub_contract_json.info.name', () => {
      const contract = contractFactory.build({
        overrides: {
          hub_contract_json: {
            info: {
              name: 'Custom Contract Name',
            },
          },
        },
      })

      renderWithProviders(<ContractCard contract={contract} />)

      expect(screen.getByText('Custom Contract Name')).toBeInTheDocument()
    })

    it('falls back to contract ID when name is missing', () => {
      const contract = contractFactory.build({
        overrides: {
          hub_contract_json: {
            id: 'contract-id-123',
            info: {
              name: undefined,
            },
          },
        },
      })

      renderWithProviders(<ContractCard contract={contract} />)

      expect(screen.getByText('contract-id-123')).toBeInTheDocument()
    })

    it('falls back to "Unnamed Contract" when both name and ID are missing', () => {
      const contract = contractFactory.build({
        overrides: {
          hub_contract_json: {
            id: undefined,
            info: {
              name: undefined,
            },
          },
        },
      })

      renderWithProviders(<ContractCard contract={contract} />)

      expect(screen.getByText('Unnamed Contract')).toBeInTheDocument()
    })
  })

  describe('Event Propagation', () => {
    it('stops event propagation for action buttons', () => {
      const contract = contractFactory.build()
      const handleClick = vi.fn()
      const handleEdit = vi.fn()

      render(
        <MemoryRouter>
          <ContractCard contract={contract} onClick={handleClick} onEdit={handleEdit} />
        </MemoryRouter>
      )

      const editButton = screen.getByText('Edit')
      fireEvent.click(editButton)

      expect(handleEdit).toHaveBeenCalled()
      expect(handleClick).not.toHaveBeenCalled()
    })
  })
})

