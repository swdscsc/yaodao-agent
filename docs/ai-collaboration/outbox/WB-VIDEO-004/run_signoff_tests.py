#!/usr/bin/env python3
"""WB-VIDEO-004 automated tests: per-item subtitle sign-off + QA improvements.

All media is generated locally with PIL (test frames) and the SRT/JSON are
written locally. No hosted quota, no network call, no paid service, no change
to any user project. Test reviewers are synthetic and are kept OUT of any
production sign-off ledger; the tests explicitly prove that.

Outputs
-------
* subtitle-signoff-tests.json          (required deliverable)
* evidence/signoff_before_after.json   (WB-VIDEO-003 vs WB-VIDEO-004 gate)
* evidence/signoff_sample_contact_sheet.jpg (small visual evidence)
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]  # workspace root
sys.path.insert(0, str(HERE))

import subtitle_checks as sc  # noqa: E402

TZ = timezone(timedelta(hours=8))
MEDIA = ROOT / "pipeline/qa004"
EVIDENCE = HERE / "evidence"
MEDIA.mkdir(parents=True, exist_ok=True)
EVIDENCE.mkdir(parents=True, exist_ok=True)

CANVAS = [640, 360]
BOX = [40, 288, 560, 46]
FRAME_ID = "frame_t5.0s"
VIDEO_VERSION = "wb003_vertical_v2_TEST_SIGNAL_ONLY"
REVIEW_WINDOW = [4.0, 6.0]
SRT_TEXT = "1\n00:00:04,800 --> 00:00:05,600\nTAKE WITH WATER AFTER MEALS\n\n"
SUBTITLE_VERSION = "sha256:" + hashlib.sha256(SRT_TEXT.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Local test media (synthetic, clearly NOT real footage / real AI assets)
# ---------------------------------------------------------------------------
def _font(size: int):
    cfg = ROOT / "pipeline/config.local.json"
    try:
        p = json.loads(cfg.read_text(encoding="utf-8")).get("font")
        if p and Path(p).exists():
            return ImageFont.truetype(p, size)
    except Exception:
        pass
    return ImageFont.load_default(size=size)


def _background(high_contrast_bars: bool, base: int) -> Image.Image:
    img = Image.new("RGB", tuple(CANVAS), (base, base, base))
    d = ImageDraw.Draw(img)
    for i in range(0, CANVAS[0], 40):
        shade = base + (8 if (i // 40) % 2 else 0)
        d.rectangle([i, 0, i + 39, CANVAS[1]], fill=(shade, shade, shade))
    if high_contrast_bars:
        x, y, w, h = BOX
        for i in range(x + 20, x + w, 55):
            d.rectangle([i, y + 2, i + 6, y + h - 2], fill=(245, 245, 245))
    return img


def make_pair(name: str, base: int, text_colour, bars: bool, draw_text: bool) -> dict:
    ref = _background(bars, base)
    ref_path = MEDIA / f"{name}_ref.png"
    ref.save(ref_path)
    frame = ref.copy()
    if draw_text:
        d = ImageDraw.Draw(frame)
        d.text((BOX[0] + 12, BOX[1] + 4), "TAKE WITH WATER  |  08:00",
               fill=text_colour, font=_font(36))
    frame_path = MEDIA / f"{name}_frame.png"
    frame.save(frame_path)
    return {"frame_path": str(frame_path), "reference_frame_path": str(ref_path)}


def make_srt() -> str:
    p = MEDIA / "signoff_test.srt"
    p.write_text(SRT_TEXT, encoding="utf-8")
    return str(p)


class Suite:
    def __init__(self):
        self.cases = []

    def add(self, group, name, expected, actual, passed, evidence=None):
        self.cases.append({"group": group, "name": name, "expected": expected,
                           "actual": actual, "passed": bool(passed),
                           "evidence": evidence or {}})

    @property
    def summary(self):
        return {"total": len(self.cases),
                "passed": sum(1 for c in self.cases if c["passed"]),
                "failed": sum(1 for c in self.cases if not c["passed"]),
                "all_passed": all(c["passed"] for c in self.cases)}


# ---------------------------------------------------------------------------
# Sign-off record helpers
# ---------------------------------------------------------------------------
REVIEWERS = {
    "text_content_matches_srt": "QA_LEAD_AAA",
    "semantic_readability": "QA_LEAD_BBB",
    "occlusion_by_undeclared_content": "QA_LEAD_CCC",
}
REVIEW_TIMES = {
    "text_content_matches_srt": "2026-11-08T16:12:00+08:00",
    "semantic_readability": "2026-11-08T16:15:00+08:00",
    "occlusion_by_undeclared_content": "2026-11-08T16:18:00+08:00",
}


def record(item, **over):
    r = {
        "reviewer": REVIEWERS[item],
        "reviewed_at": REVIEW_TIMES[item],
        "item_id": item,
        "verdict": "APPROVED",
        "evidence": (f"On {FRAME_ID} at 4.8-5.2s I visually read the burned-in "
                     f"subtitle and checked {item} against subtitle version "
                     f"{SUBTITLE_VERSION} of video {VIDEO_VERSION}."),
        "notes": f"Independent review of {item}; no automatic result reused.",
        "frame_ref": FRAME_ID,
        "time_range": [4.8, 5.2],
        "video_version": VIDEO_VERSION,
        "subtitle_version": SUBTITLE_VERSION,
    }
    r.update(over)
    return r


def all_records(**per_item_over):
    out = []
    for item in sc.MANUAL_ITEMS:
        out.append(record(item, **per_item_over.get(item, {})))
    return out


def base_spec(media: dict, srt: str, **over) -> dict:
    s = {
        "canvas": CANVAS, "declared_box": BOX, "orientation": "horizontal",
        "frame_path": media["frame_path"], "reference_frame_path": media["reference_frame_path"],
        "srt_path": srt, "font_px": 36,
        "subject_boxes": [[10, 10, 60, 40]],  # declared, non-overlapping
        "frame_id": FRAME_ID, "review_time_range": REVIEW_WINDOW,
        "video_version": VIDEO_VERSION, "subtitle_version": SUBTITLE_VERSION,
    }
    s.update(over)
    return s


def with_review(spec, records, context="production"):
    s = dict(spec)
    s["manual_review"] = {"items": records, "context": context}
    return s


def run_check(s: Suite, group, name, expected, actual, predicate, evidence=None):
    s.add(group, name, expected, actual, bool(predicate), evidence)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def main() -> int:
    s = Suite()
    good = make_pair("normal", 30, (245, 245, 245), False, True)
    low = make_pair("low_contrast", 100, (112, 112, 112), True, True)
    no_sub = make_pair("no_burn_in", 30, (245, 245, 245), False, False)
    srt = make_srt()
    base = base_spec(good, srt)
    full = with_review(base, all_records())

    # --- 1. all three items individually approved -> FIXED -----------------
    r = sc.evaluate_subtitle_fix(full)
    run_check(s, "P0_signoff", "all_three_items_approved",
              "FIXED with 3 independent per-item records", r["fix_result"],
              r["fix_result"] == "FIXED" and r["manual_review"]["all_items_approved"],
              {"approved_items": r["manual_review"]["approved_items"],
               "prerequisites": r["prerequisites"],
               "automatic_verdict": r["automatic"]["verdict"]})

    # --- 2. only one item approved ----------------------------------------
    r = sc.evaluate_subtitle_fix(with_review(base, [record(sc.MANUAL_ITEMS[0])]))
    run_check(s, "P0_signoff", "only_one_item_approved",
              "NOT FIXED, 2 items still missing", r["fix_result"],
              r["fix_result"] != "FIXED" and len(r["manual_review"]["missing_or_invalid_items"]) == 2,
              {"approved_items": r["manual_review"]["approved_items"],
               "missing": r["manual_review"]["missing_or_invalid_items"]})

    # --- 3. one item not reviewed at all ----------------------------------
    partial = [record(sc.MANUAL_ITEMS[0]), record(sc.MANUAL_ITEMS[1])]
    r = sc.evaluate_subtitle_fix(with_review(base, partial))
    target = r["manual_review"]["items"][sc.MANUAL_ITEMS[2]]
    run_check(s, "P0_signoff", "one_item_not_reviewed",
              "NOT_REVIEWED blocks FIXED", r["fix_result"],
              r["fix_result"] != "FIXED" and target["verdict"] == "NOT_REVIEWED",
              {"target_item_status": target["verdict"],
               "missing": r["manual_review"]["missing_or_invalid_items"]})

    # --- 4. empty reviewer -------------------------------------------------
    recs = all_records(text_content_matches_srt={"reviewer": ""})
    r = sc.evaluate_subtitle_fix(with_review(base, recs))
    errs = r["manual_review"]["items"][sc.MANUAL_ITEMS[0]]["errors"]
    run_check(s, "P0_signoff", "empty_reviewer_rejected",
              "record invalid, no FIXED", r["fix_result"],
              r["fix_result"] != "FIXED" and any("empty_reviewer" in e for e in errs),
              {"errors": errs})

    # --- 5. empty evidence -------------------------------------------------
    recs = all_records(semantic_readability={"evidence": ""})
    r = sc.evaluate_subtitle_fix(with_review(base, recs))
    errs = r["manual_review"]["items"]["semantic_readability"]["errors"]
    run_check(s, "P0_signoff", "empty_evidence_rejected",
              "record invalid, no FIXED", r["fix_result"],
              r["fix_result"] != "FIXED" and any("invalid_evidence" in e for e in errs),
              {"errors": errs})

    # --- 6. wrong video version -------------------------------------------
    recs = all_records(text_content_matches_srt={"video_version": "some_other_render_v9"})
    v = sc.verify_signoff_set(base, recs, "production")
    run_check(s, "P0_signoff", "wrong_video_version_rejected",
              "binding fails, no FIXED", v["verdict"],
              not v["all_items_approved"] and any(
                  "video_version_does_not_match_spec" in e
                  for e in v["items"][sc.MANUAL_ITEMS[0]]["errors"]),
              {"errors": v["items"][sc.MANUAL_ITEMS[0]]["errors"],
               "binding_valid": v["signoff_integrity"]["binding_valid"]})

    # --- 7. wrong subtitle version ----------------------------------------
    recs = all_records(semantic_readability={"subtitle_version": "sha256:deadbeef"})
    v = sc.verify_signoff_set(base, recs, "production")
    run_check(s, "P0_signoff", "wrong_subtitle_version_rejected",
              "binding fails, no FIXED", v["verdict"],
              not v["all_items_approved"] and any(
                  "subtitle_version_does_not_match_spec" in e
                  for e in v["items"]["semantic_readability"]["errors"]),
              {"errors": v["items"]["semantic_readability"]["errors"]})

    # --- 8. automatic FAIL but human APPROVED ------------------------------
    low_spec = base_spec(low, srt)
    r = sc.evaluate_subtitle_fix(with_review(low_spec, all_records()))
    run_check(s, "P0_signoff", "auto_fail_but_human_approved",
              "STILL_FAILING; human cannot override automatic FAIL", r["fix_result"],
              r["fix_result"] == "STILL_FAILING"
              and r["manual_review"]["all_items_approved"]
              and r["automatic"]["verdict"] == "FAIL",
              {"automatic_failures": r["automatic"]["failures"],
               "human_approved": r["manual_review"]["all_items_approved"],
               "human_cannot_override_automatic_fail": r["human_cannot_override_automatic_fail"]})

    # --- 9. automatic PASS but human not reviewed --------------------------
    r = sc.evaluate_subtitle_fix(with_review(base, []))
    run_check(s, "P0_signoff", "auto_pass_but_human_not_reviewed",
              "NEEDS_MANUAL_REVIEW; auto PASS is not a human PASS", r["fix_result"],
              r["fix_result"] == "NEEDS_MANUAL_REVIEW"
              and r["automatic"]["verdict"] == "PASS"
              and not r["manual_review"]["all_items_approved"],
              {"automatic_verdict": r["automatic"]["verdict"],
               "missing": r["manual_review"]["missing_or_invalid_items"],
               "auto_pass_is_not_human_pass": r["auto_pass_is_not_human_pass"]})

    # --- 10. synthetic test reviewer cannot impersonate real review --------
    recs = [dict(r, reviewer="TEST_REVIEWER_004", test_only=True,
                 review_source="unit_test") for r in all_records()]
    r = sc.evaluate_subtitle_fix(with_review(base, recs))
    ledger = MEDIA / "production_signoff_ledger.jsonl"
    if ledger.exists():
        ledger.unlink()
    refused = False
    try:
        sc.append_production_signoff(ledger, base, recs)
    except sc.SignoffError:
        refused = True
    run_check(s, "P0_signoff", "synthetic_reviewer_cannot_impersonate_production",
              "all records invalid in production + ledger write refused", r["fix_result"],
              r["fix_result"] != "FIXED"
              and all("synthetic_test_reviewer_not_admissible" in
                      " ".join(v["errors"]) for v in r["manual_review"]["items"].values())
              and refused and not ledger.exists(),
              {"errors": {k: v["errors"] for k, v in r["manual_review"]["items"].items()},
               "production_ledger_write_refused": refused,
               "production_ledger_exists": ledger.exists()})

    # --- 11. legacy single global APPROVED object is rejected --------------
    legacy_review = {"verdict": "APPROVED", "reviewer": "QA_LEAD_AAA",
                     "evidence": "looks good"}
    before = sc.legacy_wb003_signoff_gate(legacy_review)
    after = sc.verify_signoff_set(base, legacy_review, "production")
    run_check(s, "P0_signoff", "legacy_global_approved_object_rejected",
              "old gate signed=True; new gate requires 3 per-item records",
              after["verdict"],
              before["signed_off"] is True
              and not after["all_items_approved"]
              and len(after["missing_or_invalid_items"]) == 3,
              {"old_gate_signed_off": before["signed_off"],
               "new_gate_approved_items": after["approved_items"],
               "extraneous_records": after["extraneous_records"]})

    # --- 12. future reviewed_at -------------------------------------------
    recs = all_records(text_content_matches_srt={"reviewed_at": "2099-01-01T00:00:00+08:00"})
    v = sc.verify_signoff_set(base, recs, "production")
    run_check(s, "P0_signoff", "future_reviewed_at_rejected",
              "invalid timestamp rejected", v["verdict"],
              any("invalid_reviewed_at" in e
                  for e in v["items"][sc.MANUAL_ITEMS[0]]["errors"]),
              {"errors": v["items"][sc.MANUAL_ITEMS[0]]["errors"]})

    # --- 13. wrong frame reference ----------------------------------------
    recs = all_records(semantic_readability={"frame_ref": "frame_t9.9s"})
    v = sc.verify_signoff_set(base, recs, "production")
    run_check(s, "P0_signoff", "wrong_frame_ref_rejected",
              "frame binding rejected", v["verdict"],
              any("frame_ref_does_not_match_specified_frame" in e
                  for e in v["items"]["semantic_readability"]["errors"]),
              {"errors": v["items"]["semantic_readability"]["errors"]})

    # --- 14. time range outside the declared review window -----------------
    recs = all_records(occlusion_by_undeclared_content={"time_range": [8.0, 9.0]})
    v = sc.verify_signoff_set(base, recs, "production")
    run_check(s, "P0_signoff", "time_range_outside_window_rejected",
              "time binding rejected", v["verdict"],
              any("time_range_outside_specified_review_window" in e
                  for e in v["items"]["occlusion_by_undeclared_content"]["errors"]),
              {"errors": v["items"]["occlusion_by_undeclared_content"]["errors"]})

    # --- 15. duplicate record for one item --------------------------------
    recs = all_records() + [record(sc.MANUAL_ITEMS[0])]
    v = sc.verify_signoff_set(base, recs, "production")
    run_check(s, "P0_signoff", "duplicate_item_record_rejected",
              "duplicate rejected", v["verdict"],
              any("duplicate_records_for_item" in e
                  for e in v["items"][sc.MANUAL_ITEMS[0]]["errors"]),
              {"errors": v["items"][sc.MANUAL_ITEMS[0]]["errors"]})

    # --- 16. one item explicitly REJECTED ---------------------------------
    recs = all_records(semantic_readability={"verdict": "REJECTED"})
    v = sc.verify_signoff_set(base, recs, "production")
    run_check(s, "P0_signoff", "human_rejected_item_cannot_fix",
              "REJECTED blocks FIXED", v["verdict"],
              not v["all_items_approved"] and any("verdict_is_not_APPROVED" in e
                                                  for e in v["items"]["semantic_readability"]["errors"]),
              {"errors": v["items"]["semantic_readability"]["errors"]})

    # --- 17. font size: render parameter alone must NOT auto-PASS ----------
    no_ref = dict(base)
    no_ref.pop("reference_frame_path")
    r = sc.evaluate_subtitle_fix(with_review(no_ref, all_records()))
    fs = r["automatic"]["checks"]["font_size"]
    run_check(s, "font", "font_size_render_param_only_not_pass",
              "NEEDS_MANUAL_REVIEW; render param has decision_weight 0", fs["verdict"],
              fs["verdict"] == "NEEDS_MANUAL_REVIEW"
              and fs["render_param_used_for_verdict"] is False
              and fs["font_px_render_param"] == 36
              and fs["font_px_measured"] is None,
              {"font_size": fs})

    # --- 18. font size three states recorded separately --------------------
    r = sc.evaluate_subtitle_fix(full)
    states = r["font_size_states"]
    run_check(s, "font", "font_three_states_recorded_separately",
              "render / measured / human-confirmed are distinct fields",
              list(states.keys()),
              states["frame_measured"] is not None
              and states["render_parameter"] == 36
              and states["human_confirmed"] is None,
              {"states": states,
               "note": states["note"]})

    # --- 19. contrast measures TEXT vs ADJACENT BACKGROUND -----------------
    lc = sc.inspect_subtitle(base_spec(low, srt))
    c = lc["automatic"]["checks"]["contrast"]
    run_check(s, "contrast", "contrast_measures_text_not_whole_band",
              "FAIL even though band luma spread is large", c["verdict"],
              c["verdict"] == "FAIL"
              and (c["band_spread_diagnostic_only"] or 0) >= sc.MIN_CONTRAST_SPREAD
              and c["band_spread_used_for_verdict"] is False,
              {"contrast": c})

    gc = sc.inspect_subtitle(base)["automatic"]["checks"]["contrast"]
    run_check(s, "contrast", "high_contrast_text_passes_real_measurement",
              "PASS with measured ratio and luma delta", gc["verdict"],
              gc["verdict"] == "PASS" and (gc["contrast_ratio"] or 0) >= sc.MIN_TEXT_CONTRAST_RATIO,
              {"contrast": gc})

    # --- 20. IoU-only occlusion would miss a small subject -----------------
    occ_spec = base_spec(good, srt, subject_boxes=[[300, 300, 8, 8]])
    occ = sc.inspect_subtitle(occ_spec)["automatic"]["checks"]["subject_overlap"]
    run_check(s, "occlusion", "small_occluder_iou_miss_detected",
              "new coverage signal FAILs where legacy IoU would PASS", occ["verdict"],
              occ["verdict"] == "FAIL"
              and occ["legacy_iou_would_pass"] is True
              and occ["coverage_signal_detected"] is True,
              {"occlusion": occ})

    # --- 21. automatic and manual structures are separate ------------------
    r = sc.evaluate_subtitle_fix(full)
    separate = ("checks" in r["automatic"]
                and "items" in r["manual_review"]
                and "checks" not in r["manual_review"]
                and "items" not in r["automatic"]
                and r["automatic_and_manual_recorded_separately"])
    run_check(s, "P0_signoff", "automatic_and_manual_structures_separate",
              "two independent data structures", separate, separate,
              {"automatic_keys": sorted(r["automatic"].keys()),
               "manual_keys": sorted(r["manual_review"].keys())})

    # --- 22. each item keeps its own reviewer/time/evidence/hash -----------
    items = r["manual_review"]["items"]
    reviewers = {items[k]["reviewer"] for k in sc.MANUAL_ITEMS}
    times = {items[k]["reviewed_at"] for k in sc.MANUAL_ITEMS}
    hashes = {items[k]["record_sha256"] for k in sc.MANUAL_ITEMS}
    independent = len(reviewers) == 3 and len(times) == 3 and len(hashes) == 3
    run_check(s, "P0_signoff", "per_item_independent_records",
              "3 distinct reviewers, timestamps, evidence hashes", independent, independent,
              {"reviewers": sorted(reviewers), "timestamps": sorted(times),
               "signoff_hash": r["manual_review"]["signoff_integrity"]["signoff_hash"]})

    # --- 23. synthetic reviewers confined to unit_test context -------------
    synthetic = [dict(x, reviewer="MOCK_UNIT_REVIEWER", test_only=True) for x in all_records()]
    v_ut = sc.verify_signoff_set(base, synthetic, "unit_test")
    v_pr = sc.verify_signoff_set(base, synthetic, "production")
    run_check(s, "P0_signoff", "synthetic_reviewers_confined_to_unit_test",
              "allowed in unit_test only; never production-admissible",
              {"unit_test": v_ut["all_items_approved"], "production": v_pr["all_items_approved"]},
              v_ut["all_items_approved"] and not v_pr["all_items_approved"]
              and not v_ut["signoff_integrity"]["production_admissible"],
              {"unit_test_admissible": v_ut["signoff_integrity"]["production_admissible"],
               "production_admissible": v_pr["signoff_integrity"]["production_admissible"]})

    # --- 24. SRT exists but no burned-in subtitle --------------------------
    r = sc.evaluate_subtitle_fix(with_review(base_spec(no_sub, srt), all_records()))
    be = r["automatic"]["checks"]["burned_in_evidence"]
    run_check(s, "regression", "srt_exists_but_no_burned_in_subtitle",
              "automatic FAIL -> STILL_FAILING despite full sign-off", r["fix_result"],
              be["verdict"] == "FAIL" and r["fix_result"] == "STILL_FAILING",
              {"burned_in_evidence": be, "human_approved": r["manual_review"]["all_items_approved"]})

    # --- 25. production ledger accepts a real (non-synthetic) sign-off -----
    ledger = MEDIA / "production_signoff_ledger.jsonl"
    if ledger.exists():
        ledger.unlink()
    try:
        w = sc.append_production_signoff(ledger, base, all_records())
        written = w["written"] and ledger.exists()
    except sc.SignoffError as e:
        written, w = False, {"error": str(e)}
    run_check(s, "P0_signoff", "production_ledger_accepts_valid_signoff",
              "valid non-synthetic per-item sign-off is auditable", written, written,
              {"result": w, "note": "test-only ledger in a local scratch directory; no production defect was signed off"})

    # -----------------------------------------------------------------------
    # Before/after evidence + contact sheet
    # -----------------------------------------------------------------------
    global_review = {"verdict": "APPROVED", "reviewer": "QA_LEAD_AAA",
                     "evidence": "looks good"}
    before_after = {
        "task_id": "WB-VIDEO-004",
        "captured_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "defect": "WB-VIDEO-003 evaluate_subtitle_fix accepted ONE global APPROVED object; MANUAL_ITEMS were never individually reviewed",
        "before": {
            "source": "docs/ai-collaboration/outbox/WB-VIDEO-003/subtitle_checks.py lines 319-320",
            "legacy_expression": "signed = bool(review.get('verdict') == 'APPROVED' and review.get('reviewer') and review.get('evidence'))",
            "input": global_review,
            "result": sc.legacy_wb003_signoff_gate(global_review),
        },
        "after": {
            "source": "docs/ai-collaboration/outbox/WB-VIDEO-004/subtitle_checks.py verify_signoff_set()",
            "input": global_review,
            "result": sc.verify_signoff_set(base, global_review, "production"),
            "required_per_item_records": sc.MANUAL_ITEMS,
        },
        "comparison": "same single global APPROVED input: old gate signed_off=true; new gate approved 0 of 3 items and refuses FIXED",
    }
    (EVIDENCE / "signoff_before_after.json").write_text(
        json.dumps(before_after, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        thumbs = []
        for p in [good["frame_path"], low["frame_path"], no_sub["frame_path"]]:
            im = Image.open(p).convert("RGB").resize((320, 180))
            thumbs.append(im)
        sheet = Image.new("RGB", (320 * 3, 180), (20, 20, 20))
        for i, im in enumerate(thumbs):
            sheet.paste(im, (320 * i, 0))
        sheet.save(EVIDENCE / "signoff_sample_contact_sheet.jpg", quality=82)
    except Exception as e:
        print("contact sheet failed:", e)

    doc = {
        "task_id": "WB-VIDEO-004",
        "captured_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "timezone": "Asia/Shanghai (UTC+08:00)",
        "module_under_test": "outbox/WB-VIDEO-004/subtitle_checks.py",
        "policy": "per_item_signoff_v1",
        "media_generation": ("Local PIL test frames + local SRT only. Synthetic TEST SIGNAL "
                             "frames are NOT real footage and NOT AI-generated assets. "
                             "No network, no hosted quota, no paid service."),
        "signoff_disclaimer": ("All reviewer names in this test file are synthetic test data. "
                               "No real human sign-off was performed and NO production "
                               "sign-off ledger in the repository was written. D004 remains "
                               "STILL_FAILING / REVIEW_REQUIRED."),
        "signoff_policy": {
            "required_items": sc.MANUAL_ITEMS,
            "required_fields_per_item": sc.SIGNOFF_REQUIRED_FIELDS,
            "required_binding_fields_per_item": sc.SIGNOFF_BINDING_FIELDS,
            "spec_binding_anchors": sc.SPEC_BINDING_FIELDS,
            "rejects": ["empty reviewer", "empty/placeholder evidence", "missing timestamp",
                        "future timestamp", "wrong video version", "wrong subtitle version",
                        "wrong frame reference", "out-of-window time range",
                        "duplicate item record", "non-APPROVED verdict",
                        "synthetic/test reviewer in production context",
                        "single global APPROVED object"],
            "auto_pass_is_not_human_pass": True,
            "human_cannot_override_automatic_fail": True,
        },
        "summary": s.summary,
        "exit_code": 0 if s.summary["all_passed"] else 1,
        "cases": s.cases,
        "limitations": [
            "Frame-measured font size is an estimated glyph height, not a certified font metric.",
            "Contrast is a sRGB grey-proxy estimate against adjacent background pixels, not a certified WCAG audit.",
            "Occlusion coverage only covers DECLARED subject boxes; undeclared content stays a human item.",
            "Tests prove the gate logic on synthetic frames; they do NOT prove any real subtitle defect was fixed.",
        ],
    }
    out = HERE / "subtitle-signoff-tests.json"
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"WROTE {out.name}: {s.summary}")
    if not s.summary["all_passed"]:
        for c in s.cases:
            if not c["passed"]:
                print("FAILED CASE:", c["name"], "expected", c["expected"], "actual", c["actual"])
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
