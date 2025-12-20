# Onboarding Patterns

This document describes the onboarding patterns implemented for the Data Interoperability Hub frontend.

## Table of Contents

1. [Guided Tour](#guided-tour)
2. [Enhanced Tooltip](#enhanced-tooltip)
3. [Progressive Disclosure](#progressive-disclosure)
4. [Welcome Screen](#welcome-screen)
5. [Usage Examples](#usage-examples)
6. [Best Practices](#best-practices)

## Guided Tour

### Features

- Step-by-step tooltips highlighting UI elements
- Progress indicator
- Skip option
- Remembers completion (localStorage)
- Smooth transitions between steps
- Auto-positioning tooltips
- Highlight target elements

### Usage

#### Basic Guided Tour

```tsx
import { GuidedTour, useGuidedTour } from '@/components/onboarding'

const tourSteps = [
  {
    id: 'step-1',
    title: 'Welcome to Data Hub',
    content: 'This is the main dashboard where you can see all your data assets.',
    target: '[data-tour="dashboard"]',
    placement: 'bottom',
  },
  {
    id: 'step-2',
    title: 'Create Your First Asset',
    content: 'Click here to create your first data asset.',
    target: '[data-tour="create-button"]',
    placement: 'right',
  },
]

function Dashboard() {
  const { isActive, startTour, stopTour } = useGuidedTour({
    storageKey: 'dashboard-tour-completed',
  })

  return (
    <>
      <button onClick={startTour}>Start Tour</button>
      <div data-tour="dashboard">Dashboard Content</div>
      <button data-tour="create-button">Create Asset</button>

      <GuidedTour
        steps={tourSteps}
        isActive={isActive}
        onComplete={stopTour}
        onSkip={stopTour}
        storageKey="dashboard-tour-completed"
      />
    </>
  )
}
```

#### Auto-start Tour

```tsx
const { isActive, stopTour } = useGuidedTour({
  storageKey: 'welcome-tour-completed',
  autoStart: true, // Automatically start on mount
})

<GuidedTour
  steps={tourSteps}
  isActive={isActive}
  onComplete={stopTour}
/>
```

#### Using Refs

```tsx
const createButtonRef = useRef<HTMLButtonElement>(null)

const tourSteps = [
  {
    id: 'create-button',
    title: 'Create Asset',
    content: 'Use this button to create new assets.',
    target: createButtonRef,
    placement: 'right',
  },
]

<button ref={createButtonRef}>Create</button>
```

## Enhanced Tooltip

### Features

- Help text and feature highlights
- Title and content sections
- Learn more links
- Multiple trigger modes (hover, click, focus)
- Highlight mode for feature discovery
- Customizable styling

### Usage

#### Basic Tooltip

```tsx
import { EnhancedTooltip } from '@/components/onboarding'

<EnhancedTooltip
  content="This field is required and must be unique."
  placement="top"
>
  <input type="text" />
</EnhancedTooltip>
```

#### Help Icon Tooltip

```tsx
<EnhancedTooltip
  content="Asset names must be unique within your workspace."
  title="Asset Name"
  showHelpIcon
  highlight
  learnMoreLink={{
    text: 'Learn more about naming',
    href: '/docs/naming',
  }}
/>
```

#### Click-to-Show Tooltip

```tsx
<EnhancedTooltip
  content="Click to see more information about this feature."
  trigger="click"
  showClose
  highlight
  title="Advanced Search"
>
  <button>?</button>
</EnhancedTooltip>
```

#### Feature Highlight

```tsx
<EnhancedTooltip
  content="This feature allows you to filter data by multiple criteria simultaneously."
  title="Multi-Filter Feature"
  highlight
  learnMoreLink={{
    text: 'View documentation',
    href: '/docs/filters',
    external: true,
  }}
>
  <FilterIcon />
</EnhancedTooltip>
```

## Progressive Disclosure

### Features

- Gradually show features as users become familiar
- Show after delay
- Show after user actions
- Remember visibility state
- Track user interactions

### Usage

#### Show After Delay

```tsx
import { useProgressiveDisclosure } from '@/hooks/useProgressiveDisclosure'

function AdvancedFeatures() {
  const { isVisible } = useProgressiveDisclosure({
    storageKey: 'advanced-features-visible',
    showAfterDelay: 10000, // Show after 10 seconds
  })

  return (
    <>
      {isVisible && (
        <div>
          <h3>Advanced Features</h3>
          <AdvancedFeaturePanel />
        </div>
      )}
    </>
  )
}
```

#### Show After User Actions

```tsx
function MyComponent() {
  const { isVisible, recordAction } = useProgressiveDisclosure({
    storageKey: 'power-user-features-visible',
    showAfterActions: 5, // Show after 5 user actions
    trackActions: true,
  })

  const handleUserAction = () => {
    recordAction()
    // ... perform action
  }

  return (
    <>
      <button onClick={handleUserAction}>Do Something</button>
      {isVisible && <PowerUserFeatures />}
    </>
  )
}
```

#### Manual Control

```tsx
const { isVisible, show, hide, toggle } = useProgressiveDisclosure({
  storageKey: 'beta-features-visible',
})

return (
  <>
    <button onClick={toggle}>
      {isVisible ? 'Hide' : 'Show'} Beta Features
    </button>
    {isVisible && <BetaFeatures />}
  </>
)
```

## Welcome Screen

### Features

- Multi-step welcome flow
- Progress indicator
- Skip option
- Remembers dismissal
- Customizable content
- Feature highlights

### Usage

#### Simple Welcome Screen

```tsx
import { WelcomeScreen } from '@/components/onboarding'

<WelcomeScreen
  title="Welcome to Data Interoperability Hub"
  subtitle="Get started by creating your first asset"
  primaryAction={{
    label: 'Get Started',
    onClick: () => navigate('/assets/create'),
  }}
  storageKey="welcome-screen-dismissed"
/>
```

#### Multi-Step Welcome

```tsx
<WelcomeScreen
  title="Welcome!"
  steps={[
    {
      title: 'Discover Your Data',
      description: 'Explore and manage all your data assets in one place.',
      features: [
        'Centralized data catalog',
        'Advanced search and filtering',
        'Real-time data synchronization',
      ],
    },
    {
      title: 'Connect Your Services',
      description: 'Integrate with your favorite data sources and tools.',
      features: [
        '100+ integrations available',
        'Easy setup and configuration',
        'Secure API connections',
      ],
    },
    {
      title: 'Automate Workflows',
      description: 'Create automated pipelines to process your data.',
      features: [
        'Visual workflow builder',
        'Scheduled data processing',
        'Event-driven automation',
      ],
    },
  ]}
  primaryAction={{
    label: 'Start Exploring',
    onClick: () => navigate('/dashboard'),
  }}
  storageKey="welcome-screen-dismissed"
/>
```

#### With Custom Content

```tsx
<WelcomeScreen
  title="Welcome!"
  subtitle="Let's get you set up"
>
  <div>
    <h3>Quick Setup</h3>
    <ol>
      <li>Create your first workspace</li>
      <li>Connect a data source</li>
      <li>Import your first asset</li>
    </ol>
  </div>
</WelcomeScreen>
```

## Usage Examples

### Complete Onboarding Flow

```tsx
import {
  WelcomeScreen,
  GuidedTour,
  useGuidedTour,
} from '@/components/onboarding'
import { useProgressiveDisclosure } from '@/hooks/useProgressiveDisclosure'

function App() {
  const [showWelcome, setShowWelcome] = useState(true)
  const { isActive, startTour, stopTour } = useGuidedTour({
    storageKey: 'main-tour-completed',
  })
  const { isVisible: showAdvanced } = useProgressiveDisclosure({
    storageKey: 'advanced-features-visible',
    showAfterDelay: 30000, // Show after 30 seconds
  })

  return (
    <>
      {showWelcome && (
        <WelcomeScreen
          title="Welcome to Data Hub"
          steps={welcomeSteps}
          primaryAction={{
            label: 'Start Tour',
            onClick: () => {
              setShowWelcome(false)
              startTour()
            },
          }}
          onDismiss={() => setShowWelcome(false)}
          storageKey="welcome-screen-dismissed"
        />
      )}

      <GuidedTour
        steps={tourSteps}
        isActive={isActive}
        onComplete={stopTour}
        storageKey="main-tour-completed"
      />

      {showAdvanced && <AdvancedFeaturesPanel />}
    </>
  )
}
```

### Contextual Help with Tooltips

```tsx
import { EnhancedTooltip } from '@/components/onboarding'

function FormField({ label, helpText, helpLink }) {
  return (
    <div>
      <label>
        {label}
        <EnhancedTooltip
          content={helpText}
          title={label}
          highlight
          learnMoreLink={helpLink}
          showHelpIcon
        />
      </label>
      <input type="text" />
    </div>
  )
}
```

### Feature Discovery

```tsx
function FeatureButton({ feature }) {
  const { isVisible, show } = useProgressiveDisclosure({
    storageKey: `feature-${feature.id}-visible`,
    showAfterDelay: feature.showAfter * 1000,
  })

  return (
    <>
      <button onClick={show}>Show Feature</button>
      {isVisible && (
        <EnhancedTooltip
          content={feature.description}
          title={feature.name}
          highlight
          trigger="click"
          showClose
        >
          <FeatureIcon />
        </EnhancedTooltip>
      )}
    </>
  )
}
```

## Best Practices

### 1. Guided Tours

- **Keep tours short**: 3-5 steps maximum
- **Focus on key features**: Don't overwhelm users
- **Allow skipping**: Always provide skip option
- **Remember completion**: Use storage keys to avoid showing again
- **Test target selectors**: Ensure elements exist before tour starts

### 2. Tooltips

- **Be concise**: Keep tooltip content brief
- **Provide context**: Explain why, not just what
- **Link to docs**: Include learn more links for complex features
- **Use highlight mode**: For important feature discoveries
- **Consider trigger mode**: Use click for important info, hover for quick help

### 3. Progressive Disclosure

- **Start simple**: Show basic features first
- **Reveal gradually**: Show advanced features after users are comfortable
- **Track engagement**: Use action counting for power users
- **Respect user choice**: Allow manual show/hide

### 4. Welcome Screens

- **Keep it brief**: Don't make users read too much
- **Show value**: Focus on benefits, not features
- **Provide clear actions**: Make next steps obvious
- **Allow skipping**: Some users prefer to explore on their own
- **Use steps**: Break complex onboarding into digestible steps

### 5. Storage Keys

Use descriptive, unique storage keys:

```tsx
// Good
storageKey="dashboard-tour-completed"
storageKey="welcome-screen-dismissed"
storageKey="advanced-features-visible"

// Bad
storageKey="tour"
storageKey="dismissed"
```

### 6. Accessibility

- Use proper ARIA labels
- Support keyboard navigation
- Ensure sufficient color contrast
- Provide alternative text for illustrations

## Type Safety

All components are fully typed:

```tsx
import type {
  TourStep,
  WelcomeStep,
} from '@/components/onboarding'
```

## See Also

- [UX Patterns Documentation](../../../docs/UI/UX_PATTERNS.md)
- [Component Library Documentation](../../../docs/UI/COMPONENT_LIBRARY.md)

