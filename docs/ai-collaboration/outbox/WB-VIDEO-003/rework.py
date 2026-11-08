#!/usr/bin/env python3
"""WB-VIDEO-003 corrected repair loop (P0-1 + P0-2 fixes).

This is the CORRECTED replacement for WB-VIDEO-002/rework.py.

Two defects fixed
-----------------
P0-1  Final-render QA no longer calls ``qa_media(..., static_material_expected=True)``.
      It now passes EXPLICIT, validated static-card intervals derived from the
      real concatenated timeline (intro card / chapter card / outro card).
      Static SOURCE MATERIAL (e.g. an smptebars clip) is deliberately NOT
      whitelisted: it is a frozen dynamic shot and must be reported.

P0-2  D004 is no longer resolved by ``bool(v2.exists() and size>0)``. It is
      resolved by ``subtitle_checks.evaluate_subtitle_fix()`` which requires
      automatic geometric/pixel evidence AND a separate named human sign-off.

The original WB-VIDEO-002 files are kept untouched as before/after evidence.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(HERE))                       # strict qa.py wins
sys.path.append(str(PARENT / "WB-VIDEO-002"))      # reuse verified core.py only

from qa import qa_media, validate_static_whitelist  # noqa: E402
from subtitle_checks import (  # noqa: E402
    detect_subtitle_band, evaluate_subtitle_fix, legacy_d004_verdict,
)
from core import RetryPolicy, now  # noqa: E402  (reuse the verified bounded gate)

# Real WB-VIDEO-002 concatenated timeline, seconds:
#   card_intro 1.5 | S001 3.0 | card_chapter 1.0 | S002 3.0 | S003 2.0 | card_outro 1.5 = 12.0
# ONLY confirmed static CARDS are whitelisted. S002 is a static smptebars
# SOURCE CLIP, not a card, and is intentionally NOT exempted.
FINAL_TIMELINE_STATIC_INTERVALS = [
    {"start": 0.0, "end": 1.5, "reason": "confirmed static intro title card"},
    {"start": 4.5, "end": 5.5, "reason": "confirmed static chapter card"},
    {"start": 10.5, "end": 12.0, "reason": "confirmed static outro card"},
]


def run(cmd, timeout=420):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return p.returncode, p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:
        return -1, "", f"{type(e).__name__}: {e}"


def final_render_qa(ffmpeg: str, ffprobe: str, path, tag: str,
                    expect: dict) -> dict:
    """Strict final QA. NO whole-video freeze exemption exists any more."""
    return qa_media(
        ffmpeg, ffprobe, path, tag=tag, expect=expect,
        static_intervals=FINAL_TIMELINE_STATIC_INTERVALS,
    )


def resolve_defect(ledger: dict, defect_id: str, evidence: dict, cycle: int) -> dict:
    """Only sufficient evidence may mark a defect FIXED.

    P0-2: file existence is NOT sufficient. Automatic and manual evidence are
    stored in separate fields and both are required.
    """
    auto = evidence.get("automatic", {}).get("verdict")
    manual = evidence.get("manual_review", {})
    can_fix = evidence.get("can_mark_fixed") is True
    if can_fix:
        result = "FIXED"
    elif auto == "FAIL":
        result = "STILL_FAILING"
    else:
        result = "NEEDS_MANUAL_REVIEW"

    record = {
        "defect_id": defect_id,
        "previous_result": None,
        "new_result": result,
        "retry_count": cycle,
        "decided_at": now(),
        "decision_basis": {
            "file_existence_weight": 0,
            "automatic_verdict": auto,
            "human_review_verdict": manual.get("verdict"),
            "human_review_signed_off": manual.get("signed_off"),
            "can_mark_fixed": can_fix,
        },
        "automatic_evidence": evidence.get("automatic"),
        "manual_review_evidence": manual,
        "unverified_items": evidence.get("unverified_items", []),
    }
    for d in ledger.get("defects", []):
        if d.get("defect_id") == defect_id:
            record["previous_result"] = d.get("fix_result")
            break
    return record


def _extract_reference(ffmpeg: str, src, out: Path, t: float) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    rc, _, err = run([ffmpeg, "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}",
                      "-i", str(src), "-frames:v", "1", "-q:v", "3", "-y", str(out)])
    return {"ok": rc == 0 and out.exists() and out.stat().st_size > 0,
            "path": str(out), "stderr": err[-200:]}


def reassess_d004(root: Path, ffmpeg: str, ffprobe: str) -> dict:
    """Re-judge the historical D004 using REAL frames, not file existence."""
    qa3 = root / "qa003"
    srt = root / "renders" / "subtitles.srt"
    cases = [
        {
            "label": "horizontal_v2",
            "frame": root / "qa" / "keyframes" / "final_horizontal_v2_f01_2.5s.jpg",
            "nosub_video": root / "renders" / "timeline_raw_v2.mp4",
            "canvas": [1920, 1080], "orientation": "horizontal",
        },
        {
            "label": "vertical_v2",
            "frame": root / "qa" / "keyframes" / "final_vertical_v2_f01_2.5s.jpg",
            "nosub_video": root / "renders" / "vertical_nosub_v2.mp4",
            "canvas": [1080, 1920], "orientation": "vertical",
        },
    ]
    out = {"defect_id": "D004", "reassessed_at": now(), "cases": []}
    for c in cases:
        ref = qa3 / f"{c['label']}_nosub_2.5s.jpg"
        extract = _extract_reference(ffmpeg, c["nosub_video"], ref, 2.5)
        entry = {"label": c["label"], "reference_frame_extraction": extract,
                 "frame": str(c["frame"]), "srt": str(srt)}
        if not extract["ok"] or not c["frame"].exists():
            entry["status"] = "MISSING_EVIDENCE"
            entry["error"] = "cannot reassess without real frames"
            out["cases"].append(entry)
            continue
        band = detect_subtitle_band(c["frame"], ref)
        entry["detected_band"] = band
        if not band.get("detected"):
            # No on-screen subtitle difference at all -> still failing.
            box = [int(c["canvas"][0] * 0.1), int(c["canvas"][1] * 0.80),
                   int(c["canvas"][0] * 0.8), int(c["canvas"][1] * 0.12)]
            box_source = "fallback_estimated_because_no_subtitle_pixels_detected"
        else:
            box = band["box"]
            box_source = band["box_source"]
        spec = {
            "srt_path": str(srt), "frame_path": str(c["frame"]),
            "reference_frame_path": str(ref),
            "canvas": c["canvas"], "orientation": c["orientation"],
            "declared_box": box, "declared_box_source": box_source,
            "font_px": 26 if c["orientation"] == "vertical" else 30,
            "subject_boxes": [],
            # NO human sign-off is supplied: this is an automatic reassessment.
        }
        ev = evaluate_subtitle_fix(spec)
        entry["evaluation"] = ev
        entry["fix_result"] = ev["fix_result"]
        entry["status"] = "REASSESSED"
        out["cases"].append(entry)
    # legacy decision, reproduced only as before/after evidence
    out["legacy_decision"] = legacy_d004_verdict(root / "renders" / "final_vertical_v2.mp4")
    auto_results = [c.get("evaluation", {}).get("automatic", {}).get("verdict")
                    for c in out["cases"]]
    auto_failures = sorted({
        k for c in out["cases"]
        for k in c.get("evaluation", {}).get("automatic", {}).get("failures", [])
    })
    manual_items = sorted({
        k for c in out["cases"]
        for k in c.get("evaluation", {}).get("unverified_items", [])
    })
    if auto_failures:
        new_result = "STILL_FAILING"
        reason = ("automatic subtitle checks found real defects: " + ", ".join(auto_failures)
                  + "; the legacy FIXED verdict was therefore false")
    elif any(not c.get("evaluation", {}).get("can_mark_fixed") for c in out["cases"]):
        new_result = "NEEDS_MANUAL_REVIEW"
        reason = ("automatic checks passed but no named human sign-off was supplied; "
                  "FIXED is not permitted without it")
    else:
        new_result = "FIXED"
        reason = "automatic evidence and named human sign-off are both present"
    out["overall"] = {
        "legacy_result": out["legacy_decision"]["legacy_result"],
        "new_result": new_result,
        "automatic_failures": auto_failures,
        "unverified_items": manual_items,
        "human_sign_off_supplied": False,
        "reason": reason,
    }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="local pipeline root (NOT committed)")
    ap.add_argument("--config", required=True, help="local config.local.json with ffmpeg/ffprobe")
    ap.add_argument("--legacy-defects", required=True, help="WB-VIDEO-002 evidence/defects.json")
    ap.add_argument("--out", required=True, help="output JSON path (WB-VIDEO-003/evidence)")
    a = ap.parse_args()

    root = Path(a.root).resolve()
    cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
    ff, fp = cfg["ffmpeg"], cfg["ffprobe"]
    legacy = json.loads(Path(a.legacy_defects).read_text(encoding="utf-8"))

    result = {
        "task_id": "WB-VIDEO-003-REWORK-FIX",
        "started_at": now(),
        "quota_consuming_calls": 0,
        "p0_1": {}, "p0_2": {}, "bounded_gate": {},
    }

    # --- P0-1: strict final-render QA with an explicit whitelist -----------
    norm, errors = validate_static_whitelist(FINAL_TIMELINE_STATIC_INTERVALS, 12.0)
    result["p0_1"]["whitelist_validation"] = {"normalised": norm, "errors": errors}
    for label, rel, expect in [
        ("horizontal_v2", "renders/final_horizontal_v2.mp4", {"width": 1920, "height": 1080, "fps": 30}),
        ("vertical_v2", "renders/final_vertical_v2.mp4", {"width": 1080, "height": 1920, "fps": 30}),
    ]:
        p = root / rel
        if not p.exists():
            result["p0_1"][label] = {"verdict": "MISSING"}
            continue
        r = final_render_qa(ff, fp, p, f"strict_{label}", expect)
        result["p0_1"][label] = {
            "verdict": r["verdict"], "problems": r["problems"],
            "frozen_frame_check": r["checks"]["frozen_frame"],
            "whitelist_errors": r["freeze_policy"]["whitelist_errors"],
            "raw_freeze_intervals": r["freeze_policy"]["raw_intervals"],
            "evaluated_freeze_intervals": r["freeze_policy"]["evaluated_intervals"],
            "needs_manual_review": r["needs_manual_review"],
        }

    # --- P0-2: reassess D004 from real frame evidence ----------------------
    d004 = reassess_d004(root, ff, fp)
    result["p0_2"]["d004_reassessment"] = d004
    result["p0_2"]["ledger_resolution"] = resolve_defect(
        legacy, "D004",
        d004["cases"][-1].get("evaluation", {}),
        cycle=2,
    )

    # --- bounded gate (reuse verified policy, do not rebuild it) -----------
    policy = RetryPolicy()
    policy.cycles["S003"] = 1
    c1 = policy.cycle("S003")
    policy.cycle("S003")
    result["bounded_gate"] = {
        "cycle_used": c1, "max_rework_cycles": policy.MAX_REWORK_CYCLES,
        "third_cycle_allowed": policy.can_rework("S003"),
        "human_review_gate": policy.HUMAN_REVIEW_GATE,
        "note": "rework stops at REVIEW_REQUIRED; P0 defects are not auto-resolved past the gate",
    }
    result["ended_at"] = now()

    BS = chr(92)
    home = str(Path.home()).replace(BS, "/")
    local_prefixes = [home, home.replace("/", BS)]
    for key in ("vidova_data_root", "jianying_app_dir", "jianying_draft_root"):
        v = str(cfg.get(key, "") or "")
        if v:
            local_prefixes += [v, v.replace("/", BS), v.replace(BS, "/")]

    def redact(o):
        if isinstance(o, str):
            s = o
            for prefix in set(local_prefixes):
                if prefix:
                    s = s.replace(prefix, "<LOCAL>")
            return s.replace(str(root), "<PIPELINE>")
        if isinstance(o, dict):
            return {k: redact(v) for k, v in o.items()}
        if isinstance(o, list):
            return [redact(v) for v in o]
        return o

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(redact(result), ensure_ascii=False, indent=2, default=str),
                   encoding="utf-8")
    print(json.dumps({
        "p0_1": {k: v.get("verdict") for k, v in result["p0_1"].items()
                 if isinstance(v, dict) and "verdict" in v},
        "p0_2_new_result": d004["overall"]["new_result"],
        "p0_2_legacy_result": d004["overall"]["legacy_result"],
        "third_cycle_allowed": result["bounded_gate"]["third_cycle_allowed"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
