/**
 * Phase 227 Wave 1 (227.L5.12) — ModelsEditor component tests.
 *
 * Pins the editor's user-facing invariants:
 * * Add / remove / reorder of models and fields.
 * * Save is disabled while validation issues exist.
 * * Conflict dialog appears when the save handler rejects with
 *   ``code: PRECONDITION_FAILED``.
 *
 * No mocks of internal code paths — we drive the component with a
 * thin in-test ``onSave`` stub that returns / rejects deterministically.
 */
import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import { ModelsEditor, validateEditorState } from './ModelsEditor';
import type { SchemaEditorState } from '../../../shared/types/contracts';

function makeInitialState(): SchemaEditorState {
  return {
    specType: 'ODCS',
    specVersion: '3.1.0',
    info: { name: 'orders', version: '1.0.0', status: 'active' },
    models: [
      {
        _uiKey: 'm-1',
        name: 'customers',
        fields: [
          { _uiKey: 'f-1', name: 'id', data_type: 'string', is_primary_key: true },
          { _uiKey: 'f-2', name: 'email', data_type: 'string' },
        ],
      },
    ],
    etag: 'W/"abc123"',
    originalRaw: '',
  };
}

describe('validateEditorState', () => {
  it('reports MODEL_NAME_REQUIRED for blank model names', () => {
    const state = makeInitialState();
    state.models[0].name = '';
    const issues = validateEditorState(state);
    expect(issues.some((i) => i.code === 'MODEL_NAME_REQUIRED')).toBe(true);
  });

  it('reports MODEL_FIELDS_REQUIRED for empty fields', () => {
    const state = makeInitialState();
    state.models[0].fields = [];
    const issues = validateEditorState(state);
    expect(issues.some((i) => i.code === 'MODEL_FIELDS_REQUIRED')).toBe(true);
  });

  it('reports FIELD_NAME_REQUIRED when a field has no name', () => {
    const state = makeInitialState();
    state.models[0].fields[0].name = '';
    const issues = validateEditorState(state);
    expect(issues.some((i) => i.code === 'FIELD_NAME_REQUIRED')).toBe(true);
  });

  it('reports FIELD_NAME_DUPLICATE for duplicate names within a model', () => {
    const state = makeInitialState();
    state.models[0].fields = [
      { _uiKey: 'f-1', name: 'dup', data_type: 'string' },
      { _uiKey: 'f-2', name: 'dup', data_type: 'integer' },
    ];
    const issues = validateEditorState(state);
    expect(issues.some((i) => i.code === 'FIELD_NAME_DUPLICATE')).toBe(true);
  });

  it('reports OBJECT_FIELD_REQUIRES_NESTED_FIELDS', () => {
    const state = makeInitialState();
    state.models[0].fields = [
      { _uiKey: 'f-1', name: 'addr', data_type: 'object' },
    ];
    const issues = validateEditorState(state);
    expect(
      issues.some((i) => i.code === 'OBJECT_FIELD_REQUIRES_NESTED_FIELDS'),
    ).toBe(true);
  });

  it('reports ARRAY_FIELD_REQUIRES_ITEMS', () => {
    const state = makeInitialState();
    state.models[0].fields = [
      { _uiKey: 'f-1', name: 'tags', data_type: 'array' },
    ];
    const issues = validateEditorState(state);
    expect(
      issues.some((i) => i.code === 'ARRAY_FIELD_REQUIRES_ITEMS'),
    ).toBe(true);
  });

  it('reports nothing on a clean state', () => {
    const issues = validateEditorState(makeInitialState());
    expect(issues).toEqual([]);
  });
});

describe('<ModelsEditor />', () => {
  it('renders a model and its fields', () => {
    const onSave = vi.fn().mockResolvedValue({ etag: 'W/"new"' });
    render(<ModelsEditor initialState={makeInitialState()} onSave={onSave} />);
    expect(screen.getByTestId('model-0')).toBeTruthy();
    expect(screen.getByTestId('field-0-0')).toBeTruthy();
    expect(screen.getByTestId('field-0-1')).toBeTruthy();
  });

  it('Save is disabled when a model has no fields', () => {
    const state = makeInitialState();
    state.models[0].fields = [];
    const onSave = vi.fn().mockResolvedValue({ etag: null });
    render(<ModelsEditor initialState={state} onSave={onSave} />);
    const save = screen.getByTestId('save-models') as HTMLButtonElement;
    expect(save.disabled).toBe(true);
  });

  it('Save fires onSave with compiled raw + initial etag', async () => {
    const onSave = vi.fn().mockResolvedValue({ etag: 'W/"new"' });
    render(<ModelsEditor initialState={makeInitialState()} onSave={onSave} />);
    fireEvent.click(screen.getByTestId('save-models'));
    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    const arg = onSave.mock.calls[0][0];
    expect(arg.format).toBe('JSON');
    expect(arg.ifMatch).toBe('W/"abc123"');
    // Compiled raw must be valid JSON containing the model name.
    expect(() => JSON.parse(arg.raw)).not.toThrow();
    expect(arg.raw).toContain('customers');
  });

  it('shows the conflict dialog on PRECONDITION_FAILED', async () => {
    const onSave = vi.fn().mockRejectedValue({
      code: 'PRECONDITION_FAILED',
      message: 'Contract has been modified since you read it',
      details: { current_etag: 'W/"server"' },
    });
    render(<ModelsEditor initialState={makeInitialState()} onSave={onSave} />);
    fireEvent.click(screen.getByTestId('save-models'));
    await waitFor(() => expect(screen.queryByTestId('conflict-dialog')).toBeTruthy());
    expect(screen.getByTestId('conflict-refresh')).toBeTruthy();
    expect(screen.getByTestId('conflict-discard')).toBeTruthy();
    expect(screen.getByTestId('conflict-newtab')).toBeTruthy();
  });

  it('surfaces STRUCTURELESS_CONTRACT remediation copy on save error', async () => {
    const onSave = vi.fn().mockRejectedValue({
      code: 'STRUCTURELESS_CONTRACT',
      message: 'Contract failed structural-floor invariant',
      details: {
        subcode: 'STRUCTURELESS_ODCS_NO_SCHEMA',
        remediation_url: 'https://example.com/contracts/abc/edit?tab=schema',
      },
    });
    render(<ModelsEditor initialState={makeInitialState()} onSave={onSave} />);
    fireEvent.click(screen.getByTestId('save-models'));
    await waitFor(() => expect(screen.queryByTestId('save-error')).toBeTruthy());
    expect(screen.getByTestId('save-error-cta')).toBeTruthy();
  });

  it('add-model adds a new row', () => {
    const onSave = vi.fn();
    render(<ModelsEditor initialState={makeInitialState()} onSave={onSave} />);
    expect(screen.queryByTestId('model-1')).toBeNull();
    fireEvent.click(screen.getByTestId('add-model'));
    expect(screen.getByTestId('model-1')).toBeTruthy();
  });

  it('add-field appends a row to the existing model', () => {
    const onSave = vi.fn();
    render(<ModelsEditor initialState={makeInitialState()} onSave={onSave} />);
    expect(screen.queryByTestId('field-0-2')).toBeNull();
    fireEvent.click(screen.getByTestId('model-0-add-field'));
    expect(screen.getByTestId('field-0-2')).toBeTruthy();
  });

  it('remove-field deletes the row', () => {
    const onSave = vi.fn();
    render(<ModelsEditor initialState={makeInitialState()} onSave={onSave} />);
    fireEvent.click(screen.getByTestId('field-0-1-remove'));
    expect(screen.queryByTestId('field-0-1')).toBeNull();
  });
});
