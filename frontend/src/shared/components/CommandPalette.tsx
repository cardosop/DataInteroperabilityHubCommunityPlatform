/**
 * CommandPalette — 223.5.3.
 *
 * Global ⌘K/Ctrl-K launcher. Wraps the `cmdk` primitive so we don't
 * re-implement fuzzy match, keyboard navigation, or a11y semantics
 * (it's already a proper combobox with `role="listbox"` + `role="option"`).
 *
 * Groups:
 *   - **Recent** (from localStorage) — the last ≤8 paths the user
 *     navigated to via this palette, newest first, deduped.
 *   - **Pages** — a static list of nav targets (Sidebar / Router).
 *   - **Actions** — verb-style shortcuts (Create Asset, Create Contract…).
 *
 * Consumers inject `pages` / `actions` so the palette stays presentation-
 * only: no tight coupling to any specific sidebar or route tree, which
 * keeps it testable in isolation.
 */

import { Command } from 'cmdk';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useKeyboardShortcut } from '../hooks/useKeyboardShortcut';
import './CommandPalette.css';

export interface PaletteItem {
  /** Stable id used as React key and cmdk `value`. Defaults to `path`. */
  id?: string;
  label: string;
  path: string;
  keywords?: string[];
}

export interface CommandPaletteProps {
  pages: PaletteItem[];
  actions?: PaletteItem[];
  /** localStorage key for recent navigations. Defaults to `meshant.palette.recent`. */
  recentKey?: string;
  /** Upper bound on recent entries. Defaults to 8. */
  maxRecent?: number;
}

const DEFAULT_RECENT_KEY = 'meshant.palette.recent';
const DEFAULT_MAX_RECENT = 8;

function readRecent(key: string): string[] {
  if (typeof localStorage === 'undefined') return [];
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((p): p is string => typeof p === 'string') : [];
  } catch {
    return [];
  }
}

function writeRecent(key: string, paths: string[]): void {
  try {
    localStorage.setItem(key, JSON.stringify(paths));
  } catch {
    /* storage might be full / disabled — silent */
  }
}

export function CommandPalette({
  pages,
  actions = [],
  recentKey = DEFAULT_RECENT_KEY,
  maxRecent = DEFAULT_MAX_RECENT,
}: CommandPaletteProps) {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [recentPaths, setRecentPaths] = useState<string[]>(() => readRecent(recentKey));

  useKeyboardShortcut(
    { key: 'k', modOrCtrl: true },
    useCallback(() => setOpen((v) => !v), []),
  );

  // Sync the recent list from storage whenever the palette opens, so a
  // previous-tab navigation shows up without requiring a re-mount.
  useEffect(() => {
    if (open) setRecentPaths(readRecent(recentKey));
  }, [open, recentKey]);

  const pageByPath = useMemo(() => {
    const m = new Map<string, PaletteItem>();
    [...pages, ...actions].forEach((item) => m.set(item.path, item));
    return m;
  }, [pages, actions]);

  const recentItems = useMemo(
    () =>
      recentPaths
        .map((p) => pageByPath.get(p))
        .filter((x): x is PaletteItem => !!x),
    [recentPaths, pageByPath],
  );

  const handleSelect = useCallback(
    (item: PaletteItem) => {
      const next = [item.path, ...recentPaths.filter((p) => p !== item.path)].slice(
        0,
        maxRecent,
      );
      writeRecent(recentKey, next);
      setRecentPaths(next);
      setOpen(false);
      navigate(item.path);
    },
    [recentPaths, recentKey, maxRecent, navigate],
  );

  // `cmdk` already handles Escape internally via Radix Dialog when we
  // pass `onOpenChange`; we rely on that instead of rolling our own.
  return (
    <Command.Dialog
      open={open}
      onOpenChange={setOpen}
      label="Command palette"
      overlayClassName="command-palette-overlay"
      contentClassName="command-palette-content"
    >
      <Command.Input
        placeholder="Type to search pages, actions, and recent items…"
        className="command-palette-input"
      />
      <Command.List className="command-palette-list">
        <Command.Empty className="command-palette-empty">
          No results.
        </Command.Empty>

        {recentItems.length > 0 && (
          <Command.Group heading="Recent" className="command-palette-group">
            {recentItems.map((item) => (
              // `value` drives cmdk's fuzzy filter. We pack label + path
              // + keywords only — deliberately NOT the group name, so
              // typing "page" or "recent" doesn't accidentally match
              // every row in a group. `key` disambiguates items that
              // share a path across groups (Recent ↔ Pages).
              <Command.Item
                key={`recent-${item.id ?? item.path}`}
                value={`${item.label} ${item.path} ${(item.keywords ?? []).join(' ')}`}
                onSelect={() => handleSelect(item)}
                className="command-palette-item"
              >
                {item.label}
                <span className="command-palette-hint">{item.path}</span>
              </Command.Item>
            ))}
          </Command.Group>
        )}

        <Command.Group heading="Pages" className="command-palette-group">
          {pages.map((item) => (
            <Command.Item
              key={`page-${item.id ?? item.path}`}
              value={`${item.label} ${item.path} ${(item.keywords ?? []).join(' ')}`}
              onSelect={() => handleSelect(item)}
              className="command-palette-item"
            >
              {item.label}
              <span className="command-palette-hint">{item.path}</span>
            </Command.Item>
          ))}
        </Command.Group>

        {actions.length > 0 && (
          <Command.Group heading="Actions" className="command-palette-group">
            {actions.map((item) => (
              <Command.Item
                key={`action-${item.id ?? item.path}`}
                value={`${item.label} ${item.path} ${(item.keywords ?? []).join(' ')}`}
                onSelect={() => handleSelect(item)}
                className="command-palette-item"
              >
                {item.label}
              </Command.Item>
            ))}
          </Command.Group>
        )}
      </Command.List>
    </Command.Dialog>
  );
}
