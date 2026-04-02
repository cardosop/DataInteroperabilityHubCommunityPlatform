/**
 * ContractExportModal
 *
 * Modal for exporting a contract with spec-type and version selection.
 * Warns on downgrade paths (fields will be dropped) and disables
 * upgrade paths that require manual mapping (e.g. v2.2.2 → v3.1.0).
 */

import { useState, useCallback } from 'react';
import { ODCS_EXPORT_VERSIONS, type ODCSExportVersion } from '../../../shared/types/contracts';
import { useSupportedContractVersions } from '../hooks/useSupportedContractVersions';
import './ContractExportModal.css';
import { Button } from '../../../shared/components/Button';

interface ContractExportModalProps {
  /** Whether the modal is open */
  isOpen: boolean;
  /** Close handler */
  onClose: () => void;
  /** Export handler — called with chosen format + version */
  onExport: (format: 'ODCS' | 'ODPS', version: string) => void;
  /** Current spec version of the contract being exported */
  currentVersion?: string;
  /** Current spec type */
  currentSpecType?: string;
  /** Whether export is in progress */
  isExporting?: boolean;
}

/** Determine the major.minor version number for comparison */
function versionNumber(v: string): number {
  const parts = v.split('.').map(Number);
  return (parts[0] || 0) * 1000 + (parts[1] || 0) * 10 + (parts[2] || 0);
}

/** Check if target is a major upgrade from source (cross-major) */
function isCrossMajorUpgrade(source: string, target: string): boolean {
  const sMajor = parseInt(source.split('.')[0] || '0', 10);
  const tMajor = parseInt(target.split('.')[0] || '0', 10);
  return tMajor > sMajor;
}

export function ContractExportModal({
  isOpen,
  onClose,
  onExport,
  currentVersion,
  currentSpecType,
  isExporting,
}: ContractExportModalProps) {
  const [specFormat, setSpecFormat] = useState<'ODCS' | 'ODPS'>(
    (currentSpecType === 'ODPS' ? 'ODPS' : 'ODCS') as 'ODCS' | 'ODPS',
  );
  const [targetVersion, setTargetVersion] = useState<ODCSExportVersion>(
    ODCS_EXPORT_VERSIONS.includes(currentVersion as ODCSExportVersion)
      ? (currentVersion as ODCSExportVersion)
      : '3.1.0',
  );

  const isDowngrade =
    currentVersion != null &&
    specFormat === 'ODCS' &&
    versionNumber(targetVersion) < versionNumber(currentVersion);

  const isBlockedUpgrade =
    currentVersion != null &&
    specFormat === 'ODCS' &&
    isCrossMajorUpgrade(currentVersion, targetVersion);

  // Fetch dynamic version list (falls back to ODCS_EXPORT_VERSIONS)
  const { data: supportedVersions } = useSupportedContractVersions();
  const odcsVersions = (supportedVersions?.odcs ?? [...ODCS_EXPORT_VERSIONS]) as string[];

  const handleExport = useCallback(() => {
    onExport(specFormat, targetVersion);
  }, [onExport, specFormat, targetVersion]);

  if (!isOpen) return null;

  return (
    <div className="export-modal-backdrop" onClick={onClose} role="presentation">
      <div
        className="export-modal"
        role="dialog"
        aria-modal="true"
        aria-label="Export contract"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="export-modal-header">
          <h2>Export Contract</h2>
          <button type="button" className="export-modal-close" onClick={onClose} aria-label="Close">
            &times;
          </button>
        </div>

        <div className="export-modal-body">
          {/* Spec format */}
          <div className="export-field">
            <label htmlFor="export-format">Spec format</label>
            <select
              id="export-format"
              value={specFormat}
              onChange={(e) => setSpecFormat(e.target.value as 'ODCS' | 'ODPS')}
            >
              <option value="ODCS">ODCS (Open Data Contract Standard)</option>
              <option value="ODPS">ODPS (Open Data Product Standard)</option>
            </select>
          </div>

          {/* Version selector (ODCS only) */}
          {specFormat === 'ODCS' && (
            <div className="export-field">
              <label htmlFor="export-version">Target version</label>
              <select
                id="export-version"
                value={targetVersion}
                onChange={(e) => setTargetVersion(e.target.value as ODCSExportVersion)}
              >
                {odcsVersions.map((v) => {
                  const disabled =
                    currentVersion != null && isCrossMajorUpgrade(currentVersion, v);
                  return (
                    <option key={v} value={v} disabled={disabled}>
                      {v}
                      {disabled ? ' (requires manual mapping)' : ''}
                    </option>
                  );
                })}
              </select>
            </div>
          )}

          {/* Downgrade warning */}
          {isDowngrade && (
            <div className="export-warning">
              Exporting to an older version may drop fields not present in {targetVersion}
              (e.g. relationships, element_id, logicalType).
            </div>
          )}

          {/* Blocked upgrade info */}
          {isBlockedUpgrade && (
            <div className="export-warning export-warning-blocked">
              Upgrading from v{currentVersion} to v{targetVersion} requires manual field
              mapping and is not automated.
            </div>
          )}
        </div>

        <div className="export-modal-footer">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
 variant="primary"
 onClick={handleExport}
 disabled={isExporting || isBlockedUpgrade}>
            {isExporting ? 'Exporting…' : 'Export'}
          </Button>
        </div>
      </div>
    </div>
  );
}
