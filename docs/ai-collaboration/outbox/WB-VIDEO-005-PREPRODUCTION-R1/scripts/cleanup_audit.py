#!/usr/bin/env python3
"""Audit and clean ONLY the stray tree created by the failed R1 generator run.

Safety properties:
  * hard-coded absolute target, verified to be inside the workspace pipeline dir
  * refuses to act if any file outside the known generated-name whitelist exists
  * records SHA-256 + byte size of every file BEFORE deletion
  * unlinks files one by one, then rmdir()s ONLY directories that are empty
    (rmdir fails rather than recursing if anything unexpected remains)
  * records the AFTER state and asserts the tree is gone
  * never touches the real repository at <workspace>/yaodao-agent
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime

def _find_workspace() -> str:
    """Resolve the workspace by two repo markers; never hard-code a home path."""
    p = os.path.abspath(__file__)
    for _ in range(10):
        p = os.path.dirname(p)
        cand = os.path.join(p, "yaodao-agent")
        if (os.path.isdir(os.path.join(cand, ".git"))
                and os.path.isdir(os.path.join(cand, "docs", "ai-collaboration", "inbox"))):
            return p
    raise RuntimeError("workspace root containing the real repo not found")


WORKSPACE = _find_workspace()
TARGET = os.path.join(WORKSPACE, "pipeline", "yaodao-agent")
REAL_REPO = os.path.join(WORKSPACE, "yaodao-agent")
EVID = os.path.join(
    WORKSPACE, "yaodao-agent", "docs", "ai-collaboration", "outbox",
    "WB-VIDEO-005-PREPRODUCTION-R1", "evidence")

GENERATED_NAMES = {
    "dialogue-cue-index.csv",
    "dialogue-subtitle-draft.srt",
    "narration-table.md",
    "subtitle-draft.meta.json",
    "main-film-shotlist.csv",
    "subtitle-draft.srt",
}


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot() -> dict:
    if not os.path.exists(TARGET):
        return {"exists": False, "files": [], "dirs": []}
    files, dirs = [], []
    for root, dnames, fnames in os.walk(TARGET):
        for d in dnames:
            dirs.append(os.path.join(root, d))
        for fn in fnames:
            p = os.path.join(root, fn)
            files.append({"path": p, "bytes": os.path.getsize(p), "sha256": sha256(p)})
    return {"exists": True, "files": sorted(files, key=lambda x: x["path"]),
            "dirs": sorted(dirs)}


def main() -> None:
    os.makedirs(EVID, exist_ok=True)
    before = snapshot()

    # Guard 1: target must be the stray tree, never the real repo.
    assert os.path.abspath(TARGET) != os.path.abspath(REAL_REPO), "target is the real repo"
    assert os.path.basename(os.path.dirname(TARGET)) == "pipeline", "unexpected target parent"
    assert os.path.isdir(os.path.join(REAL_REPO, ".git")), "real repo marker missing"

    # Guard 2: only files this round's failed run could have produced.
    unexpected = [f["path"] for f in before["files"]
                  if os.path.basename(f["path"]) not in GENERATED_NAMES]
    assert not unexpected, f"refusing to clean unexpected files: {unexpected}"

    actions = []
    for f in before["files"]:
        os.unlink(f["path"])
        actions.append({"action": "unlink", "path": f["path"], "sha256": f["sha256"]})
    for d in sorted(before["dirs"], key=lambda p: p.count(os.sep), reverse=True):
        if os.path.isdir(d):
            os.rmdir(d)  # fails if not empty; never recursive
            actions.append({"action": "rmdir_empty", "path": d})
    if os.path.isdir(TARGET):
        os.rmdir(TARGET)
        actions.append({"action": "rmdir_empty", "path": TARGET})

    after = snapshot()
    audit = {
        "audit_id": "R1-CLEANUP-001",
        "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "cause": "R1 generator initially computed WORKSPACE with a fixed number of "
                 "dirname() calls; after the script moved into pipeline/probe005/r1/ it "
                 "resolved to pipeline/ and created a stray directory tree.",
        "target_absolute_path": TARGET,
        "real_repository_path": REAL_REPO,
        "real_repository_untouched": True,
        "real_repository_markers": {
            ".git": os.path.isdir(os.path.join(REAL_REPO, ".git")),
            "docs/ai-collaboration/inbox": os.path.isdir(
                os.path.join(REAL_REPO, "docs", "ai-collaboration", "inbox")),
        },
        "guards": [
            "target != real repository",
            "target parent is pipeline/",
            "all files match the 6-name generated whitelist",
            "files unlinked individually; directories removed with rmdir() only when empty",
        ],
        "whitelist": sorted(GENERATED_NAMES),
        "before": before,
        "actions": actions,
        "after": after,
        "cleanup_verified": (not after["exists"]) and all(
            not os.path.exists(f["path"]) for f in before["files"]),
    }
    assert audit["cleanup_verified"], "cleanup did not fully remove the stray tree"
    out = os.path.join(EVID, "cleanup-audit.json")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(audit, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps({
        "target": TARGET,
        "before_files": len(before["files"]),
        "before_dirs": len(before["dirs"]),
        "deleted_files": sum(1 for a in actions if a["action"] == "unlink"),
        "removed_empty_dirs": sum(1 for a in actions if a["action"] == "rmdir_empty"),
        "after_exists": after["exists"],
        "cleanup_verified": audit["cleanup_verified"],
        "audit_file": out,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
