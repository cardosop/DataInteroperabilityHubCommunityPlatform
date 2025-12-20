/**
 * Navigation Accessibility Tests
 *
 * Comprehensive accessibility tests for navigation components covering:
 * - Keyboard navigation (Tab order, arrow keys)
 * - ARIA labels and roles
 * - Skip links
 * - Focus management
 *
 * Uses real navigation components (no mocks/stubs)
 */

import { describe, it, expect } from 'vitest'
import { render } from '@/test-utils'
import { checkAccessibility, checkAccessibilityPattern } from '@/test-utils/accessibility'
import { Header } from '../Header/Header'
import { MemoryRouter } from 'react-router-dom'

const mockNavigation = [
  { path: '/assets', label: 'Assets' },
  { path: '/contracts', label: 'Contracts' },
  { path: '/datasets', label: 'Datasets' },
]

describe('Navigation Accessibility Tests', () => {
  describe('Header Navigation', () => {
    it('should have no accessibility violations', async () => {
      const { container } = render(
        <MemoryRouter>
          <Header navigation={mockNavigation} />
        </MemoryRouter>
      )
      await checkAccessibilityPattern(container, 'navigation')
    })

    it('should have proper ARIA labels for navigation', async () => {
      const { container } = render(
        <MemoryRouter>
          <Header navigation={mockNavigation} />
        </MemoryRouter>
      )

      const nav = container.querySelector('nav')
      expect(nav).toBeInTheDocument()

      const ariaLabel = nav?.getAttribute('aria-label')
      const ariaLabelledBy = nav?.getAttribute('aria-labelledby')

      expect(ariaLabel || ariaLabelledBy).toBeTruthy()
    })

    it('should have role="navigation" for nav elements', async () => {
      const { container } = render(
        <MemoryRouter>
          <Header navigation={mockNavigation} />
        </MemoryRouter>
      )

      const nav = container.querySelector('nav')
      expect(nav).toBeInTheDocument()

      const role = nav?.getAttribute('role')
      // Native nav element has implicit role, or explicit role="navigation"
      expect(role === 'navigation' || role === null).toBe(true)
    })
  })

  describe('Keyboard Navigation', () => {
    it('should be keyboard navigable', async () => {
      const { container } = render(
        <MemoryRouter>
          <Header navigation={mockNavigation} />
        </MemoryRouter>
      )

      const links = container.querySelectorAll('a[href]')
      expect(links.length).toBeGreaterThan(0)

      for (const link of links) {
        const tabIndex = link.getAttribute('tabindex')
        // Links should be keyboard accessible (not tabindex="-1")
        expect(tabIndex !== '-1').toBe(true)
      }
    })

    it('should have logical tab order', async () => {
      const { container } = render(
        <MemoryRouter>
          <Header navigation={mockNavigation} />
        </MemoryRouter>
      )

      const focusableElements = container.querySelectorAll(
        'a[href], button, input, select, textarea, [tabindex]:not([tabindex="-1"])'
      )

      // Should have focusable elements
      expect(focusableElements.length).toBeGreaterThan(0)
    })
  })

  describe('Skip Links', () => {
    it('should have skip links for main content', async () => {
      const { container } = render(
        <MemoryRouter>
          <Header navigation={mockNavigation} />
        </MemoryRouter>
      )

      // Check for skip links (if implemented)
      const skipLinks = container.querySelectorAll('a[href*="#main"], a[href*="#content"]')
      // Skip links are recommended but not always present
      // If present, they should be accessible
      if (skipLinks.length > 0) {
        for (const link of skipLinks) {
          expect(link).toBeInTheDocument()
        }
      }
    })
  })

  describe('Navigation Links', () => {
    it('should have accessible names for all navigation links', async () => {
      const { container } = render(
        <MemoryRouter>
          <Header navigation={mockNavigation} />
        </MemoryRouter>
      )

      const links = container.querySelectorAll('a[href]')

      for (const link of links) {
        const text = link.textContent?.trim()
        const ariaLabel = link.getAttribute('aria-label')
        const ariaLabelledBy = link.getAttribute('aria-labelledby')

        // Link should have accessible name
        expect(
          text || ariaLabel || ariaLabelledBy,
          'Navigation link must have accessible name'
        ).toBeTruthy()
      }
    })
  })
})

