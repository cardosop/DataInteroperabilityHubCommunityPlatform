/**
 * ContractPreview Tests
 *
 * Comprehensive tests for the ContractPreview component covering:
 * - Compact view rendering
 * - Full view rendering
 * - Schema display
 * - Owners display
 * - Marketplace policy display
 * - Accordion sections
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ContractPreview } from '../ContractPreview'
import type { HubContract } from '@/components/contracts/types'

const mockHubContract: HubContract = {
  hub_contract_version: 1,
  id: 'contract-1',
  info: {
    name: 'Test Contract',
    description: 'This is a test contract description',
    version: '1.0.0',
    domain: 'marketing',
    tags: ['analytics', 'customer'],
    owners: [
      { name: 'John Doe', email: 'john@example.com' },
      { name: 'Jane Smith', email: 'jane@example.com' },
    ],
  },
  schema: {
    fields: [
      {
        name: 'customer_id',
        data_type: 'string',
        nullable: false,
        description: 'Customer identifier',
      },
      {
        name: 'email',
        data_type: 'string',
        nullable: true,
        description: 'Customer email',
      },
    ],
    primary_key: ['customer_id'],
  },
  quality: {
    rules: [
      {
        rule_id: 'rule-1',
        name: 'Email Format Check',
        dimension: 'completeness',
        severity: 'ERROR',
      },
    ],
  },
  privacy_compliance: {
    contains_personal_data: true,
    personal_data_categories: ['email', 'name'],
    jurisdictions: ['EU', 'US'],
  },
  marketplace: {
    license_summary: 'Free for internal use',
    intended_use: ['analytics', 'reporting'],
    restricted_use: ['resale', 'redistribution'],
  },
}

describe('ContractPreview', () => {
  describe('Compact View', () => {
    it('should render contract name', () => {
      render(<ContractPreview contract={mockHubContract} compact />)

      expect(screen.getByText('Test Contract')).toBeInTheDocument()
    })

    it('should render contract description', () => {
      render(<ContractPreview contract={mockHubContract} compact />)

      expect(screen.getByText('This is a test contract description')).toBeInTheDocument()
    })

    it('should render domain and tags', () => {
      render(<ContractPreview contract={mockHubContract} compact />)

      expect(screen.getByText('marketing')).toBeInTheDocument()
      expect(screen.getByText('analytics')).toBeInTheDocument()
      expect(screen.getByText('customer')).toBeInTheDocument()
    })

    it('should render schema summary', () => {
      render(<ContractPreview contract={mockHubContract} compact />)

      expect(screen.getByText(/schema: 2 fields/i)).toBeInTheDocument()
      expect(screen.getByText(/customer_id, email/i)).toBeInTheDocument()
    })
  })

  describe('Full View', () => {
    it('should render contract header with name and version', () => {
      render(<ContractPreview contract={mockHubContract} />)

      expect(screen.getByText('Test Contract')).toBeInTheDocument()
      expect(screen.getByText(/version: 1\.0\.0/i)).toBeInTheDocument()
    })

    it('should render owners section', () => {
      render(<ContractPreview contract={mockHubContract} />)

      expect(screen.getByText(/owners/i)).toBeInTheDocument()
      expect(screen.getByText('John Doe')).toBeInTheDocument()
      expect(screen.getByText('john@example.com')).toBeInTheDocument()
      expect(screen.getByText('Jane Smith')).toBeInTheDocument()
      expect(screen.getByText('jane@example.com')).toBeInTheDocument()
    })

    it('should render schema fields accordion', () => {
      render(<ContractPreview contract={mockHubContract} />)

      expect(screen.getByText(/schema fields \(2\)/i)).toBeInTheDocument()
      expect(screen.getByText('customer_id')).toBeInTheDocument()
      expect(screen.getByText('email')).toBeInTheDocument()
    })

    it('should render marketplace policy accordion', () => {
      render(<ContractPreview contract={mockHubContract} />)

      expect(screen.getByText(/marketplace policy/i)).toBeInTheDocument()
      expect(screen.getByText('Free for internal use')).toBeInTheDocument()
      expect(screen.getByText('analytics')).toBeInTheDocument()
      expect(screen.getByText('reporting')).toBeInTheDocument()
    })

    it('should render restricted use chips', () => {
      render(<ContractPreview contract={mockHubContract} />)

      expect(screen.getByText('resale')).toBeInTheDocument()
      expect(screen.getByText('redistribution')).toBeInTheDocument()
    })
  })

  describe('Show All Sections', () => {
    it('should show quality rules when showAllSections is true', () => {
      render(<ContractPreview contract={mockHubContract} showAllSections />)

      expect(screen.getByText(/quality rules/i)).toBeInTheDocument()
      expect(screen.getByText('Email Format Check')).toBeInTheDocument()
    })

    it('should show compliance section when showAllSections is true', () => {
      render(<ContractPreview contract={mockHubContract} showAllSections />)

      expect(screen.getByText(/privacy & compliance/i)).toBeInTheDocument()
      expect(screen.getByText(/contains personal data: yes/i)).toBeInTheDocument()
    })

    it('should not show quality rules when showAllSections is false', () => {
      render(<ContractPreview contract={mockHubContract} showAllSections={false} />)

      expect(screen.queryByText(/quality rules/i)).not.toBeInTheDocument()
    })
  })

  describe('Empty States', () => {
    it('should handle contract without description', () => {
      const contractWithoutDescription: HubContract = {
        ...mockHubContract,
        info: {
          ...mockHubContract.info,
          description: undefined,
        },
      }

      render(<ContractPreview contract={contractWithoutDescription} />)

      expect(screen.getByText('Test Contract')).toBeInTheDocument()
    })

    it('should handle contract without owners', () => {
      const contractWithoutOwners: HubContract = {
        ...mockHubContract,
        info: {
          ...mockHubContract.info,
          owners: undefined,
        },
      }

      render(<ContractPreview contract={contractWithoutOwners} />)

      expect(screen.queryByText(/owners/i)).not.toBeInTheDocument()
    })

    it('should handle contract without schema fields', () => {
      const contractWithoutSchema: HubContract = {
        ...mockHubContract,
        schema: {
          fields: [],
        },
      }

      render(<ContractPreview contract={contractWithoutSchema} />)

      expect(screen.queryByText(/schema fields/i)).not.toBeInTheDocument()
    })
  })
})

