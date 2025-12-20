# Error Message System

Comprehensive error message system with user-friendly messages, i18n support, suggested actions, and help links.

## Features

- **User-Friendly Messages**: No technical jargon, plain language
- **Contextual Templates**: Messages explain what happened and why
- **Actionable**: Clear suggested actions users can take
- **Help Links**: Links to relevant documentation and support
- **Next Steps**: Clear, numbered steps to resolve the issue
- **i18n Support**: Full internationalization support
- **Type-Safe**: Fully typed with TypeScript

## Usage

### Basic Usage

```tsx
import { ErrorMessageDisplay } from '@/components/error/ErrorMessageDisplay'

function MyComponent() {
  const [error, setError] = useState<Error | null>(null)

  if (error) {
    return <ErrorMessageDisplay error={error} />
  }

  return <div>Content</div>
}
```

### Using the Hook

```tsx
import { useErrorMessage } from '@/lib/errors/useErrorMessage'

function CustomErrorDisplay({ error }: { error: Error }) {
  const { title, message, suggestedActions, helpLinks, nextSteps } = useErrorMessage(error)

  return (
    <div>
      <h2>{title}</h2>
      <p>{message}</p>
      {suggestedActions.map(action => (
        <button key={action.label} onClick={action.onClick}>
          {action.label}
        </button>
      ))}
    </div>
  )
}
```

### Using Templates Directly

```tsx
import { getErrorMessageTemplate, getSuggestedActions } from '@/lib/errors/ErrorMessageTemplates'

const template = getErrorMessageTemplate(error)
const actions = getSuggestedActions(error)
```

## Error Message Templates

All error messages follow these principles:

1. **No Technical Jargon**: Avoid terms like "HTTP 500", "status code", "exception"
2. **User-Friendly**: Use plain language that users understand
3. **Contextual**: Explain what happened and why
4. **Actionable**: Provide clear actions users can take
5. **Helpful**: Include help links and next steps

## Supported Error Types

- Network errors (offline, timeout, connection issues)
- Authentication errors (session expired, login failed)
- Authorization errors (access denied, permissions)
- Validation errors (invalid input, missing fields)
- Not found errors (404, resource not found)
- Server errors (500, service unavailable)
- Rate limiting errors
- Unknown errors

## Internationalization

Error messages are fully localized. Translation keys are automatically generated from template i18n keys.

### Adding Translations

Add translations to `frontend/src/locales/{lang}/translation.json`:

```json
{
  "errors": {
    "network": {
      "error": {
        "title": "Problema de Conexión",
        "message": "Tenemos problemas para conectarnos a nuestros servidores..."
      }
    }
  }
}
```

## Architecture

- **ErrorMessageTemplates.ts**: Core template definitions
- **useErrorMessage.ts**: React hook for localized error messages
- **ErrorMessageDisplay.tsx**: Complete error display component
- **Translation files**: i18n translations in `locales/`

