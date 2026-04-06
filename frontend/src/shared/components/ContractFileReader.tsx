/**
 * ContractFileReader — drag-and-drop zone + textarea for YAML/JSON
 * contract content with real-time spec type auto-detection.
 *
 * Uses detectSpecType() to identify ODPS, ODCS, HubContract, or UNKNOWN
 * and displays a detection badge. Supports file drop, paste, and typing.
 */

import { useState, useRef, useCallback, useEffect, type RefObject } from 'react';
import { detectSpecType, type DetectedSpec } from '../utils/detectSpecType';
import { useDebouncedValue } from '../hooks/useDebouncedValue';
import './ContractFileReader.css';

/**
 * Stores the latest callback in a ref so effects don't re-run
 * when the parent passes inline functions.
 */
function useLatestRef<T>(value: T): RefObject<T> {
  const ref = useRef(value);
  ref.current = value;
  return ref;
}

const DEFAULT_MAX_SIZE = 5 * 1024 * 1024; // 5MB

export interface ContractFileReaderProps {
  /** Called when content changes (paste, type, or file drop) */
  onContentChange: (content: string, format: string) => void;
  /** Called when spec type detection completes */
  onDetection?: (detected: DetectedSpec) => void;
  /** Max file size in bytes (default 5MB) */
  maxSizeBytes?: number;
  /** Initial content (e.g., from sessionStorage restore) */
  initialContent?: string;
  /** Custom data-testid for the root element */
  'data-testid'?: string;
}

/**
 * Infer format from file extension.
 */
function formatFromFileName(name: string): string {
  const lower = name.toLowerCase();
  if (lower.endsWith('.yaml') || lower.endsWith('.yml')) return 'yaml';
  if (lower.endsWith('.json')) return 'json';
  return 'text';
}

/**
 * Infer format from content heuristic.
 */
function formatFromContent(content: string): string {
  const trimmed = content.trimStart();
  if (trimmed.startsWith('{') || trimmed.startsWith('[')) return 'json';
  return 'yaml';
}

export function ContractFileReader({
  onContentChange,
  onDetection,
  maxSizeBytes = DEFAULT_MAX_SIZE,
  initialContent = '',
  'data-testid': testId,
}: ContractFileReaderProps) {
  const [content, setContent] = useState(initialContent);
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detected, setDetected] = useState<DetectedSpec | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Stable refs for callbacks — prevents re-renders from inline functions
  const onDetectionRef = useLatestRef(onDetection);
  const onContentChangeRef = useLatestRef(onContentChange);

  // Debounce content for detection (300ms on typing, immediate on paste/drop)
  const debouncedContent = useDebouncedValue(content, 300);

  // Run detection when debounced content changes
  useEffect(() => {
    if (!debouncedContent.trim()) {
      setDetected(null);
      return;
    }
    const result = detectSpecType(debouncedContent);
    setDetected(result);
    onDetectionRef.current?.(result);
  }, [debouncedContent, onDetectionRef]);

  // Run detection immediately for initial content
  useEffect(() => {
    if (initialContent.trim()) {
      const result = detectSpecType(initialContent);
      setDetected(result);
      onDetectionRef.current?.(result);
    }
    // Only on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleContentChange = useCallback(
    (newContent: string, format: string) => {
      setContent(newContent);
      setError(null);
      onContentChangeRef.current(newContent, format);
    },
    [onContentChangeRef],
  );

  const handleTextareaChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const value = e.target.value;
      handleContentChange(value, formatFromContent(value));
    },
    [handleContentChange],
  );

  const readFile = useCallback(
    (file: File) => {
      if (file.size > maxSizeBytes) {
        setError(
          `File too large (${(file.size / 1024 / 1024).toFixed(1)}MB). Size limit is ${(maxSizeBytes / 1024 / 1024).toFixed(0)}MB.`,
        );
        return;
      }

      const format = formatFromFileName(file.name);
      const reader = new FileReader();
      reader.onload = (e) => {
        const text = e.target?.result as string;
        setContent(text);
        setError(null);
        onContentChangeRef.current(text, format);
        // Immediate detection for file drops (bypass debounce)
        const result = detectSpecType(text);
        setDetected(result);
        onDetectionRef.current?.(result);
      };
      reader.onerror = () => {
        setError('Failed to read file.');
      };
      reader.readAsText(file);
    },
    [maxSizeBytes, onContentChangeRef, onDetectionRef],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files?.[0];
      if (file) readFile(file);
    },
    [readFile],
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleFileInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) readFile(file);
    },
    [readFile],
  );

  const handleDropZoneClick = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleDropZoneKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        fileInputRef.current?.click();
      }
    },
    [],
  );

  const badgeClass = detected
    ? `contract-file-reader__badge contract-file-reader__badge--${detected.type.toLowerCase()}`
    : '';

  const rootClass = [
    'contract-file-reader',
    isDragging ? 'contract-file-reader--dragging' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={rootClass} data-testid={testId}>
      <div
        className="contract-file-reader__dropzone"
        data-testid="contract-file-reader-dropzone"
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        role="button"
        tabIndex={0}
        onClick={handleDropZoneClick}
        onKeyDown={handleDropZoneKeyDown}
        aria-label="Drop a contract file or click to browse"
      >
        <p className="contract-file-reader__dropzone-text">
          Drag and drop a YAML or JSON contract file, or click to browse
        </p>
        <input
          ref={fileInputRef}
          type="file"
          accept=".yaml,.yml,.json"
          className="contract-file-reader__file-input"
          onChange={handleFileInputChange}
          tabIndex={-1}
        />
      </div>

      <textarea
        className="contract-file-reader__textarea"
        value={content}
        onChange={handleTextareaChange}
        placeholder="Or paste your contract YAML / JSON here..."
        aria-label="Contract content (YAML or JSON)"
      />

      <div className="contract-file-reader__footer">
        {detected && detected.type !== 'UNKNOWN' && (
          <span className={badgeClass}>
            Detected: {detected.type}
            {detected.version ? ` ${detected.version}` : ''}
          </span>
        )}
        {error && <span className="contract-file-reader__error">{error}</span>}
      </div>
    </div>
  );
}
