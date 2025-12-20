/**
 * Real-Time Contracts Hook Tests
 *
 * Comprehensive tests for useRealtimeContracts hook covering:
 * - WebSocket event subscription
 * - React Query cache invalidation
 * - Event filtering by contract ID
 * - Custom callbacks
 * - Notification events
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useRealtimeContracts } from '../useRealtimeContracts'
import { createHookWrapper } from './test-utils'
import type { ContractCreatedEvent, ContractUpdatedEvent } from '@/lib/api/websocket-events'

// Mock useWebSocket
vi.mock('../useWebSocket', () => ({
  useWebSocket: vi.fn(),
}))

// Mock query keys
vi.mock('@/lib/api/react-query', () => ({
  queryKeys: {
    contracts: {
      all: ['queries', 'contracts'],
      lists: () => ['queries', 'contracts', 'list'],
      list: (filters?: Record<string, any>) => ['queries', 'contracts', 'list', filters],
      details: () => ['queries', 'contracts', 'detail'],
      detail: (id: string) => ['queries', 'contracts', 'detail', id],
    },
  },
}))

describe('useRealtimeContracts', () => {
  let queryClient: QueryClient
  let mockUseWebSocket: ReturnType<typeof vi.fn>
  let eventHandler: ((event: any) => void) | null = null

  beforeEach(async () => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    })

    // Mock useWebSocket to capture event handler
    mockUseWebSocket = vi.fn((eventTypes, onEvent) => {
      eventHandler = onEvent
      return {
        status: { isConnected: true, state: 'CONNECTED' },
        isConnected: true,
      }
    })

    const { useWebSocket } = await import('../useWebSocket')
    vi.mocked(useWebSocket).mockImplementation(mockUseWebSocket as any)
  })

  afterEach(() => {
    vi.clearAllMocks()
    eventHandler = null
  })

  it('should subscribe to contract events', () => {
    const wrapper = createHookWrapper(queryClient)
    renderHook(() => useRealtimeContracts(), { wrapper })

    expect(mockUseWebSocket).toHaveBeenCalledWith(
      ['contract.created', 'contract.updated', 'contract.deleted', 'contract.validated', 'contract.normalized'],
      expect.any(Function)
    )
  })

  it('should not subscribe when enabled is false', () => {
    const wrapper = createHookWrapper(queryClient)
    renderHook(() => useRealtimeContracts({ enabled: false }), { wrapper })

    expect(mockUseWebSocket).toHaveBeenCalledWith([], expect.any(Function))
  })

  it('should invalidate queries on contract.created event', async () => {
    const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries')
    const wrapper = createHookWrapper(queryClient)
    renderHook(() => useRealtimeContracts(), { wrapper })

    // Wait for hook to set up event handler
    await waitFor(() => {
      expect(eventHandler).not.toBeNull()
    })

    const event: ContractCreatedEvent = {
      event_id: 'event-1',
      event_type: 'contract.created',
      event_version: '1.0.0',
      timestamp: new Date().toISOString(),
      source: {
        service: 'hub',
        tenant_id: 'tenant-1',
      },
      data: {
        contract_id: 'contract-1',
        name: 'Test Contract',
        status: 'ACTIVE',
        tenant_id: 'tenant-1',
      },
    }

    await act(async () => {
      eventHandler?.(event)
    })

    await waitFor(() => {
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: ['queries', 'contracts', 'list'],
      })
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: ['queries', 'contracts'],
      })
    })
  })

  it('should invalidate specific contract query on contract.updated event', async () => {
    const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries')
    const wrapper = createHookWrapper(queryClient)
    renderHook(() => useRealtimeContracts(), { wrapper })

    // Wait for hook to set up event handler
    await waitFor(() => {
      expect(eventHandler).not.toBeNull()
    })

    const event: ContractUpdatedEvent = {
      event_id: 'event-2',
      event_type: 'contract.updated',
      event_version: '1.0.0',
      timestamp: new Date().toISOString(),
      source: {
        service: 'hub',
        tenant_id: 'tenant-1',
      },
      data: {
        contract_id: 'contract-1',
        name: 'Updated Contract',
      },
    }

    await act(async () => {
      eventHandler?.(event)
    })

    await waitFor(() => {
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: ['queries', 'contracts', 'detail', 'contract-1'],
      })
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: ['queries', 'contracts', 'list'],
      })
    })
  })

  it('should filter events by contract ID when specified', async () => {
    const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries')
    const onContractUpdated = vi.fn()
    const wrapper = createHookWrapper(queryClient)
    renderHook(() => useRealtimeContracts({ contractId: 'contract-1', onContractUpdated }), { wrapper })

    // Wait for hook to set up event handler
    await waitFor(() => {
      expect(eventHandler).not.toBeNull()
    })

    // Event for different contract - should be ignored
    const event1: ContractUpdatedEvent = {
      event_id: 'event-1',
      event_type: 'contract.updated',
      event_version: '1.0.0',
      timestamp: new Date().toISOString(),
      source: {
        service: 'hub',
        tenant_id: 'tenant-1',
      },
      data: {
        contract_id: 'contract-2',
        name: 'Other Contract',
      },
    }

    await act(async () => {
      eventHandler?.(event1)
    })

    await waitFor(() => {
      expect(invalidateQueriesSpy).not.toHaveBeenCalled()
      expect(onContractUpdated).not.toHaveBeenCalled()
    })

    // Event for matching contract - should be processed
    const event2: ContractUpdatedEvent = {
      event_id: 'event-2',
      event_type: 'contract.updated',
      event_version: '1.0.0',
      timestamp: new Date().toISOString(),
      source: {
        service: 'hub',
        tenant_id: 'tenant-1',
      },
      data: {
        contract_id: 'contract-1',
        name: 'Updated Contract',
      },
    }

    await act(async () => {
      eventHandler?.(event2)
    })

    await waitFor(() => {
      expect(invalidateQueriesSpy).toHaveBeenCalled()
      expect(onContractUpdated).toHaveBeenCalledWith(event2)
    })
  })

  it('should call custom callbacks when provided', async () => {
    const onContractCreated = vi.fn()
    const onContractValidated = vi.fn()
    const wrapper = createHookWrapper(queryClient)
    renderHook(() => useRealtimeContracts({ onContractCreated, onContractValidated }), { wrapper })

    const createdEvent: ContractCreatedEvent = {
      event_id: 'event-1',
      event_type: 'contract.created',
      event_version: '1.0.0',
      timestamp: new Date().toISOString(),
      source: {
        service: 'hub',
        tenant_id: 'tenant-1',
      },
      data: {
        contract_id: 'contract-1',
        name: 'Test Contract',
        status: 'ACTIVE',
        tenant_id: 'tenant-1',
      },
    }

    await act(async () => {
      eventHandler?.(createdEvent)
    })

    await waitFor(() => {
      expect(onContractCreated).toHaveBeenCalledWith(createdEvent)
    })
  })

  it('should dispatch custom events for notifications', async () => {
    const dispatchEventSpy = vi.spyOn(window, 'dispatchEvent')
    const wrapper = createHookWrapper(queryClient)
    renderHook(() => useRealtimeContracts({ showNotifications: true }), { wrapper })

    const event: ContractCreatedEvent = {
      event_id: 'event-1',
      event_type: 'contract.created',
      event_version: '1.0.0',
      timestamp: new Date().toISOString(),
      source: {
        service: 'hub',
        tenant_id: 'tenant-1',
      },
      data: {
        contract_id: 'contract-1',
        name: 'Test Contract',
        status: 'ACTIVE',
        tenant_id: 'tenant-1',
      },
    }

    await act(async () => {
      eventHandler?.(event)
    })

    await waitFor(() => {
      expect(dispatchEventSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          type: 'contract:created',
          detail: expect.objectContaining({
            event,
            message: 'Test Contract was created',
          }),
        })
      )
    })
  })
})

