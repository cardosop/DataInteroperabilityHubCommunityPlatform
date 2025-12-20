/**
 * React hook to generate unique IDs
 * Falls back to a counter if React.useId is not available
 */
import { useId as useReactId } from 'react'

export function useId(prefix?: string): string {
  const id = useReactId()
  return prefix ? `${prefix}-${id}` : id
}

