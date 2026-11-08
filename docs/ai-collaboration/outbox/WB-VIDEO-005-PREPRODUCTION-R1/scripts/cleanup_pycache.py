#!/usr/bin/env python3
"""Remove Python bytecode caches that were accidentally committed in the R1
delivery directory, and record a byte-level before/after audit.

This is a cleanup of THIS round's own generated cache only. It never touches
source files, evidence files, historical reports, or any personal directory.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys_path = HERE


def _find_workspace() -> str:
    p = os.path.abspath(__file__)
    for _ in range(10):
        p = os.path.dirname(p)
        cand = os.path.join(p, "yaodao-agent")
        if (os.path.isdir(os.path.join(cand, ".git"))
                and os.path.isdir(os.path.join(cand, "docs", "ai-collaboration", "inbox"))):
            return p
    raise RuntimeError("workspace root containing the real repo not found")


WORKSPACE = _find_workspace()
REPO = os.path.join(WORKSPACE, "yaodao-agent")
SCRIPTS = os.path.join(REPO, "docs", "ai-collaboration", "outbox",
                       "WB-VIDEO-005-PREPRODUCTION-R1", "scripts")
CACHE = os.path.join(SCRIPTS, "__pycache__")
EVID = os.path.join(REPO, "docs", "ai-collaboration", "outbox",
                    "WB-VIDEO-005-PREPRODUCTION-R1", "evidence")
GITIGNORE = os.path.join(REPO, ".gitignore")


def sha(p: str) -> str:
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def snapshot() -> dict:
    tracked = subprocess.run(["git", "-C", REPO, "ls-files"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    pyc_tracked = [x for x in tracked.stdout.decode("utf-8", "replace").splitlines()
                   if x.lower().endswith(".pyc")]
    disk = []
    if os.path.isdir(CACHE):
        for base, _dirs, files in os.walk(CACHE):
            for fn in files:
                p = os.path.join(base, fn)
                disk.append({"file": os.path.relpath(p, CACHE).replace("\\", "/"),
                             "bytes": os.path.getsize(p), "sha256": sha(p)})
    return {"tracked_pyc_in_index": pyc_tracked,
            "disk_files_in_cache_dir": sorted(disk, key=lambda x: x["file"]),
            "cache_dir_exists": os.path.isdir(CACHE)}


def main() -> None:
    before = snapshot()

    # 1. remove from the git index (keeps history intact; the previous commit is
    #    not amended - this is a new corrective commit).
    for rel in before["tracked_pyc_in_index"]:
        r = subprocess.run(["git", "-C", REPO, "rm", "--cached", "-q", "--", rel],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if r.returncode != 0:
            raise RuntimeError(f"git rm --cached failed for {rel}: "
                               + r.stderr.decode("utf-8", "replace"))

    # 2. delete only the cache files verified above, then the empty dir.
    removed = []
    for item in before["disk_files_in_cache_dir"]:
        p = os.path.join(CACHE, item["file"])
        if os.path.isfile(p) and sha(p) == item["sha256"]:
            os.remove(p)
            removed.append(item["file"])
    if os.path.isdir(CACHE) and not os.listdir(CACHE):
        os.rmdir(CACHE)

    after = snapshot()
    gitignore_ok = ("__pycache__/" in open(GITIGNORE, encoding="utf-8").read()
                    and "*.pyc" in open(GITIGNORE, encoding="utf-8").read())

    audit = {
        "audit_id": "R1-PYCACHE-CLEANUP-001",
        "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scope": "Only the __pycache__ directory inside this round's delivered "
                 "WB-VIDEO-005-PREPRODUCTION-R1/scripts/ directory.",
        "reason": "Two .pyc files were created by py_compile and accidentally "
                  "included in commit 9bb8ae1e9cb9b3120cecce37fa9d2afe7c1f0140 "
                  "(local, not yet pushed). Python bytecode caches are build "
                  "artefacts, not deliverables.",
        "actions": ["git rm --cached (index only, no history rewrite)",
                    "delete verified cache files from disk",
                    "remove the now-empty __pycache__ directory",
                    "add __pycache__/ and *.pyc to .gitignore"],
        "before": before,
        "after": after,
        "files_removed_from_disk": sorted(removed),
        "gitignore_rules_present": gitignore_ok,
        "cleanup_verified": (
            not after["tracked_pyc_in_index"]
            and not after["disk_files_in_cache_dir"]
            and not after["cache_dir_exists"]
            and gitignore_ok),
        "source_files_untouched": True,
        "historical_reports_untouched": True,
    }
    os.makedirs(EVID, exist_ok=True)
    with open(os.path.join(EVID, "pycache-cleanup-audit.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(audit, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(json.dumps({
        "before_tracked_pyc": len(before["tracked_pyc_in_index"]),
        "before_disk_files": len(before["disk_files_in_cache_dir"]),
        "after_tracked_pyc": len(after["tracked_pyc_in_index"]),
        "after_disk_files": len(after["disk_files_in_cache_dir"]),
        "gitignore_rules_present": gitignore_ok,
        "cleanup_verified": audit["cleanup_verified"],
    }, ensure_ascii=False, indent=2))
    assert audit["cleanup_verified"], "pycache cleanup failed"


if __name__ == "__main__":
    main()
