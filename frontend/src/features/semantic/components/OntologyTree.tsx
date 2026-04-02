/**
 * OntologyTree — collapsible class/property tree from Turtle source.
 */

import { useMemo } from 'react';
import { parseTurtleClasses } from '../utils/parseTurtleClasses';
import './OntologyTree.css';

export interface OntologyTreeProps {
  turtle: string;
}

export function OntologyTree({ turtle }: OntologyTreeProps) {
  const info = useMemo(() => parseTurtleClasses(turtle), [turtle]);
  const allProps = [...info.objectProperties, ...info.datatypeProperties];

  if (info.classes.length === 0 && allProps.length === 0) {
    return null;
  }

  return (
    <div className="ontology-tree" data-testid="ontology-tree">
      {info.classes.length > 0 && (
        <details open>
          <summary>Classes ({info.classes.length})</summary>
          <ul className="ontology-tree__list">
            {info.classes.map((c) => (
              <li key={c} className="ontology-tree__item">{c}</li>
            ))}
          </ul>
        </details>
      )}
      {allProps.length > 0 && (
        <details open>
          <summary>Properties ({allProps.length})</summary>
          <ul className="ontology-tree__list">
            {info.objectProperties.map((p) => (
              <li key={`op-${p}`} className="ontology-tree__item" title="ObjectProperty">{p}</li>
            ))}
            {info.datatypeProperties.map((p) => (
              <li key={`dp-${p}`} className="ontology-tree__item" title="DatatypeProperty">{p}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
