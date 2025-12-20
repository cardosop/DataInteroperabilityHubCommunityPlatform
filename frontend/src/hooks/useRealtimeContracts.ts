/**
 * Real-Time Contracts Hook
 *
 * Hook for subscribing to real-time contract updates via WebSocket.
 * Automatically invalidates React Query cache when contract events are received,
 * ensuring UI stays in sync with backend changes.
 *
 * Features:
 * - Subscribes to all contract events (created, updated, deleted, validated, normalized)
 * - Automatically invalidates relevant React Query queries
 * - Optional toast notifications for changes
 * - Configurable event filtering
 */

import { useEffect, useCallback, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useWebSocket } from './useWebSocket'
import type {
  ContractEventType,
  ContractCreatedEvent,
  ContractUpdatedEvent,
  ContractValidatedEvent,
  WebSocketEvent,
} from '@/lib/api/websocket-events'
import { queryKeys } from '@/lib/api/react-query'
import { isEventType } from '@/lib/api/websocket-events'

export interface UseRealtimeContractsOptions {
  /**
   * Whether to show toast notifications for changes
   * @default true
   */
  showNotifications?: boolean
  /**
   * Callback when contract is created
   */
  onContractCreated?: (event: ContractCreatedEvent) => void
  /**
   * Callback when contract is updated
   */
  onContractUpdated?: (event: ContractUpdatedEvent) => void
  /**
   * Callback when contract is validated
   */
  onContractValidated?: (event: ContractValidatedEvent) => void
  /**
   * Filter events by contract ID (only receive events for this contract)
   */
  contractId?: string
  /**
   * Whether to enable real-time updates
   * @default true
   */
  enabled?: boolean
}

/**
 * Hook for real-time contract updates
 *
 * @param options - Configuration options
 * @returns Connection status
 *
 * @example
 * ```tsx
 * function ContractsPage() {
 *   const { isConnected } = useRealtimeContracts({
 *     showNotifications: true,
 *     onContractCreated: (event) => {
 *       console.log('Contract created:', event.data.contract_id)
 *     },
 *   })
 *
 *   return <div>Contracts {isConnected ? '(Live)' : '(Offline)'}</div>
 * }
 * ```
 */
export function useRealtimeContracts(options: UseRealtimeContractsOptions = {}) {
  const {
    showNotifications = true,
    onContractCreated,
    onContractUpdated,
    onContractValidated,
    contractId,
    enabled = true,
  } = options

  const queryClient = useQueryClient()
  const callbacksRef = useRef({
    onContractCreated,
    onContractUpdated,
    onContractValidated,
    showNotifications,
  })

  // Update callbacks ref when they change
  useEffect(() => {
    callbacksRef.current = {
      onContractCreated,
      onContractUpdated,
      onContractValidated,
      showNotifications,
    }
  }, [onContractCreated, onContractUpdated, onContractValidated, showNotifications])

  // Handle contract events
  const handleEvent = useCallback(
    (event: WebSocketEvent) => {
      // Filter by contract ID if specified
      if (contractId && event.data.contract_id && event.data.contract_id !== contractId) {
        return
      }

      const callbacks = callbacksRef.current

      // Handle different event types
      if (isEventType(event, 'contract.created')) {
        // Invalidate contract list queries
        queryClient.invalidateQueries({ queryKey: queryKeys.contracts.lists() })
        queryClient.invalidateQueries({ queryKey: queryKeys.contracts.all })

        // Call custom callback
        callbacks.onContractCreated?.(event)

        // Show notification
        if (callbacks.showNotifications) {
          const contractName = event.data.name || 'Contract'
          window.dispatchEvent(
            new CustomEvent('contract:created', {
              detail: { event, message: `${contractName} was created` },
            })
          )
        }
      } else if (isEventType(event, 'contract.updated')) {
        const contractId = event.data.contract_id

        // Invalidate specific contract query
        if (contractId) {
          queryClient.invalidateQueries({ queryKey: queryKeys.contracts.detail(contractId) })
        }
        // Also invalidate list queries (in case sorting/filtering is affected)
        queryClient.invalidateQueries({ queryKey: queryKeys.contracts.lists() })

        // Call custom callback
        callbacks.onContractUpdated?.(event)

        // Show notification
        if (callbacks.showNotifications) {
          const contractName = event.data.name || 'Contract'
          window.dispatchEvent(
            new CustomEvent('contract:updated', {
              detail: { event, message: `${contractName} was updated` },
            })
          )
        }
      } else if (isEventType(event, 'contract.deleted')) {
        const contractId = event.data.contract_id

        // Invalidate specific contract query
        if (contractId) {
          queryClient.invalidateQueries({ queryKey: queryKeys.contracts.detail(contractId) })
        }
        // Also invalidate list queries
        queryClient.invalidateQueries({ queryKey: queryKeys.contracts.lists() })

        // Show notification
        if (callbacks.showNotifications) {
          const contractName = event.data.name || 'Contract'
          window.dispatchEvent(
            new CustomEvent('contract:deleted', {
              detail: { event, message: `${contractName} was deleted` },
            })
          )
        }
      } else if (isEventType(event, 'contract.validated')) {
        const contractId = event.data.contract_id

        // Invalidate specific contract query
        if (contractId) {
          queryClient.invalidateQueries({ queryKey: queryKeys.contracts.detail(contractId) })
        }
        // Also invalidate list queries (validation status might be shown in list)
        queryClient.invalidateQueries({ queryKey: queryKeys.contracts.lists() })

        // Call custom callback
        callbacks.onContractValidated?.(event)

        // Show notification
        if (callbacks.showNotifications) {
          const contractName = event.data.name || 'Contract'
          const validationStatus = event.data.validation_status || 'unknown'
          window.dispatchEvent(
            new CustomEvent('contract:validated', {
              detail: {
                event,
                message: `${contractName} validation ${validationStatus === 'VALID' ? 'passed' : 'failed'}`,
              },
            })
          )
        }
      } else if (isEventType(event, 'contract.normalized')) {
        const contractId = event.data.contract_id

        // Invalidate specific contract query
        if (contractId) {
          queryClient.invalidateQueries({ queryKey: queryKeys.contracts.detail(contractId) })
        }
        // Also invalidate list queries
        queryClient.invalidateQueries({ queryKey: queryKeys.contracts.lists() })

        // Show notification
        if (callbacks.showNotifications) {
          const contractName = event.data.name || 'Contract'
          const normalizationStatus = event.data.normalization_status || 'unknown'
          window.dispatchEvent(
            new CustomEvent('contract:normalized', {
              detail: {
                event,
                message: `${contractName} normalization ${normalizationStatus === 'SUCCESS' ? 'completed' : 'failed'}`,
              },
            })
          )
        }
      }
    },
    [contractId, queryClient]
  )

  // Subscribe to contract events
  const contractEventTypes: ContractEventType[] = [
    'contract.created',
    'contract.updated',
    'contract.deleted',
    'contract.validated',
    'contract.normalized',
  ]

  const { status, isConnected } = useWebSocket(enabled ? contractEventTypes : [], handleEvent)

  return {
    status,
    isConnected,
  }
}

