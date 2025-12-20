/**
 * Factory Utilities
 *
 * Shared utilities for test data factories.
 */

/**
 * Counter for generating unique IDs
 */
let idCounter = 0

/**
 * Generate a unique ID with optional prefix
 *
 * @param prefix - ID prefix
 * @returns Unique ID string
 */
export function generateId(prefix: string = 'test'): string {
  idCounter++
  return `${prefix}-${idCounter}-${Date.now()}`
}

/**
 * Reset ID counter (useful for test cleanup)
 */
export function resetIdCounter(): void {
  idCounter = 0
}

/**
 * Generate a UUID-like string (for realistic test data)
 *
 * @returns UUID-like string
 */
export function generateUUID(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

/**
 * Generate a random integer between min and max (inclusive)
 *
 * @param min - Minimum value
 * @param max - Maximum value
 * @returns Random integer
 */
export function randomInt(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min
}

/**
 * Pick a random element from an array
 *
 * @param array - Array to pick from
 * @returns Random element
 */
export function randomElement<T>(array: T[]): T {
  return array[Math.floor(Math.random() * array.length)]
}

/**
 * Generate a random date within a range
 *
 * @param startDate - Start date (default: 30 days ago)
 * @param endDate - End date (default: now)
 * @returns ISO date string
 */
export function randomDate(
  startDate: Date = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
  endDate: Date = new Date()
): string {
  const time = startDate.getTime() + Math.random() * (endDate.getTime() - startDate.getTime())
  return new Date(time).toISOString()
}

/**
 * Generate a random email address
 *
 * @param domain - Email domain (default: 'test.com')
 * @returns Random email address
 */
export function randomEmail(domain: string = 'test.com'): string {
  return `user-${generateId('email')}@${domain}`
}

/**
 * Generate a random string
 *
 * @param length - String length (default: 10)
 * @returns Random string
 */
export function randomString(length: number = 10): string {
  const chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
  return Array.from({ length }, () => chars[Math.floor(Math.random() * chars.length)]).join('')
}

/**
 * Factory options interface
 */
export interface FactoryOptions<T = Record<string, any>> {
  /**
   * Override specific fields
   */
  overrides?: Partial<T>
  /**
   * Generate unique IDs
   * @default true
   */
  uniqueIds?: boolean
}

/**
 * Base factory trait interface
 */
export interface FactoryTrait<T> {
  /**
   * Build a single instance
   */
  build(options?: FactoryOptions<T>): T
  /**
   * Build multiple instances
   */
  buildMany(count: number, options?: FactoryOptions<T>): T[]
  /**
   * Build a sequence with custom builder function
   */
  buildSequence(builder: (index: number) => Partial<T>): T[]
}

