/**
 * Phase 278.K.2 — StatusBadge Storybook story.
 */
import type { Meta, StoryObj } from '@storybook/react';
import { StatusBadge } from '../StatusBadge';

const meta: Meta<typeof StatusBadge> = {
  title: 'Shared/StatusBadge',
  component: StatusBadge,
  tags: ['autodocs'],
  argTypes: {
    status: { control: 'select', options: ['ACTIVE', 'FAILED', 'PENDING', 'RUNNING', 'COMPLETED', 'PUBLISHED', 'VERIFIED'] },
  },
};
export default meta;

type Story = StoryObj<typeof StatusBadge>;

export const Active: Story = { args: { status: 'ACTIVE' } };
export const Failed: Story = { args: { status: 'FAILED' } };
export const Pending: Story = { args: { status: 'PENDING' } };
export const Running: Story = { args: { status: 'RUNNING' } };
export const Completed: Story = { args: { status: 'COMPLETED' } };
export const Verified: Story = { args: { status: 'VERIFIED' } };
export const CustomTooltip: Story = { args: { status: 'ACTIVE', tooltip: 'System is operational' } };
export const CustomIcon: Story = { args: { status: 'ACTIVE', icon: '★' } };
export const CustomLabel: Story = { args: { status: 'ACTIVE', children: 'Online' } };
