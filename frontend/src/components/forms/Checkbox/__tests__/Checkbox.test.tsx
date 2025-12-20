/**
 * Checkbox Component Tests
 *
 * Comprehensive tests for the Checkbox component covering:
 * - Basic rendering
 * - Label display
 * - Checked state
 * - Indeterminate state
 * - Disabled state
 * - Change events
 * - Ref forwarding
 * - Accessibility
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Checkbox } from '../Checkbox'

describe('Checkbox', () => {
  describe('Basic Rendering', () => {
    it('should render checkbox input', () => {
      render(<Checkbox />)
      const checkbox = screen.getByRole('checkbox')
      expect(checkbox).toBeInTheDocument()
      expect(checkbox.tagName).toBe('INPUT')
      expect((checkbox as HTMLInputElement).type).toBe('checkbox')
    })

    it('should render with default props', () => {
      render(<Checkbox />)
      const checkbox = screen.getByRole('checkbox') as HTMLInputElement
      expect(checkbox.checked).toBe(false)
      expect(checkbox.disabled).toBe(false)
    })

    it('should apply custom className', () => {
      const { container } = render(<Checkbox className="custom-class" />)
      const wrapper = container.querySelector('.checkbox')
      expect(wrapper).toHaveClass('custom-class')
    })
  })

  describe('Label', () => {
    it('should render label when provided', () => {
      render(<Checkbox label="Test Label" />)
      expect(screen.getByText('Test Label')).toBeInTheDocument()
    })

    it('should not render label when not provided', () => {
      render(<Checkbox />)
      const labels = screen.queryAllByRole('label')
      expect(labels).toHaveLength(0)
    })

    it('should associate label with checkbox using htmlFor', () => {
      render(<Checkbox label="Test Label" id="test-checkbox" />)
      const label = screen.getByText('Test Label')
      const checkbox = screen.getByRole('checkbox')
      expect(label.getAttribute('for')).toBe('test-checkbox')
      expect(checkbox.id).toBe('test-checkbox')
    })

    it('should generate unique id when id is not provided', () => {
      render(<Checkbox label="Test" />)
      const checkbox = screen.getByRole('checkbox')
      const label = screen.getByText('Test')
      const checkboxId = checkbox.id
      expect(checkboxId).toBeTruthy()
      expect(label.getAttribute('for')).toBe(checkboxId)
    })
  })

  describe('Checked State', () => {
    it('should be unchecked by default', () => {
      render(<Checkbox />)
      const checkbox = screen.getByRole('checkbox') as HTMLInputElement
      expect(checkbox.checked).toBe(false)
    })

    it('should be checked when checked prop is true', () => {
      render(<Checkbox checked />)
      const checkbox = screen.getByRole('checkbox') as HTMLInputElement
      expect(checkbox.checked).toBe(true)
    })

    it('should update checked state when prop changes', () => {
      const { rerender } = render(<Checkbox checked={false} />)
      const checkbox = screen.getByRole('checkbox') as HTMLInputElement
      expect(checkbox.checked).toBe(false)

      rerender(<Checkbox checked={true} />)
      expect(checkbox.checked).toBe(true)
    })
  })

  describe('Indeterminate State', () => {
    it('should set indeterminate state on input element', () => {
      render(<Checkbox indeterminate />)
      const checkbox = screen.getByRole('checkbox') as HTMLInputElement
      expect(checkbox.indeterminate).toBe(true)
    })

    it('should update indeterminate state when prop changes', () => {
      const { rerender } = render(<Checkbox indeterminate={false} />)
      const checkbox = screen.getByRole('checkbox') as HTMLInputElement
      expect(checkbox.indeterminate).toBe(false)

      rerender(<Checkbox indeterminate={true} />)
      expect(checkbox.indeterminate).toBe(true)
    })
  })

  describe('Change Events', () => {
    it('should call onChange when checkbox is clicked', async () => {
      const user = userEvent.setup()
      const handleChange = vi.fn()
      render(<Checkbox onChange={handleChange} />)
      const checkbox = screen.getByRole('checkbox')
      await user.click(checkbox)
      expect(handleChange).toHaveBeenCalledTimes(1)
      expect(handleChange.mock.calls[0][0]).toBe(true)
    })

    it('should pass checked value to onChange', async () => {
      const user = userEvent.setup()
      const handleChange = vi.fn()
      render(<Checkbox checked onChange={handleChange} />)
      const checkbox = screen.getByRole('checkbox')
      await user.click(checkbox)
      expect(handleChange).toHaveBeenCalledWith(false)
    })

    it('should not call onChange when disabled', async () => {
      const user = userEvent.setup()
      const handleChange = vi.fn()
      render(<Checkbox disabled onChange={handleChange} />)
      const checkbox = screen.getByRole('checkbox')
      await user.click(checkbox)
      expect(handleChange).not.toHaveBeenCalled()
    })
  })

  describe('Disabled State', () => {
    it('should disable checkbox when disabled is true', () => {
      render(<Checkbox disabled />)
      const checkbox = screen.getByRole('checkbox') as HTMLInputElement
      expect(checkbox.disabled).toBe(true)
    })

    it('should apply disabled styling to label', () => {
      const { container } = render(<Checkbox label="Test" disabled />)
      const label = container.querySelector('label')
      expect(label).toBeInTheDocument()
      // Label should have disabled cursor styling
      expect(label?.style.cursor).toBe('not-allowed')
    })

    it('should not allow interaction when disabled', async () => {
      const user = userEvent.setup()
      const handleChange = vi.fn()
      render(<Checkbox disabled onChange={handleChange} />)
      const checkbox = screen.getByRole('checkbox')
      await user.click(checkbox)
      expect(handleChange).not.toHaveBeenCalled()
    })
  })

  describe('Ref Forwarding', () => {
    it('should forward ref to input element', () => {
      const ref = vi.fn()
      render(<Checkbox ref={ref} />)
      expect(ref).toHaveBeenCalled()
      expect(ref.mock.calls[0][0]).toBeInstanceOf(HTMLInputElement)
    })
  })

  describe('Accessibility', () => {
    it('should have proper label association', () => {
      render(<Checkbox label="Test Checkbox" />)
      const checkbox = screen.getByRole('checkbox')
      const label = screen.getByText('Test Checkbox')
      expect(label.getAttribute('for')).toBe(checkbox.id)
    })

    it('should be keyboard accessible', async () => {
      const user = userEvent.setup()
      const handleChange = vi.fn()
      render(<Checkbox onChange={handleChange} />)
      const checkbox = screen.getByRole('checkbox')
      checkbox.focus()
      await user.keyboard(' ')
      expect(handleChange).toHaveBeenCalled()
    })
  })

  describe('HTML Attributes', () => {
    it('should pass through HTML input attributes', () => {
      render(<Checkbox name="test-checkbox" value="test" />)
      const checkbox = screen.getByRole('checkbox') as HTMLInputElement
      expect(checkbox.name).toBe('test-checkbox')
      expect(checkbox.value).toBe('test')
    })

    it('should handle custom styles', () => {
      render(<Checkbox style={{ margin: '10px' }} />)
      const checkbox = screen.getByRole('checkbox') as HTMLInputElement
      expect(checkbox.style.margin).toBe('10px')
    })
  })
})

