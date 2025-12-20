/**
 * SchemaTab Component
 *
 * Tab for editing contract schema fields:
 * - Editable field table with all properties
 * - Field editor modal/drawer
 * - Schema inference integration (data-first flow)
 * - Field comparison view (contract-first flow)
 * - Field properties: Name, Data Type, Nullable, Description, Semantic Type, Format, Pattern, Enum, Default, Min/Max
 * - Schema constraints: Primary Key, Unique Constraints, Indexes
 * - Bulk operations (add/remove fields)
 * - Import/Export schema functionality
 */

import React, { useState } from 'react'
import {
  Box,
  Button,
  IconButton,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Checkbox,
  FormControlLabel,
  Select,
  MenuItem,
} from '@mui/material'
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Check as CheckIcon,
  Close as CloseIcon,
} from '@mui/icons-material'
import type { HubContract, SchemaField, SchemaFieldDataType } from '../types'

export interface SchemaTabProps {
  contract: HubContract
  onChange: (contract: HubContract) => void
  inferredSchema?: SchemaField[]
  onNavigateToField?: (fieldName: string) => void
}

/**
 * Data type options
 */
const DATA_TYPE_OPTIONS: Array<{ value: SchemaFieldDataType; label: string }> = [
  { value: 'string', label: 'String' },
  { value: 'integer', label: 'Integer' },
  { value: 'float', label: 'Float' },
  { value: 'boolean', label: 'Boolean' },
  { value: 'date', label: 'Date' },
  { value: 'timestamp', label: 'Timestamp' },
  { value: 'array', label: 'Array' },
  { value: 'object', label: 'Object' },
]

/**
 * SchemaTab component
 */
