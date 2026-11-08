#!/usr/bin/env python3
"""Test the R1 generator from the repo root AND from the script directory.

The user explicitly asked for both. A third run uses the committed scripts/
snapshot, proving the delivered source is itself executable. Byte-level output
stability is asserted; the only volatile field (checked_at) is normalised.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build_deliverables_r1 import WORKSPACE, REPO, OUT, EVID, R1_OUT, R1_EVID

DELIVERED_SCRIPTS = os.path.join(R1_OUT, "scripts")
STABLE_FILES = [
    "main-film-shotlist.csv", "subtitle-draft.srt", "asset-inventory.csv",
    "evidence/dialogue-subtitle-draft.srt", "evidence/narration-table.md",
    "evidence/dialogue-cue-index.csv", "evidence/subtitle-draft.meta.json",
]
MD_FILES = ["main-film-script.md", "narration-draft.md"]
VOLATILE_JSON = "evidence/consistency-check.json"


def sha(p: str) -> str:
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def snapshot() -> dict:
    out = {}
    for rel in STABLE_FILES + MD_FILES:
        p = os.path.join(OUT, rel)
        out[rel] = sha(p) if os.path.isfile(p) else "MISSING"
    p = os.path.join(EVID, "consistency-check.json")
    d = json.load(open(p, encoding="utf-8"))
    d.pop("checked_at", None)
    out[VOLATILE_JSON + "__normalised"] = hashlib.sha256(
        json.dumps(d, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return out


def run(label: str, cwd: str, script: str, args: list[str] | None = None) -> dict:
    cmd = [sys.executable, script] + (args or [])
    # Imports from the delivered scripts/ snapshot would otherwise recreate a
    # __pycache__ inside the delivery directory. Keep the tree bytecode-free.
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    p = subprocess.run(cmd, cwd=cwd, env=env, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=180)
    tail = p.stdout.decode("utf-8", "replace").strip()[-600:]
    return {"label": label, "cwd": cwd, "script": script,
            "exit_code": p.returncode, "stdout_tail": tail,
            "stderr_tail": p.stderr.decode("utf-8", "replace").strip()[-300:]}


def main() -> None:
    os.makedirs(R1_EVID, exist_ok=True)
    cases = [
        ("A_script_directory", HERE, os.path.join(HERE, "build_deliverables_r1.py"), None),
        ("B_repository_root", REPO, os.path.join(HERE, "build_deliverables_r1.py"), None),
        ("C_delivered_scripts_snapshot", REPO,
         os.path.join(DELIVERED_SCRIPTS, "build_deliverables_r1.py"), None),
        ("D_markdown_from_repository_root", REPO,
         os.path.join(HERE, "build_markdown_r1.py"), None),
        ("E_markdown_from_delivered_scripts", REPO,
         os.path.join(DELIVERED_SCRIPTS, "build_markdown_r1.py"), None),
    ]
    results = []
    for label, cwd, script, args in cases:
        assert os.path.isfile(script), f"missing generator: {script}"
        r = run(label, cwd, script, args)
        r["outputs_after_run"] = snapshot()
        results.append(r)
        print(f"{label}: exit={r['exit_code']}")

    baseline = results[0]["outputs_after_run"]
    mismatches = {}
    for r in results[1:]:
        diff = {k: (baseline[k], r["outputs_after_run"][k])
                for k in baseline if baseline[k] != r["outputs_after_run"][k]}
        mismatches[r["label"]] = diff

    all_ok = (all(r["exit_code"] == 0 for r in results)
              and all(not d for d in mismatches.values()))
    # workspace locator must resolve identically from every cwd
    locators = []
    for cwd in (HERE, REPO, DELIVERED_SCRIPTS, WORKSPACE):
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        p = subprocess.run([sys.executable, "-c",
                            "import sys;sys.path.insert(0,r'" + HERE + "');"
                            "import build_deliverables_r1 as b;print(b.WORKSPACE)"],
                           cwd=cwd, env=env, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=60)
        locators.append({"cwd": cwd, "resolved_workspace":
                         p.stdout.decode("utf-8", "replace").strip(),
                         "exit_code": p.returncode})
    locator_ok = all(x["resolved_workspace"] == WORKSPACE and x["exit_code"] == 0
                     for x in locators)

    out = {
        "test_id": "R1-GENERATOR-LOCATION-001",
        "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "requirement": "run the generator from the repository root AND from the "
                       "script directory; verify the repo-root locator by two markers",
        "workspace": WORKSPACE,
        "stable_files_compared": STABLE_FILES + MD_FILES,
        "volatile_field_normalised": "consistency-check.json : checked_at",
        "runs": results,
        "byte_level_mismatches": mismatches,
        "locator_resolution": locators,
        "all_runs_exit_zero": all(r["exit_code"] == 0 for r in results),
        "all_outputs_byte_identical": all(not d for d in mismatches.values()),
        "locator_consistent": locator_ok,
        "all_tests_passed": all_ok and locator_ok,
    }
    path = os.path.join(R1_EVID, "generator-location-tests.json")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps({"runs": len(results), "all_outputs_byte_identical":
                      out["all_outputs_byte_identical"],
                      "locator_consistent": locator_ok,
                      "all_tests_passed": out["all_tests_passed"]},
                     ensure_ascii=False, indent=2))
    assert out["all_tests_passed"], f"generator location tests failed: {mismatches}"


if __name__ == "__main__":
    main()
