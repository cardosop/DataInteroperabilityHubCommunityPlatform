/**
 * Phase 278.J.1 — HelpTip Storybook story.
 */
import type { Meta, StoryObj } from '@storybook/react';
import { HelpTip } from '../HelpTip';

const meta: Meta<typeof HelpTip> = {
  title: 'Shared/HelpTip',
  component: HelpTip,
  tags: ['autodocs'],
  argTypes: {
    position: { control: 'select', options: ['top', 'bottom', 'right'] },
  },
};
export default meta;

type Story = StoryObj<typeof HelpTip>;

export const GlossaryTerm: Story = { args: { term: 'RLS' } };
export const WithCustomDescription: Story = {
  args: { term: 'CUSTOM', description: 'This field controls the replication factor for your data pipeline.' },
};
export const WithLearnMoreLink: Story = {
  args: { term: 'ODCS', learnMoreUrl: 'https://example.com/docs' },
};
export const PositionBottom: Story = { args: { term: 'SPARQL', position: 'bottom' } };
export const PositionRight: Story = { args: { term: 'DSAR', position: 'right' } };
