/**
 * Real-Time Notifications Hook
 *
 * Hook for listening to real-time change notifications from asset and contract events.
 * Displays toast notifications when changes occur.
 *
 * This hook should be used at the app level to provide global notifications
 * for asset and contract changes.
 */

import { useEffect } from 'react'
import { useToastManager } from '@/components/feedback/Toast/useToastManager'

export interface UseRealtimeNotificationsOptions {
  /**
   * Whether to enable notifications
   * @default true
   */
  enabled?: boolean
  /**
   * Custom notification handler
   */
  onNotification?: (event: string, message: string, detail: any) => void
}

/**
 * Hook for displaying real-time change notifications
 *
 * @param options - Configuration options
 *
 * @example
 * ```tsx
 * function App() {
 *   useRealtimeNotifications({ enabled: true })
 *   return <Router>...</Router>
 * }
 * ```
 */
export function useRealtimeNotifications(options: UseRealtimeNotificationsOptions = {}) {
  const { enabled = true, onNotification } = options
  const { success, info, warning } = useToastManager()

  useEffect(() => {
    if (!enabled) return

    // Asset event handlers
    const handleAssetCreated = (e: CustomEvent) => {
      const message = e.detail.message || 'Asset was created'
      success(message, 5000)
      onNotification?.('asset:created', message, e.detail)
    }

    const handleAssetUpdated = (e: CustomEvent) => {
      const message = e.detail.message || 'Asset was updated'
      info(message, 5000)
      onNotification?.('asset:updated', message, e.detail)
    }

    const handleAssetActivated = (e: CustomEvent) => {
      const message = e.detail.message || 'Asset was activated'
      success(message, 5000)
      onNotification?.('asset:activated', message, e.detail)
    }

    const handleAssetPublished = (e: CustomEvent) => {
      const message = e.detail.message || 'Asset was published'
      success(message, 5000)
      onNotification?.('asset:published', message, e.detail)
    }

    const handleAssetRetired = (e: CustomEvent) => {
      const message = e.detail.message || 'Asset was retired'
      warning(message, 5000)
      onNotification?.('asset:retired', message, e.detail)
    }

    // Contract event handlers
    const handleContractCreated = (e: CustomEvent) => {
      const message = e.detail.message || 'Contract was created'
      success(message, 5000)
      onNotification?.('contract:created', message, e.detail)
    }

    const handleContractUpdated = (e: CustomEvent) => {
      const message = e.detail.message || 'Contract was updated'
      info(message, 5000)
      onNotification?.('contract:updated', message, e.detail)
    }

    const handleContractDeleted = (e: CustomEvent) => {
      const message = e.detail.message || 'Contract was deleted'
      warning(message, 5000)
      onNotification?.('contract:deleted', message, e.detail)
    }

    const handleContractValidated = (e: CustomEvent) => {
      const message = e.detail.message || 'Contract validation completed'
      const severity = e.detail.event?.data?.validation_status === 'VALID' ? 'success' : 'warning'
      if (severity === 'success') {
        success(message, 5000)
      } else {
        warning(message, 5000)
      }
      onNotification?.('contract:validated', message, e.detail)
    }

    const handleContractNormalized = (e: CustomEvent) => {
      const message = e.detail.message || 'Contract normalization completed'
      const severity = e.detail.event?.data?.normalization_status === 'SUCCESS' ? 'success' : 'warning'
      if (severity === 'success') {
        success(message, 5000)
      } else {
        warning(message, 5000)
      }
      onNotification?.('contract:normalized', message, e.detail)
    }

    // Register event listeners
    window.addEventListener('asset:created', handleAssetCreated as EventListener)
    window.addEventListener('asset:updated', handleAssetUpdated as EventListener)
    window.addEventListener('asset:activated', handleAssetActivated as EventListener)
    window.addEventListener('asset:published', handleAssetPublished as EventListener)
    window.addEventListener('asset:retired', handleAssetRetired as EventListener)
    window.addEventListener('contract:created', handleContractCreated as EventListener)
    window.addEventListener('contract:updated', handleContractUpdated as EventListener)
    window.addEventListener('contract:deleted', handleContractDeleted as EventListener)
    window.addEventListener('contract:validated', handleContractValidated as EventListener)
    window.addEventListener('contract:normalized', handleContractNormalized as EventListener)

    // Cleanup
    return () => {
      window.removeEventListener('asset:created', handleAssetCreated as EventListener)
      window.removeEventListener('asset:updated', handleAssetUpdated as EventListener)
      window.removeEventListener('asset:activated', handleAssetActivated as EventListener)
      window.removeEventListener('asset:published', handleAssetPublished as EventListener)
      window.removeEventListener('asset:retired', handleAssetRetired as EventListener)
      window.removeEventListener('contract:created', handleContractCreated as EventListener)
      window.removeEventListener('contract:updated', handleContractUpdated as EventListener)
      window.removeEventListener('contract:deleted', handleContractDeleted as EventListener)
      window.removeEventListener('contract:validated', handleContractValidated as EventListener)
      window.removeEventListener('contract:normalized', handleContractNormalized as EventListener)
    }
  }, [enabled, onNotification, success, info, warning])
}

