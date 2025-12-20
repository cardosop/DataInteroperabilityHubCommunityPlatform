/**
 * FormField Component
 *
 * Enhanced form field with inline validation support.
 * Integrates with react-hook-form and provides validation on blur.
 */

import React from 'react'
import {
  TextField,
  TextFieldProps,
  FormControl,
  FormLabel,
  FormHelperText,
  FormControlLabel,
  Checkbox,
  Radio,
  RadioGroup,
  Select,
  MenuItem,
  InputLabel,
  Box,
} from '@mui/material'
import CheckCircleIcon from '@mui/icons-material/CheckCircle'
import ErrorIcon from '@mui/icons-material/Error'
import { Controller, useFormContext, FieldPath, FieldValues } from 'react-hook-form'

export interface FormFieldProps<T extends FieldValues = FieldValues>
  extends Omit<TextFieldProps, 'name' | 'error' | 'helperText'> {
  /**
   * Field name (for react-hook-form)
   */
  name: FieldPath<T>
  /**
   * Field label
   */
  label: string
  /**
   * Field type
   */
  type?: 'text' | 'email' | 'password' | 'number' | 'textarea' | 'select' | 'checkbox' | 'radio'
  /**
   * Show validation on blur
   */
  validateOnBlur?: boolean
  /**
   * Show success indicator when valid
   */
  showSuccessIndicator?: boolean
  /**
   * Select options (for select type)
   */
  options?: Array<{ value: string | number; label: string }>
  /**
   * Radio options (for radio type)
   */
  radioOptions?: Array<{ value: string | number; label: string }>
  /**
   * Checkbox label (for checkbox type)
   */
  checkboxLabel?: string
}

/**
 * FormField component with inline validation
 */
export function FormField<T extends FieldValues = FieldValues>({
  name,
  label,
  type = 'text',
  validateOnBlur = true,
  showSuccessIndicator = true,
  options,
  radioOptions,
  checkboxLabel,
  required,
  ...props
}: FormFieldProps<T>) {
  const {
    control,
    formState: { errors, touchedFields, isSubmitted },
    trigger,
  } = useFormContext<T>()

  const error = errors[name]
  const isTouched = touchedFields[name]
  // Show error if field is touched OR form has been submitted (for onSubmit mode)
  const hasError = (isTouched || isSubmitted) && !!error
  const isValid = isTouched && !error && showSuccessIndicator

  const handleBlur = async () => {
    if (validateOnBlur) {
      await trigger(name)
    }
  }

  const renderField = () => {
    switch (type) {
      case 'checkbox':
        return (
          <Controller
            name={name}
            control={control}
            render={({ field }) => (
              <FormControlLabel
                control={
                  <Checkbox
                    {...field}
                    checked={field.value || false}
                    onBlur={handleBlur}
                  />
                }
                label={checkboxLabel || label}
              />
            )}
          />
        )

      case 'radio':
        return (
          <Controller
            name={name}
            control={control}
            render={({ field }) => (
              <FormControl error={!!hasError}>
                <FormLabel>{label}</FormLabel>
                <RadioGroup {...field} onBlur={handleBlur}>
                  {radioOptions?.map((option) => (
                    <FormControlLabel
                      key={option.value}
                      value={option.value}
                      control={<Radio />}
                      label={option.label}
                    />
                  ))}
                </RadioGroup>
              </FormControl>
            )}
          />
        )

      case 'select':
        return (
          <Controller
            name={name}
            control={control}
            render={({ field }) => (
              <FormControl fullWidth error={!!hasError} required={required}>
                <InputLabel>{label}</InputLabel>
                <Select
                  {...field}
                  label={label}
                  onBlur={handleBlur}
                  {...props}
                >
                  {options?.map((option) => (
                    <MenuItem key={option.value} value={option.value}>
                      {option.label}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            )}
          />
        )

      case 'textarea':
        return (
          <Controller
            name={name}
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                {...props}
                label={label}
                multiline
                rows={4}
                error={!!hasError}
                helperText={hasError ? (error?.message as string) : props.helperText}
                onBlur={(e) => {
                  field.onBlur()
                  handleBlur()
                }}
                InputProps={{
                  endAdornment: isValid ? (
                    <CheckCircleIcon color="success" sx={{ marginRight: 1 }} />
                  ) : hasError ? (
                    <ErrorIcon color="error" sx={{ marginRight: 1 }} />
                  ) : undefined,
                }}
              />
            )}
          />
        )

      default:
        return (
          <Controller
            name={name}
            control={control}
            render={({ field }) => (
              <TextField
                {...field}
                {...props}
                type={type}
                label={label}
                required={required}
                error={!!hasError}
                helperText={hasError ? (error?.message as string) : props.helperText}
                onBlur={(e) => {
                  field.onBlur()
                  handleBlur()
                }}
                InputProps={{
                  endAdornment: isValid ? (
                    <CheckCircleIcon color="success" sx={{ marginRight: 1 }} />
                  ) : hasError ? (
                    <ErrorIcon color="error" sx={{ marginRight: 1 }} />
                  ) : undefined,
                }}
              />
            )}
          />
        )
    }
  }

  return (
    <Box sx={{ marginBottom: 2 }}>
      {renderField()}
      {hasError && error?.message && (
        <FormHelperText error>{error.message as string}</FormHelperText>
      )}
    </Box>
  )
}

