/**
 * CodeBlock — syntax-highlighted code viewer with copy button.
 *
 * Uses highlight.js with only the grammars we need (no 190-lang bundle).
 * Falls back to plain <pre><code> for 'plaintext' or on highlight error.
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import hljs from 'highlight.js/lib/core';
import json from 'highlight.js/lib/languages/json';
import xml from 'highlight.js/lib/languages/xml';
import plaintext from 'highlight.js/lib/languages/plaintext';
import DOMPurify from 'dompurify';
import { Copy, Check } from '../config/iconRegistry';
import { Button } from './Button';
import './CodeBlock.css';

/* Register only the grammars we need */
hljs.registerLanguage('json', json);
hljs.registerLanguage('xml', xml);
hljs.registerLanguage('plaintext', plaintext);
/* turtle / sparql / csv have no official hljs grammar — render as plaintext */

type CodeLanguage = 'turtle' | 'json' | 'sparql' | 'xml' | 'csv' | 'plaintext';

export interface CodeBlockProps {
  language: CodeLanguage;
  code: string;
  maxHeight?: string;
}

const HIGHLIGHTABLE: Record<string, string> = { json: 'json', xml: 'xml' };

export function CodeBlock({ language, code, maxHeight = '500px' }: CodeBlockProps) {
  const codeRef = useRef<HTMLElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!codeRef.current) return;
    const lang = HIGHLIGHTABLE[language];
    if (!lang) {
      codeRef.current.textContent = code;
      return;
    }
    try {
      const result = hljs.highlight(code, { language: lang });
      codeRef.current.innerHTML = DOMPurify.sanitize(result.value, {
        ALLOWED_TAGS: ['span'],
        ALLOWED_ATTR: ['class'],
      });
    } catch {
      codeRef.current.textContent = code;
    }
  }, [code, language]);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard unavailable */
    }
  }, [code]);

  return (
    <div className="code-block" style={{ maxHeight }}>
      <div className="code-block__toolbar">
        <span className="code-block__lang">{language}</span>
        <Button
          variant="ghost"
          size="sm"
          leadingIcon={copied ? Check : Copy}
          onClick={handleCopy}
          aria-label="Copy code"
          data-testid="code-block-copy"
        >
          {copied ? 'Copied' : 'Copy'}
        </Button>
      </div>
      <pre className="code-block__pre">
        <code ref={codeRef} className="code-block__code">
          {code}
        </code>
      </pre>
    </div>
  );
}
