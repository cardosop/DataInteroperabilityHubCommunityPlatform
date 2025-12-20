/**
 * Request ID Utilities Tests
 *
 * Comprehensive tests for request ID generation utilities covering:
 * - Unique ID generation
 * - UUID v4 generation
 * - Format validation
 * - Uniqueness guarantees
 */

import { describe, it, expect } from 'vitest'
import { generateRequestId, generateUUIDRequestId } from '../requestId'

describe('requestId utilities', () => {
  describe('generateRequestId', () => {
    it('should generate a request ID with timestamp-random format', () => {
      const id = generateRequestId()

      expect(id).toBeDefined()
      expect(typeof id).toBe('string')
      expect(id.length).toBeGreaterThan(0)
      expect(id).toMatch(/^[a-z0-9]+-[a-z0-9]+$/)
    })

    it('should generate unique IDs on consecutive calls', () => {
      const id1 = generateRequestId()
      const id2 = generateRequestId()

      expect(id1).not.toBe(id2)
    })

    it('should generate unique IDs even when called rapidly', () => {
      const ids = new Set<string>()
      const iterations = 100

      for (let i = 0; i < iterations; i++) {
        ids.add(generateRequestId())
      }

      expect(ids.size).toBe(iterations)
    })

    it('should include timestamp component in the ID', () => {
      const before = Date.now()
      const id = generateRequestId()
      const after = Date.now()

      // Extract timestamp from ID (first part before dash)
      const timestampStr = id.split('-')[0]
      const timestamp = parseInt(timestampStr, 36)

      // Timestamp should be within reasonable range
      expect(timestamp).toBeGreaterThanOrEqual(before - 1000) // Allow 1s margin
      expect(timestamp).toBeLessThanOrEqual(after + 1000)
    })

    it('should generate IDs with consistent format', () => {
      const ids = Array.from({ length: 50 }, () => generateRequestId())

      ids.forEach(id => {
        expect(id).toMatch(/^[a-z0-9]+-[a-z0-9]+$/)
        const parts = id.split('-')
        expect(parts.length).toBe(2)
        expect(parts[0].length).toBeGreaterThan(0)
        expect(parts[1].length).toBeGreaterThan(0)
      })
    })

    it('should handle rapid successive calls without collisions', async () => {
      const ids = await Promise.all(
        Array.from({ length: 1000 }, () =>
          Promise.resolve(generateRequestId())
        )
      )

      const uniqueIds = new Set(ids)
      expect(uniqueIds.size).toBe(1000)
    })
  })

  describe('generateUUIDRequestId', () => {
    it('should generate a UUID v4 format ID', () => {
      const id = generateUUIDRequestId()

      expect(id).toBeDefined()
      expect(typeof id).toBe('string')
      expect(id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i)
    })

    it('should generate unique UUIDs on consecutive calls', () => {
      const id1 = generateUUIDRequestId()
      const id2 = generateUUIDRequestId()

      expect(id1).not.toBe(id2)
    })

    it('should generate unique UUIDs even when called rapidly', () => {
      const ids = new Set<string>()
      const iterations = 100

      for (let i = 0; i < iterations; i++) {
        ids.add(generateUUIDRequestId())
      }

      expect(ids.size).toBe(iterations)
    })

    it('should have correct UUID v4 format structure', () => {
      const id = generateUUIDRequestId()
      const parts = id.split('-')

      expect(parts.length).toBe(5)
      expect(parts[0].length).toBe(8)
      expect(parts[1].length).toBe(4)
      expect(parts[2].length).toBe(4)
      expect(parts[3].length).toBe(4)
      expect(parts[4].length).toBe(12)
    })

    it('should have version 4 indicator in third segment', () => {
      const ids = Array.from({ length: 100 }, () => generateUUIDRequestId())

      ids.forEach(id => {
        const parts = id.split('-')
        expect(parts[2][0]).toBe('4')
      })
    })

    it('should have variant bits set correctly in fourth segment', () => {
      const ids = Array.from({ length: 100 }, () => generateUUIDRequestId())

      ids.forEach(id => {
        const parts = id.split('-')
        const variantChar = parts[3][0].toLowerCase()
        expect(['8', '9', 'a', 'b']).toContain(variantChar)
      })
    })

    it('should generate valid hexadecimal characters only', () => {
      const id = generateUUIDRequestId()
      const hexPattern = /^[0-9a-f-]+$/i

      expect(id).toMatch(hexPattern)
    })

    it('should handle rapid successive calls without collisions', async () => {
      const ids = await Promise.all(
        Array.from({ length: 1000 }, () =>
          Promise.resolve(generateUUIDRequestId())
        )
      )

      const uniqueIds = new Set(ids)
      expect(uniqueIds.size).toBe(1000)
    })

    it('should produce different IDs from generateRequestId', () => {
      const uuidId = generateUUIDRequestId()
      const timestampId = generateRequestId()

      expect(uuidId).not.toBe(timestampId)
      expect(uuidId.length).toBeGreaterThan(timestampId.length)
    })
  })
})

