#!/usr/bin/env python3
"""Preserve R0 generated artefacts byte-for-byte before R1 regenerates them.

R1 re-generates the derived files from the corrected authoritative shot table.
The ORIGINAL R0 bytes are copied here so the previous round is never lost, and
an old/new SHA-256 comparison is written as evidence. Historical reports and
raw probe/manifest evidence are NOT regenerated and NOT touched at all.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
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
R0 = os.path.join(WORKSPACE, "yaodao-agent", "docs", "ai-collaboration",
                  "outbox", "WB-VIDEO-005-PREPRODUCTION")
R1 = os.path.join(WORKSPACE, "yaodao-agent", "docs", "ai-collaboration",
                  "outbox", "WB-VIDEO-005-PREPRODUCTION-R1")
SNAP = os.path.join(R1, "evidence", "r0-originals")

# Derived artefacts that R1 regenerates from the corrected shot table.
REGENERATED = [
    "main-film-shotlist.csv",
    "subtitle-draft.srt",
    "narration-draft.md",
    "main-film-script.md",
    "product-claims-register.md",
    "evidence/consistency-check.json",
    "evidence/subtitle-draft.meta.json",
    "evidence/narration-table.md",
    "evidence/dialogue-subtitle-draft.srt",
]

# Historical reports and raw evidence: explicitly preserved, never regenerated.
PRESERVED_UNTOUCHED = [
    "report.md",
    "first-cut-readiness.md",
    "creative-research.md",
    # vertical-cut-plan.md is R1-revised in place (V04/V05 example dialogue),
    # so it is NOT in this list; its R0 bytes are in r0-originals/ instead.
    "asset-inventory.csv",
    "evidence/asset-probe.json",
    "evidence/capability-probe.json",
    "evidence/manifest.sha256.json",
    "evidence/delivery-verification.json",
    "evidence/push-verification.json",
    "evidence/push-verification-addendum.md",
]


def sha256(p: str) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main() -> None:
    os.makedirs(SNAP, exist_ok=True)
    before = []
    for rel in REGENERATED:
        src = os.path.join(R0, rel)
        dst = os.path.join(SNAP, rel.replace("/", "__"))
        assert os.path.isfile(src), f"missing R0 file: {src}"
        shutil.copyfile(src, dst)
        before.append({"path": rel, "bytes": os.path.getsize(src),
                       "sha256": sha256(src), "preserved_copy":
                       os.path.relpath(dst, R1).replace("\\", "/")})
    untouched = []
    for rel in PRESERVED_UNTOUCHED:
        src = os.path.join(R0, rel)
        assert os.path.isfile(src), f"missing preserved file: {src}"
        untouched.append({"path": rel, "bytes": os.path.getsize(src),
                          "sha256": sha256(src), "r1_action": "NOT_MODIFIED"})

    out = {
        "audit_id": "R1-PRESERVATION-001",
        "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "r0_baseline_commit": "334ddbc60a50a794300188fa886d388a85c9edd2",
        "policy": "R1 regenerates derived artefacts from the corrected SHOTS table; "
                  "the exact R0 bytes are preserved under evidence/r0-originals/; "
                  "historical reports, probe results, manifests and push verification "
                  "are never overwritten.",
        "regenerated_in_place": before,
        "preserved_untouched": untouched,
    }
    with open(os.path.join(R1, "evidence", "r0-file-preservation.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps({
        "regenerated_files_preserved": len(before),
        "historical_files_left_untouched": len(untouched),
        "snapshots_dir": os.path.relpath(SNAP, WORKSPACE).replace("\\", "/"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
