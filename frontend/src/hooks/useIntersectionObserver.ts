/**
 * useIntersectionObserver Hook
 *
 * Reusable hook for observing element intersection with viewport or container.
 * Useful for lazy loading, infinite scroll, animations, and visibility tracking.
 */

import { useEffect, useRef, useState, RefObject } from 'react'

export interface UseIntersectionObserverOptions extends IntersectionObserverInit {
  /**
   * Whether the observer is enabled
   * @default true
   */
  enabled?: boolean
  /**
   * Callback when intersection changes
   */
  onIntersect?: (entry: IntersectionObserverEntry) => void
  /**
   * Callback when element enters viewport
   */
  onEnter?: (entry: IntersectionObserverEntry) => void
  /**
   * Callback when element leaves viewport
   */
  onLeave?: (entry: IntersectionObserverEntry) => void
  /**
   * Whether to disconnect after first intersection
   * @default false
   */
  once?: boolean
}

export interface UseIntersectionObserverReturn {
  /**
   * Whether the element is currently intersecting
   */
  isIntersecting: boolean
  /**
   * Intersection ratio (0-1)
   */
  intersectionRatio: number
  /**
   * Latest intersection entry
   */
  entry: IntersectionObserverEntry | null
  /**
   * Ref to attach to the element to observe
   */
  ref: RefObject<HTMLElement>
}

/**
 * Hook for observing element intersection with viewport
 *
 * @param options - Intersection Observer options
 * @returns Intersection state and ref
 *
 * @example
 * ```tsx
 * // Basic usage
 * const { ref, isIntersecting } = useIntersectionObserver()
 *
 * return <div ref={ref}>{isIntersecting && <HeavyComponent />}</div>
 * ```
 *
 * @example
 * ```tsx
 * // With callbacks
 * const { ref } = useIntersectionObserver({
 *   rootMargin: '100px',
 *   onEnter: (entry) => console.log('Entered viewport'),
 *   onLeave: (entry) => console.log('Left viewport'),
 * })
 *
 * return <div ref={ref}>Content</div>
 * ```
 *
 * @example
 * ```tsx
 * // Lazy load component
 * const { ref, isIntersecting } = useIntersectionObserver({ once: true })
 *
 * return (
 *   <div ref={ref}>
 *     {isIntersecting ? <HeavyComponent /> : <Placeholder />}
 *   </div>
 * )
 * ```
 */
export function useIntersectionObserver(
  options: UseIntersectionObserverOptions = {}
): UseIntersectionObserverReturn {
  const {
    enabled = true,
    root = null,
    rootMargin = '0px',
    threshold = 0,
    onIntersect,
    onEnter,
    onLeave,
    once = false,
  } = options

  const [isIntersecting, setIsIntersecting] = useState(false)
  const [intersectionRatio, setIntersectionRatio] = useState(0)
  const [entry, setEntry] = useState<IntersectionObserverEntry | null>(null)
  const ref = useRef<HTMLElement>(null)
  const observerRef = useRef<IntersectionObserver | null>(null)
  const hasIntersectedRef = useRef(false)

  useEffect(() => {
    if (!enabled || !ref.current) {
      return
    }

    const element = ref.current

    // Create observer
    observerRef.current = new IntersectionObserver(
      (entries) => {
        const [intersectionEntry] = entries

        if (!intersectionEntry) return

        const isCurrentlyIntersecting = intersectionEntry.isIntersecting
        const ratio = intersectionEntry.intersectionRatio

        setEntry(intersectionEntry)
        setIsIntersecting(isCurrentlyIntersecting)
        setIntersectionRatio(ratio)

        // Call callbacks
        onIntersect?.(intersectionEntry)

        if (isCurrentlyIntersecting) {
          if (!hasIntersectedRef.current) {
            hasIntersectedRef.current = true
            onEnter?.(intersectionEntry)
          }
        } else {
          if (hasIntersectedRef.current) {
            onLeave?.(intersectionEntry)
          }
        }

        // Disconnect if once is true and element has intersected
        if (once && isCurrentlyIntersecting && observerRef.current) {
          observerRef.current.disconnect()
          observerRef.current = null
        }
      },
      {
        root,
        rootMargin,
        threshold,
      }
    )

    // Start observing
    observerRef.current.observe(element)

    // Cleanup
    return () => {
      if (observerRef.current) {
        observerRef.current.disconnect()
        observerRef.current = null
      }
    }
  }, [enabled, root, rootMargin, threshold, onIntersect, onEnter, onLeave, once])

  return {
    isIntersecting,
    intersectionRatio,
    entry,
    ref,
  }
}

/**
 * Hook for observing multiple elements
 *
 * @param refs - Array of refs to observe
 * @param options - Intersection Observer options
 * @returns Array of intersection states
 *
 * @example
 * ```tsx
 * const ref1 = useRef<HTMLDivElement>(null)
 * const ref2 = useRef<HTMLDivElement>(null)
 *
 * const intersections = useMultipleIntersectionObserver([ref1, ref2], {
 *   rootMargin: '50px',
 * })
 *
 * return (
 *   <>
 *     <div ref={ref1}>
 *       {intersections[0].isIntersecting && <Component1 />}
 *     </div>
 *     <div ref={ref2}>
 *       {intersections[1].isIntersecting && <Component2 />}
 *     </div>
 *   </>
 * )
 * ```
 */
export function useMultipleIntersectionObserver(
  refs: RefObject<HTMLElement>[],
  options: Omit<UseIntersectionObserverOptions, 'enabled'> = {}
): UseIntersectionObserverReturn[] {
  const [states, setStates] = useState<UseIntersectionObserverReturn[]>(() =>
    refs.map(() => ({
      isIntersecting: false,
      intersectionRatio: 0,
      entry: null,
      ref: { current: null },
    }))
  )

  useEffect(() => {
    const elements = refs.map((ref) => ref.current).filter(Boolean) as HTMLElement[]

    if (elements.length === 0) return

    const {
      root = null,
      rootMargin = '0px',
      threshold = 0,
      onIntersect,
      onEnter,
      onLeave,
      once = false,
    } = options

    const observer = new IntersectionObserver(
      (entries) => {
        setStates((prevStates) => {
          const newStates = [...prevStates]

          entries.forEach((entry) => {
            const index = elements.findIndex((el) => el === entry.target)
            if (index === -1) return

            const isCurrentlyIntersecting = entry.isIntersecting
            const ratio = entry.intersectionRatio

            newStates[index] = {
              isIntersecting: isCurrentlyIntersecting,
              intersectionRatio: ratio,
              entry,
              ref: refs[index],
            }

            // Call callbacks
            onIntersect?.(entry)

            if (isCurrentlyIntersecting) {
              onEnter?.(entry)
            } else {
              onLeave?.(entry)
            }
          })

          return newStates
        })

        // Disconnect if once is true and all elements have intersected
        if (once) {
          const allIntersected = entries.every((entry) => entry.isIntersecting)
          if (allIntersected) {
            observer.disconnect()
          }
        }
      },
      {
        root,
        rootMargin,
        threshold,
      }
    )

    elements.forEach((element) => observer.observe(element))

    return () => {
      observer.disconnect()
    }
  }, [refs, options.root, options.rootMargin, options.threshold, options.onIntersect, options.onEnter, options.onLeave, options.once])

  return states
}

