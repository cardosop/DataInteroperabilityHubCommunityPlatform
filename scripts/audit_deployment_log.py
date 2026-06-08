#!/usr/bin/env python3
"""306.7 — Extract deployment history from git tags + CI logs."""
import json, os, subprocess, sys
from datetime import datetime, timezone

OUTPUT_DIR = "evidence"

def get_git_tags():
    try:
        result = subprocess.run(["git", "tag", "--sort=-creatordate"], capture_output=True, text=True)
        return [t.strip() for t in result.stdout.strip().split("\n") if t.strip()]
    except: return []

def get_deploy_history():
    tags = get_git_tags()
    log = {"generated_at": datetime.now(timezone.utc).isoformat(), "deployments": []}
    for tag in tags[:50]:  # Last 50 deployments
        try:
            r = subprocess.run(["git", "log", "-1", "--format=%H %ai %s", tag], capture_output=True, text=True)
            parts = r.stdout.strip().split(" ", 2)
            if len(parts) >= 3:
                log["deployments"].append({
                    "tag": tag, "commit": parts[0], "date": f"{parts[1]} {parts[2][:10]}", "message": parts[2]
                })
        except: pass
    return log

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    output = os.path.join(OUTPUT_DIR, f"DEPLOYMENT_LOG-{date_str}.json")
    log = get_deploy_history()
    with open(output, "w") as f: json.dump(log, f, indent=2)
    print(f"Deployment log: {output} ({len(log['deployments'])} entries)")

if __name__ == "__main__":
    main()
