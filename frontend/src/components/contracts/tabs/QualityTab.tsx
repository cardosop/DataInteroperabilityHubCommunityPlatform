/**
 * QualityTab Component
 *
 * Tab for editing data quality rules (HubContract-specific):
 * - Default Profile selector (intake_basic, custom)
 * - Quality Rules table with inline editing
 * - Rule editor modal
 * - Rule properties: ID, Name, Dimension, Expression, Severity, Target Level, Target Column, Target Pattern, Parameters
 * - Rule templates (pre-defined rules)
 * - Rule validation
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
} from '@mui/material'
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Check as CheckIcon,
} from '@mui/icons-material'
import { Select } from '@/components/forms/Select'
import type {
  HubContract,
  QualityRule,
  QualityRuleDimension,
  QualityRuleSeverity,
  QualityRuleTargetLevel,
} from '../types'

export interface QualityTabProps {
  contract: HubContract
  onChange: (contract: HubContract) => void
}

/**
 * Dimension options
 */
const DIMENSION_OPTIONS: Array<{ value: QualityRuleDimension; label: string }> = [
  { value: 'completeness', label: 'Completeness' },
  { value: 'validity', label: 'Validity' },
  { value: 'uniqueness', label: 'Uniqueness' },
  { value: 'consistency', label: 'Consistency' },
  { value: 'accuracy', label: 'Accuracy' },
  { value: 'timeliness', label: 'Timeliness' },
]

/**
 * Severity options
 */
const SEVERITY_OPTIONS: Array<{ value: QualityRuleSeverity; label: string }> = [
  { value: 'ERROR', label: 'Error' },
  { value: 'WARNING', label: 'Warning' },
  { value: 'INFO', label: 'Info' },
]

/**
 * Target level options
 */
const TARGET_LEVEL_OPTIONS: Array<{ value: QualityRuleTargetLevel; label: string }> = [
  { value: 'COLUMN', label: 'Column' },
  { value: 'TABLE', label: 'Table' },
  { value: 'DATASET', label: 'Dataset' },
]

/**
 * Quality profile options
 */
const QUALITY_PROFILE_OPTIONS = [
  { value: 'intake_basic', label: 'Intake Basic' },
  { value: 'custom', label: 'Custom' },
]

/**
 * QualityTab component
 */
