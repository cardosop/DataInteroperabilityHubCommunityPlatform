import { useEffect, useRef, useCallback } from 'react'

export interface KeyboardNavigationOptions {
  /**
   * Container element ref
   */
  containerRef: React.RefObject<HTMLElement>
  /**
   * Selector for focusable items
   * @default 'a, button, [tabindex]:not([tabindex="-1"])'
   */
  itemSelector?: string
  /**
   * Whether navigation is enabled
   * @default true
   */
  enabled?: boolean
  /**
   * Callback when item is activated (Enter/Space)
   */
  onActivate?: (element: HTMLElement) => void
  /**
   * Orientation of navigation
   * @default 'horizontal'
   */
  orientation?: 'horizontal' | 'vertical' | 'both'
}

/**
 * Hook for keyboard navigation in navigation components
 * Supports Arrow keys, Home, End, Enter, Space
 */
export function useKeyboardNavigation({
  containerRef,
  itemSelector = 'a, button, [tabindex]:not([tabindex="-1"])',
  enabled = true,
  onActivate,
  orientation = 'horizontal',
}: KeyboardNavigationOptions) {
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (!enabled || !containerRef.current) return

      const container = containerRef.current
      const items = Array.from(
        container.querySelectorAll<HTMLElement>(itemSelector)
      ).filter((item) => {
        const style = window.getComputedStyle(item)
        return style.display !== 'none' && style.visibility !== 'hidden'
      })

      if (items.length === 0) return

      const currentIndex = items.findIndex(
        (item) => item === document.activeElement
      )

      let nextIndex = currentIndex

      switch (e.key) {
        case 'ArrowRight':
          if (orientation === 'horizontal' || orientation === 'both') {
            e.preventDefault()
            nextIndex = currentIndex < items.length - 1 ? currentIndex + 1 : 0
          }
          break

        case 'ArrowLeft':
          if (orientation === 'horizontal' || orientation === 'both') {
            e.preventDefault()
            nextIndex = currentIndex > 0 ? currentIndex - 1 : items.length - 1
          }
          break

        case 'ArrowDown':
          if (orientation === 'vertical' || orientation === 'both') {
            e.preventDefault()
            nextIndex = currentIndex < items.length - 1 ? currentIndex + 1 : 0
          }
          break

        case 'ArrowUp':
          if (orientation === 'vertical' || orientation === 'both') {
            e.preventDefault()
            nextIndex = currentIndex > 0 ? currentIndex - 1 : items.length - 1
          }
          break

        case 'Home':
          e.preventDefault()
          nextIndex = 0
          break

        case 'End':
          e.preventDefault()
          nextIndex = items.length - 1
          break

        case 'Enter':
        case ' ':
          if (currentIndex >= 0 && onActivate) {
            e.preventDefault()
            onActivate(items[currentIndex])
          }
          break

        default:
          return
      }

      if (nextIndex !== currentIndex && nextIndex >= 0 && nextIndex < items.length) {
        items[nextIndex].focus()
      }
    },
    [enabled, containerRef, itemSelector, orientation, onActivate]
  )

  useEffect(() => {
    if (!enabled) return

    const container = containerRef.current
    if (!container) return

    container.addEventListener('keydown', handleKeyDown)
    return () => {
      container.removeEventListener('keydown', handleKeyDown)
    }
  }, [enabled, containerRef, handleKeyDown])
}

