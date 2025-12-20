/**
 * Chip Component Tests
 *
 * Comprehensive tests for the Chip component covering:
 * - Basic rendering
 * - Removable functionality
 * - Clickable functionality
 * - Color variants
 * - Hover effects
 * - Accessibility
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Chip } from '../Chip'

describe('Chip', () => {
  describe('Basic Rendering', () => {
    it('should render label', () => {
      render(<Chip label="Test Chip" />)
      expect(screen.getByText('Test Chip')).toBeInTheDocument()
    })

    it('should apply custom className', () => {
      const { container } = render(<Chip label="Test" className="custom-class" />)
      const chip = container.querySelector('.chip')
      expect(chip).toHaveClass('custom-class')
    })
  })

  describe('Removable Functionality', () => {
    it('should not show remove button by default', () => {
      render(<Chip label="Test" />)
      expect(screen.queryByLabelText(/remove/i)).not.toBeInTheDocument()
    })

    it('should show remove button when removable is true', () => {
      render(<Chip label="Test" removable />)
      expect(screen.getByLabelText('Remove Test')).toBeInTheDocument()
    })

    it('should call onRemove when remove button is clicked', async () => {
      const user = userEvent.setup()
      const handleRemove = vi.fn()
      render(<Chip label="Test" removable onRemove={handleRemove} />)
      const removeButton = screen.getByLabelText('Remove Test')
      await user.click(removeButton)
      expect(handleRemove).toHaveBeenCalledTimes(1)
    })

    it('should not call onRemove if not provided', async () => {
      const user = userEvent.setup()
      render(<Chip label="Test" removable />)
      const removeButton = screen.getByLabelText('Remove Test')
      await user.click(removeButton)
      // Should not throw error
      expect(removeButton).toBeInTheDocument()
    })
  })

  describe('Clickable Functionality', () => {
    it('should not be clickable by default', () => {
      render(<Chip label="Test" />)
      const chip = screen.getByText('Test').parentElement
      expect(chip?.style.cursor).not.toBe('pointer')
    })

    it('should be clickable when clickable is true', () => {
      const { container } = render(<Chip label="Test" clickable />)
      const chip = container.querySelector('.chip') as HTMLElement
      expect(chip.style.cursor).toBe('pointer')
    })

    it('should call onClick when clicked and clickable is true', async () => {
      const user = userEvent.setup()
      const handleClick = vi.fn()
      const { container } = render(<Chip label="Test" clickable onClick={handleClick} />)
      // The chip is the span element itself, find it by class or by text's parent
      const chip = container.querySelector('.chip') as HTMLElement
      expect(chip).toBeTruthy()
      await user.click(chip)
      expect(handleClick).toHaveBeenCalledTimes(1)
    })

    it('should not call onClick when clickable is false', async () => {
      const user = userEvent.setup()
      const handleClick = vi.fn()
      render(<Chip label="Test" onClick={handleClick} />)
      const chip = screen.getByText('Test').parentElement
      if (chip) {
        await user.click(chip)
        expect(handleClick).not.toHaveBeenCalled()
      }
    })
  })

  describe('Color Variants', () => {
    it('should apply default color by default', () => {
      const { container } = render(<Chip label="Test" />)
      const chip = container.querySelector('.chip')
      expect(chip).toHaveClass('chip-default')
    })

    it('should apply primary color', () => {
      const { container } = render(<Chip label="Test" color="primary" />)
      const chip = container.querySelector('.chip')
      expect(chip).toHaveClass('chip-primary')
    })

    it('should apply success color', () => {
      const { container } = render(<Chip label="Test" color="success" />)
      const chip = container.querySelector('.chip')
      expect(chip).toHaveClass('chip-success')
    })

    it('should apply warning color', () => {
      const { container } = render(<Chip label="Test" color="warning" />)
      const chip = container.querySelector('.chip')
      expect(chip).toHaveClass('chip-warning')
    })

    it('should apply error color', () => {
      const { container } = render(<Chip label="Test" color="error" />)
      const chip = container.querySelector('.chip')
      expect(chip).toHaveClass('chip-error')
    })
  })

  describe('Hover Effects', () => {
    it('should change background on hover when clickable', async () => {
      const user = userEvent.setup()
      const { container } = render(<Chip label="Test" clickable />)
      const chip = container.querySelector('.chip') as HTMLElement
      const initialBg = chip.style.background

      await user.hover(chip)
      // Background should change on hover
      expect(chip.style.background).not.toBe(initialBg)

      await user.unhover(chip)
      // Background should return to initial
      expect(chip.style.background).toBe(initialBg)
    })

    it('should change background on hover when removable', async () => {
      const user = userEvent.setup()
      const { container } = render(<Chip label="Test" removable />)
      const chip = container.querySelector('.chip') as HTMLElement
      const initialBg = chip.style.background

      await user.hover(chip)
      expect(chip.style.background).not.toBe(initialBg)
    })

    it('should not change background on hover when not clickable or removable', async () => {
      const user = userEvent.setup()
      const { container } = render(<Chip label="Test" />)
      const chip = container.querySelector('.chip') as HTMLElement
      const initialBg = chip.style.background

      await user.hover(chip)
      // Background should not change
      expect(chip.style.background).toBe(initialBg)
    })
  })

  describe('Event Handling', () => {
    it('should stop propagation when remove button is clicked', async () => {
      const user = userEvent.setup()
      const handleChipClick = vi.fn()
      const handleRemove = vi.fn()
      render(
        <Chip
          label="Test"
          clickable
          removable
          onClick={handleChipClick}
          onRemove={handleRemove}
        />
      )
      const removeButton = screen.getByLabelText('Remove Test')
      await user.click(removeButton)
      expect(handleRemove).toHaveBeenCalled()
      expect(handleChipClick).not.toHaveBeenCalled()
    })
  })
})

