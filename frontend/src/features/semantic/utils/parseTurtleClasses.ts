/**
 * parseTurtleClasses — extract OWL class and property names from Turtle source.
 *
 * Handles both single-line and multi-line declarations:
 *   hub:Asset a owl:Class ;           (single-line)
 *   hub:Asset                          (multi-line: subject on prev line)
 *     a owl:Class ;
 */

export interface TurtleClassInfo {
  classes: string[];
  objectProperties: string[];
  datatypeProperties: string[];
}

function localName(iri: string): string {
  // Strip angle brackets from full IRIs like <http://...#Name>
  const cleaned = iri.replace(/^<|>$/g, '');
  const hashIdx = cleaned.lastIndexOf('#');
  if (hashIdx >= 0) return cleaned.slice(hashIdx + 1);
  const slashIdx = cleaned.lastIndexOf('/');
  if (slashIdx >= 0) return cleaned.slice(slashIdx + 1);
  return cleaned.replace(/^[a-zA-Z_]+:/, '');
}

/** Check if a token looks like a Turtle subject (prefixed name or full IRI). */
function isSubject(token: string): boolean {
  if (!token) return false;
  if (token === 'a' || token === '@prefix' || token === '@base') return false;
  return /^<[^>]+>$/.test(token) || /^[a-zA-Z_][\w.-]*:[a-zA-Z_]/.test(token);
}

export function parseTurtleClasses(turtle: string): TurtleClassInfo {
  const result: TurtleClassInfo = {
    classes: [],
    objectProperties: [],
    datatypeProperties: [],
  };

  if (!turtle) return result;

  try {
    const lines = turtle.split('\n');
    let currentSubject: string | null = null;

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#') || trimmed.startsWith('@')) continue;

      // Track the current subject: first token on a line that looks like a subject
      const firstToken = trimmed.split(/\s+/)[0];
      if (isSubject(firstToken)) {
        currentSubject = firstToken;
      }

      // Determine the subject for this line's declarations
      const subject = isSubject(firstToken) ? firstToken : currentSubject;
      if (!subject) continue;

      const name = localName(subject);
      if (!name) continue;

      if (trimmed.includes('owl:Class')) {
        if (!result.classes.includes(name)) result.classes.push(name);
      }
      if (trimmed.includes('owl:ObjectProperty')) {
        if (!result.objectProperties.includes(name)) result.objectProperties.push(name);
      }
      if (trimmed.includes('owl:DatatypeProperty')) {
        if (!result.datatypeProperties.includes(name)) result.datatypeProperties.push(name);
      }

      // Reset subject after statement terminator '.'
      if (trimmed.endsWith('.')) {
        currentSubject = null;
      }
    }
  } catch {
    // Never throw — return whatever we have
  }

  return result;
}
