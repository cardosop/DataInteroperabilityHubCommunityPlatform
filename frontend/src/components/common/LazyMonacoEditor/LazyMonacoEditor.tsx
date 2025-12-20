/**
 * LazyMonacoEditor Component
 *
 * Lazy-loaded wrapper for Monaco Editor to enable component-based code splitting.
 * Monaco Editor is a heavy library (~2MB) and should be loaded only when needed.
 */

import React, { Suspense, ComponentType } from 'react'
import { Box, CircularProgress, Typography } from '@mui/material'

// Lazy load Monaco Editor
const MonacoEditorLazy = React.lazy(() => import('@monaco-editor/react'))

/**
 * Loading fallback for Monaco Editor
 */
const MonacoEditorFallback: React.FC = () => (
  <Box
    sx={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '200px',
      gap: 2,
    }}
  >
    <CircularProgress size={40} />
    <Typography variant="body2" color="text.secondary">
      Loading editor...
    </Typography>
  </Box>
)

/**
 * Props for LazyMonacoEditor (matches @monaco-editor/react Editor props)
 */
export interface LazyMonacoEditorProps {
  /**
   * Editor value
   */
  value?: string
  /**
   * Default value
   */
  defaultValue?: string
  /**
   * Language (e.g., 'javascript', 'typescript', 'yaml', 'json')
   */
  language?: string
  /**
   * Theme
   */
  theme?: string
  /**
   * Editor options
   */
  options?: any
  /**
   * On change handler
   */
  onChange?: (value: string | undefined) => void
  /**
   * On mount handler
   */
  onMount?: (editor: any, monaco: any) => void
  /**
   * Height
   */
  height?: string | number
  /**
   * Width
   */
  width?: string | number
  /**
   * Loading component
   */
  loading?: React.ReactNode
  /**
   * Custom fallback component
   */
  fallback?: React.ReactNode
  /**
   * Other props
   */
  [key: string]: any
}

/**
 * LazyMonacoEditor component
 *
 * Wraps Monaco Editor with lazy loading and Suspense boundary.
 * The editor chunk will only be loaded when this component is rendered.
 *
 * @example
 * ```tsx
 * <LazyMonacoEditor
 *   language="yaml"
 *   value={yamlContent}
 *   onChange={handleChange}
 *   height="500px"
 * />
 * ```
 */
export const LazyMonacoEditor: React.FC<LazyMonacoEditorProps> = ({
  fallback,
  ...editorProps
}) => {
  return (
    <Suspense fallback={fallback || <MonacoEditorFallback />}>
      <MonacoEditorLazy {...editorProps} />
    </Suspense>
  )
}

/**
 * Preload Monaco Editor chunk
 * Useful for prefetching the editor before it's needed
 *
 * @example
 * ```tsx
 * // Preload on hover
 * <Button
 *   onMouseEnter={() => preloadMonacoEditor()}
 *   onClick={() => setShowEditor(true)}
 * >
 *   Open Editor
 * </Button>
 * ```
 */
export async function preloadMonacoEditor(): Promise<void> {
  await import('@monaco-editor/react')
}

