/**
 * TextInput Component Tests
 *
 * Comprehensive tests for the TextInput component covering:
 * - Basic rendering
 * - Label display
 * - Value handling
 * - Error states
 * - Helper text
 * - Required field indicator
 * - Disabled state
 * - Focus and blur events
 * - Accessibility
 * - Ref forwarding
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TextInput } from '../TextInput'

describe('TextInput', () => {
  describe('Basic Rendering', () => {
    it('should render input element', () => {
      render(<TextInput />)
      const input = screen.getByRole('textbox')
      expect(input).toBeInTheDocument()
      expect(input.tagName).toBe('INPUT')
    })

    it('should render with default props', () => {
      render(<TextInput />)
      const input = screen.getByRole('textbox') as HTMLInputElement
      expect(input.type).toBe('text')
      expect(input.disabled).toBe(false)
      expect(input.required).toBe(false)
    })

    it('should apply custom className', () => {
      const { container } = render(<TextInput className="custom-class" />)
      const wrapper = container.querySelector('.text-input')
      expect(wrapper).toHaveClass('custom-class')
    })
  })

  describe('Label', () => {
    it('should render label when provided', () => {
      render(<TextInput label="Test Label" />)
      expect(screen.getByText('Test Label')).toBeInTheDocument()
    })

    it('should not render label when not provided', () => {
      render(<TextInput />)
      const labels = screen.queryAllByRole('label')
      expect(labels).toHaveLength(0)
    })

    it('should associate label with input using htmlFor', () => {
      render(<TextInput label="Test Label" id="test-input" />)
      const label = screen.getByText('Test Label')
      const input = screen.getByRole('textbox')
      expect(label.getAttribute('for')).toBe('test-input')
      expect(input.id).toBe('test-input')
    })
  })

  describe('Value Handling', () => {
    it('should render with initial value', () => {
      render(<TextInput defaultValue="Initial Value" />)
      const input = screen.getByRole('textbox') as HTMLInputElement
      expect(input.value).toBe('Initial Value')
    })

    it('should call onChange when value changes', async () => {
      const user = userEvent.setup()
      const handleChange = vi.fn()
      render(<TextInput onChange={handleChange} />)
      const input = screen.getByRole('textbox')
      await user.type(input, 'test')
      expect(handleChange).toHaveBeenCalled()
      expect(handleChange.mock.calls[0][0]).toBe('t')
    })

    it('should update value on controlled input', async () => {
      const user = userEvent.setup()
      const { rerender } = render(<TextInput value="initial" onChange={vi.fn()} />)
      const input = screen.getByRole('textbox') as HTMLInputElement
      expect(input.value).toBe('initial')

      rerender(<TextInput value="updated" onChange={vi.fn()} />)
      expect(input.value).toBe('updated')
    })
  })

  describe('Error States', () => {
    it('should display error message when error is provided', () => {
      render(<TextInput error="This field is required" />)
      expect(screen.getByText('This field is required')).toBeInTheDocument()
    })

    it('should not display error when error is null', () => {
      render(<TextInput error={null} />)
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    })

    it('should apply error styling to input', () => {
      render(<TextInput error="Error message" />)
      const input = screen.getByRole('textbox')
      expect(input.getAttribute('aria-invalid')).toBe('true')
    })

    it('should apply error styling to label', () => {
      const { container } = render(<TextInput label="Test" error="Error" />)
      const label = container.querySelector('label')
      expect(label).toBeInTheDocument()
      // Label should have error color styling
      expect(label?.style.color).toBeTruthy()
    })
  })

  describe('Helper Text', () => {
    it('should display helper text when provided', () => {
      render(<TextInput helperText="This is helper text" />)
      expect(screen.getByText('This is helper text')).toBeInTheDocument()
    })

    it('should not display helper text when error is present', () => {
      render(<TextInput helperText="Helper" error="Error" />)
      expect(screen.queryByText('Helper')).not.toBeInTheDocument()
      expect(screen.getByText('Error')).toBeInTheDocument()
    })

    it('should associate helper text with input using aria-describedby', () => {
      render(<TextInput helperText="Helper text" id="test-input" />)
      const input = screen.getByRole('textbox')
      const helperId = input.getAttribute('aria-describedby')
      expect(helperId).toBeTruthy()
      expect(helperId).toContain('helper')
    })
  })

  describe('Required Field', () => {
    it('should display required indicator when required is true', () => {
      render(<TextInput label="Test" required />)
      const requiredIndicator = screen.getByLabelText('required')
      expect(requiredIndicator).toBeInTheDocument()
      expect(requiredIndicator.textContent).toBe('*')
    })

    it('should not display required indicator when required is false', () => {
      render(<TextInput label="Test" required={false} />)
      expect(screen.queryByLabelText('required')).not.toBeInTheDocument()
    })

    it('should set required attribute on input', () => {
      render(<TextInput required />)
      const input = screen.getByRole('textbox')
      expect(input).toHaveAttribute('required')
    })
  })

  describe('Disabled State', () => {
    it('should disable input when disabled is true', () => {
      render(<TextInput disabled />)
      const input = screen.getByRole('textbox') as HTMLInputElement
      expect(input.disabled).toBe(true)
    })

    it('should apply disabled styling', () => {
      render(<TextInput disabled label="Test" />)
      const input = screen.getByRole('textbox')
      expect(input).toHaveAttribute('disabled')
    })

    it('should not allow input when disabled', async () => {
      const user = userEvent.setup()
      const handleChange = vi.fn()
      render(<TextInput disabled onChange={handleChange} />)
      const input = screen.getByRole('textbox')
      await user.type(input, 'test')
      expect(handleChange).not.toHaveBeenCalled()
    })
  })

  describe('Focus and Blur Events', () => {
    it('should apply focus styling on focus', async () => {
      const user = userEvent.setup()
      render(<TextInput />)
      const input = screen.getByRole('textbox') as HTMLInputElement
      await user.click(input)
      // Focus should apply border color and box shadow
      expect(input.style.borderColor).toBeTruthy()
    })

    it('should apply blur styling on blur', async () => {
      const user = userEvent.setup()
      render(<TextInput />)
      const input = screen.getByRole('textbox') as HTMLInputElement
      await user.click(input)
      await user.tab()
      // Blur should reset border color
      expect(input.style.boxShadow).toBe('none')
    })

    it('should handle onFocus event', async () => {
      const user = userEvent.setup()
      const handleFocus = vi.fn()
      render(<TextInput onFocus={handleFocus} />)
      const input = screen.getByRole('textbox') as HTMLInputElement
      // Focus the input - this should trigger onFocus
      input.focus()
      // Wait for focus event
      await waitFor(() => {
        expect(handleFocus).toHaveBeenCalled()
      }, { timeout: 2000 })
    })

    it('should handle onBlur event', async () => {
      const user = userEvent.setup()
      const handleBlur = vi.fn()
      render(<TextInput onBlur={handleBlur} />)
      const input = screen.getByRole('textbox')
      await user.click(input)
      await user.tab()
      expect(handleBlur).toHaveBeenCalled()
    })
  })

  describe('Accessibility', () => {
    it('should set aria-invalid when error is present', () => {
      render(<TextInput error="Error" />)
      const input = screen.getByRole('textbox')
      expect(input.getAttribute('aria-invalid')).toBe('true')
    })

    it('should set aria-invalid to false when no error', () => {
      render(<TextInput />)
      const input = screen.getByRole('textbox')
      expect(input.getAttribute('aria-invalid')).toBe('false')
    })

    it('should set aria-describedby for error', () => {
      render(<TextInput error="Error" id="test-input" />)
      const input = screen.getByRole('textbox')
      const describedBy = input.getAttribute('aria-describedby')
      expect(describedBy).toBeTruthy()
      expect(describedBy).toContain('error')
    })

    it('should set aria-describedby for helper text', () => {
      render(<TextInput helperText="Helper" id="test-input" />)
      const input = screen.getByRole('textbox')
      const describedBy = input.getAttribute('aria-describedby')
      expect(describedBy).toBeTruthy()
      expect(describedBy).toContain('helper')
    })
  })

  describe('Ref Forwarding', () => {
    it('should forward ref to input element', () => {
      const ref = vi.fn()
      render(<TextInput ref={ref} />)
      expect(ref).toHaveBeenCalled()
      expect(ref.mock.calls[0][0]).toBeInstanceOf(HTMLInputElement)
    })
  })

  describe('HTML Attributes', () => {
    it('should pass through HTML input attributes', () => {
      render(<TextInput placeholder="Enter text" maxLength={10} />)
      const input = screen.getByRole('textbox') as HTMLInputElement
      expect(input.placeholder).toBe('Enter text')
      expect(input.maxLength).toBe(10)
    })

    it('should handle different input types', () => {
      render(<TextInput type="email" />)
      const input = screen.getByRole('textbox') as HTMLInputElement
      expect(input.type).toBe('email')
    })
  })
})

