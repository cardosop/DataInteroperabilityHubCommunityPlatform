/**
 * SyncStatusIndicator Tests
 *
 * Comprehensive tests for the SyncStatusIndicator component covering:
 * - Display queued actions count
 * - Show syncing state
 * - Display sync errors
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SyncStatusIndicator } from '../SyncStatusIndicator'

describe('SyncStatusIndicator', () => {
  describe('Rendering', () => {
    it('should display queued actions count', () => {
      render(<SyncStatusIndicator queuedCount={5} isSyncing={false} />)
      expect(screen.getByText(/5.*queued/i)).toBeInTheDocument()
    })

    it('should show syncing state', () => {
      render(<SyncStatusIndicator queuedCount={3} isSyncing={true} />)
      expect(screen.getByText(/syncing/i)).toBeInTheDocument()
    })

    it('should not render when no queued actions', () => {
      const { container } = render(<SyncStatusIndicator queuedCount={0} isSyncing={false} />)
      expect(container.firstChild).toBeNull()
    })

    it('should display sync errors', () => {
      render(
        <SyncStatusIndicator
          queuedCount={2}
          isSyncing={false}
          syncErrors={[{ actionId: '1', error: 'Network error' }]}
        />
      )
      expect(screen.getByText(/error/i)).toBeInTheDocument()
    })
  })
})

