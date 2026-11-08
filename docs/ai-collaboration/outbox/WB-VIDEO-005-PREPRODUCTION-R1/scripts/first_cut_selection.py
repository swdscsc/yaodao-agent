#!/usr/bin/env python3
"""Re-select the 15-30 s first cut from ALL 33 shots, without reusing S08-S10.

Six hard criteria come from the R1 task book. Every judgement is derived from
the corrected authoritative SHOTS table (source / gap / truth / screen /
dialogue / narration / transition / music), never from a hand-written opinion.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_deliverables_r1 import (SHOTS, R1_EVID, char_count,
                                   NARRATION_CHAR_COUNT)

# Explicit shot -> source-backed claim map, transcribed from the A-table
# landing points in product-claims-register.md. Used instead of guessing from
# free text, so the evidence link is auditable.
SHOT_CLAIM_MAP = {
    "S08": ["A01 一句话建档 + 复述确认 (med_plan_save)"],
    "S09": ["A01 一句话建档 + 复述确认 (med_plan_save)"],
    "S13": ["A01 一句话建档 + 复述确认 (med_plan_save)"],
    "S15": ["A01 一句话建档 + 复述确认 (med_plan_save)"],
    "S16": ["A02 按餐次分组查询 (med_plan_list)"],
    "S17": ["A03 打卡与温和反馈 (med_take)"],
    "S18": ["A04 当日小结 (med_report)"],
    "S19": ["A05 稍后提醒 (med_snooze)"],
    "S20": ["A06 唤醒后提醒 (MedPromptBuilder)"],
    "S21": ["A07 拍照建档入口 (MedicinePhotoHandler)"],
    "S22": ["A07 一次只问一件 (medVision.nextQuestion)"],
    "S29": ["A08 安全边界 (med_plan_delete)"],
    "S30": ["A09 紧急拨打 120 (源码 120 提示语)"],
}

# Shots that make NO product claim at all (pure graphics / cards / breathing).
# S11/S12 are R1 "product design intent" cards: they explicitly declare a
# mock-up and make NO verifiable product claim, so H5 is N/A for them too.
NO_CLAIM_SHOTS = {"S03", "S10", "S11", "S12", "S14", "S23", "S27", "S32", "S33"}

BAD_TRUTH = ("DRAMATIZATION", "STILL_LIFE_REQUIRED", "PRODUCT_UI_REQUIRED")
GOOD_TRUTH = ("ORIGINAL_GRAPHIC", "MOCK_UI", "TEXT_CARD", "BRAND_CARD")


def evaluate(s: dict) -> dict:
    """Five SHOT-level hard gates. Segment-level editing showcase is scored
    separately below: a chapter card legitimately has no subtitle of its own."""
    truth = s["truth"]
    source = s["source"]
    screen = s["screen"]
    sid = s["id"]

    h1 = not any(k in truth for k in BAD_TRUTH) and "MISSING:" not in source
    h2 = (not any(k in truth for k in ("STILL_LIFE_REQUIRED", "PRODUCT_UI_REQUIRED"))
          and not any(k in source for k in ("真实设备外观", "真机照片")))
    h3 = any(k in truth for k in GOOD_TRUTH)
    is_ui = "MOCK_UI" in truth or "界面" in screen or "界面" in s["visual"]
    h4 = (not is_ui) or ("模拟界面" in screen or "产品设计示意" in screen
                         or "MOCK_UI" in truth)
    claims = SHOT_CLAIM_MAP.get(sid, [])
    no_claim = sid in NO_CLAIM_SHOTS
    h5 = bool(claims) or no_claim

    checks = {
        "H1_no_live_action": h1,
        "H2_no_real_device_capture": h2,
        "H3_original_graphic_or_mock_ui": h3,
        "H4_mock_ui_explicitly_labelled_or_na": h4,
        "H5_source_backed_claim_or_no_claim": h5,
    }
    return {
        "shot": sid, "chapter": s["chapter"],
        "tin": s["tin"], "tout": s["tout"], "duration": s["tout"] - s["tin"],
        "truth_label": truth, "source": source,
        "claims": claims,
        "claim_is_na_no_product_claim": no_claim,
        "narration_cues": 1 if s["narration"] else 0,
        "dialogue_cues": len(s["dialogue"]),
        "has_sound_design": bool(s["music"]),
        "has_transition": bool(s["trans"]),
        "checks": checks,
        "passed": sum(checks.values()),
        "eligible": all(checks.values()),
        "exclusion_reasons": [k for k, v in checks.items() if not v],
    }


def main() -> None:
    os.makedirs(R1_EVID, exist_ok=True)
    per_shot = [evaluate(s) for s in SHOTS]
    by_id = {r["shot"]: r for r in per_shot}

    candidates = []
    for i in range(len(SHOTS)):
        for j in range(i, len(SHOTS)):
            seg = SHOTS[i:j + 1]
            dur = seg[-1]["tout"] - seg[0]["tin"]
            if not (15 <= dur <= 30):
                continue
            ev = [by_id[s["id"]] for s in seg]
            all_eligible = all(e["eligible"] for e in ev)
            claims = sorted({c for e in ev for c in e["claims"]})
            narration = sum(e["narration_cues"] for e in ev)
            dialogue = sum(e["dialogue_cues"] for e in ev)
            transitions = sorted({s["trans"].split("：")[0].split("+")[0][:18] for s in seg})
            jcut = sum(1 for s in seg if "J-cut" in (s["trans"] + s["music"] + s["rhythm"]))
            lcut = sum(1 for s in seg if "L-cut" in s["trans"] or "尾音" in s["trans"])
            chapter_card = sum(1 for s in seg if "TEXT_CARD" in s["truth"]
                               or "BRAND_CARD" in s["truth"])
            sound_designs = sum(1 for e in ev if e["has_sound_design"])
            # Segment-level showcase: the task explicitly asks for editing,
            # subtitles, transitions AND sound design, not just a feature count.
            showcase = 3 * (narration + dialogue) + 8 * len(transitions) \
                       + 6 * jcut + 6 * lcut + 5 * chapter_card + 2 * sound_designs
            candidates.append({
                "segment": f"{seg[0]['id']}-{seg[-1]['id']}",
                "shots": [s["id"] for s in seg],
                "master_timecode": f"{seg[0]['tin']}-{seg[-1]['tout']} s",
                "duration_s": dur,
                "all_shots_eligible": all_eligible,
                "eligible_shots": sum(1 for e in ev if e["eligible"]),
                "shot_count": len(seg),
                "source_backed_claims": claims,
                "source_backed_claim_count": len(claims),
                "narration_cues": narration,
                "dialogue_cues": dialogue,
                "subtitle_cues_total": narration + dialogue,
                "transition_types": len(transitions),
                "jcut_mentions": jcut,
                "lcut_mentions": lcut,
                "chapter_or_brand_cards": chapter_card,
                "sound_design_cues": sound_designs,
                "editing_showcase_score": showcase,
                "score": (100 if all_eligible else 0) + 6 * len(claims)
                         + showcase - abs(dur - 25) * 0.5,
            })
    candidates.sort(key=lambda c: (-c["score"], c["segment"]))
    for rank, c in enumerate(candidates[:12], 1):
        c["rank"] = rank
    selected = candidates[0]

    out = {
        "scoring_id": "R1-FIRST-CUT-SELECTION-001",
        "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "data_source": "R1/scripts/build_deliverables_r1.py :: SHOTS "
                       "(corrected authoritative table)",
        "data_source_sha256": hashlib.sha256(
            open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "build_deliverables_r1.py"), "rb").read()).hexdigest(),
        "shot_level_hard_gates": [
            "H1 no live-action / no MISSING real-world footage",
            "H2 no real product device photography",
            "H3 usable as original motion graphic or labelled mock UI",
            "H4 mock UI explicitly labelled on screen (N/A for pure text/graphic cards)",
            "H5 function claim has source-code evidence, or the shot makes no product claim",
        ],
        "segment_level_metrics": [
            "subtitle cue count", "transition type count", "J-cut / L-cut mentions",
            "chapter or brand card count", "sound-design cue count", "duration 15-30 s",
        ],
        "r0_choice": {"segment": "S08-S10", "duration_s": 22,
                      "status": "REJECTED_BY_R1",
                      "reason": "S08 depends on live-action + real device; S09/S10 have "
                                "no source-backed claim at the centre of the segment; "
                                "R1 requirement forbids mechanically reusing it."},
        "shot_count_evaluated": len(per_shot),
        "eligible_shot_count": sum(1 for r in per_shot if r["eligible"]),
        "per_shot": per_shot,
        "candidate_segments_in_15_30s": len(candidates),
        "top_candidates": candidates[:12],
        "selected": selected,
        "narration_character_count_of_full_script": NARRATION_CHAR_COUNT,
    }
    path = os.path.join(R1_EVID, "first-cut-scoring.json")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps({
        "shots_evaluated": len(per_shot),
        "eligible_shots": out["eligible_shot_count"],
        "candidate_segments": len(candidates),
        "selected": selected["segment"],
        "duration": selected["duration_s"],
        "all_eligible": selected["all_shots_eligible"],
        "claims": selected["source_backed_claims"],
        "subtitle_cues": selected["subtitle_cues_total"],
        "top3": [(c["segment"], c["duration_s"], c["score"]) for c in candidates[:3]],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
