/**
 * OfflineIndicator Tests
 *
 * Comprehensive tests for the OfflineIndicator component covering:
 * - Display when offline
 * - Hide when online
 * - Sticky positioning
 * - Non-intrusive design
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { OfflineIndicator } from '../OfflineIndicator'
import { useNetworkStatus } from '@/hooks/useNetworkStatus'

// Mock useNetworkStatus hook
vi.mock('@/hooks/useNetworkStatus', () => ({
  useNetworkStatus: vi.fn(),
}))

describe('OfflineIndicator', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('should display when offline', () => {
      vi.mocked(useNetworkStatus).mockReturnValue({
        isOnline: false,
        isOffline: true,
        isSlowConnection: false,
        effectiveType: undefined,
        downlink: undefined,
        rtt: undefined,
        saveData: undefined,
      })

      render(<OfflineIndicator />)
      expect(screen.getByText(/offline/i)).toBeInTheDocument()
    })

    it('should hide when online', () => {
      vi.mocked(useNetworkStatus).mockReturnValue({
        isOnline: true,
        isOffline: false,
        isSlowConnection: false,
        effectiveType: undefined,
        downlink: undefined,
        rtt: undefined,
        saveData: undefined,
      })

      render(<OfflineIndicator />)
      expect(screen.queryByText(/offline/i)).not.toBeInTheDocument()
    })

    it('should have sticky positioning', () => {
      vi.mocked(useNetworkStatus).mockReturnValue({
        isOnline: false,
        isOffline: true,
        isSlowConnection: false,
        effectiveType: undefined,
        downlink: undefined,
        rtt: undefined,
        saveData: undefined,
      })

      const { container } = render(<OfflineIndicator />)
      const banner = container.querySelector('.MuiAlert-root')
      expect(banner).toHaveStyle({ position: 'sticky' })
    })
  })

  describe('Slow Connection', () => {
    it('should display slow connection message', () => {
      vi.mocked(useNetworkStatus).mockReturnValue({
        isOnline: true,
        isOffline: false,
        isSlowConnection: true,
        effectiveType: '2g' as const,
        downlink: undefined,
        rtt: undefined,
        saveData: undefined,
      })

      render(<OfflineIndicator />)
      expect(screen.getByText(/slow connection/i)).toBeInTheDocument()
    })
  })
})

