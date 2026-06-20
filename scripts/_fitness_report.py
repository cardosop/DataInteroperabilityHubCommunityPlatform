"""CI helper — reads a fitness-results JSON file and prints warnings.

Usage:
  python scripts/_fitness_report.py <json-file> <check-name>         # full report
  python scripts/_fitness_report.py <json-file> <check-name> --count # count only
  python scripts/_fitness_report.py <json-file> <check-name> 5      # top 5
"""

import json
import sys


def report(json_path: str, check_name: str, top_n: int = 10) -> None:
    """Read fitness JSON, print top-N violations as CI warnings."""
    with open(json_path) as f:
        data = json.load(f)

    section = data.get(check_name, {})
    violations = section.get("violations", 0)
    details = section.get("details", [])

    if violations == 0:
        print(f"✅ All {check_name} checks passed.")
        return

    threshold = section.get("threshold", "N/A")
    print(f"⚠️  {violations} {check_name} violation(s) (limit={threshold}):")
    for v in details[:top_n]:
        if check_name == "file_size":
            print(f"    {v['file']}: {v['lines']} lines (limit={v['threshold']})")
        elif check_name == "complexity":
            print(
                f"    {v['file']}:{v['line']} {v['function']}() "
                f"— complexity {v['complexity']} (limit={v['threshold']})"
            )
        elif check_name == "app_boundaries":
            print(f"    {v['file']}:{v['line']} — {v['source_group']} → {v['target_group']}")
        else:
            print(f"    {v}")


if __name__ == "__main__":
    json_path = sys.argv[1]
    check_name = sys.argv[2]

    if "--count" in sys.argv:
        # CI output capture mode: print violation count only
        with open(json_path) as f:
            data = json.load(f)
        section = data.get(check_name, {})
        print(section.get("violations", 0))
    else:
        top_n = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else 10
        report(json_path, check_name, top_n)
