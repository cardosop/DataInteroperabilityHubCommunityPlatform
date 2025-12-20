/**
 * Select Component Tests
 *
 * Comprehensive tests for the Select component covering:
 * - Basic rendering
 * - Label display
 * - Single selection
 * - Multiple selection
 * - Searchable functionality
 * - Error states
 * - Helper text
 * - Disabled state
 * - Click outside to close
 * - Accessibility
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Select } from '../Select'

const mockOptions = [
  { value: 'option1', label: 'Option 1' },
  { value: 'option2', label: 'Option 2' },
  { value: 'option3', label: 'Option 3' },
]

describe('Select', () => {
  describe('Basic Rendering', () => {
    it('should render select button', () => {
      render(<Select options={mockOptions} value={null} onChange={vi.fn()} />)
      const button = screen.getByRole('button')
      expect(button).toBeInTheDocument()
    })

    it('should display placeholder when no value is selected', () => {
      render(
        <Select
          options={mockOptions}
          value={null}
          onChange={vi.fn()}
          placeholder="Select an option"
        />
      )
      expect(screen.getByText('Select an option')).toBeInTheDocument()
    })

    it('should apply custom className', () => {
      const { container } = render(
        <Select
          options={mockOptions}
          value={null}
          onChange={vi.fn()}
          className="custom-class"
        />
      )
      const wrapper = container.querySelector('.select')
      expect(wrapper).toHaveClass('custom-class')
    })
  })

  describe('Label', () => {
    it('should render label when provided', () => {
      render(
        <Select
          label="Test Label"
          options={mockOptions}
          value={null}
          onChange={vi.fn()}
        />
      )
      expect(screen.getByText('Test Label')).toBeInTheDocument()
    })

    it('should not render label when not provided', () => {
      render(<Select options={mockOptions} value={null} onChange={vi.fn()} />)
      const labels = screen.queryAllByRole('label')
      expect(labels).toHaveLength(0)
    })

    it('should associate label with select button', () => {
      render(
        <Select
          label="Test Label"
          options={mockOptions}
          value={null}
          onChange={vi.fn()}
        />
      )
      const label = screen.getByText('Test Label')
      const button = screen.getByRole('button')
      // The component uses useId to generate a unique ID
      // Check that the label's 'for' attribute matches the button's id
      const buttonId = button.id
      expect(buttonId).toBeTruthy()
      expect(label.getAttribute('for')).toBe(buttonId)
    })
  })

  describe('Single Selection', () => {
    it('should display selected option label', () => {
      render(
        <Select
          options={mockOptions}
          value="option1"
          onChange={vi.fn()}
        />
      )
      expect(screen.getByText('Option 1')).toBeInTheDocument()
    })

    it('should call onChange when option is selected', async () => {
      const user = userEvent.setup()
      const handleChange = vi.fn()
      render(
        <Select
          options={mockOptions}
          value={null}
          onChange={handleChange}
        />
      )
      const button = screen.getByRole('button')
      await user.click(button)

      const option = await screen.findByText('Option 1')
      await user.click(option)

      expect(handleChange).toHaveBeenCalledWith('option1')
    })

    it('should close dropdown after selection in single mode', async () => {
      const user = userEvent.setup()
      render(
        <Select
          options={mockOptions}
          value={null}
          onChange={vi.fn()}
        />
      )
      const button = screen.getByRole('button')
      await user.click(button)

      const option = await screen.findByText('Option 1')
      await user.click(option)

      await waitFor(() => {
        expect(screen.queryByText('Option 2')).not.toBeInTheDocument()
      })
    })
  })

  describe('Multiple Selection', () => {
    it('should display count when multiple options are selected', () => {
      render(
        <Select
          options={mockOptions}
          value={['option1', 'option2']}
          onChange={vi.fn()}
          multiple
        />
      )
      expect(screen.getByText('2 selected')).toBeInTheDocument()
    })

    it('should display placeholder when no options are selected in multiple mode', () => {
      render(
        <Select
          options={mockOptions}
          value={[]}
          onChange={vi.fn()}
          multiple
          placeholder="Select options"
        />
      )
      expect(screen.getByText('Select options')).toBeInTheDocument()
    })

    it('should select option in multiple mode', async () => {
      const user = userEvent.setup()
      const handleChange = vi.fn()

      render(
        <Select
          options={mockOptions}
          value={[]}
          onChange={handleChange}
          multiple
        />
      )

      // Open dropdown and select option1
      const button = screen.getByRole('button')
      await user.click(button)
      const option1 = await screen.findByText('Option 1')
      await user.click(option1)

      // Should call onChange with the selected option
      expect(handleChange).toHaveBeenCalledTimes(1)
      expect(handleChange).toHaveBeenCalledWith(['option1'])
    })

    it('should deselect option in multiple mode', async () => {
      const user = userEvent.setup()
      const handleChange = vi.fn()

      // Render with option1 already selected
      render(
        <Select
          options={mockOptions}
          value={['option1']}
          onChange={handleChange}
          multiple
        />
      )

      // Verify button shows selected count
      expect(screen.getByRole('button')).toHaveTextContent('1 selected')

      // Open dropdown
      const button = screen.getByRole('button')
      await user.click(button)

      // Wait for dropdown to open and find the selected option
      const option1 = await waitFor(
        () => {
          const option = screen.getByText('Option 1')
          // Verify dropdown is open by checking for listbox
          const listbox = document.querySelector('[role="listbox"]')
          if (!listbox) {
            throw new Error('Dropdown not open')
          }
          return option
        },
        { timeout: 3000 }
      )

      // Click to deselect
      await user.click(option1)

      // Should call onChange with empty array
      expect(handleChange).toHaveBeenCalledTimes(1)
      expect(handleChange).toHaveBeenCalledWith([])
    })

    it('should show checkboxes in multiple mode', async () => {
      const user = userEvent.setup()
      render(
        <Select
          options={mockOptions}
          value={[]}
          onChange={vi.fn()}
          multiple
        />
      )
      const button = screen.getByRole('button')
      await user.click(button)

      const checkboxes = await screen.findAllByRole('checkbox')
      expect(checkboxes.length).toBeGreaterThan(0)
    })
  })

  describe('Searchable Functionality', () => {
    it('should show search input when searchable is true', async () => {
      const user = userEvent.setup()
      render(
        <Select
          options={mockOptions}
          value={null}
          onChange={vi.fn()}
          searchable
        />
      )
      const button = screen.getByRole('button')
      await user.click(button)

      const searchInput = await screen.findByPlaceholderText('Search...')
      expect(searchInput).toBeInTheDocument()
    })

    it('should filter options based on search term', async () => {
      const user = userEvent.setup()
      render(
        <Select
          options={mockOptions}
          value={null}
          onChange={vi.fn()}
          searchable
        />
      )
      const button = screen.getByRole('button')
      await user.click(button)

      const searchInput = await screen.findByPlaceholderText('Search...')
      await user.type(searchInput, 'Option 1')

      expect(screen.getByText('Option 1')).toBeInTheDocument()
      expect(screen.queryByText('Option 2')).not.toBeInTheDocument()
    })

    it('should display "No options found" when search has no results', async () => {
      const user = userEvent.setup()
      render(
        <Select
          options={mockOptions}
          value={null}
          onChange={vi.fn()}
          searchable
        />
      )
      const button = screen.getByRole('button')
      await user.click(button)

      const searchInput = await screen.findByPlaceholderText('Search...')
      await user.type(searchInput, 'Non-existent')

      expect(screen.getByText('No options found')).toBeInTheDocument()
    })
  })

  describe('Error States', () => {
    it('should display error message when error is provided', () => {
      render(
        <Select
          options={mockOptions}
          value={null}
          onChange={vi.fn()}
          error="This field is required"
        />
      )
      expect(screen.getByText('This field is required')).toBeInTheDocument()
    })

    it('should apply error styling to button', () => {
      const { container } = render(
        <Select
          options={mockOptions}
          value={null}
          onChange={vi.fn()}
          error="Error"
        />
      )
      const button = screen.getByRole('button')
      expect(button.style.borderColor).toBeTruthy()
    })

    it('should apply error styling to label', () => {
      const { container } = render(
        <Select
          label="Test"
          options={mockOptions}
          value={null}
          onChange={vi.fn()}
          error="Error"
        />
      )
      const label = container.querySelector('label')
      expect(label).toBeInTheDocument()
      // Label should have error color styling
      expect(label?.style.color).toBeTruthy()
    })
  })

  describe('Helper Text', () => {
    it('should display helper text when provided', () => {
      render(
        <Select
          options={mockOptions}
          value={null}
          onChange={vi.fn()}
          helperText="This is helper text"
        />
      )
      expect(screen.getByText('This is helper text')).toBeInTheDocument()
    })

    it('should not display helper text when error is present', () => {
      render(
        <Select
          options={mockOptions}
          value={null}
          onChange={vi.fn()}
          helperText="Helper"
          error="Error"
        />
      )
      expect(screen.queryByText('Helper')).not.toBeInTheDocument()
      expect(screen.getByText('Error')).toBeInTheDocument()
    })
  })

  describe('Required Field', () => {
    it('should display required indicator when required is true', () => {
      render(
        <Select
          label="Test"
          options={mockOptions}
          value={null}
          onChange={vi.fn()}
          required
        />
      )
      const requiredIndicator = screen.getByLabelText('required')
      expect(requiredIndicator).toBeInTheDocument()
      expect(requiredIndicator.textContent).toBe('*')
    })
  })

  describe('Disabled State', () => {
    it('should disable button when disabled is true', () => {
      render(
        <Select
          options={mockOptions}
          value={null}
          onChange={vi.fn()}
          disabled
        />
      )
      const button = screen.getByRole('button')
      expect(button).toHaveAttribute('disabled')
    })

    it('should not open dropdown when disabled', async () => {
      const user = userEvent.setup()
      render(
        <Select
          options={mockOptions}
          value={null}
          onChange={vi.fn()}
          disabled
        />
      )
      const button = screen.getByRole('button')
      await user.click(button)

      expect(screen.queryByText('Option 1')).not.toBeInTheDocument()
    })
  })

  describe('Click Outside to Close', () => {
    it('should close dropdown when clicking outside', async () => {
      const user = userEvent.setup()
      render(
        <div>
          <Select
            options={mockOptions}
            value={null}
            onChange={vi.fn()}
          />
          <div data-testid="outside">Outside</div>
        </div>
      )
      const button = screen.getByRole('button')
      await user.click(button)

      expect(await screen.findByText('Option 1')).toBeInTheDocument()

      const outside = screen.getByTestId('outside')
      await user.click(outside)

      await waitFor(() => {
        expect(screen.queryByText('Option 1')).not.toBeInTheDocument()
      })
    })
  })

  describe('Accessibility', () => {
    it('should have proper ARIA attributes', () => {
      render(
        <Select
          options={mockOptions}
          value={null}
          onChange={vi.fn()}
        />
      )
      const button = screen.getByRole('button')
      expect(button.getAttribute('aria-haspopup')).toBe('listbox')
      expect(button.getAttribute('aria-expanded')).toBe('false')
    })

    it('should update aria-expanded when dropdown opens', async () => {
      const user = userEvent.setup()
      render(
        <Select
          options={mockOptions}
          value={null}
          onChange={vi.fn()}
        />
      )
      const button = screen.getByRole('button')
      expect(button.getAttribute('aria-expanded')).toBe('false')

      await user.click(button)
      expect(button.getAttribute('aria-expanded')).toBe('true')
    })

    it('should have proper role for dropdown list', async () => {
      const user = userEvent.setup()
      render(
        <Select
          options={mockOptions}
          value={null}
          onChange={vi.fn()}
        />
      )
      const button = screen.getByRole('button')
      await user.click(button)

      const listbox = await screen.findByRole('listbox')
      expect(listbox).toBeInTheDocument()
    })

    it('should have proper role for options', async () => {
      const user = userEvent.setup()
      render(
        <Select
          options={mockOptions}
          value={null}
          onChange={vi.fn()}
        />
      )
      const button = screen.getByRole('button')
      await user.click(button)

      const options = await screen.findAllByRole('option')
      expect(options.length).toBe(3)
    })
  })

  describe('Disabled Options', () => {
    it('should not allow selection of disabled options', async () => {
      const user = userEvent.setup()
      const handleChange = vi.fn()
      const optionsWithDisabled = [
        { value: 'option1', label: 'Option 1' },
        { value: 'option2', label: 'Option 2', disabled: true },
      ]
      render(
        <Select
          options={optionsWithDisabled}
          value={null}
          onChange={handleChange}
        />
      )
      const button = screen.getByRole('button')
      await user.click(button)

      const option2 = await screen.findByText('Option 2')
      await user.click(option2)

      expect(handleChange).not.toHaveBeenCalled()
    })
  })
})