export const QualityTab: React.FC<QualityTabProps> = ({ contract, onChange }) => {
  const [editingRule, setEditingRule] = useState<QualityRule | null>(null)
  const [isRuleEditorOpen, setIsRuleEditorOpen] = useState(false)

  const quality = contract.quality || {}
  const rules = quality.rules || []

  const handleQualityChange = (field: string, value: any) => {
    onChange({
      ...contract,
      quality: {
        ...quality,
        [field]: value,
      },
    })
  }

  const handleAddRule = () => {
    setEditingRule(null)
    setIsRuleEditorOpen(true)
  }

  const handleEditRule = (rule: QualityRule) => {
    setEditingRule(rule)
    setIsRuleEditorOpen(true)
  }

  const handleDeleteRule = (ruleId: string) => {
    handleQualityChange(
      'rules',
      rules.filter((r) => r.rule_id !== ruleId)
    )
  }

  const handleSaveRule = (rule: QualityRule) => {
    if (editingRule) {
      // Update existing rule
      handleQualityChange(
        'rules',
        rules.map((r) => (r.rule_id === editingRule.rule_id ? rule : r))
      )
    } else {
      // Add new rule
      handleQualityChange('rules', [...rules, rule])
    }
    setIsRuleEditorOpen(false)
    setEditingRule(null)
  }

  return (
    <Box sx={{ padding: 3 }}>
      {/* Default Profile */}
      <Box sx={{ mb: 3 }}>
        <Select
          label="Default Quality Profile"
          value={quality.default_profile_key || ''}
          onChange={(value) => handleQualityChange('default_profile_key', value)}
          options={QUALITY_PROFILE_OPTIONS}
          placeholder="Select quality profile"
        />
      </Box>

      {/* Rules Section */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h6" sx={{ fontWeight: 600 }}>
          Quality Rules ({rules.length})
        </Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={handleAddRule}>
          Add Rule
        </Button>
      </Box>

      {/* Rules Table */}
      {rules.length > 0 ? (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Rule ID</TableCell>
                <TableCell>Name</TableCell>
                <TableCell>Dimension</TableCell>
                <TableCell>Severity</TableCell>
                <TableCell>Target Level</TableCell>
                <TableCell>Target Column</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {rules.map((rule) => (
                <TableRow key={rule.rule_id}>
                  <TableCell sx={{ fontWeight: 500 }}>{rule.rule_id}</TableCell>
                  <TableCell>{rule.name}</TableCell>
                  <TableCell>
                    <Chip label={rule.dimension} size="small" />
                  </TableCell>
                  <TableCell>
                    <Chip
                      label={rule.severity}
                      size="small"
                      color={rule.severity === 'ERROR' ? 'error' : rule.severity === 'WARNING' ? 'warning' : 'default'}
                    />
                  </TableCell>
                  <TableCell>{rule.target_level || '—'}</TableCell>
                  <TableCell>{rule.target_column || '—'}</TableCell>
                  <TableCell align="right">
                    <IconButton size="small" onClick={() => handleEditRule(rule)}>
                      <EditIcon fontSize="small" />
                    </IconButton>
                    <IconButton size="small" color="error" onClick={() => handleDeleteRule(rule.rule_id)}>
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
            No quality rules defined. Add your first rule to get started.
          </Typography>
        </Paper>
      )}

      {/* Rule Editor Dialog */}
      <RuleEditorDialog
        open={isRuleEditorOpen}
        rule={editingRule}
        onClose={() => {
          setIsRuleEditorOpen(false)
          setEditingRule(null)
        }}
        onSave={handleSaveRule}
      />
    </Box>
  )
}

/**
 * Rule Editor Dialog Component
 */
interface RuleEditorDialogProps {
  open: boolean
  rule: QualityRule | null
  onClose: () => void
  onSave: (rule: QualityRule) => void
}

const RuleEditorDialog: React.FC<RuleEditorDialogProps> = ({ open, rule, onClose, onSave }) => {
  const [editedRule, setEditedRule] = useState<QualityRule>(
    rule || {
      rule_id: '',
      name: '',
      dimension: 'completeness',
      severity: 'WARNING',
    }
  )

  React.useEffect(() => {
    if (rule) {
      setEditedRule(rule)
    } else {
      setEditedRule({
        rule_id: `rule_${Date.now()}`,
        name: '',
        dimension: 'completeness',
        severity: 'WARNING',
      })
    }
  }, [rule])

  const handleSave = () => {
    if (!editedRule.rule_id || !editedRule.name) return
    onSave(editedRule)
  }

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>{rule ? 'Edit Quality Rule' : 'Add Quality Rule'}</DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          <TextField
            label="Rule ID"
            value={editedRule.rule_id}
            onChange={(e) => setEditedRule({ ...editedRule, rule_id: e.target.value })}
            required
            fullWidth
            disabled={!!rule} // Don't allow editing ID for existing rules
          />
          <TextField
            label="Rule Name"
            value={editedRule.name}
            onChange={(e) => setEditedRule({ ...editedRule, name: e.target.value })}
            required
            fullWidth
          />
          <Select
            label="Dimension"
            value={editedRule.dimension}
            onChange={(value) => setEditedRule({ ...editedRule, dimension: value as QualityRuleDimension })}
            options={DIMENSION_OPTIONS}
            fullWidth
          />
          <Select
            label="Severity"
            value={editedRule.severity}
            onChange={(value) => setEditedRule({ ...editedRule, severity: value as QualityRuleSeverity })}
            options={SEVERITY_OPTIONS}
            fullWidth
          />
          <Select
            label="Target Level"
            value={editedRule.target_level || ''}
            onChange={(value) => setEditedRule({ ...editedRule, target_level: value as QualityRuleTargetLevel })}
            options={TARGET_LEVEL_OPTIONS}
            fullWidth
            placeholder="Select target level"
          />
          <TextField
            label="Target Column"
            value={editedRule.target_column || ''}
            onChange={(e) => setEditedRule({ ...editedRule, target_column: e.target.value })}
            fullWidth
            helperText="Required if target level is COLUMN"
          />
          <TextField
            label="Target Pattern (Regex)"
            value={editedRule.target_pattern || ''}
            onChange={(e) => setEditedRule({ ...editedRule, target_pattern: e.target.value })}
            fullWidth
          />
          <TextField
            label="Expression"
            value={editedRule.expression || ''}
            onChange={(e) => setEditedRule({ ...editedRule, expression: e.target.value })}
            multiline
            rows={4}
            fullWidth
            helperText="SQL expression or rule definition"
          />
          <TextField
            label="Parameters (JSON)"
            value={editedRule.params ? JSON.stringify(editedRule.params, null, 2) : ''}
            onChange={(e) => {
              try {
                const params = e.target.value ? JSON.parse(e.target.value) : undefined
                setEditedRule({ ...editedRule, params })
              } catch {
                // Invalid JSON, keep as is
              }
            }}
            multiline
            rows={3}
            fullWidth
            helperText="Rule-specific parameters as JSON object"
          />
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          variant="contained"
          onClick={handleSave}
          disabled={!editedRule.rule_id || !editedRule.name}
          startIcon={<CheckIcon />}
        >
          Save
        </Button>
      </DialogActions>
    </Dialog>
  )
}

QualityTab.displayName = 'QualityTab'