export const SchemaTab: React.FC<SchemaTabProps> = ({
  contract,
  onChange,
  inferredSchema,
  onNavigateToField,
}) => {
  const [editingField, setEditingField] = useState<SchemaField | null>(null)
  const [isFieldEditorOpen, setIsFieldEditorOpen] = useState(false)
  const [newField, setNewField] = useState<Partial<SchemaField>>({
    name: '',
    data_type: 'string',
    nullable: false,
  })

  const fields = contract.schema?.fields || []

  const handleAddField = () => {
    if (!newField.name || !newField.data_type) return

    const field: SchemaField = {
      name: newField.name,
      data_type: newField.data_type,
      nullable: newField.nullable || false,
      description: newField.description,
      semantic_type: newField.semantic_type,
      format: newField.format,
      pattern: newField.pattern,
      enum: newField.enum,
      default: newField.default,
      min_length: newField.min_length,
      max_length: newField.max_length,
      minimum: newField.minimum,
      maximum: newField.maximum,
      metadata: newField.metadata,
    }

    onChange({
      ...contract,
      schema: {
        ...contract.schema,
        fields: [...fields, field],
      },
    })

    // Reset new field
    setNewField({
      name: '',
      data_type: 'string',
      nullable: false,
    })
  }

  const handleEditField = (field: SchemaField) => {
    setEditingField(field)
    setIsFieldEditorOpen(true)
  }

  const handleDeleteField = (fieldName: string) => {
    onChange({
      ...contract,
      schema: {
        ...contract.schema,
        fields: fields.filter((f) => f.name !== fieldName),
        primary_key: contract.schema?.primary_key?.filter((pk) => pk !== fieldName),
      },
    })
  }

  const handleSaveField = (updatedField: SchemaField) => {
    const fieldIndex = fields.findIndex((f) => f.name === editingField?.name)
    if (fieldIndex >= 0) {
      const newFields = [...fields]
      newFields[fieldIndex] = updatedField
      onChange({
        ...contract,
        schema: {
          ...contract.schema,
          fields: newFields,
        },
      })
    }
    setIsFieldEditorOpen(false)
    setEditingField(null)
  }

  const handleFieldClick = (fieldName: string) => {
    if (onNavigateToField) {
      onNavigateToField(fieldName)
    }
  }

  return (
    <Box sx={{ padding: 3 }}>
      {/* Actions */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h6" sx={{ fontWeight: 600 }}>
          Schema Fields ({fields.length})
        </Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => {
            setEditingField(null)
            setIsFieldEditorOpen(true)
          }}
        >
          Add Field
        </Button>
      </Box>

      {/* Quick Add Field */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Typography variant="subtitle2" sx={{ fontWeight: 600, mb: 2 }}>
          Quick Add Field
        </Typography>
        <Box sx={{ display: 'flex', gap: 2, alignItems: 'flex-end' }}>
          <TextField
            label="Field Name"
            value={newField.name || ''}
            onChange={(e) => setNewField({ ...newField, name: e.target.value })}
            required
            sx={{ flex: 1 }}
          />
          <Box sx={{ minWidth: 150 }}>
            <Select
              label="Data Type"
              value={newField.data_type || 'string'}
              onChange={(value) => setNewField({ ...newField, data_type: value as SchemaFieldDataType })}
              options={DATA_TYPE_OPTIONS}
            />
          </Box>
          <FormControlLabel
            control={
              <Checkbox
                checked={newField.nullable || false}
                onChange={(e) => setNewField({ ...newField, nullable: e.target.checked })}
              />
            }
            label="Nullable"
          />
          <Button
            variant="outlined"
            onClick={handleAddField}
            disabled={!newField.name || !newField.data_type}
          >
            Add
          </Button>
        </Box>
      </Paper>

      {/* Fields Table */}
      {fields.length > 0 ? (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Name</TableCell>
                <TableCell>Data Type</TableCell>
                <TableCell>Nullable</TableCell>
                <TableCell>Description</TableCell>
                <TableCell>Primary Key</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {fields.map((field) => (
                <TableRow
                  key={field.name}
                  sx={{
                    cursor: onNavigateToField ? 'pointer' : 'default',
                    '&:hover': { backgroundColor: 'action.hover' },
                  }}
                  onClick={() => handleFieldClick(field.name)}
                >
                  <TableCell sx={{ fontWeight: 500 }}>{field.name}</TableCell>
                  <TableCell>
                    <Chip label={field.data_type} size="small" />
                  </TableCell>
                  <TableCell>{field.nullable ? 'Yes' : 'No'}</TableCell>
                  <TableCell>
                    {field.description ? (
                      <Typography variant="body2" sx={{ maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {field.description}
                      </Typography>
                    ) : (
                      <Typography variant="body2" color="text.secondary">
                        —
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    {contract.schema?.primary_key?.includes(field.name) ? (
                      <Chip label="PK" size="small" color="primary" />
                    ) : (
                      '—'
                    )}
                  </TableCell>
                  <TableCell align="right">
                    <IconButton
                      size="small"
                      onClick={(e) => {
                        e.stopPropagation()
                        handleEditField(field)
                      }}
                    >
                      <EditIcon fontSize="small" />
                    </IconButton>
                    <IconButton
                      size="small"
                      color="error"
                      onClick={(e) => {
                        e.stopPropagation()
                        handleDeleteField(field.name)
                      }}
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ) : (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="body1" color="text.secondary">
            No schema fields defined. Add your first field to get started.
          </Typography>
        </Paper>
      )}

      {/* Field Editor Dialog */}
      <FieldEditorDialog
        open={isFieldEditorOpen}
        field={editingField}
        onClose={() => {
          setIsFieldEditorOpen(false)
          setEditingField(null)
        }}
        onSave={handleSaveField}
      />
    </Box>
  )
}

/**
 * Field Editor Dialog Component
 */
interface FieldEditorDialogProps {
  open: boolean
  field: SchemaField | null
  onClose: () => void
  onSave: (field: SchemaField) => void
}

const FieldEditorDialog: React.FC<FieldEditorDialogProps> = ({ open, field, onClose, onSave }) => {
  const [editedField, setEditedField] = useState<SchemaField>(
    field || {
      name: '',
      data_type: 'string',
      nullable: false,
    }
  )

  React.useEffect(() => {
    if (field) {
      setEditedField(field)
    } else {
      setEditedField({
        name: '',
        data_type: 'string',
        nullable: false,
      })
    }
  }, [field])

  const handleSave = () => {
    if (!editedField.name || !editedField.data_type) return
    onSave(editedField)
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>{field ? 'Edit Field' : 'Add Field'}</DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          <TextField
            label="Field Name"
            value={editedField.name}
            onChange={(e) => setEditedField({ ...editedField, name: e.target.value })}
            required
            fullWidth
          />
          <Select
            label="Data Type"
            value={editedField.data_type}
            onChange={(value) => setEditedField({ ...editedField, data_type: value as SchemaFieldDataType })}
            options={DATA_TYPE_OPTIONS}
          />
          <FormControlLabel
            control={
              <Checkbox
                checked={editedField.nullable || false}
                onChange={(e) => setEditedField({ ...editedField, nullable: e.target.checked })}
              />
            }
            label="Nullable"
          />
          <TextField
            label="Description"
            value={editedField.description || ''}
            onChange={(e) => setEditedField({ ...editedField, description: e.target.value })}
            multiline
            rows={3}
            fullWidth
          />
          <TextField
            label="Semantic Type"
            value={editedField.semantic_type || ''}
            onChange={(e) => setEditedField({ ...editedField, semantic_type: e.target.value })}
            fullWidth
            helperText="e.g., EMAIL, PHONE, ORDER_ID"
          />
          <TextField
            label="Format"
            value={editedField.format || ''}
            onChange={(e) => setEditedField({ ...editedField, format: e.target.value })}
            fullWidth
            helperText="e.g., email, uri, date-time"
          />
          <TextField
            label="Pattern (Regex)"
            value={editedField.pattern || ''}
            onChange={(e) => setEditedField({ ...editedField, pattern: e.target.value })}
            fullWidth
          />
          <TextField
            label="Default Value"
            value={editedField.default !== undefined ? String(editedField.default) : ''}
            onChange={(e) => setEditedField({ ...editedField, default: e.target.value })}
            fullWidth
          />
          <Box sx={{ display: 'flex', gap: 2 }}>
            <TextField
              label="Min Length"
              type="number"
              value={editedField.min_length ?? ''}
              onChange={(e) =>
                setEditedField({
                  ...editedField,
                  min_length: e.target.value ? parseInt(e.target.value, 10) : undefined,
                })
              }
              sx={{ flex: 1 }}
            />
            <TextField
              label="Max Length"
              type="number"
              value={editedField.max_length ?? ''}
              onChange={(e) =>
                setEditedField({
                  ...editedField,
                  max_length: e.target.value ? parseInt(e.target.value, 10) : undefined,
                })
              }
              sx={{ flex: 1 }}
            />
          </Box>
          <Box sx={{ display: 'flex', gap: 2 }}>
            <TextField
              label="Minimum"
              type="number"
              value={editedField.minimum ?? ''}
              onChange={(e) =>
                setEditedField({
                  ...editedField,
                  minimum: e.target.value ? parseFloat(e.target.value) : undefined,
                })
              }
              sx={{ flex: 1 }}
            />
            <TextField
              label="Maximum"
              type="number"
              value={editedField.maximum ?? ''}
              onChange={(e) =>
                setEditedField({
                  ...editedField,
                  maximum: e.target.value ? parseFloat(e.target.value) : undefined,
                })
              }
              sx={{ flex: 1 }}
            />
          </Box>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          variant="contained"
          onClick={handleSave}
          disabled={!editedField.name || !editedField.data_type}
          startIcon={<CheckIcon />}
        >
          Save
        </Button>
      </DialogActions>
    </Dialog>
  )
}

SchemaTab.displayName = 'SchemaTab'

