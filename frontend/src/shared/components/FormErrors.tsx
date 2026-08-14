/**
 * FormErrors — grouped field-level errors at form top (278.D.2).
 *
 * Renders ``field_errors`` from an ApiError response as a consolidated
 * list above the form, with each field name linked to its input via
 * ``document.getElementById`` on click.
 */
import type { FC } from 'react';
import './FormErrors.css';

export interface FieldError {
  field: string;
  message: string;
  code: string;
}

export interface FormErrorsProps {
  /** Per-field errors from the API response. */
  errors: FieldError[];
  /** Optional prefix for field IDs (e.g. "create-asset-" → focuses "#create-asset-name"). */
  fieldIdPrefix?: string;
}

export const FormErrors: FC<FormErrorsProps> = ({ errors, fieldIdPrefix = '' }) => {
  if (!errors || errors.length === 0) return null;

  const handleFieldClick = (field: string) => {
    const el = document.getElementById(`${fieldIdPrefix}${field}`);
    if (el) {
      el.focus();
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  };

  return (
    <div className="form-errors" role="alert" data-testid="form-errors">
      <p className="form-errors__heading">
        Please fix {errors.length} {errors.length === 1 ? 'error' : 'errors'}:
      </p>
      <ul className="form-errors__list">
        {errors.map((e, i) => (
          <li key={`${e.field}-${i}`} className="form-errors__item">
            <button
              type="button"
              className="form-errors__field-link"
              onClick={() => handleFieldClick(e.field)}
            >
              {e.field}
            </button>
            : {e.message}
          </li>
        ))}
      </ul>
    </div>
  );
};
