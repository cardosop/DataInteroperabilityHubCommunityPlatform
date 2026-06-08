#!/usr/bin/env python3
"""307.4 — Audit management commands for audit event emission coverage."""
import os, re, sys

def find_commands():
    cmds = []
    for root, dirs, files in os.walk("hub/apps"):
        if root.endswith("/management/commands"):
            for f in files:
                if f.endswith(".py") and not f.startswith("__"):
                    path = os.path.join(root, f)
                    with open(path) as fh: content = fh.read()
                    has_audit = bool(re.search(r"create_audit_event|_audit_plan_mutation|log_tenant_operation", content))
                    has_dry_run = "--dry-run" in content or "dry_run" in content
                    app = root.split("/")[2]
                    cmds.append({"app": app, "command": f.replace(".py", ""), "audit": has_audit, "dry_run": has_dry_run})
    return cmds

def main():
    cmds = find_commands()
    covered = sum(1 for c in cmds if c["audit"])
    print(f"Management commands: {len(cmds)} total, {covered} audit-covered, {len(cmds)-covered} uncovered")
    if len(cmds) - covered > 0:
        print("\nUncovered commands:")
        for c in sorted(cmds, key=lambda c: (c["app"], c["command"])):
            if not c["audit"]:
                print(f"  {c['app']}.{c['command']}")
    sys.exit(0)

if __name__ == "__main__":
    main()
