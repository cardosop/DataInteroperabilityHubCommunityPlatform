import { useState, useEffect, useCallback } from 'react'

export interface ProgressiveLoadingOptions<T> {
  /**
   * Critical data loader (loads first)
   */
  loadCritical: () => Promise<T>
  /**
   * Non-critical data loader (loads after critical)
   */
  loadNonCritical?: () => Promise<any>
  /**
   * Delay before loading non-critical content (ms)
   * @default 0
   */
  nonCriticalDelay?: number
  /**
   * Whether to load non-critical content
   * @default true
   */
  loadNonCriticalEnabled?: boolean
}

export interface ProgressiveLoadingState<T> {
  /**
   * Critical data
   */
  critical: T | null
  /**
   * Non-critical data
   */
  nonCritical: any | null
  /**
   * Whether critical data is loading
   */
  loadingCritical: boolean
  /**
   * Whether non-critical data is loading
   */
  loadingNonCritical: boolean
  /**
   * Error state
   */
  error: Error | null
  /**
   * Reload function
   */
  reload: () => void
}

/**
 * Hook for progressive loading - loads critical content first, then non-critical
 */
export function useProgressiveLoading<T>({
  loadCritical,
  loadNonCritical,
  nonCriticalDelay = 0,
  loadNonCriticalEnabled = true,
}: ProgressiveLoadingOptions<T>): ProgressiveLoadingState<T> {
  const [critical, setCritical] = useState<T | null>(null)
  const [nonCritical, setNonCritical] = useState<any | null>(null)
  const [loadingCritical, setLoadingCritical] = useState(true)
  const [loadingNonCritical, setLoadingNonCritical] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const [reloadTrigger, setReloadTrigger] = useState(0)

  const load = useCallback(async () => {
    try {
      // Load critical content first
      setLoadingCritical(true)
      setError(null)
      const criticalData = await loadCritical()
      setCritical(criticalData)
      setLoadingCritical(false)

      // Load non-critical content after delay
      if (loadNonCritical && loadNonCriticalEnabled) {
        if (nonCriticalDelay > 0) {
          await new Promise((resolve) => setTimeout(resolve, nonCriticalDelay))
        }
        setLoadingNonCritical(true)
        const nonCriticalData = await loadNonCritical()
        setNonCritical(nonCriticalData)
        setLoadingNonCritical(false)
      }
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Loading failed'))
      setLoadingCritical(false)
      setLoadingNonCritical(false)
    }
  }, [
    loadCritical,
    loadNonCritical,
    nonCriticalDelay,
    loadNonCriticalEnabled,
  ])

  useEffect(() => {
    load()
  }, [load, reloadTrigger])

  const reload = useCallback(() => {
    setCritical(null)
    setNonCritical(null)
    setReloadTrigger((prev) => prev + 1)
  }, [])

  return {
    critical,
    nonCritical,
    loadingCritical,
    loadingNonCritical,
    error,
    reload,
  }
}

