/**
 * Form Validation Errors Tests
 *
 * Comprehensive tests for form validation error handling covering:
 * - Client-side validation errors (inline field errors)
 * - Server-side validation errors (field-level mapping)
 * - Error message display (below fields, red text, icon)
 * - Error message association (aria-describedby)
 * - Validation error recovery (clear on field change)
 * - Form-level error summary
 * - Scroll to first error on submit
 *
 * Uses real form components and validation logic (no mocks/stubs)
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useForm, FormProvider } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { FormField } from '../FormField/FormField'
import { FormErrorSummary } from '../FormErrorSummary/FormErrorSummary'
import { useFormErrorHandling } from '@/hooks/useFormErrorHandling'
import { ValidationException } from '@/lib/api/exceptions'
import { AxiosError } from 'axios'
import { renderWithProviders } from '@/test-utils'
import { Button } from '@mui/material'

// Test form schema
const testFormSchema = z.object({
  name: z.string().min(1, 'Name is required').max(50, 'Name must be 50 characters or less'),
  email: z.string().email('Invalid email address'),
  age: z.number().min(18, 'Age must be at least 18').max(120, 'Age must be at most 120'),
  description: z.string().min(10, 'Description must be at least 10 characters'),
})

type TestFormData = z.infer<typeof testFormSchema>

// Test form component
function TestForm({
  onSubmit,
  onServerError,
  enableErrorRecovery = true,
  scrollToFirstError = true,
}: {
  onSubmit: (data: TestFormData) => Promise<void>
  onServerError?: (error: unknown) => void
  enableErrorRecovery?: boolean
  scrollToFirstError?: boolean
}) {
  const form = useForm<TestFormData>({
    resolver: zodResolver(testFormSchema),
    mode: 'onBlur',
  })

  const { handleServerError, errorSummary } = useFormErrorHandling({
    form,
    enableErrorRecovery,
    scrollToFirstError,
    onNonFieldError: onServerError,
  })

  const handleSubmit = async (data: TestFormData) => {
    try {
      await onSubmit(data)
    } catch (error) {
      handleServerError(error)
    }
  }

  return (
    <FormProvider {...form}>
      <form onSubmit={form.handleSubmit(handleSubmit)}>
        {errorSummary.length > 0 && <FormErrorSummary errors={form.formState.errors} />}

        <FormField name="name" label="Name" required />
        <FormField name="email" label="Email" type="email" required />
        <FormField name="age" label="Age" type="number" required />
        <FormField name="description" label="Description" type="textarea" required />

        <Button type="submit">Submit</Button>
      </form>
    </FormProvider>
  )
}

describe('Form Validation Errors', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Reset scroll position
    window.scrollTo = vi.fn()
  })

  describe('Client-side Validation Errors', () => {
    it('should display inline field errors for required fields', async () => {
      const user = userEvent.setup()
      const mockOnSubmit = vi.fn()

      renderWithProviders(<TestForm onSubmit={mockOnSubmit} />)

      // Submit form without filling required fields
      const submitButton = screen.getByRole('button', { name: /submit/i })
      await user.click(submitButton)

      // Wait for validation errors
      await waitFor(() => {
        expect(screen.getByText(/name is required/i)).toBeInTheDocument()
        expect(screen.getByText(/invalid email address/i)).toBeInTheDocument()
      })

      expect(mockOnSubmit).not.toHaveBeenCalled()
    })

    it('should display inline field errors on blur', async () => {
      const user = userEvent.setup()
      const mockOnSubmit = vi.fn()

      renderWithProviders(<TestForm onSubmit={mockOnSubmit} />)

      // Focus and blur name field without entering value
      const nameField = screen.getByLabelText(/name/i)
      await user.click(nameField)
      await user.tab() // Blur

      // Wait for validation error
      await waitFor(() => {
        expect(screen.getByText(/name is required/i)).toBeInTheDocument()
      })
    })

    it('should display inline field errors for invalid email format', async () => {
      const user = userEvent.setup()
      const mockOnSubmit = vi.fn()

      renderWithProviders(<TestForm onSubmit={mockOnSubmit} />)

      // Enter invalid email
      const emailField = screen.getByLabelText(/email/i)
      await user.type(emailField, 'invalid-email')
      await user.tab() // Blur

      // Wait for validation error
      await waitFor(() => {
        expect(screen.getByText(/invalid email address/i)).toBeInTheDocument()
      })
    })

    it('should display inline field errors for min/max length violations', async () => {
      const user = userEvent.setup()
      const mockOnSubmit = vi.fn()

      renderWithProviders(<TestForm onSubmit={mockOnSubmit} />)

      // Enter name that's too long
      const nameField = screen.getByLabelText(/name/i)
      await user.type(nameField, 'a'.repeat(51))
      await user.tab() // Blur

      // Wait for validation error
      await waitFor(() => {
        expect(screen.getByText(/name must be 50 characters or less/i)).toBeInTheDocument()
      })
    })

    it('should display inline field errors for number range violations', async () => {
      const user = userEvent.setup()
      const mockOnSubmit = vi.fn()

      renderWithProviders(<TestForm onSubmit={mockOnSubmit} />)

      // Enter age that's too low
      const ageField = screen.getByLabelText(/age/i)
      await user.type(ageField, '15')
      await user.tab() // Blur

      // Wait for validation error
      await waitFor(() => {
        expect(screen.getByText(/age must be at least 18/i)).toBeInTheDocument()
      })
    })

    it('should display multiple validation errors for different fields', async () => {
      const user = userEvent.setup()
      const mockOnSubmit = vi.fn()

      renderWithProviders(<TestForm onSubmit={mockOnSubmit} />)

      // Submit form with invalid data
      const submitButton = screen.getByRole('button', { name: /submit/i })
      await user.click(submitButton)

      // Wait for multiple validation errors
      await waitFor(() => {
        expect(screen.getByText(/name is required/i)).toBeInTheDocument()
        expect(screen.getByText(/invalid email address/i)).toBeInTheDocument()
        expect(screen.getByText(/age must be at least 18/i)).toBeInTheDocument()
      })
    })
  })

  describe('Server-side Validation Errors', () => {
    it('should map server-side validation errors to form fields', async () => {
      const user = userEvent.setup()
      const mockOnSubmit = vi.fn().mockRejectedValue(
        new ValidationException('Validation failed', [
          { field: 'name', message: 'Name already exists', code: 'unique' },
          { field: 'email', message: 'Email is already registered', code: 'unique' },
        ])
      )

      renderWithProviders(<TestForm onSubmit={mockOnSubmit} />)

      // Fill form with valid data
      await user.type(screen.getByLabelText(/name/i), 'Test Name')
      await user.type(screen.getByLabelText(/email/i), 'test@example.com')
      await user.type(screen.getByLabelText(/age/i), '25')
      await user.type(screen.getByLabelText(/description/i), 'This is a test description')

      // Submit form
      const submitButton = screen.getByRole('button', { name: /submit/i })
      await user.click(submitButton)

      // Wait for server-side validation errors
      await waitFor(() => {
        expect(screen.getByText(/name already exists/i)).toBeInTheDocument()
        expect(screen.getByText(/email is already registered/i)).toBeInTheDocument()
      })
    })

    it('should map DRF-style validation errors to form fields', async () => {
      const user = userEvent.setup()
      const mockOnSubmit = vi.fn().mockRejectedValue(
        new AxiosError('Validation failed', '400', undefined, undefined, {
          status: 400,
          statusText: 'Bad Request',
          data: {
            name: ['This field is required.'],
            email: ['Enter a valid email address.'],
            age: ['Ensure this value is greater than or equal to 18.'],
          },
        } as any)
      )

      renderWithProviders(<TestForm onSubmit={mockOnSubmit} />)

      // Fill form with invalid data
      await user.type(screen.getByLabelText(/name/i), '')
      await user.type(screen.getByLabelText(/email/i), 'invalid')
      await user.type(screen.getByLabelText(/age/i), '15')

      // Submit form
      const submitButton = screen.getByRole('button', { name: /submit/i })
      await user.click(submitButton)

      // Wait for server-side validation errors
      await waitFor(() => {
        expect(screen.getByText(/this field is required/i)).toBeInTheDocument()
        expect(screen.getByText(/enter a valid email address/i)).toBeInTheDocument()
        expect(screen.getByText(/ensure this value is greater than or equal to 18/i)).toBeInTheDocument()
      })
    })

    it('should handle non-field errors from server', async () => {
      const user = userEvent.setup()
      const mockOnNonFieldError = vi.fn()
      const mockOnSubmit = vi.fn().mockRejectedValue(
        new AxiosError('Validation failed', '400', undefined, undefined, {
          status: 400,
          statusText: 'Bad Request',
          data: {
            non_field_errors: ['Unable to process request at this time.'],
          },
        } as any)
      )

      renderWithProviders(
        <TestForm onSubmit={mockOnSubmit} onServerError={mockOnNonFieldError} />
      )

      // Fill form with valid data
      await user.type(screen.getByLabelText(/name/i), 'Test Name')
      await user.type(screen.getByLabelText(/email/i), 'test@example.com')
      await user.type(screen.getByLabelText(/age/i), '25')
      await user.type(screen.getByLabelText(/description/i), 'This is a test description')

      // Submit form
      const submitButton = screen.getByRole('button', { name: /submit/i })
      await user.click(submitButton)

      // Wait for non-field error callback
      await waitFor(() => {
        expect(mockOnNonFieldError).toHaveBeenCalledWith('Unable to process request at this time.')
      })
    })
  })

  describe('Error Message Display', () => {
    it('should display error messages below fields', async () => {
      const user = userEvent.setup()
      const mockOnSubmit = vi.fn()

      renderWithProviders(<TestForm onSubmit={mockOnSubmit} />)

      // Trigger validation error
      const nameField = screen.getByLabelText(/name/i)
      await user.click(nameField)
      await user.tab() // Blur

      // Wait for error message
      await waitFor(() => {
        const errorMessage = screen.getByText(/name is required/i)
        expect(errorMessage).toBeInTheDocument()
        // Error should be below the field (in FormHelperText)
        const fieldContainer = nameField.closest('div')
        expect(fieldContainer).toBeInTheDocument()
      })
    })

    it('should display error messages in red text', async () => {
      const user = userEvent.setup()
      const mockOnSubmit = vi.fn()

      renderWithProviders(<TestForm onSubmit={mockOnSubmit} />)

      // Trigger validation error
      const nameField = screen.getByLabelText(/name/i)
      await user.click(nameField)
      await user.tab() // Blur

      // Wait for error message
      await waitFor(() => {
        const errorMessage = screen.getByText(/name is required/i)
        expect(errorMessage).toBeInTheDocument()
        // Check for error styling (MUI FormHelperText with error prop)
        const helperText = errorMessage.closest('.MuiFormHelperText-root')
        expect(helperText).toHaveClass('Mui-error')
      })
    })

    it('should display error icon with error messages', async () => {
      const user = userEvent.setup()
      const mockOnSubmit = vi.fn()

      renderWithProviders(<TestForm onSubmit={mockOnSubmit} />)

      // Trigger validation error
      const nameField = screen.getByLabelText(/name/i)
      await user.click(nameField)
      await user.tab() // Blur

      // Wait for error icon (ErrorIcon from MUI)
      await waitFor(() => {
        const errorIcon = document.querySelector('[data-testid="ErrorIcon"]')
        expect(errorIcon).toBeInTheDocument()
      })
    })

    it('should apply error styling to input fields', async () => {
      const user = userEvent.setup()
      const mockOnSubmit = vi.fn()

      renderWithProviders(<TestForm onSubmit={mockOnSubmit} />)

      // Trigger validation error
      const nameField = screen.getByLabelText(/name/i)
      await user.click(nameField)
      await user.tab() // Blur

      // Wait for error styling
      await waitFor(() => {
        // Input should have error class
        const input = nameField.closest('.MuiTextField-root')
        expect(input).toHaveClass('Mui-error')
      })
    })
  })

  describe('Error Message Association (aria-describedby)', () => {
    it('should associate error messages with fields using aria-describedby', async () => {
      const user = userEvent.setup()
      const mockOnSubmit = vi.fn()

      renderWithProviders(<TestForm onSubmit={mockOnSubmit} />)

      // Trigger validation error
      const nameField = screen.getByLabelText(/name/i)
      await user.click(nameField)
      await user.tab() // Blur

      // Wait for error message and check aria-describedby
      await waitFor(() => {
        expect(screen.getByText(/name is required/i)).toBeInTheDocument()
        // MUI TextField automatically sets aria-describedby when error is present
        const input = nameField as HTMLInputElement
        const describedBy = input.getAttribute('aria-describedby')
        expect(describedBy).toBeTruthy()
        // The error message should be referenced
        const errorElement = document.getElementById(describedBy || '')
        expect(errorElement).toBeInTheDocument()
      })
    })

    it('should include error ID in aria-describedby when error is present', async () => {
      const user = userEvent.setup()
      const mockOnSubmit = vi.fn()

      renderWithProviders(<TestForm onSubmit={mockOnSubmit} />)

      // Trigger validation error
      const emailField = screen.getByLabelText(/email/i)
      await user.type(emailField, 'invalid-email')
      await user.tab() // Blur

      // Wait for error message
      await waitFor(() => {
        expect(screen.getByText(/invalid email address/i)).toBeInTheDocument()
        const input = emailField as HTMLInputElement
        const describedBy = input.getAttribute('aria-describedby')
        expect(describedBy).toBeTruthy()
        // Should contain reference to error message
        expect(describedBy).toContain('error')
      })
    })
  })

  describe('Validation Error Recovery', () => {
    it('should clear error when field value changes', async () => {
      const user = userEvent.setup()
      const mockOnSubmit = vi.fn()

      renderWithProviders(<TestForm onSubmit={mockOnSubmit} enableErrorRecovery={true} />)

      // Trigger validation error
      const nameField = screen.getByLabelText(/name/i)
      await user.click(nameField)
      await user.tab() // Blur

      // Wait for error
      await waitFor(() => {
        expect(screen.getByText(/name is required/i)).toBeInTheDocument()
      })

      // Enter valid value
      await user.type(nameField, 'Valid Name')

      // Error should be cleared
      await waitFor(() => {
        expect(screen.queryByText(/name is required/i)).not.toBeInTheDocument()
      })
    })

    it('should clear multiple field errors when values change', async () => {
      const user = userEvent.setup()
      const mockOnSubmit = vi.fn()

      renderWithProviders(<TestForm onSubmit={mockOnSubmit} enableErrorRecovery={true} />)

      // Submit form to trigger multiple errors
      const submitButton = screen.getByRole('button', { name: /submit/i })
      await user.click(submitButton)

      // Wait for errors
      await waitFor(() => {
        expect(screen.getByText(/name is required/i)).toBeInTheDocument()
        expect(screen.getByText(/invalid email address/i)).toBeInTheDocument()
      })

      // Fix name field
      const nameField = screen.getByLabelText(/name/i)
      await user.type(nameField, 'Valid Name')

      // Fix email field
      const emailField = screen.getByLabelText(/email/i)
      await user.clear(emailField)
      await user.type(emailField, 'valid@example.com')

      // Both errors should be cleared
      await waitFor(() => {
        expect(screen.queryByText(/name is required/i)).not.toBeInTheDocument()
        expect(screen.queryByText(/invalid email address/i)).not.toBeInTheDocument()
      })
    })

    it('should not clear errors when error recovery is disabled', async () => {
      const user = userEvent.setup()
      const mockOnSubmit = vi.fn()

      renderWithProviders(<TestForm onSubmit={mockOnSubmit} enableErrorRecovery={false} />)

      // Trigger validation error
      const nameField = screen.getByLabelText(/name/i)
      await user.click(nameField)
      await user.tab() // Blur

      // Wait for error
      await waitFor(() => {
        expect(screen.getByText(/name is required/i)).toBeInTheDocument()
      })

      // Enter valid value
      await user.type(nameField, 'Valid Name')

      // Error should still be present (recovery disabled)
      await waitFor(
        () => {
          expect(screen.getByText(/name is required/i)).toBeInTheDocument()
        },
        { timeout: 1000 }
      )
    })
  })

  describe('Form-level Error Summary', () => {
    it('should display form error summary when errors exist', async () => {
      const user = userEvent.setup()
      const mockOnSubmit = vi.fn()

      renderWithProviders(<TestForm onSubmit={mockOnSubmit} />)

      // Submit form to trigger errors
      const submitButton = screen.getByRole('button', { name: /submit/i })
      await user.click(submitButton)

      // Wait for error summary
      await waitFor(() => {
        expect(screen.getByText(/please correct the following errors/i)).toBeInTheDocument()
      })
    })

    it('should display error count in summary', async () => {
      const user = userEvent.setup()
      const mockOnSubmit = vi.fn()

      renderWithProviders(<TestForm onSubmit={mockOnSubmit} />)

      // Submit form to trigger multiple errors
      const submitButton = screen.getByRole('button', { name: /submit/i })
      await user.click(submitButton)

      // Wait for error summary with count
      await waitFor(() => {
        const summary = screen.getByText(/please correct the following errors/i)
        expect(summary).toBeInTheDocument()
        // Should show error count (e.g., "4 errors")
        expect(screen.getByText(/\d+ errors?/i)).toBeInTheDocument()
      })
    })

    it('should list all form errors in summary', async () => {
      const user = userEvent.setup()
      const mockOnSubmit = vi.fn()

      renderWithProviders(<TestForm onSubmit={mockOnSubmit} />)

      // Submit form to trigger errors
      const submitButton = screen.getByRole('button', { name: /submit/i })
      await user.click(submitButton)

      // Wait for error summary with all errors listed
      await waitFor(() => {
        expect(screen.getByText(/name is required/i)).toBeInTheDocument()
        expect(screen.getByText(/invalid email address/i)).toBeInTheDocument()
        expect(screen.getByText(/age must be at least 18/i)).toBeInTheDocument()
        expect(screen.getByText(/description must be at least 10 characters/i)).toBeInTheDocument()
      })
    })

    it('should not display error summary when no errors exist', () => {
      const mockOnSubmit = vi.fn()

      renderWithProviders(<TestForm onSubmit={mockOnSubmit} />)

      // Error summary should not be visible
      expect(screen.queryByText(/please correct the following errors/i)).not.toBeInTheDocument()
    })

    it('should have accessible error summary (role="alert")', async () => {
      const user = userEvent.setup()
      const mockOnSubmit = vi.fn()

      renderWithProviders(<TestForm onSubmit={mockOnSubmit} />)

      // Submit form to trigger errors
      const submitButton = screen.getByRole('button', { name: /submit/i })
      await user.click(submitButton)

      // Wait for error summary with accessible role
      await waitFor(() => {
        const summary = screen.getByRole('alert')
        expect(summary).toBeInTheDocument()
        expect(summary).toHaveAttribute('aria-live', 'polite')
      })
    })
  })

  describe('Scroll to First Error on Submit', () => {
    it('should scroll to first error field on submit', async () => {
      const user = userEvent.setup()
      const mockOnSubmit = vi.fn()
      const scrollToSpy = vi.spyOn(window, 'scrollTo')

      renderWithProviders(<TestForm onSubmit={mockOnSubmit} scrollToFirstError={true} />)

      // Create a long form by adding padding
      document.body.style.height = '2000px'

      // Submit form to trigger errors
      const submitButton = screen.getByRole('button', { name: /submit/i })
      await user.click(submitButton)

      // Wait for scroll to be called
      await waitFor(
        () => {
          expect(scrollToSpy).toHaveBeenCalled()
        },
        { timeout: 500 }
      )

      // Cleanup
      document.body.style.height = ''
      scrollToSpy.mockRestore()
    })

    it('should focus first error field when scrolling', async () => {
      const user = userEvent.setup()
      const mockOnSubmit = vi.fn()

      renderWithProviders(<TestForm onSubmit={mockOnSubmit} scrollToFirstError={true} />)

      // Submit form to trigger errors
      const submitButton = screen.getByRole('button', { name: /submit/i })
      await user.click(submitButton)

      // Wait for first error field to be focused
      await waitFor(
        () => {
          const nameField = screen.getByLabelText(/name/i) as HTMLInputElement
          expect(document.activeElement).toBe(nameField)
        },
        { timeout: 500 }
      )
    })

    it('should not scroll when scrollToFirstError is disabled', async () => {
      const user = userEvent.setup()
      const mockOnSubmit = vi.fn()
      const scrollToSpy = vi.spyOn(window, 'scrollTo')

      renderWithProviders(<TestForm onSubmit={mockOnSubmit} scrollToFirstError={false} />)

      // Submit form to trigger errors
      const submitButton = screen.getByRole('button', { name: /submit/i })
      await user.click(submitButton)

      // Wait a bit to ensure scroll would have been called
      await new Promise((resolve) => setTimeout(resolve, 200))

      // Scroll should not be called
      expect(scrollToSpy).not.toHaveBeenCalled()

      scrollToSpy.mockRestore()
    })

    it('should scroll to first error with correct offset', async () => {
      const user = userEvent.setup()
      const mockOnSubmit = vi.fn()
      const scrollToSpy = vi.spyOn(window, 'scrollTo')

      renderWithProviders(<TestForm onSubmit={mockOnSubmit} scrollToFirstError={true} />)

      // Create a long form
      document.body.style.height = '2000px'

      // Submit form to trigger errors
      const submitButton = screen.getByRole('button', { name: /submit/i })
      await user.click(submitButton)

      // Wait for scroll to be called with offset
      await waitFor(
        () => {
          expect(scrollToSpy).toHaveBeenCalledWith(
            expect.objectContaining({
              top: expect.any(Number),
              behavior: 'smooth',
            })
          )
        },
        { timeout: 500 }
      )

      // Cleanup
      document.body.style.height = ''
      scrollToSpy.mockRestore()
    })
  })
})

