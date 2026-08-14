/**
 * 281.A.7.3 — Storybook component library for all shared components.
 *
 * Each story exercises a single component in its key states.
 * Stories double as visual-regression baselines for Chromatic.
 */
import type { Meta, StoryObj } from '@storybook/react';
import React from 'react';

// ── Button ──────────────────────────────────────────────────────────────
import { Button } from './Button';
const ButtonMeta: Meta<typeof Button> = {
  title: 'Shared/Button',
  component: Button,
  argTypes: {
    variant: { control: 'select', options: ['primary', 'secondary', 'danger', 'ghost'] },
    size: { control: 'select', options: ['sm', 'md', 'lg'] },
    disabled: { control: 'boolean' },
  },
};
export default ButtonMeta;

type ButtonStory = StoryObj<typeof Button>;
export const ButtonPrimary: ButtonStory = { args: { variant: 'primary', children: 'Save', size: 'md' } };
export const ButtonSecondary: ButtonStory = { args: { variant: 'secondary', children: 'Cancel', size: 'md' } };
export const ButtonDanger: ButtonStory = { args: { variant: 'danger', children: 'Delete', size: 'md' } };
export const ButtonGhost: ButtonStory = { args: { variant: 'ghost', children: 'Learn more', size: 'md' } };
export const ButtonDisabled: ButtonStory = { args: { variant: 'primary', children: 'Submit', disabled: true } };
export const ButtonSmall: ButtonStory = { args: { variant: 'primary', children: 'OK', size: 'sm' } };
export const ButtonLoading: ButtonStory = { args: { variant: 'primary', children: 'Saving…', disabled: true } };

// ── EmptyState ──────────────────────────────────────────────────────────
import { EmptyState } from './EmptyState';
const EmptyStateMeta: Meta<typeof EmptyState> = {
  title: 'Shared/EmptyState',
  component: EmptyState,
};
export const EmptyStateDefault: StoryObj<typeof EmptyState> = {
  render: () => <EmptyState title="No assets yet" description="Create your first asset to get started." />,
};
export const EmptyStateWithAction: StoryObj<typeof EmptyState> = {
  render: () => (
    <EmptyState
      title="No listings found"
      description="Try adjusting your search filters or create a new listing."
      action={<Button variant="primary">Create listing</Button>}
    />
  ),
};

// ── Banner ──────────────────────────────────────────────────────────────
import { Banner } from './Banner';
const BannerMeta: Meta<typeof Banner> = {
  title: 'Shared/Banner',
  component: Banner,
};
export const BannerInfo: StoryObj<typeof Banner> = {
  render: () => <Banner variant="info" message="Your plan will renew on June 1, 2026." />,
};
export const BannerWarning: StoryObj<typeof Banner> = {
  render: () => <Banner variant="warning" message="KYC verification expires in 7 days." />,
};
export const BannerError: StoryObj<typeof Banner> = {
  render: () => <Banner variant="error" message="Payment method declined. Update your billing details." />,
};
export const BannerSuccess: StoryObj<typeof Banner> = {
  render: () => <Banner variant="success" message="Changes saved successfully." />,
};

// ── ConfirmDialog ───────────────────────────────────────────────────────
import { ConfirmDialog } from './ConfirmDialog';
const ConfirmDialogMeta: Meta<typeof ConfirmDialog> = {
  title: 'Shared/ConfirmDialog',
  component: ConfirmDialog,
};
export const ConfirmDialogDefault: StoryObj<typeof ConfirmDialog> = {
  render: () => (
    <ConfirmDialog
      open={true}
      title="Delete asset?"
      message="This action cannot be undone. The asset and all associated contracts will be permanently removed."
      confirmLabel="Delete"
      cancelLabel="Cancel"
      onConfirm={() => {}}
      onCancel={() => {}}
    />
  ),
};

// ── DestructiveConfirmDialog ────────────────────────────────────────────
import { DestructiveConfirmDialog } from './DestructiveConfirmDialog';
const DestructiveConfirmMeta: Meta<typeof DestructiveConfirmDialog> = {
  title: 'Shared/DestructiveConfirmDialog',
  component: DestructiveConfirmDialog,
};
export const DestructiveConfirm: StoryObj<typeof DestructiveConfirmDialog> = {
  render: () => (
    <DestructiveConfirmDialog
      open={true}
      title="Delete tenant?"
      message="All data, users, and configurations for this tenant will be permanently deleted. Type the tenant name to confirm."
      confirmText="my-tenant"
      confirmLabel="Delete tenant"
      onConfirm={() => {}}
      onCancel={() => {}}
    />
  ),
};

