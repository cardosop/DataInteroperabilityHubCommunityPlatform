/**
 * FormFieldError Component Tests
 *
 * Comprehensive tests for FormFieldError component covering:
 * - Error message display
 * - Icon display
 * - Accessibility attributes
 * - Field ID association
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { FormFieldError } from '../FormFieldError'

describe('FormFieldError', () => {
  it('should render error message', () => {
    render(<FormFieldError message="This field is required" />)

    expect(screen.getByText('This field is required')).toBeInTheDocument()
  })

  it('should display error icon by default', () => {
    const { container } = render(<FormFieldError message="Error message" />)

    const icon = container.querySelector('svg')
    expect(icon).toBeInTheDocument()
  })

  it('should not display icon when showIcon is false', () => {
    const { container } = render(<FormFieldError message="Error message" showIcon={false} />)

    const icon = container.querySelector('svg')
    expect(icon).not.toBeInTheDocument()
  })

  it('should have correct accessibility attributes', () => {
    render(<FormFieldError message="Error message" />)

    const errorElement = screen.getByRole('alert')
    expect(errorElement).toHaveAttribute('aria-live', 'polite')
  })

  it('should associate error with field ID', () => {
    render(<FormFieldError message="Error message" fieldId="test-field" />)

    const errorElement = screen.getByRole('alert')
    expect(errorElement).toHaveAttribute('id', 'test-field-error')
  })

  it('should apply custom className', () => {
    const { container } = render(
      <FormFieldError message="Error message" className="custom-class" />
    )

    expect(container.firstChild).toHaveClass('custom-class')
  })
})

