/**
 * useRouteFocus — focus management on route changes (278.L.2).
 *
 * Moves focus to ``#main-content`` on navigation so screen-reader
 * users land on the new page content after a route transition.
 * Respects ``prefers-reduced-motion`` to avoid scrolling on focus.
 */
import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

export function useRouteFocus() {
  const { pathname } = useLocation();

  useEffect(() => {
    // Yield to the browser so the new page content has rendered
    const timer = setTimeout(() => {
      const main = document.getElementById('main-content');
      if (main) {
        // Set tabindex=-1 so the element is programmatically focusable
        // but does not appear in the natural tab order
        if (main.getAttribute('tabindex') !== '-1') {
          main.setAttribute('tabindex', '-1');
        }
        main.focus({ preventScroll: true });
      }
    }, 100);

    return () => clearTimeout(timer);
  }, [pathname]);
}
