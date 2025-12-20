/**
 * Real-Time Assets Hook
 *
 * Hook for subscribing to real-time asset updates via WebSocket.
 * Automatically invalidates React Query cache when asset events are received,
 * ensuring UI stays in sync with backend changes.
 *
 * Features:
 * - Subscribes to all asset events (created, updated, activated, published, retired)
 * - Automatically invalidates relevant React Query queries
 * - Optional toast notifications for changes
 * - Configurable event filtering
 */

import { useEffect, useCallback, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useWebSocket } from './useWebSocket'
import type {
  AssetEventType,
  AssetCreatedEvent,
  AssetUpdatedEvent,
  AssetActivatedEvent,
  AssetPublishedEvent,
  AssetRetiredEvent,
  WebSocketEvent,
} from '@/lib/api/websocket-events'
import { queryKeys } from '@/lib/api/react-query'
import { isEventType } from '@/lib/api/websocket-events'

export interface UseRealtimeAssetsOptions {
  /**
   * Whether to show toast notifications for changes
   * @default true
   */
  showNotifications?: boolean
  /**
   * Callback when asset is created
   */
  onAssetCreated?: (event: AssetCreatedEvent) => void
  /**
   * Callback when asset is updated
   */
  onAssetUpdated?: (event: AssetUpdatedEvent) => void
  /**
   * Callback when asset is activated
   */
  onAssetActivated?: (event: AssetActivatedEvent) => void
  /**
   * Callback when asset is published
   */
  onAssetPublished?: (event: AssetPublishedEvent) => void
  /**
   * Callback when asset is retired
   */
  onAssetRetired?: (event: AssetRetiredEvent) => void
  /**
   * Filter events by asset ID (only receive events for this asset)
   */
  assetId?: string
  /**
   * Whether to enable real-time updates
   * @default true
   */
  enabled?: boolean
}

/**
 * Hook for real-time asset updates
 *
 * @param options - Configuration options
 * @returns Connection status
 *
 * @example
 * ```tsx
 * function AssetsPage() {
 *   const { isConnected } = useRealtimeAssets({
 *     showNotifications: true,
 *     onAssetCreated: (event) => {
 *       console.log('Asset created:', event.data.asset_id)
 *     },
 *   })
 *
 *   return <div>Assets {isConnected ? '(Live)' : '(Offline)'}</div>
 * }
 * ```
 */
export function useRealtimeAssets(options: UseRealtimeAssetsOptions = {}) {
  const {
    showNotifications = true,
    onAssetCreated,
    onAssetUpdated,
    onAssetActivated,
    onAssetPublished,
    onAssetRetired,
    assetId,
    enabled = true,
  } = options

  const queryClient = useQueryClient()
  const callbacksRef = useRef({
    onAssetCreated,
    onAssetUpdated,
    onAssetActivated,
    onAssetPublished,
    onAssetRetired,
    showNotifications,
  })

  // Update callbacks ref when they change
  useEffect(() => {
    callbacksRef.current = {
      onAssetCreated,
      onAssetUpdated,
      onAssetActivated,
      onAssetPublished,
      onAssetRetired,
      showNotifications,
    }
  }, [onAssetCreated, onAssetUpdated, onAssetActivated, onAssetPublished, onAssetRetired, showNotifications])

  // Handle asset events
  const handleEvent = useCallback(
    (event: WebSocketEvent) => {
      // Filter by asset ID if specified
      if (assetId && event.data.asset_id && event.data.asset_id !== assetId) {
        return
      }

      const callbacks = callbacksRef.current

      // Handle different event types
      if (isEventType(event, 'asset.created')) {
        // Invalidate asset list queries
        queryClient.invalidateQueries({ queryKey: queryKeys.assets.lists() })
        queryClient.invalidateQueries({ queryKey: queryKeys.assets.all })

        // Call custom callback
        callbacks.onAssetCreated?.(event)

        // Show notification
        if (callbacks.showNotifications) {
          const assetName = event.data.name || event.data.key || 'Asset'
          // Note: Toast notifications would be handled by the component using this hook
          // We'll emit a custom event that components can listen to
          window.dispatchEvent(
            new CustomEvent('asset:created', {
              detail: { event, message: `${assetName} was created` },
            })
          )
        }
      } else if (isEventType(event, 'asset.updated')) {
        const assetId = event.data.asset_id

        // Invalidate specific asset query
        if (assetId) {
          queryClient.invalidateQueries({ queryKey: queryKeys.assets.detail(assetId) })
        }
        // Also invalidate list queries (in case sorting/filtering is affected)
        queryClient.invalidateQueries({ queryKey: queryKeys.assets.lists() })

        // Call custom callback
        callbacks.onAssetUpdated?.(event)

        // Show notification
        if (callbacks.showNotifications) {
          const assetName = event.data.name || event.data.key || 'Asset'
          window.dispatchEvent(
            new CustomEvent('asset:updated', {
              detail: { event, message: `${assetName} was updated` },
            })
          )
        }
      } else if (isEventType(event, 'asset.activated')) {
        const assetId = event.data.asset_id

        // Invalidate specific asset query
        if (assetId) {
          queryClient.invalidateQueries({ queryKey: queryKeys.assets.detail(assetId) })
        }
        // Also invalidate list queries
        queryClient.invalidateQueries({ queryKey: queryKeys.assets.lists() })

        // Call custom callback
        callbacks.onAssetActivated?.(event)

        // Show notification
        if (callbacks.showNotifications) {
          const assetName = event.data.name || event.data.key || 'Asset'
          window.dispatchEvent(
            new CustomEvent('asset:activated', {
              detail: { event, message: `${assetName} was activated` },
            })
          )
        }
      } else if (isEventType(event, 'asset.published')) {
        const assetId = event.data.asset_id

        // Invalidate specific asset query
        if (assetId) {
          queryClient.invalidateQueries({ queryKey: queryKeys.assets.detail(assetId) })
        }
        // Also invalidate marketplace queries
        queryClient.invalidateQueries({ queryKey: queryKeys.marketplace.all })

        // Call custom callback
        callbacks.onAssetPublished?.(event)

        // Show notification
        if (callbacks.showNotifications) {
          const assetName = event.data.name || event.data.key || 'Asset'
          window.dispatchEvent(
            new CustomEvent('asset:published', {
              detail: { event, message: `${assetName} was published to marketplace` },
            })
          )
        }
      } else if (isEventType(event, 'asset.retired')) {
        const assetId = event.data.asset_id

        // Invalidate specific asset query
        if (assetId) {
          queryClient.invalidateQueries({ queryKey: queryKeys.assets.detail(assetId) })
        }
        // Also invalidate list queries
        queryClient.invalidateQueries({ queryKey: queryKeys.assets.lists() })

        // Call custom callback
        callbacks.onAssetRetired?.(event)

        // Show notification
        if (callbacks.showNotifications) {
          const assetName = event.data.name || event.data.key || 'Asset'
          window.dispatchEvent(
            new CustomEvent('asset:retired', {
              detail: { event, message: `${assetName} was retired` },
            })
          )
        }
      }
    },
    [assetId, queryClient]
  )

  // Subscribe to asset events
  const assetEventTypes: AssetEventType[] = [
    'asset.created',
    'asset.updated',
    'asset.activated',
    'asset.published',
    'asset.retired',
  ]

  const { status, isConnected } = useWebSocket(enabled ? assetEventTypes : [], handleEvent)

  return {
    status,
    isConnected,
  }
}