// ── Breadcrumbs ─────────────────────────────────────────────────────────
import { Breadcrumbs } from './Breadcrumbs';
const BreadcrumbsMeta: Meta<typeof Breadcrumbs> = {
  title: 'Shared/Breadcrumbs',
  component: Breadcrumbs,
};
export const BreadcrumbsTwoLevel: StoryObj<typeof Breadcrumbs> = {
  render: () => (
    <Breadcrumbs
      items={[
        { label: 'Assets', href: '/assets' },
        { label: 'Customer Database' },
      ]}
    />
  ),
};
export const BreadcrumbsThreeLevel: StoryObj<typeof Breadcrumbs> = {
  render: () => (
    <Breadcrumbs
      items={[
        { label: 'Governance', href: '/governance' },
        { label: 'Access Requests', href: '/governance/access-requests' },
        { label: 'REQ-2026-0042' },
      ]}
    />
  ),
};

// ── Skeleton (loading) ──────────────────────────────────────────────────
import { Skeleton } from './Skeleton';
const SkeletonMeta: Meta<typeof Skeleton> = {
  title: 'Shared/Skeleton',
  component: Skeleton,
};
export const SkeletonText: StoryObj<typeof Skeleton> = {
  render: () => <Skeleton variant="text" width="100%" />,
};
export const SkeletonCard: StoryObj<typeof Skeleton> = {
  render: () => <Skeleton variant="rect" width={320} height={200} />,
};
export const SkeletonCircle: StoryObj<typeof Skeleton> = {
  render: () => <Skeleton variant="circle" width={48} height={48} />,
};

// ── ComingSoonPage ──────────────────────────────────────────────────────
import { ComingSoonPage } from './ComingSoonPage';
const ComingSoonMeta: Meta<typeof ComingSoonPage> = {
  title: 'Shared/ComingSoonPage',
  component: ComingSoonPage,
};
export const ComingSoon: StoryObj<typeof ComingSoonPage> = {
  render: () => <ComingSoonPage featureName="Advanced Analytics" />,
};

// ── CodeBlock ───────────────────────────────────────────────────────────
import { CodeBlock } from './CodeBlock';
const CodeBlockMeta: Meta<typeof CodeBlock> = {
  title: 'Shared/CodeBlock',
  component: CodeBlock,
};
export const CodeBlockJSON: StoryObj<typeof CodeBlock> = {
  render: () => (
    <CodeBlock
      language="json"
      code={JSON.stringify({ name: 'customer-db', type: 'dataset', columns: 12 }, null, 2)}
    />
  ),
};

// ── BulkActionBar ───────────────────────────────────────────────────────
import { BulkActionBar } from './BulkActionBar';
const BulkActionBarMeta: Meta<typeof BulkActionBar> = {
  title: 'Shared/BulkActionBar',
  component: BulkActionBar,
};
export const BulkActionBarDefault: StoryObj<typeof BulkActionBar> = {
  render: () => (
    <BulkActionBar
      selectedCount={5}
      actions={[
        { label: 'Delete', action: 'delete', variant: 'danger' },
        { label: 'Export', action: 'export' },
      ]}
      onAction={(action) => console.log('Action:', action)}
      onClear={() => console.log('Clear selection')}
    />
  ),
};

// ── ActivityTimeline ────────────────────────────────────────────────────
import { ActivityTimeline } from './ActivityTimeline';
const ActivityTimelineMeta: Meta<typeof ActivityTimeline> = {
  title: 'Shared/ActivityTimeline',
  component: ActivityTimeline,
};
export const ActivityTimelineDefault: StoryObj<typeof ActivityTimeline> = {
  render: () => (
    <ActivityTimeline
      events={[
        { timestamp: '2026-05-15T10:30:00Z', actor: 'jane@acme.com', action: 'created asset', target: 'customer-db' },
        { timestamp: '2026-05-15T11:00:00Z', actor: 'bob@acme.com', action: 'published contract', target: 'customer-db-v2' },
        { timestamp: '2026-05-15T12:15:00Z', actor: 'system', action: 'compliance scan completed', target: 'customer-db' },
      ]}
    />
  ),
};
