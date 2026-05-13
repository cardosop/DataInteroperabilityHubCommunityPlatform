/**
 * Phase 278.E.4 — keyboard shortcuts cheatsheet modal.
 *
 * Opens on `?` keypress. Shows common shortcuts: n=new, /=search,
 * g a=go assets, g c=go contracts, plus navigation + Cmd-K palette.
 */
import { useEffect, useState, useCallback, type FC } from 'react';
import './KeyboardShortcuts.css';

interface ShortcutGroup {
  title: string;
  shortcuts: Array<{ keys: string; description: string }>;
}

const SHORTCUTS: ShortcutGroup[] = [
  {
    title: 'Navigation',
    shortcuts: [
      { keys: 'g a', description: 'Go to Assets' },
      { keys: 'g c', description: 'Go to Contracts' },
      { keys: 'g m', description: 'Go to Marketplace' },
      { keys: 'g d', description: 'Go to Dashboard' },
      { keys: 'g s', description: 'Go to Settings' },
    ],
  },
  {
    title: 'Actions',
    shortcuts: [
      { keys: 'n', description: 'New asset / item (contextual)' },
      { keys: '/', description: 'Search' },
      { keys: '⌘ K', description: 'Command palette' },
      { keys: '?', description: 'Show this cheatsheet' },
      { keys: 'Esc', description: 'Close modal / dialog / cheatsheet' },
    ],
  },
  {
    title: 'Lists',
    shortcuts: [
      { keys: 'j', description: 'Next item' },
      { keys: 'k', description: 'Previous item' },
      { keys: 'Enter', description: 'Open selected item' },
    ],
  },
];

export const KeyboardShortcuts: FC = () => {
  const [open, setOpen] = useState(false);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === '?' && !e.ctrlKey && !e.metaKey && !e.altKey) {
        const target = e.target as HTMLElement;
        if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
          return;
        }
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === 'Escape' && open) {
        setOpen(false);
      }
    },
    [open],
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  if (!open) return null;

  return (
    <div
      className="kbd-cheatsheet-overlay"
      onClick={() => setOpen(false)}
      role="dialog"
      aria-label="Keyboard shortcuts"
      data-testid="keyboard-shortcuts"
    >
      <div className="kbd-cheatsheet" onClick={(e) => e.stopPropagation()}>
        <div className="kbd-cheatsheet-header">
          <h2>Keyboard Shortcuts</h2>
          <button
            type="button"
            className="kbd-cheatsheet-close"
            onClick={() => setOpen(false)}
            aria-label="Close shortcuts"
          >
            &times;
          </button>
        </div>
        {SHORTCUTS.map((group) => (
          <div key={group.title} className="kbd-cheatsheet-group">
            <h3>{group.title}</h3>
            <ul>
              {group.shortcuts.map((s) => (
                <li key={s.keys}>
                  <kbd>{s.keys}</kbd>
                  <span>{s.description}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
};
