/**
 * Phase 250.6.B.7 — Storybook story for the AssetTypePickerStep.
 *
 * The repo has no live Storybook install yet (Storybook is a
 * cross-cutting deliverable in a separate phase); this file is
 * authored in canonical Storybook 8 CSF format so when Storybook
 * ships, the story is ready to render. It also serves as
 * runnable usage documentation for the picker — the
 * ``Default`` story shows the unselected state, ``WithSelection``
 * shows the selected state, and ``Skippable`` shows the skip CTA.
 *
 * Chromatic snapshot expectations
 * --------------------------------
 * * Default — no card highlighted; all four cards visible.
 * * Selected (each variant) — the named card has the
 *   ``[data-selected="true"]`` style applied (border + box-
 *   shadow ring).
 * * Skippable — the Skip CTA renders as a text link below the
 *   card grid.
 *
 * The ``args`` API on each story lets a Chromatic / VRT pipeline
 * iterate over the four ``selected`` values without re-authoring
 * stories per kind.
 */
import type { Meta, StoryObj } from '@storybook/react';

import {
  AssetTypePickerStep,
  type AssetTypeKind,
} from './AssetTypePickerStep';

const meta: Meta<typeof AssetTypePickerStep> = {
  title: 'Assets/AssetTypePickerStep',
  component: AssetTypePickerStep,
  parameters: {
    layout: 'centered',
    docs: {
      description: {
        component:
          'Phase 250.6.B (Gap 12) — first step of the asset-creation flow. ' +
          'Lets the user pick one of four shapes (data / contract / both / ' +
          'metadata) before the form renders.',
      },
    },
    a11y: {
      // Chromatic + axe: pin the role tree expected on this page.
      element: '[data-testid="asset-type-picker-step"]',
      config: {
        rules: [
          // The container is a radiogroup; each option is a radio.
          // We rely on the default axe rules; additional pins
          // come from the test suite (.test.tsx).
        ],
      },
    },
  },
  argTypes: {
    selected: {
      control: 'select',
      options: [null, 'data', 'contract', 'both', 'metadata'],
    },
  },
  args: {
    onSelect: () => undefined,
  },
};

export default meta;

type Story = StoryObj<typeof AssetTypePickerStep>;

export const Default: Story = {
  args: {
    selected: null,
  },
};

export const SelectedData: Story = {
  args: {
    selected: 'data' as AssetTypeKind,
  },
};

export const SelectedContract: Story = {
  args: {
    selected: 'contract' as AssetTypeKind,
  },
};

export const SelectedBoth: Story = {
  args: {
    selected: 'both' as AssetTypeKind,
  },
};

export const SelectedMetadata: Story = {
  args: {
    selected: 'metadata' as AssetTypeKind,
  },
};

export const Skippable: Story = {
  args: {
    selected: null,
    onSkip: () => undefined,
  },
};
