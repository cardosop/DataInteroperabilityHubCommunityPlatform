/**
 * Real-Time Assets Hook Tests
 *
 * Comprehensive tests for useRealtimeAssets hook covering:
 * - WebSocket event subscription
 * - React Query cache invalidation
 * - Event filtering by asset ID
 * - Custom callbacks
 * - Notification events
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useRealtimeAssets } from '../useRealtimeAssets'
import { createHookWrapper } from './test-utils'
import type { AssetCreatedEvent, AssetUpdatedEvent } from '@/lib/api/websocket-events'

// Mock useWebSocket
vi.mock('../useWebSocket', () => ({
  useWebSocket: vi.fn(),
}))

// Mock query keys
vi.mock('@/lib/api/react-query', () => ({
  queryKeys: {
    assets: {
      all: ['queries', 'assets'],
      lists: () => ['queries', 'assets', 'list'],
      list: (filters?: Record<string, any>) => ['queries', 'assets', 'list', filters],
      details: () => ['queries', 'assets', 'detail'],
      detail: (id: string) => ['queries', 'assets', 'detail', id],
    },
    marketplace: {
      all: ['queries', 'marketplace'],
    },
  },
}))

describe('useRealtimeAssets', () => {
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

  it('should subscribe to asset events', () => {
    const wrapper = createHookWrapper(queryClient)
    renderHook(() => useRealtimeAssets(), { wrapper })

    expect(mockUseWebSocket).toHaveBeenCalledWith(
      ['asset.created', 'asset.updated', 'asset.activated', 'asset.published', 'asset.retired'],
      expect.any(Function)
    )
  })

  it('should not subscribe when enabled is false', () => {
    const wrapper = createHookWrapper(queryClient)
    renderHook(() => useRealtimeAssets({ enabled: false }), { wrapper })

    expect(mockUseWebSocket).toHaveBeenCalledWith([], expect.any(Function))
  })

  it('should invalidate queries on asset.created event', async () => {
    const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries')
    const wrapper = createHookWrapper(queryClient)
    renderHook(() => useRealtimeAssets(), { wrapper })

    // Wait for hook to set up event handler
    await waitFor(() => {
      expect(eventHandler).not.toBeNull()
    })

    const event: AssetCreatedEvent = {
      event_id: 'event-1',
      event_type: 'asset.created',
      event_version: '1.0.0',
      timestamp: new Date().toISOString(),
      source: {
        service: 'hub',
        tenant_id: 'tenant-1',
      },
      data: {
        asset_id: 'asset-1',
        key: 'test-asset',
        name: 'Test Asset',
        status: 'ACTIVE',
        tenant_id: 'tenant-1',
      },
    }

    await act(async () => {
      eventHandler?.(event)
    })

    await waitFor(() => {
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: ['queries', 'assets', 'list'],
      })
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: ['queries', 'assets'],
      })
    })
  })

  it('should invalidate specific asset query on asset.updated event', async () => {
    const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries')
    const wrapper = createHookWrapper(queryClient)
    renderHook(() => useRealtimeAssets(), { wrapper })

    // Wait for hook to set up event handler
    await waitFor(() => {
      expect(eventHandler).not.toBeNull()
    })

    const event: AssetUpdatedEvent = {
      event_id: 'event-2',
      event_type: 'asset.updated',
      event_version: '1.0.0',
      timestamp: new Date().toISOString(),
      source: {
        service: 'hub',
        tenant_id: 'tenant-1',
      },
      data: {
        asset_id: 'asset-1',
        name: 'Updated Asset',
      },
    }

    await act(async () => {
      eventHandler?.(event)
    })

    await waitFor(() => {
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: ['queries', 'assets', 'detail', 'asset-1'],
      })
      expect(invalidateQueriesSpy).toHaveBeenCalledWith({
        queryKey: ['queries', 'assets', 'list'],
      })
    })
  })

  it('should filter events by asset ID when specified', async () => {
    const invalidateQueriesSpy = vi.spyOn(queryClient, 'invalidateQueries')
    const onAssetUpdated = vi.fn()
    const wrapper = createHookWrapper(queryClient)
    renderHook(() => useRealtimeAssets({ assetId: 'asset-1', onAssetUpdated }), { wrapper })

    // Wait for hook to set up event handler
    await waitFor(() => {
      expect(eventHandler).not.toBeNull()
    })

    // Event for different asset - should be ignored
    const event1: AssetUpdatedEvent = {
      event_id: 'event-1',
      event_type: 'asset.updated',
      event_version: '1.0.0',
      timestamp: new Date().toISOString(),
      source: {
        service: 'hub',
        tenant_id: 'tenant-1',
      },
      data: {
        asset_id: 'asset-2',
        name: 'Other Asset',
      },
    }

    await act(async () => {
      eventHandler?.(event1)
    })

    await waitFor(() => {
      expect(invalidateQueriesSpy).not.toHaveBeenCalled()
      expect(onAssetUpdated).not.toHaveBeenCalled()
    })

    // Event for matching asset - should be processed
    const event2: AssetUpdatedEvent = {
      event_id: 'event-2',
      event_type: 'asset.updated',
      event_version: '1.0.0',
      timestamp: new Date().toISOString(),
      source: {
        service: 'hub',
        tenant_id: 'tenant-1',
      },
      data: {
        asset_id: 'asset-1',
        name: 'Updated Asset',
      },
    }

    await act(async () => {
      eventHandler?.(event2)
    })

    await waitFor(() => {
      expect(invalidateQueriesSpy).toHaveBeenCalled()
      expect(onAssetUpdated).toHaveBeenCalledWith(event2)
    })
  })

  it('should call custom callbacks when provided', async () => {
    const onAssetCreated = vi.fn()
    const onAssetActivated = vi.fn()
    const wrapper = createHookWrapper(queryClient)
    renderHook(() => useRealtimeAssets({ onAssetCreated, onAssetActivated }), { wrapper })

    const createdEvent: AssetCreatedEvent = {
      event_id: 'event-1',
      event_type: 'asset.created',
      event_version: '1.0.0',
      timestamp: new Date().toISOString(),
      source: {
        service: 'hub',
        tenant_id: 'tenant-1',
      },
      data: {
        asset_id: 'asset-1',
        key: 'test-asset',
        name: 'Test Asset',
        status: 'ACTIVE',
        tenant_id: 'tenant-1',
      },
    }

    await act(async () => {
      eventHandler?.(createdEvent)
    })

    await waitFor(() => {
      expect(onAssetCreated).toHaveBeenCalledWith(createdEvent)
    })
  })

  it('should dispatch custom events for notifications', async () => {
    const dispatchEventSpy = vi.spyOn(window, 'dispatchEvent')
    const wrapper = createHookWrapper(queryClient)
    renderHook(() => useRealtimeAssets({ showNotifications: true }), { wrapper })

    const event: AssetCreatedEvent = {
      event_id: 'event-1',
      event_type: 'asset.created',
      event_version: '1.0.0',
      timestamp: new Date().toISOString(),
      source: {
        service: 'hub',
        tenant_id: 'tenant-1',
      },
      data: {
        asset_id: 'asset-1',
        key: 'test-asset',
        name: 'Test Asset',
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
          type: 'asset:created',
          detail: expect.objectContaining({
            event,
            message: 'Test Asset was created',
          }),
        })
      )
    })
  })

  it('should not dispatch notification events when showNotifications is false', async () => {
    const dispatchEventSpy = vi.spyOn(window, 'dispatchEvent')
    const wrapper = createHookWrapper(queryClient)
    renderHook(() => useRealtimeAssets({ showNotifications: false }), { wrapper })

    const event: AssetCreatedEvent = {
      event_id: 'event-1',
      event_type: 'asset.created',
      event_version: '1.0.0',
      timestamp: new Date().toISOString(),
      source: {
        service: 'hub',
        tenant_id: 'tenant-1',
      },
      data: {
        asset_id: 'asset-1',
        key: 'test-asset',
        name: 'Test Asset',
        status: 'ACTIVE',
        tenant_id: 'tenant-1',
      },
    }

    await act(async () => {
      eventHandler?.(event)
    })

    await waitFor(() => {
      expect(dispatchEventSpy).not.toHaveBeenCalled()
    })
  })
})

