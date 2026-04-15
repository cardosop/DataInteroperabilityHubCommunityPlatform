/**
 * Tooltip — WCAG-accessible hover/focus tooltip built on @floating-ui/react.
 *
 * Hover, focus, and Escape-dismiss come from the `useHover`, `useFocus`, and
 * `useDismiss` interactions. Content is rendered in a `FloatingPortal` so it
 * always escapes clipping ancestors (overflow:hidden cards, modals, etc.)
 * without manual z-index gymnastics.
 *
 * The wrapped child is cloned so the trigger props (`ref`, hover/focus/keydown
 * listeners, `aria-describedby`) land on the real interactive element — not on
 * an extra <span> that would break label-association and focus rings.
 */

import {
  FloatingArrow,
  FloatingPortal,
  arrow,
  autoUpdate,
  flip,
  offset,
  shift,
  useDismiss,
  useFloating,
  useFocus,
  useHover,
  useInteractions,
  useRole,
  useTransitionStyles,
} from '@floating-ui/react';
import {
  Children,
  cloneElement,
  isValidElement,
  useId,
  useRef,
  useState,
  type ReactElement,
  type ReactNode,
  type Ref,
} from 'react';
import './Tooltip.css';

export interface TooltipProps {
  /** Content rendered inside the tooltip bubble. */
  content: ReactNode;
  /**
   * Exactly one interactive child (button, link, icon wrapper). The child
   * must forward `ref` and spread props; lucide icons wrapped in a <span>
   * or <button> satisfy this.
   */
  children: ReactElement;
  /** Tooltip side relative to the trigger. Defaults to "top". */
  placement?: 'top' | 'right' | 'bottom' | 'left';
  /** Hover open delay in ms. Defaults to 150. */
  openDelay?: number;
}

const ARROW_SIZE = 8;

type TriggerProps = {
  ref?: Ref<HTMLElement>;
  'aria-describedby'?: string;
} & Record<string, unknown>;

export function Tooltip({
  content,
  children,
  placement = 'top',
  openDelay = 150,
}: TooltipProps) {
  const [isOpen, setIsOpen] = useState(false);
  const arrowRef = useRef<SVGSVGElement>(null);
  const tooltipId = useId();

  const { refs, floatingStyles, context } = useFloating({
    open: isOpen,
    onOpenChange: setIsOpen,
    placement,
    whileElementsMounted: autoUpdate,
    middleware: [
      offset(ARROW_SIZE + 2),
      flip({ fallbackAxisSideDirection: 'start' }),
      shift({ padding: 8 }),
      arrow({ element: arrowRef }),
    ],
  });

  const hover = useHover(context, {
    move: false,
    delay: { open: openDelay, close: 0 },
  });
  const focus = useFocus(context);
  const dismiss = useDismiss(context, { escapeKey: true });
  const role = useRole(context, { role: 'tooltip' });

  const { getReferenceProps, getFloatingProps } = useInteractions([
    hover,
    focus,
    dismiss,
    role,
  ]);

  const { isMounted, styles: transitionStyles } = useTransitionStyles(context, {
    duration: 120,
  });

  const child = Children.only(children);
  if (!isValidElement(child)) {
    throw new Error('Tooltip requires exactly one React element child.');
  }

  const childProps = child.props as TriggerProps;
  const existingDescribedBy = childProps['aria-describedby'] as
    | string
    | undefined;
  const mergedDescribedBy = isOpen
    ? [existingDescribedBy, tooltipId].filter(Boolean).join(' ')
    : existingDescribedBy;

  // getReferenceProps merges floating-ui event listeners with any
  // caller-provided handlers on the child (onClick, onMouseEnter, …). Ref
  // is a React prop and is not plumbed through getReferenceProps, so we
  // attach it separately on the cloned element.
  const referenceProps = getReferenceProps({
    ...childProps,
    'aria-describedby': mergedDescribedBy,
  }) as TriggerProps;

  const trigger = cloneElement(child, {
    ref: refs.setReference as Ref<HTMLElement>,
    ...referenceProps,
  });

  return (
    <>
      {trigger}
      {isMounted && (
        <FloatingPortal>
          <div
            ref={refs.setFloating}
            id={tooltipId}
            className="tooltip-bubble"
            style={{ ...floatingStyles, ...transitionStyles }}
            {...getFloatingProps()}
          >
            {content}
            <FloatingArrow
              ref={arrowRef}
              context={context}
              className="tooltip-arrow"
              width={ARROW_SIZE * 2}
              height={ARROW_SIZE}
            />
          </div>
        </FloatingPortal>
      )}
    </>
  );
}
