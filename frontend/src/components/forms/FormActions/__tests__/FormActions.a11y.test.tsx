/**
 * FormActions Accessibility Tests
 *
 * Comprehensive accessibility tests for the FormActions component.
 * Uses vitest-axe to check for WCAG 2.1 Level AA compliance.
 */

import { describe, it } from 'vitest'
import { renderWithProviders, checkAccessibility } from '@/test-utils'
import { FormActions } from '../FormActions'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'

// Test form schema
const testSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  email: z.string().email('Invalid email'),
})

type TestFormData = z.infer<typeof testSchema>

// Test component wrapper
function TestFormActions() {
  const form = useForm<TestFormData>({
    resolver: zodResolver(testSchema),
    defaultValues: {
      name: '',
      email: '',
    },
  })

  return (
    <FormActions
      form={form}
      submitLabel="Submit"
      resetLabel="Reset"
      onSubmit={async () => {
        // Mock submit
      }}
    />
  )
}

describe('FormActions Accessibility', () => {
  it('has no accessibility violations', async () => {
    const { container } = renderWithProviders(<TestFormActions />)
    await checkAccessibility(container)
  })

  it('has accessible button labels', async () => {
    const { container } = renderWithProviders(<TestFormActions />)

    // Check that buttons have accessible names
    const submitButton = container.querySelector('button[type="submit"]')
    const resetButton = container.querySelector('button[type="button"]')

    expect(submitButton).toBeInTheDocument()
    expect(resetButton).toBeInTheDocument()

    // Check that buttons have text content or aria-label
    expect(submitButton?.textContent || submitButton?.getAttribute('aria-label')).toBeTruthy()
    expect(resetButton?.textContent || resetButton?.getAttribute('aria-label')).toBeTruthy()
  })

  it('is keyboard navigable', async () => {
    const { container } = renderWithProviders(<TestFormActions />)

    const buttons = container.querySelectorAll('button')
    buttons.forEach((button) => {
      expect(button).toBeVisible()
      // Buttons should be focusable
      expect(button.tabIndex).toBeGreaterThanOrEqual(0)
    })
  })
})

