/**
 * parseTurtleClasses Tests — Phase 37
 */

import { describe, expect, it } from 'vitest';
import { parseTurtleClasses } from '../parseTurtleClasses';

describe('parseTurtleClasses', () => {
  it('extracts class from "hub:Asset a owl:Class ;"', () => {
    const result = parseTurtleClasses('hub:Asset a owl:Class ;');
    expect(result.classes).toContain('Asset');
  });

  it('extracts objectProperty from "hub:hasContract a owl:ObjectProperty"', () => {
    const result = parseTurtleClasses('hub:hasContract a owl:ObjectProperty .');
    expect(result.objectProperties).toContain('hasContract');
  });

  it('extracts datatypeProperty', () => {
    const result = parseTurtleClasses('hub:name a owl:DatatypeProperty ;');
    expect(result.datatypeProperties).toContain('name');
  });

  it('handles full IRI subjects', () => {
    const turtle = '<http://example.org/ontology#Person> a owl:Class .';
    const result = parseTurtleClasses(turtle);
    expect(result.classes).toContain('Person');
  });

  it('handles multiple declarations', () => {
    const turtle = [
      'hub:Asset a owl:Class ;',
      'hub:Contract a owl:Class ;',
      'hub:hasOwner a owl:ObjectProperty ;',
      'hub:displayName a owl:DatatypeProperty ;',
    ].join('\n');
    const result = parseTurtleClasses(turtle);
    expect(result.classes).toEqual(['Asset', 'Contract']);
    expect(result.objectProperties).toEqual(['hasOwner']);
    expect(result.datatypeProperties).toEqual(['displayName']);
  });

  it('empty string returns empty arrays without throwing', () => {
    const result = parseTurtleClasses('');
    expect(result.classes).toEqual([]);
    expect(result.objectProperties).toEqual([]);
    expect(result.datatypeProperties).toEqual([]);
  });

  it('malformed input returns empty arrays without throwing', () => {
    const result = parseTurtleClasses('not valid turtle at all {}[]');
    expect(result.classes).toEqual([]);
    expect(result.objectProperties).toEqual([]);
    expect(result.datatypeProperties).toEqual([]);
  });

  it('handles multi-line declarations (subject on separate line)', () => {
    const turtle = [
      'hub:Asset',
      '  a owl:Class ;',
      '  rdfs:label "Asset" .',
      '',
      'hub:hasContract',
      '  a owl:ObjectProperty ;',
      '  rdfs:domain hub:Asset .',
    ].join('\n');
    const result = parseTurtleClasses(turtle);
    expect(result.classes).toContain('Asset');
    expect(result.objectProperties).toContain('hasContract');
  });

  it('resets subject after period terminator', () => {
    const turtle = [
      'hub:Asset a owl:Class .',
      '  rdfs:label "should not match" .',
    ].join('\n');
    const result = parseTurtleClasses(turtle);
    expect(result.classes).toEqual(['Asset']);
    // The rdfs:label line after '.' should not carry forward the subject
  });
});
