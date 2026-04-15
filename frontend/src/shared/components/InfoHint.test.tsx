/**
 * InfoHint tests — 222.3.
 *
 * Verifies the helper renders an accessible icon trigger and surfaces the
 * supplied tooltip content on hover and focus. Real Tooltip/@floating-ui —
 * no mocks.
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { InfoHint } from './InfoHint';

describe('InfoHint', () => {
  it('renders a focusable help trigger', () => {
    render(<InfoHint label="What is normalization?" content="An explanation." />);
    const trigger = screen.getByRole('button', { name: /what is normalization/i });
    expect(trigger).toBeInTheDocument();
    expect(trigger).toHaveAttribute('type', 'button');
  });

  it('reveals tooltip content on hover', async () => {
    const user = userEvent.setup();
    render(
      <InfoHint
        label="Quality Score"
        content="Aggregated DQ check pass rate for this run."
      />,
    );
    const trigger = screen.getByRole('button', { name: /quality score/i });
    await user.hover(trigger);
    await waitFor(() => {
      expect(screen.getByRole('tooltip')).toHaveTextContent(
        /Aggregated DQ check pass rate/,
      );
    });
  });

  it('reveals tooltip content on keyboard focus', async () => {
    render(
      <InfoHint label="Activation" content="Whether the asset is live." />,
    );
    const trigger = screen.getByRole('button', { name: /activation/i });
    trigger.focus();
    await waitFor(() => {
      expect(screen.getByRole('tooltip')).toHaveTextContent(
        /Whether the asset is live/,
      );
    });
  });

  it('renders the lucide help-circle icon inside the trigger', () => {
    const { container } = render(
      <InfoHint label="Spec Type" content="OpenAPI or JSON Schema." />,
    );
    // lucide-react v0.577 aliases HelpCircle -> CircleQuestionMark; every
    // icon also carries the base `lucide` class. Target the svg under the
    // trigger button so this passes regardless of which alias is exported.
    const trigger = container.querySelector('button.info-hint-trigger');
    expect(trigger).not.toBeNull();
    const svg = trigger!.querySelector('svg.lucide');
    expect(svg).not.toBeNull();
    expect(svg).toHaveAttribute('aria-hidden', 'true');
    expect(svg).toHaveAttribute('focusable', 'false');
  });
});
