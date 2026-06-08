import type { Meta, StoryObj } from '@storybook/react-vite';
import { FileScanStatus } from '../../../shared/types/files';
import { ScanStatusPill } from './ScanStatusPill';

/**
 * Chromatic captures one snapshot per story — five variants = Gap 7 / D260.7 coverage.
 */
const meta = {
  title: 'Features/Files/ScanStatusPill',
  component: ScanStatusPill,
  tags: ['autodocs'],
} satisfies Meta<typeof ScanStatusPill>;

export default meta;
type Story = StoryObj<typeof meta>;

export const PendingScan: Story = {
  args: { status: FileScanStatus.PENDING_SCAN },
};

export const Clean: Story = {
  args: {
    status: FileScanStatus.CLEAN,
    scannedAt: '2025-01-15T10:30:00.000Z',
  },
};

export const Infected: Story = {
  args: { status: FileScanStatus.INFECTED, scannedAt: '2025-01-15T10:31:00.000Z' },
};

export const ScanUnavailable: Story = {
  args: { status: FileScanStatus.SCAN_UNAVAILABLE },
};

export const ScanError: Story = {
  args: { status: FileScanStatus.SCAN_ERROR, scannedAt: '2025-01-15T10:32:00.000Z' },
};
