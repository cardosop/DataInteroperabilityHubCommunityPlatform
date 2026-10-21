/**
 * Validation helpers for the schema editor (Phase 227 Wave 1).
 *
 * Lives in its own module so ``react-refresh/only-export-components``
 * keeps ``ModelsEditor.tsx`` component-only and Fast Refresh
 * boundaries stay clean.
 */
import type {
  EditorValidationIssue,
  SchemaEditorState,
} from '../../../shared/types/contracts';
import { FIELD_DATA_TYPES } from '../../../shared/types/contracts';

/**
 * Walk the JSON-Schema ``$defs`` for the ``HubContractField`` definition
 * and return its ``data_type`` enum. Returns ``null`` when the shape
 * doesn't match expectations so callers can fall back to the static set.
 */
export function deriveAllowedDataTypes(
  jsonSchema: Record<string, unknown> | null | undefined,
): string[] | null {
  if (!jsonSchema || typeof jsonSchema !== 'object') return null;
  const defs = (jsonSchema.$defs ?? jsonSchema.definitions) as
    | Record<string, unknown>
    | undefined;
  if (!defs) return null;
  // Pydantic v2 emits ``$defs`` keyed by class name.
  const fieldDef = defs.HubContractField as Record<string, unknown> | undefined;
  if (!fieldDef || typeof fieldDef !== 'object') return null;
  const props = fieldDef.properties as Record<string, unknown> | undefined;
  if (!props) return null;
  const typeProp = (props.type ?? props.data_type) as
    | { enum?: unknown[] }
    | undefined;
  if (!typeProp || !Array.isArray(typeProp.enum)) return null;
  return typeProp.enum.filter((v): v is string => typeof v === 'string');
}

export function validateEditorState(
  state: SchemaEditorState,
  jsonSchema?: Record<string, unknown> | null,
): EditorValidationIssue[] {
  const issues: EditorValidationIssue[] = [];
  // When a JSON Schema is supplied, narrow the allowed data_type set
  // to whatever the backend Pydantic model permits. Otherwise fall
  // back to the static ``FIELD_DATA_TYPES`` constant.
  const allowedTypes = (deriveAllowedDataTypes(jsonSchema) ?? FIELD_DATA_TYPES) as readonly string[];
  state.models.forEach((model, modelIndex) => {
    if (!model.name || !model.name.trim()) {
      issues.push({
        modelIndex,
        message: 'Model name is required',
        code: 'MODEL_NAME_REQUIRED',
      });
    }
    if (model.fields.length === 0) {
      issues.push({
        modelIndex,
        message: `Model "${model.name || `#${modelIndex + 1}`}" must have at least one field`,
        code: 'MODEL_FIELDS_REQUIRED',
      });
    }
    const seenNames = new Set<string>();
    model.fields.forEach((field, fieldIndex) => {
      const fieldPath = `${model.name || `#${modelIndex + 1}`}.fields[${fieldIndex}]`;
      if (!field.name || !field.name.trim()) {
        issues.push({
          modelIndex,
          fieldPath,
          message: 'Field name is required',
          code: 'FIELD_NAME_REQUIRED',
        });
      } else if (seenNames.has(field.name)) {
        issues.push({
          modelIndex,
          fieldPath,
          message: `Duplicate field name "${field.name}" in this model`,
          code: 'FIELD_NAME_DUPLICATE',
        });
      } else {
        seenNames.add(field.name);
      }
      // JSON-Schema-driven check: data_type must be in the allowed set.
      if (field.data_type && !allowedTypes.includes(field.data_type)) {
        issues.push({
          modelIndex,
          fieldPath,
          message: `Field "${field.name || '?'}" has unsupported type "${field.data_type}". Allowed: ${allowedTypes.join(', ')}.`,
          code: 'FIELD_NAME_REQUIRED', // closest fit; see EditorValidationIssue codes
        });
      }
      if (field.data_type === 'object' && (!field.fields || field.fields.length === 0)) {
        issues.push({
          modelIndex,
          fieldPath,
          message: `Object-typed field "${field.name || '?'}" must declare nested fields`,
          code: 'OBJECT_FIELD_REQUIRES_NESTED_FIELDS',
        });
      }
      if (field.data_type === 'array' && !field.items) {
        issues.push({
          modelIndex,
          fieldPath,
          message: `Array-typed field "${field.name || '?'}" must declare an items schema`,
          code: 'ARRAY_FIELD_REQUIRES_ITEMS',
        });
      }
    });
  });
  return issues;
}
