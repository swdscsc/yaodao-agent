#!/usr/bin/env python3
"""Final R1 verification: revision assertions, preservation, manifests.

Produces:
  evidence/revision-verification.json
  evidence/secret-scan.json
  evidence/manifest.sha256.json
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from build_deliverables_r1 import (WORKSPACE, REPO, OUT, EVID, R1_OUT, R1_EVID,
                                   NARRATION_CHAR_COUNT, CHAR_COUNT_RULE)

BASE = "334ddbc60a50a794300188fa886d388a85c9edd2"

# Files that carry CURRENT production text. They must be clean.
CURRENT_TEXT_FILES = [
    (OUT, "main-film-shotlist.csv"), (OUT, "subtitle-draft.srt"),
    (OUT, "narration-draft.md"), (OUT, "main-film-script.md"),
    (OUT, "vertical-cut-plan.md"), (OUT, "product-claims-register.md"),
    (EVID, "dialogue-subtitle-draft.srt"), (EVID, "narration-table.md"),
    (EVID, "subtitle-draft.meta.json"), (EVID, "dialogue-cue-index.csv"),
    (R1_OUT, "narration-revised.md"), (R1_OUT, "subtitle-draft-revised.srt"),
    (R1_OUT, "dialogue-subtitle-revised.srt"),
    (R1_OUT, "first-cut-subtitles.srt"), (R1_OUT, "first-cut-dialogue.srt"),
    (R1_OUT, "first-cut-timeline.csv"),
    (R1_OUT, "assets/first-cut-mockui.html"),
    (R1_OUT, "assets/s14-chapter-cards.svg"),
    (R1_OUT, "assets/s15-mockui-save.svg"),
    (R1_OUT, "assets/s16-mockui-query.svg"),
    (R1_OUT, "assets/s17-mockui-checkin.svg"),
]
DRUG_WORDS = ["降压药", "一片", "两片", "半片", "毫克", "每日三次", "早晚各",
              "阿司匹林", "二甲双胍", "硝苯地平"]
CREDENTIAL_PATTERNS = {
    "github_pat": re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}"),
    "bearer_token": re.compile(r"(?i)bearer\s+[A-Za-z0-9._-]{20,}"),
    "assigned_secret": re.compile(
        r"(?i)(password|api[_-]?key|access[_-]?token|secret)\s*[:=]\s*['\"][^'\"]{8,}['\"]"),
    "runtime_token_value": re.compile(r"(?i)JIANYING_AGENT_RUNTIME_TOKEN\s*=\s*[A-Za-z0-9_-]{12,}"),
}
LOCAL_PATH_PATTERN = re.compile(r"(?:C:\\Users\\|C:/Users/|/c/Users/)[^\s\"'|,)]{0,120}")


def sha(p: str) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def text(p: str) -> str:
    return open(p, encoding="utf-8", errors="replace").read()


def main() -> None:
    os.makedirs(R1_EVID, exist_ok=True)
    consistency = json.load(open(os.path.join(EVID, "consistency-check.json"),
                                 encoding="utf-8"))
    meta = json.load(open(os.path.join(EVID, "subtitle-draft.meta.json"),
                          encoding="utf-8"))
    ccaudit = json.load(open(os.path.join(R1_EVID, "character-count-audit.json"),
                             encoding="utf-8"))
    scoring = json.load(open(os.path.join(R1_EVID, "first-cut-scoring.json"),
                             encoding="utf-8"))
    kf = json.load(open(os.path.join(R1_EVID, "keyframe-render-log.json"),
                        encoding="utf-8"))
    preserve = json.load(open(os.path.join(R1_EVID, "r0-file-preservation.json"),
                              encoding="utf-8"))
    loc = json.load(open(os.path.join(R1_EVID, "generator-location-tests.json"),
                         encoding="utf-8"))
    cleanup = json.load(open(os.path.join(R1_EVID, "cleanup-audit.json"),
                             encoding="utf-8"))

    checks: dict[str, dict] = {}

    # 1 claims policy consistency ------------------------------------------------
    reg = text(os.path.join(OUT, "product-claims-register.md"))
    c1 = all(x in reg for x in ["R1-C1", "R1-C2", "R1-C3", "R1-C4", "R1-C5",
                                "DESIGN_INTENT_DOC_ONLY", "### A.1",
                                "## A.2 仅可作为设计示意的表述"])
    checks["R1-1_claims_policy_consistent"] = {
        "passed": c1, "detail": "台账含五条分类规则、A.1 一致性矩阵、A.2 设计示意表与新状态枚举"}

    # 2 N09/N10 design-intent qualification --------------------------------------
    narr = text(os.path.join(OUT, "narration-draft.md"))
    reg0_design = ("这一段是设计示意，不是真机，也不是录屏。" in narr
                   and "按设计，它一次只说一件事" in narr
                   and "能听懂普通话" not in narr
                   and "一块放在桌上的小屏" not in narr)
    checks["R1-2_design_intent_qualified"] = {
        "passed": reg0_design and consistency["r1_assertions"]["design_intent_qualifiers_present"],
        "detail": "N09/N10 改为设计示意表述，识别能力与硬件形态宣称已删除"}

    # 3 one single machine-counted character count -------------------------------
    decl_files = ["main-film-script.md", "narration-draft.md"]
    declared = {}
    for name in decl_files:
        t = text(os.path.join(OUT, name))
        declared[name] = re.findall(r"共\s*(\d+)\s*字", t)
    r1_decl = re.findall(r"(\d+)\s*字", text(os.path.join(R1_OUT, "narration-revised.md")))
    no_stale = all("560" not in text(os.path.join(OUT, n)) and "473" not in
                   text(os.path.join(OUT, n)) for n in decl_files)
    c3 = (NARRATION_CHAR_COUNT == ccaudit["machine_count"]
          and all(v == [str(NARRATION_CHAR_COUNT)] for v in declared.values())
          and str(NARRATION_CHAR_COUNT) in r1_decl and no_stale)
    checks["R1-3_single_character_count"] = {
        "passed": c3, "machine_value": NARRATION_CHAR_COUNT,
        "declared_in": declared, "stale_560_or_473_in_current_script_files": not no_stale,
        "rule": CHAR_COUNT_RULE}

    # 4 unique dialogue cue IDs --------------------------------------------------
    cues = list(csv_rows(os.path.join(EVID, "dialogue-cue-index.csv")))
    ids = [r["cue_id"] for r in cues]
    c4 = (len(ids) == len(set(ids)) == consistency["dialogue_cue_count"]
          and consistency["r1_assertions"]["cue_ids_globally_unique"]
          and consistency["r1_assertions"]["collision_pairs_unique"]
          and all(re.fullmatch(r"S\d{2}-D\d{2}", i) for i in ids))
    checks["R1-4_unique_dialogue_cue_ids"] = {
        "passed": c4, "cue_count": len(ids), "unique_count": len(set(ids)),
        "s04_ids": [i for i in ids if i.startswith("S04")],
        "s16_ids": [i for i in ids if i.startswith("S16")]}

    # 5 no specific drug / dosage in CURRENT production text ---------------------
    hits = []
    for base, rel in CURRENT_TEXT_FILES:
        p = os.path.join(base, rel)
        if not os.path.isfile(p):
            hits.append({"file": rel, "reason": "MISSING"})
            continue
        t = text(p)
        for w in DRUG_WORDS:
            if w in t:
                hits.append({"file": rel, "word": w})
    # product-claims-register.md C07 quotes the banned words as a RULE; that is
    # a rule statement, not production text -> classified separately.
    rule_quotes = [h for h in hits if h["file"] == "product-claims-register.md"]
    production_hits = [h for h in hits if h["file"] != "product-claims-register.md"]
    checks["R1-5_specific_drug_or_dosage_removed"] = {
        "passed": not production_hits and consistency["r1_assertions"]["specific_drug_or_dosage_removed"],
        "production_text_hits": production_hits,
        "rule_statement_quotes_in_register": rule_quotes,
        "files_scanned": len(CURRENT_TEXT_FILES)}

    # 6 consistency check re-run --------------------------------------------------
    checks["R1-6_consistency_re_run"] = {
        "passed": (consistency["errors"] == []
                   and consistency["all_consistency_checks_passed"]
                   and consistency["r1_assertions_all_passed"]
                   and consistency["revision_id"] == "WB-VIDEO-005-PREPRODUCTION-R1"),
        "errors": consistency["errors"], "warnings": len(consistency["warnings"]),
        "r1_assertions": consistency["r1_assertions"]}

    # preservation: historical files must equal the git blobs at BASE ------------
    preservation = []
    for item in preserve["preserved_untouched"]:
        rel = "docs/ai-collaboration/outbox/WB-VIDEO-005-PREPRODUCTION/" + item["path"]
        p = subprocess.run(["git", "-C", REPO, "show", f"{BASE}:{rel}"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        blob = p.stdout
        local = open(os.path.join(OUT, item["path"]), "rb").read()
        preservation.append({"path": item["path"],
                             "git_blob_sha256": hashlib.sha256(blob).hexdigest(),
                             "local_sha256": hashlib.sha256(local).hexdigest(),
                             "byte_identical": blob == local,
                             "exit_code": p.returncode})
    preservation_ok = all(x["byte_identical"] for x in preservation)

    # r0 originals preserved ------------------------------------------------------
    originals_ok = all(os.path.isfile(os.path.join(R1_EVID, "r0-originals",
                                                  item["preserved_copy"].split("/")[-1]))
                       for item in preserve["regenerated_in_place"])

    # no video / audio anywhere in the two delivery dirs --------------------------
    media = []
    for root in (OUT, R1_OUT):
        for base, _dirs, files in os.walk(root):
            for fn in files:
                if fn.lower().endswith((".mp4", ".mov", ".webm", ".wav", ".mp3", ".m4a")):
                    media.append(os.path.relpath(os.path.join(base, fn), WORKSPACE))

    # JSON validity ---------------------------------------------------------------
    json_bad = []
    for root in (OUT, R1_OUT):
        for base, _dirs, files in os.walk(root):
            for fn in files:
                if fn.endswith(".json"):
                    p = os.path.join(base, fn)
                    try:
                        json.load(open(p, encoding="utf-8"))
                    except Exception as e:
                        json_bad.append({"file": p, "error": str(e)})

    # secret scan -----------------------------------------------------------------
    cred_hits, path_hits = [], []
    for root in (OUT, R1_OUT):
        for base, _dirs, files in os.walk(root):
            for fn in files:
                if fn == "secret-scan.json":
                    continue  # avoid self-referential accumulation of path hits
                if not fn.endswith((".md", ".json", ".csv", ".srt", ".svg", ".html", ".py")):
                    continue
                p = os.path.join(base, fn)
                t = text(p)
                rel = os.path.relpath(p, WORKSPACE).replace("\\", "/")
                for name, pat in CREDENTIAL_PATTERNS.items():
                    for m in pat.finditer(t):
                        cred_hits.append({"file": rel, "pattern": name,
                                         "match": m.group(0)[:24]})
                for m in LOCAL_PATH_PATTERN.finditer(t):
                    path_hits.append({"file": rel, "match": m.group(0)[:100]})

    secret = {
        "scan_id": "R1-SECRET-SCAN-001",
        "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scanned_roots": ["docs/ai-collaboration/outbox/WB-VIDEO-005-PREPRODUCTION/",
                          "docs/ai-collaboration/outbox/WB-VIDEO-005-PREPRODUCTION-R1/"],
        "credential_patterns": list(CREDENTIAL_PATTERNS),
        "credential_hits": cred_hits,
        "credential_hit_count": len(cred_hits),
        "local_absolute_path_hits": path_hits,
        "local_absolute_path_hit_count": len(path_hits),
        "local_path_note": "User explicitly required the stray-directory absolute path "
                           "to be recorded in cleanup-audit.json; generator-location-tests.json "
                           "records cwd values. These are workspace paths only, contain no "
                           "credential, no personal file content and no home-directory listing.",
        "verdict": "PASS_NO_CREDENTIALS" if not cred_hits else "FAIL",
    }
    with open(os.path.join(R1_EVID, "secret-scan.json"), "w", encoding="utf-8",
              newline="\n") as f:
        json.dump(secret, f, ensure_ascii=False, indent=2)
        f.write("\n")

    overall = {
        "verification_id": "R1-VERIFY-001",
        "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "baseline_commit": BASE,
        "checks": checks,
        "all_six_revision_checks_passed": all(v["passed"] for v in checks.values()),
        "historical_evidence_byte_identical_to_baseline": preservation_ok,
        "historical_evidence_files_checked": preservation,
        "r0_originals_present": originals_ok,
        "r0_originals_count": len(preserve["regenerated_in_place"]),
        "cleanup_verified": cleanup["cleanup_verified"],
        "generator_location_tests_passed": loc["all_tests_passed"],
        "keyframes_rendered": kf["frames_ok"],
        "keyframes_total": kf["frame_count"],
        "first_cut_selected": scoring["selected"]["segment"],
        "first_cut_duration_s": scoring["selected"]["duration_s"],
        "video_or_audio_files_in_delivery_dirs": media,
        "mp4_count": 0 if not media else len(media),
        "invalid_json_files": json_bad,
        "secret_scan_verdict": secret["verdict"],
        "all_verifications_passed": (
            all(v["passed"] for v in checks.values()) and preservation_ok
            and originals_ok and not media and not json_bad
            and not cred_hits and cleanup["cleanup_verified"]
            and loc["all_tests_passed"] and kf["frames_ok"] == kf["frame_count"]),
    }
    with open(os.path.join(R1_EVID, "revision-verification.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(overall, f, ensure_ascii=False, indent=2)
        f.write("\n")

    # manifest over BOTH delivery dirs, excluding self + post-push evidence -----
    excluded = {"evidence/manifest.sha256.json", "evidence/push-verification.json",
                "evidence/push-verification-addendum.md"}
    files = []
    for root in (OUT, R1_OUT):
        for base, _dirs, names in os.walk(root):
            for fn in names:
                p = os.path.join(base, fn)
                rel = os.path.relpath(p, root).replace("\\", "/")
                key = os.path.relpath(root, os.path.dirname(OUT)).replace("\\", "/") + "/" + rel
                if rel in excluded and root == R1_OUT:
                    continue
                files.append({"path": key, "bytes": os.path.getsize(p),
                              "sha256": sha(p)})
    files.sort(key=lambda x: x["path"])
    manifest = {
        "manifest_id": "R1-MANIFEST-001",
        "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scope": "Both WB-VIDEO-005-PREPRODUCTION and ...-R1 directories, current worktree",
        "note": "R0 evidence/manifest.sha256.json is a historical snapshot of commit "
                + BASE + " and is NOT rewritten; the R1 manifest covers the current tree.",
        "excludes": ["self", "post-push verification files"],
        "file_count": len(files),
        "files": files,
    }
    with open(os.path.join(R1_EVID, "manifest.sha256.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(json.dumps({
        "all_six_revision_checks_passed": overall["all_six_revision_checks_passed"],
        "historical_evidence_untouched": preservation_ok,
        "r0_originals_present": originals_ok,
        "generator_location_tests": loc["all_tests_passed"],
        "keyframes": f"{kf['frames_ok']}/{kf['frame_count']}",
        "credential_hits": len(cred_hits),
        "local_path_hits": len(path_hits),
        "media_files": media,
        "invalid_json": len(json_bad),
        "manifest_files": len(files),
        "all_verifications_passed": overall["all_verifications_passed"],
    }, ensure_ascii=False, indent=2))
    assert overall["all_verifications_passed"], "R1 verification failed"


def csv_rows(path: str):
    import csv
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


if __name__ == "__main__":
    main()
