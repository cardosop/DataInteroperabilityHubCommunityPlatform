/**
 * useFormAutoSave Hook
 *
 * Hook for auto-saving form drafts to localStorage or backend.
 * Prevents data loss and allows users to resume forms.
 */

import { useEffect, useRef, useCallback } from 'react'
import { UseFormReturn, FieldValues } from 'react-hook-form'
import { debounce } from '@/utils/debounce'

export interface UseFormAutoSaveOptions<T extends FieldValues> {
  /**
   * React Hook Form instance
   */
  form: UseFormReturn<T>
  /**
   * Storage key for draft data
   */
  storageKey: string
  /**
   * Auto-save enabled
   */
  enabled?: boolean
  /**
   * Debounce delay in milliseconds
   */
  debounceMs?: number
  /**
   * Callback when draft is saved
   */
  onSave?: (data: T) => void | Promise<void>
  /**
   * Callback when draft is loaded
   */
  onLoad?: (data: T) => void
  /**
   * Exclude fields from auto-save
   */
  excludeFields?: (keyof T)[]
}

/**
 * Hook for form auto-save functionality
 */
export function useFormAutoSave<T extends FieldValues>(
  options: UseFormAutoSaveOptions<T>
) {
  const {
    form,
    storageKey,
    enabled = true,
    debounceMs = 1000,
    onSave,
    onLoad,
    excludeFields = [],
  } = options

  const { watch, getValues, reset } = form
  const watchedValues = watch()
  const isInitialMount = useRef(true)
  const saveTimeoutRef = useRef<NodeJS.Timeout>()

  /**
   * Save draft to storage
   */
  const saveDraft = useCallback(
    async (data: T) => {
      if (!enabled) return

      // Filter out excluded fields
      const draftData = { ...data }
      excludeFields.forEach((field) => {
        delete draftData[field]
      })

      // Save to localStorage
      if (typeof window !== 'undefined') {
        try {
          localStorage.setItem(storageKey, JSON.stringify(draftData))
        } catch (error) {
          console.error('Failed to save draft to localStorage:', error)
        }
      }

      // Call custom save callback
      if (onSave) {
        try {
          await onSave(draftData)
        } catch (error) {
          console.error('Failed to save draft via callback:', error)
        }
      }
    },
    [enabled, storageKey, excludeFields, onSave]
  )

  /**
   * Debounced save function
   */
  const debouncedSaveRef = useRef<ReturnType<typeof debounce> | null>(null)

  useEffect(() => {
    debouncedSaveRef.current = debounce((data: T) => {
      saveDraft(data)
    }, debounceMs)

    return () => {
      if (debouncedSaveRef.current) {
        debouncedSaveRef.current.cancel()
      }
    }
  }, [debounceMs, saveDraft])

  /**
   * Load draft from storage
   */
  const loadDraft = useCallback((): T | null => {
    if (typeof window === 'undefined') return null

    try {
      const stored = localStorage.getItem(storageKey)
      if (stored) {
        const data = JSON.parse(stored) as T
        if (onLoad) {
          onLoad(data)
        }
        return data
      }
    } catch (error) {
      console.error('Failed to load draft from localStorage:', error)
    }

    return null
  }, [storageKey, onLoad])

  /**
   * Clear draft from storage
   */
  const clearDraft = useCallback(() => {
    if (typeof window !== 'undefined') {
      try {
        localStorage.removeItem(storageKey)
      } catch (error) {
        console.error('Failed to clear draft from localStorage:', error)
      }
    }
  }, [storageKey])

  /**
   * Restore draft to form
   */
  const restoreDraft = useCallback(() => {
    const draft = loadDraft()
    if (draft) {
      reset(draft)
      return true
    }
    return false
  }, [loadDraft, reset])

  // Auto-save on form changes
  useEffect(() => {
    if (!enabled || isInitialMount.current) {
      isInitialMount.current = false
      return
    }

    // Debounce save
    const currentValues = getValues()
    if (debouncedSaveRef.current) {
      debouncedSaveRef.current(currentValues)
    }

    // Cleanup
    return () => {
      if (debouncedSaveRef.current) {
        debouncedSaveRef.current.cancel()
      }
    }
  }, [watchedValues, enabled, getValues])

  // Load draft on mount
  useEffect(() => {
    if (enabled && isInitialMount.current) {
      const draft = loadDraft()
      if (draft) {
        reset(draft, { keepDefaultValues: true })
      }
      isInitialMount.current = false
    }
  }, [enabled, loadDraft, reset])

  return {
    saveDraft,
    loadDraft,
    clearDraft,
    restoreDraft,
  }
}

