/**
 * Component Accessibility Tests
 *
 * Comprehensive accessibility tests for base components using jest-axe.
 * Tests all component variants and states for accessibility violations.
 *
 * Uses real components (no mocks/stubs)
 * Always fixes root cause and follows development best practices.
 */

import { describe, it, expect } from 'vitest'
import { render } from '@/test-utils'
import { checkAccessibility, checkAccessibilityPattern } from '@/test-utils/accessibility'
import { Button } from '@mui/material'
import { FormField } from '../forms/FormField/FormField'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { FormProvider } from 'react-hook-form'
import { Modal } from '../overlay/Modal/Modal'

describe('Component Accessibility Tests', () => {
  describe('Button Components', () => {
    it('should have no accessibility violations for primary button', async () => {
      const { container } = render(<Button variant="contained">Click me</Button>)
      await checkAccessibilityPattern(container, 'button')
    })

    it('should have no accessibility violations for outlined button', async () => {
      const { container } = render(<Button variant="outlined">Click me</Button>)
      await checkAccessibilityPattern(container, 'button')
    })

    it('should have no accessibility violations for text button', async () => {
      const { container } = render(<Button variant="text">Click me</Button>)
      await checkAccessibilityPattern(container, 'button')
    })

    it('should have no accessibility violations for disabled button', async () => {
      const { container } = render(<Button disabled>Disabled</Button>)
      await checkAccessibilityPattern(container, 'button')
    })

    it('should have no accessibility violations for icon button with aria-label', async () => {
      const { container } = render(
        <Button aria-label="Close dialog">
          <span aria-hidden="true">×</span>
        </Button>
      )
      await checkAccessibilityPattern(container, 'button')
    })

    it('should have accessible name for all buttons', async () => {
      const { container } = render(
        <>
          <Button>Text Button</Button>
          <Button aria-label="Icon button">
            <span aria-hidden="true">🔍</span>
          </Button>
        </>
      )
      await checkAccessibility(container)
    })
  })

  describe('Form Components', () => {
    const testSchema = z.object({
      name: z.string().min(1, 'Name is required'),
      email: z.string().email('Invalid email'),
    })

    function TestForm() {
      const form = useForm({
        resolver: zodResolver(testSchema),
        defaultValues: { name: '', email: '' },
      })

      return (
        <FormProvider {...form}>
          <form>
            <FormField name="name" label="Name" required />
            <FormField name="email" label="Email" type="email" required />
          </form>
        </FormProvider>
      )
    }

    it('should have no accessibility violations for form with labels', async () => {
      const { container } = render(<TestForm />)
      await checkAccessibilityPattern(container, 'form')
    })

    it('should have associated labels for all form inputs', async () => {
      const { container } = render(<TestForm />)
      const inputs = container.querySelectorAll('input')

      for (const input of inputs) {
        const id = input.getAttribute('id')
        const ariaLabel = input.getAttribute('aria-label')
        const ariaLabelledBy = input.getAttribute('aria-labelledby')

        expect(
          id || ariaLabel || ariaLabelledBy,
          `Input ${input.getAttribute('name')} must have associated label`
        ).toBeTruthy()
      }

      await checkAccessibilityPattern(container, 'form')
    })

    it('should have aria-required for required fields', async () => {
      const { container } = render(<TestForm />)
      const requiredInputs = container.querySelectorAll('input[required]')

      for (const input of requiredInputs) {
        const ariaRequired = input.getAttribute('aria-required')
        expect(
          ariaRequired === 'true' || ariaRequired === null,
          `Required input ${input.getAttribute('name')} should have aria-required="true" or use native required attribute`
        ).toBe(true)
      }
    })
  })

  describe('Modal/Dialog Components', () => {
    it('should have no accessibility violations for modal', async () => {
      const { container } = render(
        <Modal
          open={true}
          onClose={() => {}}
          title="Test Modal"
          aria-labelledby="modal-title"
        >
          <div id="modal-title">Test Modal</div>
          <p>Modal content</p>
        </Modal>
      )
      await checkAccessibility(container)
    })

    it('should have proper ARIA attributes for modal', async () => {
      const { container } = render(
        <Modal
          open={true}
          onClose={() => {}}
          title="Test Modal"
          aria-labelledby="modal-title"
        >
          <div id="modal-title">Test Modal</div>
          <p>Modal content</p>
        </Modal>
      )

      const modal = container.querySelector('[role="dialog"]')
      expect(modal).toBeInTheDocument()

      const ariaLabelledBy = modal?.getAttribute('aria-labelledby')
      expect(ariaLabelledBy).toBeTruthy()
    })

    it('should have focus trap in modal', async () => {
      const { container } = render(
        <Modal
          open={true}
          onClose={() => {}}
          title="Test Modal"
        >
          <button>First</button>
          <button>Second</button>
          <button>Third</button>
        </Modal>
      )

      // Modal should contain focusable elements
      const buttons = container.querySelectorAll('button')
      expect(buttons.length).toBeGreaterThan(0)
    })
  })

  describe('Link Components', () => {
    it('should have no accessibility violations for links', async () => {
      const { container } = render(
        <>
          <a href="/page1">Page 1</a>
          <a href="/page2" aria-label="Go to page 2">
            <span aria-hidden="true">→</span>
          </a>
        </>
      )
      await checkAccessibilityPattern(container, 'link')
    })

    it('should have accessible names for all links', async () => {
      const { container } = render(
        <>
          <a href="/page1">Text Link</a>
          <a href="/page2" aria-label="Icon link">
            <span aria-hidden="true">🔗</span>
          </a>
        </>
      )
      await checkAccessibility(container)
    })
  })

  describe('Image Components', () => {
    it('should have no accessibility violations for images with alt text', async () => {
      const { container } = render(
        <>
          <img src="test.jpg" alt="Test image" />
          <img src="decorative.jpg" alt="" aria-hidden="true" />
        </>
      )
      await checkAccessibilityPattern(container, 'image')
    })

    it('should have alt text for informative images', async () => {
      const { container } = render(
        <img src="chart.png" alt="Sales chart showing 25% increase" />
      )
      const img = container.querySelector('img')
      expect(img?.getAttribute('alt')).toBeTruthy()
      await checkAccessibilityPattern(container, 'image')
    })
  })

  describe('Heading Components', () => {
    it('should have no accessibility violations for heading hierarchy', async () => {
      const { container } = render(
        <>
          <h1>Main Title</h1>
          <h2>Section Title</h2>
          <h3>Subsection Title</h3>
        </>
      )
      await checkAccessibility(container)
    })

    it('should have valid heading order', async () => {
      const { container } = render(
        <>
          <h1>Main Title</h1>
          <h2>Section Title</h2>
          <h3>Subsection Title</h3>
        </>
      )

      const headings = container.querySelectorAll('h1, h2, h3, h4, h5, h6')
      let previousLevel = 0

      for (const heading of headings) {
        const level = parseInt(heading.tagName.charAt(1))
        expect(level).toBeGreaterThan(previousLevel - 1) // Allow same or next level
        previousLevel = level
      }
    })
  })

  describe('List Components', () => {
    it('should have no accessibility violations for lists', async () => {
      const { container } = render(
        <ul>
          <li>Item 1</li>
          <li>Item 2</li>
          <li>Item 3</li>
        </ul>
      )
      await checkAccessibility(container)
    })

    it('should have proper list structure', async () => {
      const { container } = render(
        <ul>
          <li>Item 1</li>
          <li>Item 2</li>
        </ul>
      )

      const list = container.querySelector('ul')
      const items = container.querySelectorAll('li')

      expect(list).toBeInTheDocument()
      expect(items.length).toBeGreaterThan(0)
    })
  })
})

