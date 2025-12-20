import { useState, useEffect, useCallback } from 'react'
import { useLocalStorage } from './useLocalStorage'

export interface ProgressiveDisclosureOptions {
  /**
   * Storage key for remembering feature visibility
   */
  storageKey?: string
  /**
   * Initial visibility state
   * @default false
   */
  initialVisible?: boolean
  /**
   * Show feature after delay (ms)
   */
  showAfterDelay?: number
  /**
   * Show feature after user action count
   */
  showAfterActions?: number
  /**
   * Track user actions
   * @default false
   */
  trackActions?: boolean
}

export interface ProgressiveDisclosureReturn {
  /**
   * Whether feature is visible
   */
  isVisible: boolean
  /**
   * Show the feature
   */
  show: () => void
  /**
   * Hide the feature
   */
  hide: () => void
  /**
   * Toggle feature visibility
   */
  toggle: () => void
  /**
   * Record user action (for showAfterActions)
   */
  recordAction: () => void
  /**
   * Action count
   */
  actionCount: number
}

/**
 * Hook for progressive disclosure of features
 *
 * Gradually shows features to users as they become more familiar with the app.
 *
 * @example
 * ```tsx
 * const { isVisible, show } = useProgressiveDisclosure({
 *   storageKey: 'advanced-features-visible',
 *   showAfterDelay: 5000, // Show after 5 seconds
 * })
 *
 * {isVisible && <AdvancedFeaturePanel />}
 * ```
 */
export function useProgressiveDisclosure(
  options: ProgressiveDisclosureOptions = {}
): ProgressiveDisclosureReturn {
  const {
    storageKey,
    initialVisible = false,
    showAfterDelay,
    showAfterActions,
    trackActions = false,
  } = options

  const [visible, setVisible] = useLocalStorage(
    storageKey || 'progressive-disclosure-visible',
    initialVisible
  )
  const [actionCount, setActionCount] = useState(0)

  const show = useCallback(() => {
    setVisible(true)
  }, [setVisible])

  const hide = useCallback(() => {
    setVisible(false)
  }, [setVisible])

  const toggle = useCallback(() => {
    setVisible((prev) => !prev)
  }, [setVisible])

  const recordAction = useCallback(() => {
    if (trackActions || showAfterActions) {
      setActionCount((prev) => {
        const newCount = prev + 1
        if (showAfterActions && newCount >= showAfterActions && !visible) {
          setVisible(true)
        }
        return newCount
      })
    }
  }, [trackActions, showAfterActions, visible, setVisible])

  // Show after delay
  useEffect(() => {
    if (showAfterDelay && !visible) {
      const timer = setTimeout(() => {
        setVisible(true)
      }, showAfterDelay)
      return () => clearTimeout(timer)
    }
  }, [showAfterDelay, visible, setVisible])

  return {
    isVisible: visible,
    show,
    hide,
    toggle,
    recordAction,
    actionCount,
  }
}

