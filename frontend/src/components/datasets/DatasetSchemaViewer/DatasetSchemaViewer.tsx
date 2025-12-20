/**
 * Dataset Schema Viewer Component
 *
 * Read-only component for displaying dataset schema information.
 * Shows field names, types, and nullable status in a table format.
 */

import React from 'react'
import {
  Box,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
} from '@mui/material'
import type { DatasetSchema, SchemaField } from '@/lib/api/datasets'

export interface DatasetSchemaViewerProps {
  /**
   * Dataset schema to display
   */
  schema: DatasetSchema | null
  /**
   * Title to display above the schema
   * @default "Schema"
   */
  title?: string
  /**
   * Whether to show the title
   * @default true
   */
  showTitle?: boolean
  /**
   * Additional className
   */
  className?: string
}

/**
 * Get type badge color
 */
const getTypeColor = (
  type: string
): 'default' | 'primary' | 'secondary' | 'success' | 'warning' | 'error' => {
  const lowerType = type.toLowerCase()
  if (lowerType.includes('string') || lowerType.includes('text')) {
    return 'primary'
  }
  if (lowerType.includes('int') || lowerType.includes('number') || lowerType.includes('float')) {
    return 'secondary'
  }
  if (lowerType.includes('bool')) {
    return 'success'
  }
  if (lowerType.includes('date') || lowerType.includes('time')) {
    return 'warning'
  }
  return 'default'
}

/**
 * Dataset Schema Viewer Component
 *
 * Displays dataset schema fields in a read-only table format.
 *
 * @example
 * ```tsx
 * <DatasetSchemaViewer
 *   schema={dataset.schema_json}
 *   title="Dataset Schema"
 * />
 * ```
 */
export const DatasetSchemaViewer: React.FC<DatasetSchemaViewerProps> = ({
  schema,
  title = 'Schema',
  showTitle = true,
  className,
}) => {
  const fields = schema?.fields || []

  // Empty state
  if (!schema || fields.length === 0) {
    return (
      <Paper sx={{ p: 3 }} className={className}>
        {showTitle && (
          <Typography variant="h6" gutterBottom>
            {title}
          </Typography>
        )}
        <Box sx={{ textAlign: 'center', py: 4 }}>
          <Typography variant="body2" color="text.secondary">
            {!schema ? 'No schema available' : 'No fields in schema'}
          </Typography>
        </Box>
      </Paper>
    )
  }

  return (
    <Paper sx={{ p: 3 }} className={className}>
      {showTitle && (
        <Typography variant="h6" gutterBottom>
          {title}
        </Typography>
      )}
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {fields.length} field{fields.length !== 1 ? 's' : ''}
      </Typography>
      <TableContainer>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell sx={{ fontWeight: 600 }}>Field Name</TableCell>
              <TableCell sx={{ fontWeight: 600 }}>Data Type</TableCell>
              <TableCell sx={{ fontWeight: 600 }}>Nullable</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {fields.map((field: SchemaField) => (
              <TableRow key={field.name} hover>
                <TableCell sx={{ fontWeight: 500 }}>{field.name}</TableCell>
                <TableCell>
                  <Chip
                    label={field.type}
                    size="small"
                    color={getTypeColor(field.type)}
                    variant="outlined"
                  />
                </TableCell>
                <TableCell>
                  <Chip
                    label={field.nullable ? 'Yes' : 'No'}
                    size="small"
                    color={field.nullable ? 'default' : 'success'}
                    variant="outlined"
                  />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Paper>
  )
}

DatasetSchemaViewer.displayName = 'DatasetSchemaViewer'

