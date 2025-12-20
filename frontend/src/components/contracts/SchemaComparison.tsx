/**
 * SchemaComparison Component
 *
 * Component for comparing inferred schema with contract schema (contract-first flow):
 * - Inferred schema display (from dataset)
 * - Contract schema display
 * - Diff view (highlight differences)
 * - Accept/reject inferred fields
 * - Merge functionality
 */

import React, { useState } from 'react'
import {
  Box,
  Typography,
  Grid,
  Button,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  IconButton,
  Tooltip,
} from '@mui/material'
import {
  Check as CheckIcon,
  Close as CloseIcon,
  MergeType as MergeIcon,
} from '@mui/icons-material'
import type { SchemaField, SchemaComparison as SchemaComparisonType } from './types'
import { compareSchemaFields } from './utils'

export interface SchemaComparisonProps {
  inferredSchema: SchemaField[]
  contractSchema: SchemaField[]
  onAcceptField: (field: SchemaField) => void
  onRejectField: (fieldName: string) => void
  onMergeSchemas: (mergedSchema: SchemaField[]) => void
}

/**
 * SchemaComparison component
 */
export const SchemaComparison: React.FC<SchemaComparisonProps> = ({
  inferredSchema,
  contractSchema,
  onAcceptField,
  onRejectField,
  onMergeSchemas,
}) => {
  const [acceptedFields, setAcceptedFields] = useState<Set<string>>(new Set())
  const [rejectedFields, setRejectedFields] = useState<Set<string>>(new Set())

  const comparison = compareSchemaFields(inferredSchema, contractSchema)

  const handleAcceptField = (field: SchemaField) => {
    setAcceptedFields(new Set([...acceptedFields, field.name]))
    setRejectedFields(new Set([...rejectedFields].filter((f) => f !== field.name)))
    onAcceptField(field)
  }

  const handleRejectField = (fieldName: string) => {
    setRejectedFields(new Set([...rejectedFields, fieldName]))
    setAcceptedFields(new Set([...acceptedFields].filter((f) => f !== fieldName)))
    onRejectField(fieldName)
  }

  const handleMergeAll = () => {
    const merged: SchemaField[] = [...contractSchema]

    // Add accepted new fields
    for (const field of comparison.differences.added) {
      if (acceptedFields.has(field.name)) {
        merged.push(field)
      }
    }

    // Update modified fields that are accepted
    for (const diff of comparison.differences.modified) {
      if (acceptedFields.has(diff.field)) {
        const index = merged.findIndex((f) => f.name === diff.field)
        if (index >= 0) {
          merged[index] = diff.inferred
        }
      }
    }

    onMergeSchemas(merged)
  }

  return (
    <Box sx={{ padding: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h6" sx={{ fontWeight: 600 }}>
          Schema Comparison
        </Typography>
        <Button
          variant="contained"
          startIcon={<MergeIcon />}
          onClick={handleMergeAll}
          disabled={acceptedFields.size === 0}
        >
          Merge Accepted Changes
        </Button>
      </Box>

      <Grid container spacing={3}>
        {/* Added Fields */}
        {comparison.differences.added.length > 0 && (
          <Grid item xs={12}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2, color: 'success.main' }}>
                New Fields in Inferred Schema ({comparison.differences.added.length})
              </Typography>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Field Name</TableCell>
                      <TableCell>Data Type</TableCell>
                      <TableCell>Nullable</TableCell>
                      <TableCell>Description</TableCell>
                      <TableCell align="right">Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {comparison.differences.added.map((field) => {
                      const isAccepted = acceptedFields.has(field.name)
                      const isRejected = rejectedFields.has(field.name)
                      return (
                        <TableRow
                          key={field.name}
                          sx={{
                            backgroundColor: isAccepted ? 'success.light' : isRejected ? 'error.light' : 'transparent',
                          }}
                        >
                          <TableCell sx={{ fontWeight: 500 }}>{field.name}</TableCell>
                          <TableCell>
                            <Chip label={field.data_type} size="small" />
                          </TableCell>
                          <TableCell>{field.nullable ? 'Yes' : 'No'}</TableCell>
                          <TableCell>{field.description || '—'}</TableCell>
                          <TableCell align="right">
                            {!isAccepted && !isRejected && (
                              <>
                                <Tooltip title="Accept field">
                                  <IconButton
                                    size="small"
                                    color="success"
                                    onClick={() => handleAcceptField(field)}
                                  >
                                    <CheckIcon />
                                  </IconButton>
                                </Tooltip>
                                <Tooltip title="Reject field">
                                  <IconButton
                                    size="small"
                                    color="error"
                                    onClick={() => handleRejectField(field.name)}
                                  >
                                    <CloseIcon />
                                  </IconButton>
                                </Tooltip>
                              </>
                            )}
                            {isAccepted && (
                              <Chip label="Accepted" size="small" color="success" />
                            )}
                            {isRejected && (
                              <Chip label="Rejected" size="small" color="error" />
                            )}
                          </TableCell>
                        </TableRow>
                      )
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          </Grid>
        )}

        {/* Modified Fields */}
        {comparison.differences.modified.length > 0 && (
          <Grid item xs={12}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2, color: 'warning.main' }}>
                Modified Fields ({comparison.differences.modified.length})
              </Typography>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Field Name</TableCell>
                      <TableCell>Contract Schema</TableCell>
                      <TableCell>Inferred Schema</TableCell>
                      <TableCell>Differences</TableCell>
                      <TableCell align="right">Actions</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {comparison.differences.modified.map((diff) => {
                      const isAccepted = acceptedFields.has(diff.field)
                      const isRejected = rejectedFields.has(diff.field)
                      return (
                        <TableRow
                          key={diff.field}
                          sx={{
                            backgroundColor: isAccepted ? 'success.light' : isRejected ? 'error.light' : 'transparent',
                          }}
                        >
                          <TableCell sx={{ fontWeight: 500 }}>{diff.field}</TableCell>
                          <TableCell>
                            <Box>
                              <Chip label={diff.contract.data_type} size="small" sx={{ mb: 0.5 }} />
                              <Typography variant="caption" display="block">
                                Nullable: {diff.contract.nullable ? 'Yes' : 'No'}
                              </Typography>
                            </Box>
                          </TableCell>
                          <TableCell>
                            <Box>
                              <Chip label={diff.inferred.data_type} size="small" sx={{ mb: 0.5 }} />
                              <Typography variant="caption" display="block">
                                Nullable: {diff.inferred.nullable ? 'Yes' : 'No'}
                              </Typography>
                            </Box>
                          </TableCell>
                          <TableCell>
                            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                              {diff.differences.map((d, idx) => (
                                <Typography key={idx} variant="caption" color="warning.main">
                                  {d}
                                </Typography>
                              ))}
                            </Box>
                          </TableCell>
                          <TableCell align="right">
                            {!isAccepted && !isRejected && (
                              <>
                                <Tooltip title="Accept inferred schema">
                                  <IconButton
                                    size="small"
                                    color="success"
                                    onClick={() => handleAcceptField(diff.inferred)}
                                  >
                                    <CheckIcon />
                                  </IconButton>
                                </Tooltip>
                                <Tooltip title="Keep contract schema">
                                  <IconButton
                                    size="small"
                                    color="error"
                                    onClick={() => handleRejectField(diff.field)}
                                  >
                                    <CloseIcon />
                                  </IconButton>
                                </Tooltip>
                              </>
                            )}
                            {isAccepted && (
                              <Chip label="Accepted" size="small" color="success" />
                            )}
                            {isRejected && (
                              <Chip label="Rejected" size="small" color="error" />
                            )}
                          </TableCell>
                        </TableRow>
                      )
                    })}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          </Grid>
        )}

        {/* Removed Fields */}
        {comparison.differences.removed.length > 0 && (
          <Grid item xs={12}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 2, color: 'error.main' }}>
                Fields Removed from Inferred Schema ({comparison.differences.removed.length})
              </Typography>
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Field Name</TableCell>
                      <TableCell>Data Type</TableCell>
                      <TableCell>Nullable</TableCell>
                      <TableCell>Description</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {comparison.differences.removed.map((field) => (
                      <TableRow key={field.name}>
                        <TableCell sx={{ fontWeight: 500 }}>{field.name}</TableCell>
                        <TableCell>
                          <Chip label={field.data_type} size="small" />
                        </TableCell>
                        <TableCell>{field.nullable ? 'Yes' : 'No'}</TableCell>
                        <TableCell>{field.description || '—'}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          </Grid>
        )}

        {/* No Differences */}
        {comparison.differences.added.length === 0 &&
          comparison.differences.modified.length === 0 &&
          comparison.differences.removed.length === 0 && (
            <Grid item xs={12}>
              <Paper sx={{ p: 4, textAlign: 'center' }}>
                <Typography variant="body1" color="success.main">
                  No differences found. Contract schema matches inferred schema.
                </Typography>
              </Paper>
            </Grid>
          )}
      </Grid>
    </Box>
  )
}

SchemaComparison.displayName = 'SchemaComparison'

