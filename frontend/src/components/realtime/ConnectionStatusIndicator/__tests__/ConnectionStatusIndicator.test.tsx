/**
 * Connection Status Indicator Tests
 *
 * Comprehensive tests for ConnectionStatusIndicator component covering:
 * - Connection state display
 * - Reconnect button functionality
 * - Tooltip display
 * - Connection loss handling
 * - Connection restoration handling
 */

import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ConnectionStatusIndicator } from '../ConnectionStatusIndicator'
import { useWebSocketConnection } from '@/hooks/useWebSocket'
import { WebSocketState } from '@/lib/api/websocket'

// Mock the useWebSocketConnection hook
vi.mock('@/hooks/useWebSocket', () => ({
  useWebSocketConnection: vi.fn(),
}))

// Mock Tooltip component
vi.mock('@/components/overlay/Tooltip', () => ({
  Tooltip: ({ children, content }: { children: React.ReactNode; content: string }) => (
    <div data-testid="tooltip" title={content}>
      {children}
    </div>
  ),
}))

describe('ConnectionStatusIndicator', () => {
  const mockConnect = vi.fn()
  const mockDisconnect = vi.fn()
  const mockOnConnectionLost = vi.fn()
  const mockOnConnectionRestored = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('Connection States', () => {
    it('should display connected state', () => {
      vi.mocked(useWebSocketConnection).mockReturnValue({
        status: {
          state: WebSocketState.CONNECTED,
          isConnected: true,
          isConnecting: false,
          isReconnecting: false,
          isDisconnected: false,
        },
        connect: mockConnect,
        disconnect: mockDisconnect,
        client: {} as any,
      })

      render(<ConnectionStatusIndicator />)

      expect(screen.getByText('Connected')).toBeInTheDocument()
    })

    it('should display connecting state', () => {
      vi.mocked(useWebSocketConnection).mockReturnValue({
        status: {
          state: WebSocketState.CONNECTING,
          isConnected: false,
          isConnecting: true,
          isReconnecting: false,
          isDisconnected: false,
        },
        connect: mockConnect,
        disconnect: mockDisconnect,
        client: {} as any,
      })

      render(<ConnectionStatusIndicator />)

      expect(screen.getByText('Connecting')).toBeInTheDocument()
    })

    it('should display reconnecting state with attempt count', () => {
      vi.mocked(useWebSocketConnection).mockReturnValue({
        status: {
          state: WebSocketState.RECONNECTING,
          isConnected: false,
          isConnecting: false,
          isReconnecting: true,
          isDisconnected: false,
          reconnectAttempt: 2,
          maxReconnectAttempts: 5,
        },
        connect: mockConnect,
        disconnect: mockDisconnect,
        client: {} as any,
      })

      render(<ConnectionStatusIndicator />)

      expect(screen.getByText(/Reconnecting.*\(2\/5\)/)).toBeInTheDocument()
    })

    it('should display error state', () => {
      vi.mocked(useWebSocketConnection).mockReturnValue({
        status: {
          state: WebSocketState.ERROR,
          isConnected: false,
          isConnecting: false,
          isReconnecting: false,
          isDisconnected: false,
          error: 'Connection failed',
        },
        connect: mockConnect,
        disconnect: mockDisconnect,
        client: {} as any,
      })

      render(<ConnectionStatusIndicator />)

      expect(screen.getByText('Error')).toBeInTheDocument()
    })

    it('should display disconnected state', () => {
      vi.mocked(useWebSocketConnection).mockReturnValue({
        status: {
          state: WebSocketState.DISCONNECTED,
          isConnected: false,
          isConnecting: false,
          isReconnecting: false,
          isDisconnected: true,
        },
        connect: mockConnect,
        disconnect: mockDisconnect,
        client: {} as any,
      })

      render(<ConnectionStatusIndicator />)

      expect(screen.getByText('Disconnected')).toBeInTheDocument()
    })
  })

  describe('Reconnect Button', () => {
    it('should show reconnect button when disconnected', () => {
      vi.mocked(useWebSocketConnection).mockReturnValue({
        status: {
          state: WebSocketState.DISCONNECTED,
          isConnected: false,
          isConnecting: false,
          isReconnecting: false,
          isDisconnected: true,
        },
        connect: mockConnect,
        disconnect: mockDisconnect,
        client: {} as any,
      })

      render(<ConnectionStatusIndicator showReconnectButton={true} />)

      const reconnectButton = screen.getByLabelText('Reconnect WebSocket')
      expect(reconnectButton).toBeInTheDocument()
    })

    it('should not show reconnect button when showReconnectButton is false', () => {
      vi.mocked(useWebSocketConnection).mockReturnValue({
        status: {
          state: WebSocketState.DISCONNECTED,
          isConnected: false,
          isConnecting: false,
          isReconnecting: false,
          isDisconnected: true,
        },
        connect: mockConnect,
        disconnect: mockDisconnect,
        client: {} as any,
      })

      render(<ConnectionStatusIndicator showReconnectButton={false} />)

      expect(screen.queryByLabelText('Reconnect WebSocket')).not.toBeInTheDocument()
    })

    it('should not show reconnect button when connected', () => {
      vi.mocked(useWebSocketConnection).mockReturnValue({
        status: {
          state: WebSocketState.CONNECTED,
          isConnected: true,
          isConnecting: false,
          isReconnecting: false,
          isDisconnected: false,
        },
        connect: mockConnect,
        disconnect: mockDisconnect,
        client: {} as any,
      })

      render(<ConnectionStatusIndicator />)

      expect(screen.queryByLabelText('Reconnect WebSocket')).not.toBeInTheDocument()
    })

    it('should call connect when reconnect button is clicked', async () => {
      const user = userEvent.setup()

      vi.mocked(useWebSocketConnection).mockReturnValue({
        status: {
          state: WebSocketState.DISCONNECTED,
          isConnected: false,
          isConnecting: false,
          isReconnecting: false,
          isDisconnected: true,
        },
        connect: mockConnect,
        disconnect: mockDisconnect,
        client: {} as any,
      })

      render(<ConnectionStatusIndicator />)

      const reconnectButton = screen.getByLabelText('Reconnect WebSocket')
      await user.click(reconnectButton)

      expect(mockConnect).toHaveBeenCalledTimes(1)
    })

    it('should disable reconnect button when connecting', () => {
      vi.mocked(useWebSocketConnection).mockReturnValue({
        status: {
          state: WebSocketState.CONNECTING,
          isConnected: false,
          isConnecting: true,
          isReconnecting: false,
          isDisconnected: false,
        },
        connect: mockConnect,
        disconnect: mockDisconnect,
        client: {} as any,
      })

      render(<ConnectionStatusIndicator />)

      // Reconnect button should not be visible when connecting
      expect(screen.queryByLabelText('Reconnect WebSocket')).not.toBeInTheDocument()
    })
  })

  describe('Tooltip', () => {
    it('should show tooltip when showTooltip is true', () => {
      vi.mocked(useWebSocketConnection).mockReturnValue({
        status: {
          state: WebSocketState.CONNECTED,
          isConnected: true,
          isConnecting: false,
          isReconnecting: false,
          isDisconnected: false,
        },
        connect: mockConnect,
        disconnect: mockDisconnect,
        client: {} as any,
      })

      render(<ConnectionStatusIndicator showTooltip={true} />)

      const tooltip = screen.getByTestId('tooltip')
      expect(tooltip).toBeInTheDocument()
      expect(tooltip).toHaveAttribute('title', 'WebSocket connection is active')
    })

    it('should not show tooltip when showTooltip is false', () => {
      vi.mocked(useWebSocketConnection).mockReturnValue({
        status: {
          state: WebSocketState.CONNECTED,
          isConnected: true,
          isConnecting: false,
          isReconnecting: false,
          isDisconnected: false,
        },
        connect: mockConnect,
        disconnect: mockDisconnect,
        client: {} as any,
      })

      render(<ConnectionStatusIndicator showTooltip={false} />)

      expect(screen.queryByTestId('tooltip')).not.toBeInTheDocument()
    })
  })

  describe('Connection Loss Handling', () => {
    it('should call onConnectionLost when connection is lost', async () => {
      // Use a mock that can change state
      let currentState = WebSocketState.CONNECTED
      vi.mocked(useWebSocketConnection).mockImplementation(() => ({
        status: {
          state: currentState,
          isConnected: currentState === WebSocketState.CONNECTED,
          isConnecting: currentState === WebSocketState.CONNECTING,
          isReconnecting: currentState === WebSocketState.RECONNECTING,
          isDisconnected: currentState === WebSocketState.DISCONNECTED,
        },
        connect: mockConnect,
        disconnect: mockDisconnect,
        client: {} as any,
      }))

      const { rerender } = render(
        <ConnectionStatusIndicator onConnectionLost={mockOnConnectionLost} onConnectionRestored={mockOnConnectionRestored} />
      )

      // Wait for initial render
      await waitFor(() => {
        expect(screen.getByText('Connected')).toBeInTheDocument()
      })

      // Connection lost - change state and rerender
      currentState = WebSocketState.DISCONNECTED
      rerender(
        <ConnectionStatusIndicator onConnectionLost={mockOnConnectionLost} onConnectionRestored={mockOnConnectionRestored} />
      )

      await waitFor(() => {
        expect(mockOnConnectionLost).toHaveBeenCalled()
      }, { timeout: 2000 })
    })

    it('should call onConnectionRestored when connection is restored', async () => {
      // Use a mock that can change state
      let currentState = WebSocketState.DISCONNECTED
      vi.mocked(useWebSocketConnection).mockImplementation(() => ({
        status: {
          state: currentState,
          isConnected: currentState === WebSocketState.CONNECTED,
          isConnecting: currentState === WebSocketState.CONNECTING,
          isReconnecting: currentState === WebSocketState.RECONNECTING,
          isDisconnected: currentState === WebSocketState.DISCONNECTED,
        },
        connect: mockConnect,
        disconnect: mockDisconnect,
        client: {} as any,
      }))

      const { rerender } = render(
        <ConnectionStatusIndicator onConnectionLost={mockOnConnectionLost} onConnectionRestored={mockOnConnectionRestored} />
      )

      // Wait for initial render
      await waitFor(() => {
        expect(screen.getByText('Disconnected')).toBeInTheDocument()
      })

      // Connection restored - change state and rerender
      currentState = WebSocketState.CONNECTED
      rerender(
        <ConnectionStatusIndicator onConnectionLost={mockOnConnectionLost} onConnectionRestored={mockOnConnectionRestored} />
      )

      await waitFor(() => {
        expect(mockOnConnectionRestored).toHaveBeenCalled()
      }, { timeout: 2000 })
    })
  })

  describe('Sizes', () => {
    it('should render with small size', () => {
      vi.mocked(useWebSocketConnection).mockReturnValue({
        status: {
          state: WebSocketState.CONNECTED,
          isConnected: true,
          isConnecting: false,
          isReconnecting: false,
          isDisconnected: false,
        },
        connect: mockConnect,
        disconnect: mockDisconnect,
        client: {} as any,
      })

      const { container } = render(<ConnectionStatusIndicator size="sm" />)

      expect(container.firstChild).toBeInTheDocument()
    })

    it('should render with medium size', () => {
      vi.mocked(useWebSocketConnection).mockReturnValue({
        status: {
          state: WebSocketState.CONNECTED,
          isConnected: true,
          isConnecting: false,
          isReconnecting: false,
          isDisconnected: false,
        },
        connect: mockConnect,
        disconnect: mockDisconnect,
        client: {} as any,
      })

      const { container } = render(<ConnectionStatusIndicator size="md" />)

      expect(container.firstChild).toBeInTheDocument()
    })

    it('should render with large size', () => {
      vi.mocked(useWebSocketConnection).mockReturnValue({
        status: {
          state: WebSocketState.CONNECTED,
          isConnected: true,
          isConnecting: false,
          isReconnecting: false,
          isDisconnected: false,
        },
        connect: mockConnect,
        disconnect: mockDisconnect,
        client: {} as any,
      })

      const { container } = render(<ConnectionStatusIndicator size="lg" />)

      expect(container.firstChild).toBeInTheDocument()
    })
  })
})

