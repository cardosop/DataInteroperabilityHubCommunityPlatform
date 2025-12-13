#!/usr/bin/env python3
"""
Analyze all ForeignKey relationships in the codebase.

This script identifies all ForeignKey, OneToOneField, and ManyToManyField
relationships to help design the UUID-based reference system migration.
"""
import os
import re
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')

import django
django.setup()

from django.apps import apps


def analyze_foreign_keys():
    """Analyze all ForeignKey relationships in Django models."""
    relationships = defaultdict(list)
    
    # Pattern to match ForeignKey definitions
    fk_pattern = re.compile(
        r'(ForeignKey|OneToOneField|ManyToManyField)\s*\(\s*["\']?([^"\',)]+)["\']?',
        re.MULTILINE
    )
    
    for app_config in apps.get_app_configs():
        app_name = app_config.name.replace('hub.apps.', '')
        
        for model in app_config.get_models():
            model_name = model.__name__
            
            # Analyze model fields
            for field in model._meta.get_fields():
                if hasattr(field, 'related_model'):
                    related_model = field.related_model
                    if related_model:
                        related_app = related_model._meta.app_label.replace('hub.apps.', '')
                        related_name = related_model.__name__
                        
                        field_type = type(field).__name__
                        
                        relationships[app_name].append({
                            'model': model_name,
                            'field': field.name,
                            'field_type': field_type,
                            'related_app': related_app,
                            'related_model': related_name,
                            'on_delete': getattr(field, 'on_delete', None),
                            'null': getattr(field, 'null', False),
                            'blank': getattr(field, 'blank', False),
                            'is_cross_app': app_name != related_app,
                        })
    
    return relationships


def generate_report(relationships: Dict[str, List[Dict]]):
    """Generate a comprehensive report of ForeignKey relationships."""
    print("=" * 80)
    print("FOREIGN KEY RELATIONSHIP ANALYSIS")
    print("=" * 80)
    print()
    
    # Count statistics
    total_relationships = 0
    cross_app_relationships = 0
    by_type = defaultdict(int)
    
    for app_name, rels in relationships.items():
        for rel in rels:
            total_relationships += 1
            by_type[rel['field_type']] += 1
            if rel['is_cross_app']:
                cross_app_relationships += 1
    
    print(f"Total Relationships: {total_relationships}")
    print(f"Cross-App Relationships: {cross_app_relationships}")
    print(f"Within-App Relationships: {total_relationships - cross_app_relationships}")
    print()
    print("By Type:")
    for field_type, count in sorted(by_type.items()):
        print(f"  {field_type}: {count}")
    print()
    
    # Group by app
    print("=" * 80)
    print("RELATIONSHIPS BY APP")
    print("=" * 80)
    print()
    
    for app_name in sorted(relationships.keys()):
        rels = relationships[app_name]
        if not rels:
            continue
        
        print(f"\n{app_name.upper()}")
        print("-" * 80)
        
        # Group by model
        by_model = defaultdict(list)
        for rel in rels:
            by_model[rel['model']].append(rel)
        
        for model_name in sorted(by_model.keys()):
            model_rels = by_model[model_name]
            print(f"\n  {model_name}:")
            
            for rel in sorted(model_rels, key=lambda x: x['field']):
                cross_app_marker = " [CROSS-APP]" if rel['is_cross_app'] else ""
                on_delete = rel['on_delete'].__name__ if rel['on_delete'] else "N/A"
                nullable = "nullable" if rel['null'] else "required"
                
                print(f"    - {rel['field']}: {rel['field_type']} -> "
                      f"{rel['related_app']}.{rel['related_model']}"
                      f"{cross_app_marker}")
                print(f"      on_delete={on_delete}, {nullable}")
    
    # Cross-app relationships summary
    print()
    print("=" * 80)
    print("CROSS-APP RELATIONSHIPS (Migration Priority)")
    print("=" * 80)
    print()
    
    cross_app_rels = []
    for app_name, rels in relationships.items():
        for rel in rels:
            if rel['is_cross_app']:
                cross_app_rels.append(rel)
    
    # Group by source app -> target app
    by_relationship = defaultdict(list)
    for rel in cross_app_rels:
        key = f"{rel['related_app']}.{rel['related_model']}"
        by_relationship[key].append(rel)
    
    for target in sorted(by_relationship.keys()):
        rels = by_relationship[target]
        print(f"\n{target}:")
        for rel in rels:
            print(f"  - {rel['related_app']}.{rel['model']}.{rel['field']} "
                  f"({rel['field_type']})")
    
    return {
        'total': total_relationships,
        'cross_app': cross_app_relationships,
        'by_type': dict(by_type),
        'relationships': relationships,
    }


if __name__ == '__main__':
    relationships = analyze_foreign_keys()
    report = generate_report(relationships)
    
    # Save to JSON for further processing
    import json
    output_file = project_root / 'docs' / 'foreign_key_analysis.json'
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert to JSON-serializable format
    json_data = {
        'total': report['total'],
        'cross_app': report['cross_app'],
        'by_type': report['by_type'],
        'relationships': {
            app: [
                {
                    k: str(v) if not isinstance(v, (str, int, bool, type(None))) else v
                    for k, v in rel.items()
                }
                for rel in rels
            ]
            for app, rels in report['relationships'].items()
        }
    }
    
    with open(output_file, 'w') as f:
        json.dump(json_data, f, indent=2)
    
    print(f"\n\nReport saved to: {output_file}")

