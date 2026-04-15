/**
 * Tooltip tests — 222.3.
 *
 * Verifies the hover-triggered tooltip also responds to focus + Escape
 * (WCAG 2.1 SC 1.4.13), renders arbitrary content, and stays hidden when
 * the trigger is not interacted with.
 *
 * Uses real `@floating-ui/react` — no mocks. Tooltip content is portaled
 * into `document.body`, so queries go through `screen`, not the rendered
 * container scope.
 */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { Tooltip } from './Tooltip';

describe('Tooltip', () => {
  it('is hidden by default', () => {
    render(
      <Tooltip content="Helpful hint">
        <button type="button">Trigger</button>
      </Tooltip>,
    );
    expect(screen.queryByRole('tooltip')).toBeNull();
  });

  it('shows the tooltip on hover and hides on unhover', async () => {
    const user = userEvent.setup();
    render(
      <Tooltip content="Helpful hint">
        <button type="button">Trigger</button>
      </Tooltip>,
    );
    const trigger = screen.getByRole('button', { name: /trigger/i });
    await user.hover(trigger);
    await waitFor(() => {
      expect(screen.getByRole('tooltip')).toHaveTextContent('Helpful hint');
    });
    await user.unhover(trigger);
    await waitFor(() => {
      expect(screen.queryByRole('tooltip')).toBeNull();
    });
  });

  it('shows on keyboard focus (WCAG keyboard access)', async () => {
    render(
      <Tooltip content="Focus hint">
        <button type="button">Trigger</button>
      </Tooltip>,
    );
    const trigger = screen.getByRole('button', { name: /trigger/i });
    trigger.focus();
    await waitFor(() => {
      expect(screen.getByRole('tooltip')).toHaveTextContent('Focus hint');
    });
  });

  it('dismisses on Escape while focused', async () => {
    render(
      <Tooltip content="Escapable hint">
        <button type="button">Trigger</button>
      </Tooltip>,
    );
    const trigger = screen.getByRole('button', { name: /trigger/i });
    trigger.focus();
    await waitFor(() => {
      expect(screen.getByRole('tooltip')).toBeInTheDocument();
    });
    fireEvent.keyDown(document.activeElement || document.body, {
      key: 'Escape',
    });
    await waitFor(() => {
      expect(screen.queryByRole('tooltip')).toBeNull();
    });
  });

  it('wires aria-describedby on the trigger while visible', async () => {
    const user = userEvent.setup();
    render(
      <Tooltip content="Described content">
        <button type="button">Trigger</button>
      </Tooltip>,
    );
    const trigger = screen.getByRole('button', { name: /trigger/i });
    expect(trigger).not.toHaveAttribute('aria-describedby');
    await user.hover(trigger);
    await waitFor(() => {
      expect(trigger).toHaveAttribute('aria-describedby');
      const id = trigger.getAttribute('aria-describedby');
      expect(id).toBeTruthy();
      expect(document.getElementById(id!)).toHaveTextContent('Described content');
    });
  });
});
