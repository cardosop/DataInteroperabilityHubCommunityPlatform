/**
 * useSPARQLHistory — persists SPARQL query history in localStorage.
 */

import { useState, useCallback } from 'react';

const STORAGE_KEY = 'meshant.sparql.history';
const MAX_ENTRIES = 20;

function readHistory(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function useSPARQLHistory() {
  const [history, setHistory] = useState<string[]>(readHistory);

  const pushToHistory = useCallback((query: string) => {
    setHistory((prev) => {
      const trimmed = query.trim();
      if (!trimmed) return prev;
      // Deduplicate: skip if same query already at index 0
      if (prev[0] === trimmed) return prev;
      const next = [trimmed, ...prev.filter((q) => q !== trimmed)].slice(0, MAX_ENTRIES);
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {
        /* quota exceeded — ignore */
      }
      return next;
    });
  }, []);

  const clearHistory = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setHistory([]);
  }, []);

  return { history, pushToHistory, clearHistory };
}
