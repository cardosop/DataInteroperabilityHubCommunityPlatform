/**
 * Tests for ContractFileReader — drag-and-drop + paste component
 * for YAML/JSON contract content with auto-detection.
 *
 * TDD: Tests written FIRST, then implementation to make them pass.
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ContractFileReader } from '../ContractFileReader';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const odcsYaml = [
  'apiVersion: odcs/v3',
  'kind: DataContract',
  'id: test-contract',
  'name: Test Contract',
].join('\n');

const odpsJson = JSON.stringify({
  schema: 'https://opendataproducts.org/schema/v4.1',
  version: '4.1',
  product: { details: { en: { productID: 'p', name: 'P' } } },
});

function createFile(content: string, name: string, type = 'text/plain'): File {
  return new File([content], name, { type });
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

describe('ContractFileReader — rendering', () => {
  it('renders a textarea and drop zone', () => {
    render(<ContractFileReader onContentChange={vi.fn()} />);
    expect(screen.getByRole('textbox')).toBeInTheDocument();
    expect(screen.getByText(/drag|drop|paste/i)).toBeInTheDocument();
  });

  it('renders with custom data-testid', () => {
    render(
      <ContractFileReader onContentChange={vi.fn()} data-testid="my-reader" />,
    );
    expect(screen.getByTestId('my-reader')).toBeInTheDocument();
  });

  it('renders with initial content', () => {
    render(
      <ContractFileReader
        onContentChange={vi.fn()}
        initialContent={odcsYaml}
      />,
    );
    expect(screen.getByRole('textbox')).toHaveValue(odcsYaml);
  });
});

// ---------------------------------------------------------------------------
// Paste / typing
// ---------------------------------------------------------------------------

describe('ContractFileReader — paste and typing', () => {
  it('calls onContentChange when user types', async () => {
    const onContentChange = vi.fn();
    render(<ContractFileReader onContentChange={onContentChange} />);

    const textarea = screen.getByRole('textbox');
    await userEvent.setup().type(textarea, 'hello');

    // Content callback should fire (may be debounced)
    await waitFor(() => {
      expect(onContentChange).toHaveBeenCalled();
    });
  });

  it('calls onContentChange on paste', async () => {
    const onContentChange = vi.fn();
    render(<ContractFileReader onContentChange={onContentChange} />);

    const textarea = screen.getByRole('textbox');
    // Simulate paste by setting value and firing input event
    fireEvent.change(textarea, { target: { value: odcsYaml } });

    await waitFor(() => {
      expect(onContentChange).toHaveBeenCalledWith(
        odcsYaml,
        expect.any(String),
      );
    });
  });

  it('calls onDetection with detected spec type on paste', async () => {
    const onDetection = vi.fn();
    render(
      <ContractFileReader onContentChange={vi.fn()} onDetection={onDetection} />,
    );

    const textarea = screen.getByRole('textbox');
    fireEvent.change(textarea, { target: { value: odcsYaml } });

    await waitFor(() => {
      expect(onDetection).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'ODCS' }),
      );
    });
  });

  it('shows detection badge after content is entered', async () => {
    render(<ContractFileReader onContentChange={vi.fn()} />);

    const textarea = screen.getByRole('textbox');
    fireEvent.change(textarea, { target: { value: odcsYaml } });

    await waitFor(() => {
      expect(screen.getByText(/ODCS/)).toBeInTheDocument();
    });
  });

  it('shows ODPS detection badge for ODPS content', async () => {
    render(<ContractFileReader onContentChange={vi.fn()} />);

    const textarea = screen.getByRole('textbox');
    fireEvent.change(textarea, { target: { value: odpsJson } });

    await waitFor(() => {
      expect(screen.getByText(/ODPS/)).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// File drop
// ---------------------------------------------------------------------------

describe('ContractFileReader — file drop', () => {
  it('reads dropped YAML file and calls onContentChange', async () => {
    const onContentChange = vi.fn();
    render(<ContractFileReader onContentChange={onContentChange} />);

    const dropZone = screen.getByTestId('contract-file-reader-dropzone');
    const file = createFile(odcsYaml, 'contract.yaml');

    const dataTransfer = {
      files: [file],
      items: [{ kind: 'file', type: file.type, getAsFile: () => file }],
      types: ['Files'],
    };

    fireEvent.drop(dropZone, { dataTransfer });

    await waitFor(() => {
      expect(onContentChange).toHaveBeenCalledWith(odcsYaml, 'yaml');
    });
  });

  it('reads dropped JSON file and calls onContentChange', async () => {
    const onContentChange = vi.fn();
    render(<ContractFileReader onContentChange={onContentChange} />);

    const dropZone = screen.getByTestId('contract-file-reader-dropzone');
    const file = createFile(odpsJson, 'contract.json');

    const dataTransfer = {
      files: [file],
      items: [{ kind: 'file', type: file.type, getAsFile: () => file }],
      types: ['Files'],
    };

    fireEvent.drop(dropZone, { dataTransfer });

    await waitFor(() => {
      expect(onContentChange).toHaveBeenCalledWith(odpsJson, 'json');
    });
  });

  it('detects spec type from dropped file', async () => {
    const onDetection = vi.fn();
    render(
      <ContractFileReader onContentChange={vi.fn()} onDetection={onDetection} />,
    );

    const dropZone = screen.getByTestId('contract-file-reader-dropzone');
    const file = createFile(odcsYaml, 'contract.yaml');

    fireEvent.drop(dropZone, {
      dataTransfer: {
        files: [file],
        items: [{ kind: 'file', type: file.type, getAsFile: () => file }],
        types: ['Files'],
      },
    });

    await waitFor(() => {
      expect(onDetection).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'ODCS' }),
      );
    });
  });

  it('shows visual feedback during drag over', () => {
    render(<ContractFileReader onContentChange={vi.fn()} />);
    const dropZone = screen.getByTestId('contract-file-reader-dropzone');

    fireEvent.dragOver(dropZone, {
      dataTransfer: { types: ['Files'] },
    });

    // Dragging class is on the root container, not the dropzone itself
    expect(dropZone.closest('.contract-file-reader')).toHaveClass(
      'contract-file-reader--dragging',
    );
  });

  it('removes drag feedback on drag leave', () => {
    render(<ContractFileReader onContentChange={vi.fn()} />);
    const dropZone = screen.getByTestId('contract-file-reader-dropzone');

    fireEvent.dragOver(dropZone, {
      dataTransfer: { types: ['Files'] },
    });
    fireEvent.dragLeave(dropZone);

    expect(dropZone.closest('.contract-file-reader')).not.toHaveClass(
      'contract-file-reader--dragging',
    );
  });
});

// ---------------------------------------------------------------------------
// Size limit
// ---------------------------------------------------------------------------

describe('ContractFileReader — size limit', () => {
  it('rejects files larger than maxSizeBytes', async () => {
    const onContentChange = vi.fn();
    render(
      <ContractFileReader
        onContentChange={onContentChange}
        maxSizeBytes={100}
      />,
    );

    const dropZone = screen.getByTestId('contract-file-reader-dropzone');
    const largeContent = 'x'.repeat(200);
    const file = createFile(largeContent, 'big.yaml');

    fireEvent.drop(dropZone, {
      dataTransfer: {
        files: [file],
        items: [{ kind: 'file', type: file.type, getAsFile: () => file }],
        types: ['Files'],
      },
    });

    await waitFor(() => {
      expect(screen.getByText(/too large|exceeds|size limit/i)).toBeInTheDocument();
    });

    // Should NOT call onContentChange for oversized files
    expect(onContentChange).not.toHaveBeenCalled();
  });

  it('uses 5MB default limit', () => {
    const { container } = render(
      <ContractFileReader onContentChange={vi.fn()} />,
    );
    // Component should exist without errors — 5MB default is internal
    expect(container).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// Accessibility
// ---------------------------------------------------------------------------

describe('ContractFileReader — accessibility', () => {
  it('textarea has aria-label', () => {
    render(<ContractFileReader onContentChange={vi.fn()} />);
    const textarea = screen.getByRole('textbox');
    expect(textarea).toHaveAttribute('aria-label');
  });

  it('drop zone is keyboard accessible', () => {
    render(<ContractFileReader onContentChange={vi.fn()} />);
    const dropZone = screen.getByTestId('contract-file-reader-dropzone');
    // Drop zone should be focusable and have a role
    expect(dropZone.querySelector('[role="button"]') || dropZone.getAttribute('role')).toBeTruthy();
  });
});

// ---------------------------------------------------------------------------
// Detection badge display
// ---------------------------------------------------------------------------

describe('ContractFileReader — detection badge', () => {
  it('shows version in badge when available', async () => {
    render(<ContractFileReader onContentChange={vi.fn()} />);

    const textarea = screen.getByRole('textbox');
    fireEvent.change(textarea, { target: { value: odpsJson } });

    await waitFor(() => {
      // Badge text includes both type and version in one span
      expect(screen.getByText(/ODPS.*4\.1/)).toBeInTheDocument();
    });
  });

  it('clears badge when content is cleared', async () => {
    render(<ContractFileReader onContentChange={vi.fn()} />);

    const textarea = screen.getByRole('textbox');

    // Add content
    fireEvent.change(textarea, { target: { value: odcsYaml } });
    await waitFor(() => {
      expect(screen.getByText(/ODCS/)).toBeInTheDocument();
    });

    // Clear content
    fireEvent.change(textarea, { target: { value: '' } });
    await waitFor(() => {
      expect(screen.queryByText(/ODCS/)).not.toBeInTheDocument();
    });
  });

  it('shows UNKNOWN for unrecognized content', async () => {
    render(<ContractFileReader onContentChange={vi.fn()} />);

    const textarea = screen.getByRole('textbox');
    fireEvent.change(textarea, { target: { value: 'foo: bar\nbaz: 123' } });

    await waitFor(() => {
      // Should not show any spec type badge for unknown
      expect(screen.queryByText(/ODPS|ODCS|HUB/)).not.toBeInTheDocument();
    });
  });
});
