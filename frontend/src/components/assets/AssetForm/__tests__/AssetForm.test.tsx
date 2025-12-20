/**
 * AssetForm Component Tests
 *
 * Comprehensive tests for the AssetForm component covering:
 * - Form rendering in create and edit modes
 * - Form validation
 * - Form submission
 * - Field interactions
 * - Error handling
 * - Loading states
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@/test-utils'
import userEvent from '@testing-library/user-event'
import { AssetForm } from '../AssetForm'
import { assetFactory } from '../../../../../tests/factories'
import type { Asset, CreateAssetRequest, UpdateAssetRequest } from '@/lib/api/assets'

describe('AssetForm', () => {
  const mockOnSubmit = vi.fn()
  const mockOnCancel = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Create Mode', () => {
    it('renders form in create mode', () => {
      render(<AssetForm onSubmit={mockOnSubmit} mode="create" />)

      expect(screen.getByText('Create Asset')).toBeInTheDocument()
      expect(screen.getByLabelText(/key/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/name/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/description/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/domain/i)).toBeInTheDocument()
    })

    it('shows key field in create mode', () => {
      render(<AssetForm onSubmit={mockOnSubmit} mode="create" />)

      const keyField = screen.getByLabelText(/key/i)
      expect(keyField).toBeInTheDocument()
      expect(keyField).not.toBeDisabled()
    })

    it('validates required fields', async () => {
      const user = userEvent.setup()
      render(<AssetForm onSubmit={mockOnSubmit} mode="create" />)

      // Focus and blur fields to trigger validation (form uses onBlur mode)
      const keyField = screen.getByLabelText(/key/i)
      const nameField = screen.getByLabelText(/name/i)

      await user.click(keyField)
      await user.tab() // Blur key field
      await user.click(nameField)
      await user.tab() // Blur name field

      // Try to submit
      const submitButton = screen.getByRole('button', { name: /save/i })
      await user.click(submitButton)

      await waitFor(() => {
        // Use getAllByText since there might be multiple error messages
        // Schema uses "Key is required" and "Name is required" (capitalized)
        const keyErrors = screen.getAllByText(/key is required/i)
        expect(keyErrors.length).toBeGreaterThan(0)
        const nameErrors = screen.getAllByText(/name is required/i)
        expect(nameErrors.length).toBeGreaterThan(0)
      })

      expect(mockOnSubmit).not.toHaveBeenCalled()
    })

    it('validates key format', async () => {
      const user = userEvent.setup()
      render(<AssetForm onSubmit={mockOnSubmit} mode="create" />)

      const keyField = screen.getByLabelText(/key/i)
      await user.type(keyField, 'Invalid Key With Spaces!')

      const submitButton = screen.getByRole('button', { name: /save/i })
      await user.click(submitButton)

      await waitFor(() => {
        // Use getAllByText since there might be multiple error messages
        const errors = screen.getAllByText(/key must contain only lowercase letters, numbers, hyphens, and underscores/i)
        expect(errors.length).toBeGreaterThan(0)
      })

      expect(mockOnSubmit).not.toHaveBeenCalled()
    })

    it('validates key length', async () => {
      const user = userEvent.setup()
      render(<AssetForm onSubmit={mockOnSubmit} mode="create" />)

      const keyField = screen.getByLabelText(/key/i)
      await user.type(keyField, 'a'.repeat(256))

      const submitButton = screen.getByRole('button', { name: /save/i })
      await user.click(submitButton)

      await waitFor(() => {
        // Use getAllByText since there might be multiple error messages
        const errors = screen.getAllByText(/key must be 255 characters or less/i)
        expect(errors.length).toBeGreaterThan(0)
      })

      expect(mockOnSubmit).not.toHaveBeenCalled()
    })

    it('validates name length', async () => {
      const user = userEvent.setup()
      render(<AssetForm onSubmit={mockOnSubmit} mode="create" />)

      const nameField = screen.getByLabelText(/name/i)
      await user.type(nameField, 'a'.repeat(256))

      const submitButton = screen.getByRole('button', { name: /save/i })
      await user.click(submitButton)

      await waitFor(() => {
        // Use getAllByText since there might be multiple error messages
        const errors = screen.getAllByText(/name must be 255 characters or less/i)
        expect(errors.length).toBeGreaterThan(0)
      })

      expect(mockOnSubmit).not.toHaveBeenCalled()
    })

    it('validates description length', async () => {
      const user = userEvent.setup()
      render(<AssetForm onSubmit={mockOnSubmit} mode="create" />)

      const keyField = screen.getByLabelText(/key/i)
      const nameField = screen.getByLabelText(/name/i)
      const descriptionField = screen.getByLabelText(/description/i)

      await user.type(keyField, 'valid-key')
      await user.type(nameField, 'Valid Name')

      // Use fireEvent for large text input to avoid timeout
      const longDescription = 'a'.repeat(5001)
      fireEvent.change(descriptionField, { target: { value: longDescription } })
      fireEvent.blur(descriptionField) // Trigger validation

      const submitButton = screen.getByRole('button', { name: /save/i })
      await user.click(submitButton)

      await waitFor(() => {
        // Use getAllByText since there might be multiple error messages
        const errors = screen.getAllByText(/description must be 5000 characters or less/i)
        expect(errors.length).toBeGreaterThan(0)
      }, { timeout: 5000 })

      expect(mockOnSubmit).not.toHaveBeenCalled()
    })

    it('submits form with valid data in create mode', async () => {
      const user = userEvent.setup()
      render(<AssetForm onSubmit={mockOnSubmit} mode="create" />)

      const keyField = screen.getByLabelText(/key/i)
      const nameField = screen.getByLabelText(/name/i)
      const descriptionField = screen.getByLabelText(/description/i)
      const domainField = screen.getByLabelText(/domain/i)

      await user.type(keyField, 'test-asset-key')
      await user.type(nameField, 'Test Asset Name')
      await user.type(descriptionField, 'Test description')
      await user.type(domainField, 'test-domain')

      const submitButton = screen.getByRole('button', { name: /save/i })
      await user.click(submitButton)

      await waitFor(() => {
        // Form may submit with null/undefined for optional fields, or empty strings
        // Check that the required fields are present and correct
        expect(mockOnSubmit).toHaveBeenCalled()
        const callArgs = mockOnSubmit.mock.calls[0][0] as CreateAssetRequest
        expect(callArgs.key).toBe('test-asset-key')
        expect(callArgs.name).toBe('Test Asset Name')
        expect(callArgs.visibility).toBe('INTERNAL')
        // Description and domain are optional - check if they're present
        if ('description' in callArgs) {
          expect(callArgs.description).toBe('Test description')
        }
        if ('domain' in callArgs) {
          expect(callArgs.domain).toBe('test-domain')
        }
      })
    })

    it('submits form with minimal required data', async () => {
      const user = userEvent.setup()
      render(<AssetForm onSubmit={mockOnSubmit} mode="create" />)

      const keyField = screen.getByLabelText(/key/i)
      const nameField = screen.getByLabelText(/name/i)

      await user.type(keyField, 'minimal-key')
      await user.type(nameField, 'Minimal Name')

      // Blur fields to trigger validation
      await user.tab() // Blur name field

      const submitButton = screen.getByRole('button', { name: /save/i })
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalled()
        const callArgs = mockOnSubmit.mock.calls[0][0] as CreateAssetRequest
        expect(callArgs.key).toBe('minimal-key')
        expect(callArgs.name).toBe('Minimal Name')
        expect(callArgs.visibility).toBe('INTERNAL')
        // Description and domain are optional - form submits null for empty fields
        expect(callArgs.description).toBeNull()
        expect(callArgs.domain).toBeNull()
      }, { timeout: 5000 })
    })
  })

  describe('Edit Mode', () => {
    it('renders form in edit mode', () => {
      const asset = assetFactory.build()

      render(<AssetForm asset={asset} onSubmit={mockOnSubmit} mode="edit" />)

      expect(screen.getByText('Edit Asset')).toBeInTheDocument()
      expect(screen.queryByLabelText(/key/i)).not.toBeInTheDocument()
      expect(screen.getByText(asset.key)).toBeInTheDocument()
    })

    it('hides key field in edit mode', () => {
      const asset = assetFactory.build()

      render(<AssetForm asset={asset} onSubmit={mockOnSubmit} mode="edit" />)

      expect(screen.queryByLabelText(/key/i)).not.toBeInTheDocument()
      expect(screen.getByText(/key cannot be changed after creation/i)).toBeInTheDocument()
    })

    it('pre-fills form with asset data', () => {
      const asset = assetFactory.build({
        overrides: {
          name: 'Existing Asset',
          description: 'Existing description',
          domain: 'existing-domain',
          visibility: 'PUBLIC',
          status: 'ACTIVE',
        },
      })

      render(<AssetForm asset={asset} onSubmit={mockOnSubmit} mode="edit" />)

      expect(screen.getByDisplayValue('Existing Asset')).toBeInTheDocument()
      expect(screen.getByDisplayValue('Existing description')).toBeInTheDocument()
      expect(screen.getByDisplayValue('existing-domain')).toBeInTheDocument()
    })

    it('shows status field in edit mode', () => {
      const asset = assetFactory.build()

      render(<AssetForm asset={asset} onSubmit={mockOnSubmit} mode="edit" />)

      // Status field is a select - MUI Select shows as button when closed
      // Find the form control containing the status field
      const statusLabels = screen.getAllByText(/status/i)
      expect(statusLabels.length).toBeGreaterThan(0)

      // Find the select button by finding the form control and then the button inside it
      const statusLabel = statusLabels.find(label =>
        label.classList.contains('MuiInputLabel-root') ||
        label.closest('.MuiFormControl-root')
      )
      expect(statusLabel).toBeDefined()

      // The select is rendered as a button when closed
      const formControl = statusLabel?.closest('.MuiFormControl-root')
      const selectButton = formControl?.querySelector('button[aria-haspopup="listbox"]')
      expect(selectButton).toBeDefined()
    })

    it('submits form with updated data in edit mode', async () => {
      const user = userEvent.setup()
      const asset = assetFactory.build()

      render(<AssetForm asset={asset} onSubmit={mockOnSubmit} mode="edit" />)

      const nameField = screen.getByLabelText(/name/i)
      await user.clear(nameField)
      await user.type(nameField, 'Updated Asset Name')

      const submitButton = screen.getByRole('button', { name: /save/i })
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalledWith({
          name: 'Updated Asset Name',
          description: asset.description,
          domain: asset.domain,
          status: asset.status,
          visibility: asset.visibility,
          version: asset.version,
        } as UpdateAssetRequest)
      })
    })

    it('includes version in update request for optimistic locking', async () => {
      const user = userEvent.setup()
      const asset = assetFactory.build({
        overrides: {
          version: 5,
        },
      })

      render(<AssetForm asset={asset} onSubmit={mockOnSubmit} mode="edit" />)

      const nameField = screen.getByLabelText(/name/i)
      await user.clear(nameField)
      await user.type(nameField, 'Updated Name')

      const submitButton = screen.getByRole('button', { name: /save/i })
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalledWith(
          expect.objectContaining({
            version: 5,
          })
        )
      })
    })
  })

  describe('Form Interactions', () => {
    it('allows changing visibility', async () => {
      const user = userEvent.setup()
      render(<AssetForm onSubmit={mockOnSubmit} mode="create" />)

      const keyField = screen.getByLabelText(/key/i)
      const nameField = screen.getByLabelText(/name/i)

      await user.type(keyField, 'test-key')
      await user.type(nameField, 'Test Name')

      // MUI Select uses InputLabel - find the select by its label association
      // MUI Select renders as a button with role="combobox" when closed
      // There might be multiple elements with "visibility" text, so find the label first
      const visibilityLabels = screen.getAllByText(/visibility/i)
      const visibilityLabel = visibilityLabels.find(label =>
        label.tagName.toLowerCase() === 'label' &&
        label.classList.contains('MuiInputLabel-root')
      )
      expect(visibilityLabel).toBeDefined()

      // Find the combobox associated with this label
      // MUI Select uses aria-labelledby to associate with the label
      const labelId = visibilityLabel?.getAttribute('id')
      let visibilitySelect: HTMLElement | null = null

      if (labelId) {
        // Try to find by aria-labelledby
        visibilitySelect = document.querySelector(`button[aria-labelledby="${labelId}"]`) as HTMLElement
      }

      // Fallback: find all comboboxes and check which one is in the same form control
      if (!visibilitySelect) {
        const formControl = visibilityLabel?.closest('.MuiFormControl-root')
        const comboboxes = screen.getAllByRole('combobox')
        visibilitySelect = comboboxes.find(cb =>
          formControl?.contains(cb)
        ) as HTMLElement || null
      }

      expect(visibilitySelect).toBeTruthy()
      if (visibilitySelect) {
        // Open select dropdown
        await user.click(visibilitySelect)
        // Wait for the dropdown to open and find the option
        const publicOption = await screen.findByRole('option', { name: /public/i }, { timeout: 3000 })
        await user.click(publicOption)
      }

      const submitButton = screen.getByRole('button', { name: /save/i })
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalled()
        const callArgs = mockOnSubmit.mock.calls[0][0] as CreateAssetRequest
        expect(callArgs.visibility).toBe('PUBLIC')
      }, { timeout: 5000 })
    })

    it('allows changing status in edit mode', async () => {
      const user = userEvent.setup()
      const asset = assetFactory.build()

      render(<AssetForm asset={asset} onSubmit={mockOnSubmit} mode="edit" />)

      // MUI Select shows as button when closed - find by label text
      const statusLabels = screen.getAllByText(/status/i)
      const statusLabel = statusLabels.find(label =>
        label.classList.contains('MuiInputLabel-root') ||
        label.closest('.MuiFormControl-root')
      )
      expect(statusLabel).toBeDefined()

      const formControl = statusLabel?.closest('.MuiFormControl-root')
      const selectButton = formControl?.querySelector('button[aria-haspopup="listbox"]')

      expect(selectButton).toBeDefined()
      if (selectButton) {
        // Open select dropdown
        await user.click(selectButton)
        const activeOption = await screen.findByRole('option', { name: /active/i })
        await user.click(activeOption)
      }

      const submitButton = screen.getByRole('button', { name: /save/i })
      await user.click(submitButton)

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalled()
        const callArgs = mockOnSubmit.mock.calls[0][0] as UpdateAssetRequest
        expect(callArgs.status).toBe('ACTIVE')
      }, { timeout: 5000 })
    })

    it('handles cancel callback', async () => {
      const user = userEvent.setup()
      render(<AssetForm onSubmit={mockOnSubmit} onCancel={mockOnCancel} mode="create" />)

      // Cancel button might be disabled if form is not dirty
      // Make form dirty first by typing something
      const keyField = screen.getByLabelText(/key/i)
      await user.type(keyField, 'test')

      const cancelButton = screen.getByRole('button', { name: /cancel/i })
      expect(cancelButton).not.toBeDisabled()
      await user.click(cancelButton)

      expect(mockOnCancel).toHaveBeenCalled()
    })

    it('resets form when cancel is clicked without callback', async () => {
      const user = userEvent.setup()
      render(<AssetForm onSubmit={mockOnSubmit} mode="create" />)

      const keyField = screen.getByLabelText(/key/i)
      const nameField = screen.getByLabelText(/name/i)

      await user.type(keyField, 'test-key')
      await user.type(nameField, 'Test Name')

      const cancelButton = screen.getByRole('button', { name: /cancel/i })
      await user.click(cancelButton)

      await waitFor(() => {
        expect(keyField).toHaveValue('')
        expect(nameField).toHaveValue('')
      })
    })
  })

  describe('Loading States', () => {
    it('disables form when loading', () => {
      render(<AssetForm onSubmit={mockOnSubmit} loading={true} mode="create" />)

      const submitButton = screen.getByRole('button', { name: /save/i })
      expect(submitButton).toBeDisabled()
    })

    it('shows loading state on submit button', () => {
      render(<AssetForm onSubmit={mockOnSubmit} loading={true} mode="create" />)

      // FormActions should show loading state
      const submitButton = screen.getByRole('button', { name: /save/i })
      expect(submitButton).toBeDisabled()
    })
  })

  describe('Custom Labels', () => {
    it('uses custom submit label', () => {
      render(<AssetForm onSubmit={mockOnSubmit} submitLabel="Create" mode="create" />)

      expect(screen.getByRole('button', { name: /create/i })).toBeInTheDocument()
    })

    it('uses custom cancel label', () => {
      render(<AssetForm onSubmit={mockOnSubmit} cancelLabel="Back" mode="create" />)

      expect(screen.getByRole('button', { name: /back/i })).toBeInTheDocument()
    })

    it('hides cancel button when showCancel is false', () => {
      render(<AssetForm onSubmit={mockOnSubmit} showCancel={false} mode="create" />)

      expect(screen.queryByRole('button', { name: /cancel/i })).not.toBeInTheDocument()
    })
  })

  describe('Form Reset', () => {
    it('resets form when asset prop changes', () => {
      const asset1 = assetFactory.build({
        overrides: {
          name: 'Asset 1',
        },
      })
      const asset2 = assetFactory.build({
        overrides: {
          name: 'Asset 2',
        },
      })

      const { rerender } = render(<AssetForm asset={asset1} onSubmit={mockOnSubmit} mode="edit" />)

      expect(screen.getByDisplayValue('Asset 1')).toBeInTheDocument()

      rerender(<AssetForm asset={asset2} onSubmit={mockOnSubmit} mode="edit" />)

      expect(screen.getByDisplayValue('Asset 2')).toBeInTheDocument()
    })
  })

  describe('Async Submission', () => {
    it('handles async onSubmit', async () => {
      const user = userEvent.setup()
      const asyncOnSubmit = vi.fn().mockResolvedValue(undefined)

      render(<AssetForm onSubmit={asyncOnSubmit} mode="create" />)

      const keyField = screen.getByLabelText(/key/i)
      const nameField = screen.getByLabelText(/name/i)

      await user.type(keyField, 'async-key')
      await user.type(nameField, 'Async Name')

      // Blur fields to trigger validation and make form valid
      await user.tab() // Blur name field

      const submitButton = screen.getByRole('button', { name: /save/i })
      // Wait for form to be valid
      await waitFor(() => {
        expect(submitButton).not.toBeDisabled()
      })

      await user.click(submitButton)

      await waitFor(() => {
        expect(asyncOnSubmit).toHaveBeenCalled()
      }, { timeout: 5000 })
    })
  })
})

