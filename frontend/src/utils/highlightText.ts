/**
 * highlightText Utility
 *
 * Utility function for highlighting search terms in text.
 */

export interface HighlightOptions {
  /**
   * Case sensitive matching
   */
  caseSensitive?: boolean
  /**
   * Custom highlight component/tag
   */
  highlightTag?: string
  /**
   * CSS class for highlight
   */
  highlightClass?: string
  /**
   * Inline styles for highlight
   */
  highlightStyle?: React.CSSProperties
}

/**
 * Highlight search terms in text
 */
export function highlightText(
  text: string,
  searchTerms: string | string[],
  options: HighlightOptions = {}
): React.ReactNode {
  const {
    caseSensitive = false,
    highlightTag = 'mark',
    highlightClass = '',
    highlightStyle = { backgroundColor: 'yellow', padding: 0 },
  } = options

  if (!text || !searchTerms) return text

  const terms = Array.isArray(searchTerms) ? searchTerms : [searchTerms]
  if (terms.length === 0) return text

  // Create regex pattern from search terms
  const pattern = terms
    .map((term) => term.trim())
    .filter(Boolean)
    .map((term) => term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    .join('|')

  if (!pattern) return text

  const regex = new RegExp(`(${pattern})`, caseSensitive ? 'g' : 'gi')
  const parts = text.split(regex)

  return (
    <>
      {parts.map((part, index) => {
        const isMatch = terms.some((term) => {
          const termLower = term.toLowerCase()
          const partLower = part.toLowerCase()
          return caseSensitive ? part === term : partLower === termLower
        })

        if (isMatch) {
          const Tag = highlightTag as keyof JSX.IntrinsicElements
          return (
            <Tag key={index} className={highlightClass} style={highlightStyle}>
              {part}
            </Tag>
          )
        }
        return <React.Fragment key={index}>{part}</React.Fragment>
      })}
    </>
  )
}

/**
 * Extract search terms from query string
 */
export function extractSearchTerms(query: string): string[] {
  if (!query) return []

  // Remove quotes and split by spaces
  return query
    .replace(/["']/g, '')
    .split(/\s+/)
    .filter(Boolean)
    .map((term) => term.trim())
}

