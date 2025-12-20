/**
 * useTouch Hook
 *
 * Hook for touch-friendly interactions including swipe gestures.
 */

import { useState, useRef, useCallback, useEffect } from 'react'

export interface SwipeDirection {
  direction: 'left' | 'right' | 'up' | 'down' | null
  distance: number
}

export interface UseTouchOptions {
  /**
   * Minimum distance for swipe detection (px)
   */
  threshold?: number
  /**
   * Callback when swipe is detected
   */
  onSwipe?: (direction: SwipeDirection) => void
  /**
   * Enable swipe detection
   */
  enabled?: boolean
}

/**
 * Hook for touch interactions and swipe gestures
 */
export function useTouch(options: UseTouchOptions = {}) {
  const { threshold = 50, onSwipe, enabled = true } = options
  const [touchStart, setTouchStart] = useState<{ x: number; y: number } | null>(null)
  const [touchEnd, setTouchEnd] = useState<{ x: number; y: number } | null>(null)
  const elementRef = useRef<HTMLElement | null>(null)

  const minSwipeDistance = threshold

  const onTouchStart = useCallback(
    (e: React.TouchEvent | TouchEvent) => {
      if (!enabled) return
      const touch = e.touches[0]
      setTouchEnd(null)
      setTouchStart({ x: touch.clientX, y: touch.clientY })
    },
    [enabled]
  )

  const onTouchMove = useCallback(
    (e: React.TouchEvent | TouchEvent) => {
      if (!enabled) return
      const touch = e.touches[0]
      setTouchEnd({ x: touch.clientX, y: touch.clientY })
    },
    [enabled]
  )

  const onTouchEnd = useCallback(() => {
    if (!enabled || !touchStart || !touchEnd) return

    const distanceX = touchStart.x - touchEnd.x
    const distanceY = touchStart.y - touchEnd.y
    const isLeftSwipe = distanceX > minSwipeDistance
    const isRightSwipe = distanceX < -minSwipeDistance
    const isUpSwipe = distanceY > minSwipeDistance
    const isDownSwipe = distanceY < -minSwipeDistance

    let direction: SwipeDirection['direction'] = null
    let distance = 0

    if (Math.abs(distanceX) > Math.abs(distanceY)) {
      // Horizontal swipe
      if (isLeftSwipe) {
        direction = 'left'
        distance = Math.abs(distanceX)
      } else if (isRightSwipe) {
        direction = 'right'
        distance = Math.abs(distanceX)
      }
    } else {
      // Vertical swipe
      if (isUpSwipe) {
        direction = 'up'
        distance = Math.abs(distanceY)
      } else if (isDownSwipe) {
        direction = 'down'
        distance = Math.abs(distanceY)
      }
    }

    if (direction && onSwipe) {
      onSwipe({ direction, distance })
    }

    setTouchStart(null)
    setTouchEnd(null)
  }, [touchStart, touchEnd, minSwipeDistance, onSwipe, enabled])

  // Attach event listeners to element
  useEffect(() => {
    const element = elementRef.current
    if (!element || !enabled) return

    element.addEventListener('touchstart', onTouchStart as EventListener)
    element.addEventListener('touchmove', onTouchMove as EventListener)
    element.addEventListener('touchend', onTouchEnd)

    return () => {
      element.removeEventListener('touchstart', onTouchStart as EventListener)
      element.removeEventListener('touchmove', onTouchMove as EventListener)
      element.removeEventListener('touchend', onTouchEnd)
    }
  }, [onTouchStart, onTouchMove, onTouchEnd, enabled])

  return {
    ref: elementRef,
    touchHandlers: {
      onTouchStart,
      onTouchMove,
      onTouchEnd,
    },
  }
}

/**
 * Hook to check if device supports touch
 */
export function useIsTouchDevice(): boolean {
  const [isTouch, setIsTouch] = useState(false)

  useEffect(() => {
    setIsTouch(
      'ontouchstart' in window ||
        navigator.maxTouchPoints > 0 ||
        // @ts-ignore - legacy support
        navigator.msMaxTouchPoints > 0
    )
  }, [])

  return isTouch
}

