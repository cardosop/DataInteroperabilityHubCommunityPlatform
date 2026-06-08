import type { Meta, StoryObj } from '@storybook/react-vite';
import { DatasetVersionDiffView } from './DatasetVersionDiffView';

/**
 * Chromatic captures snapshots per story (Gap 5 / Phase 260.3.A).
 */
const meta = {
  title: 'Features/Datasets/DatasetVersionDiffView',
  component: DatasetVersionDiffView,
  tags: ['autodocs'],
} satisfies Meta<typeof DatasetVersionDiffView>;

export default meta;
type Story = StoryObj<typeof meta>;

export const BackwardCompatible: Story = {
  args: {
    compatibilityLevel: 'BACKWARD_COMPATIBLE',
    summary: { FIELD_ADDED: 1, FIELD_REMOVED: 0 },
    changes: [
      {
        type: 'FIELD_ADDED',
        field_name: 'region',
        description: "Field 'region' added",
        breaking: false,
        old_value: null,
        new_value: { name: 'region', data_type: 'string', nullable: true },
      },
    ],
    version1Label: 'Version 1 (1.0.0)',
    version2Label: 'Version 2 (1.1.0)',
  },
};

export const BreakingTypeChange: Story = {
  args: {
    compatibilityLevel: 'INCOMPATIBLE',
    summary: { FIELD_TYPE_CHANGED: 1 },
    changes: [
      {
        type: 'FIELD_TYPE_CHANGED',
        field_name: 'id',
        description: "Field 'id' type changed from string to integer",
        breaking: true,
        old_value: 'string',
        new_value: 'integer',
      },
    ],
    version1Label: 'Version 1',
    version2Label: 'Version 2',
  },
};

export const EmptyDiff: Story = {
  args: {
    compatibilityLevel: 'FULLY_COMPATIBLE',
    summary: {},
    changes: [],
    version1Label: 'Version 3',
    version2Label: 'Version 3',
  },
};
