/**
 * UuidWithCopy Component Tests
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { UuidWithCopy } from '../UuidWithCopy';

describe('UuidWithCopy', () => {
  const testUuid = 'a1b2c3d4-e5f6-7890-abcd-ef1234567890';

  it('renders the UUID in a code element', () => {
    render(<UuidWithCopy value={testUuid} />);
    expect(screen.getByText(testUuid)).toBeInTheDocument();
    expect(screen.getByText(testUuid).tagName).toBe('CODE');
  });

  it('renders a copy button with aria-label', () => {
    render(<UuidWithCopy value={testUuid} />);
    const copyBtn = screen.getByRole('button', { name: /copy uuid/i });
    expect(copyBtn).toBeInTheDocument();
  });

  it('shows copied state when copy button is clicked', async () => {
    const user = userEvent.setup();
    render(<UuidWithCopy value={testUuid} />);
    const copyBtn = screen.getByRole('button', { name: /copy uuid/i });

    await user.click(copyBtn);

    await waitFor(() => expect(screen.getByTitle('Copied!')).toBeInTheDocument());
    expect(copyBtn).toHaveTextContent('✓');
  });

  it('renders with custom label when provided', () => {
    render(<UuidWithCopy value={testUuid} label="Asset ID" />);
    expect(screen.getByText('Asset ID')).toBeInTheDocument();
    expect(screen.getByText(testUuid)).toBeInTheDocument();
  });

  it('copy button is keyboard accessible', async () => {
    const user = userEvent.setup();
    render(<UuidWithCopy value={testUuid} />);
    const copyBtn = screen.getByRole('button', { name: /copy uuid/i });
    copyBtn.focus();
    expect(document.activeElement).toBe(copyBtn);
    await user.keyboard('{Enter}');
    await waitFor(() => expect(screen.getByTitle('Copied!')).toBeInTheDocument());
  });
});
