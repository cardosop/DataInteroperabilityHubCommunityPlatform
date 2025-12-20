import { useState, useCallback, useEffect } from 'react'
import { useLocalStorage } from '@/hooks/useLocalStorage'
import type { TourStep } from './GuidedTour'

export interface UseGuidedTourOptions {
  /**
   * Storage key for remembering completion
   */
  storageKey?: string
  /**
   * Auto-start tour on mount (if not completed)
   * @default false
   */
  autoStart?: boolean
}

export interface UseGuidedTourReturn {
  /**
   * Whether tour is active
   */
  isActive: boolean
  /**
   * Start the tour
   */
  startTour: () => void
  /**
   * Stop the tour
   */
  stopTour: () => void
  /**
   * Reset tour completion status
   */
  resetTour: () => void
  /**
   * Whether tour has been completed
   */
  isCompleted: boolean
}

/**
 * Hook for managing guided tour state
 *
 * @example
 * ```tsx
 * const { isActive, startTour, stopTour } = useGuidedTour({
 *   storageKey: 'my-tour-completed',
 * })
 *
 * <GuidedTour
 *   steps={tourSteps}
 *   isActive={isActive}
 *   onComplete={stopTour}
 * />
 * ```
 */
export function useGuidedTour(
  options: UseGuidedTourOptions = {}
): UseGuidedTourReturn {
  const { storageKey, autoStart = false } = options
  const [isActive, setIsActive] = useState(false)
  const [completed, setCompleted] = useLocalStorage(
    storageKey || 'guided-tour-completed',
    false
  )

  const startTour = useCallback(() => {
    if (!completed) {
      setIsActive(true)
    }
  }, [completed])

  const stopTour = useCallback(() => {
    setIsActive(false)
    if (storageKey) {
      setCompleted(true)
    }
  }, [storageKey, setCompleted])

  const resetTour = useCallback(() => {
    setIsActive(false)
    if (storageKey) {
      setCompleted(false)
    }
  }, [storageKey, setCompleted])

  // Auto-start if enabled and not completed
  useEffect(() => {
    if (autoStart && !completed && !isActive) {
      setIsActive(true)
    }
  }, [autoStart, completed, isActive])

  return {
    isActive,
    startTour,
    stopTour,
    resetTour,
    isCompleted: completed,
  }
}

