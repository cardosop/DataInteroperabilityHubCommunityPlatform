/**
 * NetworkErrorBanner Tests
 *
 * Comprehensive tests for the NetworkErrorBanner component covering:
 * - Network status display
 * - Offline/online states
 * - Slow connection detection
 * - Auto-dismiss on reconnect
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { NetworkErrorBanner } from '../NetworkErrorBanner'
import { useNetworkStatus } from '@/hooks/useNetworkStatus'

// Mock useNetworkStatus hook
vi.mock('@/hooks/useNetworkStatus', () => ({
  useNetworkStatus: vi.fn(),
}))

describe('NetworkErrorBanner', () => {
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

      render(<NetworkErrorBanner />)
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

      const { container } = render(<NetworkErrorBanner />)
      expect(container.firstChild).toBeNull()
    })

    it('should display slow connection warning', () => {
      vi.mocked(useNetworkStatus).mockReturnValue({
        isOnline: true,
        isOffline: false,
        isSlowConnection: true,
        effectiveType: '2g' as const,
        downlink: undefined,
        rtt: undefined,
        saveData: undefined,
      })

      render(<NetworkErrorBanner />)
      expect(screen.getByText(/slow connection/i)).toBeInTheDocument()
    })
  })

  describe('Sticky Positioning', () => {
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

      const { container } = render(<NetworkErrorBanner />)
      const banner = container.querySelector('.MuiAlert-root')
      expect(banner?.parentElement).toHaveStyle({ position: 'sticky' })
    })
  })
})

