/**
 * useContractHistory Hook
 *
 * Custom hook for managing undo/redo history for contract editor.
 * Provides undo/redo functionality with keyboard shortcuts support.
 */

import { useState, useCallback, useRef, useEffect } from 'react'
import type { HubContract } from '../types'

export interface UseContractHistoryOptions {
  /**
   * Maximum history size
   * @default 50
   */
  maxHistorySize?: number
  /**
   * Enable keyboard shortcuts (Ctrl+Z, Ctrl+Y)
   * @default true
   */
  enableKeyboardShortcuts?: boolean
}

export interface UseContractHistoryReturn {
  /**
   * Current contract state
   */
  currentContract: HubContract
  /**
   * Whether undo is available
   */
  canUndo: boolean
  /**
   * Whether redo is available
   */
  canRedo: boolean
  /**
   * Undo to previous state
   */
  undo: () => HubContract | null
  /**
   * Redo to next state
   */
  redo: () => HubContract | null
  /**
   * Add new state to history
   */
  push: (contract: HubContract) => void
  /**
   * Clear history
   */
  clear: () => void
  /**
   * Get history size
   */
  historySize: number
}

/**
 * useContractHistory hook
 */
export function useContractHistory(
  initialContract: HubContract,
  options: UseContractHistoryOptions = {}
): UseContractHistoryReturn {
  const { maxHistorySize = 50, enableKeyboardShortcuts = true } = options

  const [history, setHistory] = useState<HubContract[]>([initialContract])
  const [currentIndex, setCurrentIndex] = useState(0)
  const isPushingRef = useRef(false)

  const currentContract = history[currentIndex]
  const canUndo = currentIndex > 0
  const canRedo = currentIndex < history.length - 1

  const push = useCallback(
    (contract: HubContract) => {
      // Don't push if we're in the middle of undo/redo
      if (isPushingRef.current) return

      // Create new history by removing any "future" states if we're not at the end
      const newHistory = history.slice(0, currentIndex + 1)
      newHistory.push(contract)

      // Limit history size
      if (newHistory.length > maxHistorySize) {
        newHistory.shift()
        setHistory(newHistory)
        setCurrentIndex(newHistory.length - 1)
      } else {
        setHistory(newHistory)
        setCurrentIndex(newHistory.length - 1)
      }
    },
    [history, currentIndex, maxHistorySize]
  )

  const undo = useCallback(() => {
    if (!canUndo) return null

    isPushingRef.current = true
    const newIndex = currentIndex - 1
    setCurrentIndex(newIndex)
    isPushingRef.current = false

    return history[newIndex]
  }, [canUndo, currentIndex, history])

  const redo = useCallback(() => {
    if (!canRedo) return null

    isPushingRef.current = true
    const newIndex = currentIndex + 1
    setCurrentIndex(newIndex)
    isPushingRef.current = false

    return history[newIndex]
  }, [canRedo, currentIndex, history])

  const clear = useCallback(() => {
    setHistory([initialContract])
    setCurrentIndex(0)
  }, [initialContract])

  // Keyboard shortcuts
  useEffect(() => {
    if (!enableKeyboardShortcuts) return

    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl+Z or Cmd+Z for undo
      if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
        e.preventDefault()
        if (canUndo) {
          undo()
        }
      }
      // Ctrl+Y or Ctrl+Shift+Z or Cmd+Shift+Z for redo
      else if (
        ((e.ctrlKey || e.metaKey) && e.key === 'y') ||
        ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'z')
      ) {
        e.preventDefault()
        if (canRedo) {
          redo()
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [enableKeyboardShortcuts, canUndo, canRedo, undo, redo])

  return {
    currentContract,
    canUndo,
    canRedo,
    undo,
    redo,
    push,
    clear,
    historySize: history.length,
  }
}

