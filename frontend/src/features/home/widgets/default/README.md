# Default Widgets (Fallback)

**Persona:** default (no matching role)
**Label:** "User"

## Widget specs

### Getting Started Card (already rendered in HomePage)
- Guides new users through first actions: Create Asset → Upload Data → Run Checks
- Dismissible, persisted in localStorage

### Quick Actions (already rendered in HomePage)
- Create Asset, View Datasets, View Jobs

### Recent Assets / Datasets / Jobs (already rendered in HomePage)
- Most recently created items with status badges

### Governance Overview (already rendered in HomePage)
- Compliance Posture, DQ Health, Draft Assets, Active Assets

## Notes

The default persona has no dedicated widget components beyond what `HomePage.tsx`
already renders for all users. This directory exists for symmetry with the other
persona directories and as a future home for generic onboarding or help content.
