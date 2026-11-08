#!/usr/bin/env python3
"""WB-VIDEO-004 subtitle quality inspection + per-item human sign-off gate.

What changed versus WB-VIDEO-003/subtitle_checks.py
---------------------------------------------------
1. P0 (ChatGPT review finding): ``evaluate_subtitle_fix`` accepted ONE global
   ``manual_review.verdict = "APPROVED"`` record. The three MANUAL_ITEMS were
   never individually reviewed. Now every item needs its OWN record with its
   own reviewer, reviewed_at, evidence, notes and explicit binding to a frame,
   a time range, a VIDEO version and a SUBTITLE version. Missing / empty /
   synthetic / wrongly-bound records are rejected, never silently approved.

2. Font size: WB-VIDEO-003 read ``font_px`` from renderer parameters and called
   that a PASS. This module keeps three SEPARATE values
   (render-parameter / frame-measured / human-confirmed). Only a real
   frame measurement can produce an automatic PASS; the render parameter has
   decision_weight 0.

3. Contrast: WB-VIDEO-003 used the p95-p5 luma spread of the WHOLE subtitle
   band, which can be dominated by background texture. This module builds a
   text mask from the difference against a no-subtitle reference frame and
   measures text pixels against ADJACENT background pixels (WCAG-style
   ratio). The old spread remains as a diagnostic field only.

4. Occlusion: IoU alone misses a small subject completely inside a large
   subtitle band. This module reports intersection-over-subject,
   intersection-over-subtitle, containment and the legacy IoU, and fails on
   any coverage signal. Undeclared content still requires human review.

Honesty rules
-------------
* Anything a program cannot measure reliably -> ``NEEDS_MANUAL_REVIEW``.
* Automatic PASS is NEVER a human PASS; automatic FAIL can NEVER be
  overridden by a human APPROVED.
* Automatic evidence and human sign-off are stored in two separate structures.
* Synthetic/test reviewers are inadmissible in a production sign-off ledger.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Policy constants
# ---------------------------------------------------------------------------
HORIZONTAL_SAFE_TOP = 0.70
HORIZONTAL_SAFE_BOTTOM = 0.94
VERTICAL_SAFE_TOP = 0.72
VERTICAL_SAFE_BOTTOM = 0.94
VERTICAL_MIDFRAME_BAND = (0.35, 0.65)
MIN_FONT_PX = {"horizontal": 24, "vertical": 32}
MIN_CONTRAST_SPREAD = 55.0            # diagnostic only, NOT a verdict source
MIN_BURN_IN_MAD = 2.0
MIN_TEXT_CONTRAST_RATIO = 4.5         # WCAG AA for normal-size text
MIN_TEXT_LUMA_DELTA = 45.0            # 0..255 absolute luminance difference
MIN_TEXT_MASK_PIXELS = 40
OCCLUSION_IOU_FAIL = 0.02
OCCLUSION_COVERAGE_FAIL = 0.05        # intersection / subject OR / subtitle

MANUAL_ITEMS = [
    "text_content_matches_srt",
    "semantic_readability",
    "occlusion_by_undeclared_content",
]

SIGNOFF_REQUIRED_FIELDS = [
    "reviewer", "reviewed_at", "item_id", "verdict", "evidence", "notes",
]
SIGNOFF_BINDING_FIELDS = [
    "frame_ref", "time_range", "video_version", "subtitle_version",
]
SPEC_BINDING_FIELDS = [
    "frame_id", "review_time_range", "video_version", "subtitle_version",
]

MOCK_REVIEWER_TOKENS = {
    "", "auto", "system", "bot", "ai", "anonymous", "unknown", "default",
    "n/a", "na", "none", "test", "mock", "simulated", "unit_test", "pytest",
    "test_reviewer", "mock_reviewer", "simulated_reviewer", "placeholder",
}
EVIDENCE_PLACEHOLDERS = {
    "", "ok", "pass", "passed", "approved", "yes", "n/a", "na", "none",
    "-", "test", "placeholder", "looks good", "checked",
}
TZ = timezone(timedelta(hours=8))
EARLIEST_VALID_REVIEW = datetime(2020, 1, 1, tzinfo=TZ)


class SignoffError(ValueError):
    """Raised when a sign-off record must not enter a production ledger."""


# ---------------------------------------------------------------------------
# Basic helpers (kept compatible with WB-VIDEO-003)
# ---------------------------------------------------------------------------
def parse_srt(path) -> dict:
    p = Path(path)
    if not p.exists():
        return {"exists": False, "entries": [], "error": "srt_missing"}
    raw = p.read_text(encoding="utf-8", errors="replace")
    blocks = re.split(r"\n\s*\n", raw.strip())
    entries = []
    for b in blocks:
        lines = [x for x in b.splitlines() if x.strip()]
        if not lines:
            continue
        tc = next((x for x in lines if "-->" in x), None)
        if not tc:
            continue
        text = " ".join(x.strip() for x in lines[lines.index(tc) + 1:])
        entries.append({"timecode": tc.strip(), "text": text})
    return {"exists": True, "size_bytes": p.stat().st_size,
            "entry_count": len(entries), "entries": entries,
            "valid": len(entries) > 0 and all(e["text"] for e in entries)}


def _box_overlap(a, b) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    union = aw * ah + bw * bh - inter
    return round(inter / union, 4) if union > 0 else 0.0


def _band_stats(frame_path, box) -> dict:
    """DIAGNOSTIC ONLY. Whole-band luma spread is not a text contrast measure."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return {"available": False, "note": "cv2/numpy unavailable"}
    img = cv2.imread(str(frame_path))
    if img is None:
        return {"available": False, "note": "frame could not be decoded"}
    x, y, w, h = [int(round(v)) for v in box]
    H, W = img.shape[:2]
    x, y = max(0, x), max(0, y)
    w, h = min(w, W - x), min(h, H - y)
    if w <= 0 or h <= 0:
        return {"available": False, "note": "empty subtitle band"}
    gray = cv2.cvtColor(img[y:y + h, x:x + w], cv2.COLOR_BGR2GRAY)
    p5, p95 = np.percentile(gray, [5, 95])
    return {"available": True, "mean_luma": round(float(gray.mean()), 2),
            "p5_luma": round(float(p5), 2), "p95_luma": round(float(p95), 2),
            "contrast_spread": round(float(p95 - p5), 2),
            "std_luma": round(float(gray.std()), 2)}


def _load_frame_pair(frame_path, reference_path):
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None, None, None, "cv2/numpy unavailable"
    a = cv2.imread(str(frame_path))
    b = cv2.imread(str(reference_path)) if reference_path and Path(reference_path).exists() else None
    if a is None:
        return None, None, None, "frame could not be decoded"
    if b is None:
        return a, None, None, "no-subtitle reference missing/undecodable"
    if a.shape != b.shape:
        return a, b, None, "frame and reference have different dimensions"
    return a, b, np, None


def _crop(img, box):
    x, y, w, h = [int(round(v)) for v in box]
    H, W = img.shape[:2]
    x, y = max(0, x), max(0, y)
    w, h = min(w, W - x), min(h, H - y)
    if w <= 0 or h <= 0:
        return None
    return img[y:y + h, x:x + w], (x, y, w, h)


def _burn_in_diff(frame_path, reference_path, box) -> dict:
    a, b, np, err = _load_frame_pair(frame_path, reference_path)
    if err or a is None or b is None:
        return {"available": False, "note": err or "frame pair unavailable"}
    c = _crop(a, box)
    if c is None:
        return {"available": False, "note": "empty subtitle band"}
    (ca, _), (cb, _) = c, _crop(b, box)
    d = np.abs(ca.astype("float32") - cb.astype("float32"))
    mad = float(d.mean())
    return {"available": True, "mean_abs_diff": round(mad, 3),
            "threshold": MIN_BURN_IN_MAD,
            "subtitle_visible_in_frame": mad >= MIN_BURN_IN_MAD}


def detect_subtitle_band(frame_path, reference_path) -> dict:
    """Locate the ACTUAL burned-in subtitle band by pixel difference."""
    a, b, np, err = _load_frame_pair(frame_path, reference_path)
    if err or a is None or b is None:
        return {"available": False, "note": err or "frame pair unavailable"}
    diff = np.abs(a.astype("float32") - b.astype("float32")).mean(axis=2)
    row_mad = diff.mean(axis=1)
    thr = max(6.0, float(row_mad.mean() + 3 * row_mad.std()))
    rows = np.where(row_mad > thr)[0]
    if rows.size == 0:
        return {"available": True, "detected": False,
                "row_threshold": round(thr, 3),
                "max_row_mad": round(float(row_mad.max()), 3),
                "note": "no row shows a significant subtitle-shaped difference"}
    groups, cur = [], [int(rows[0])]
    for r in rows[1:]:
        if int(r) - cur[-1] <= 2:
            cur.append(int(r))
        else:
            groups.append(cur)
            cur = [int(r)]
    groups.append(cur)
    band = max(groups, key=len)
    y0, y1 = band[0], band[-1] + 1
    col_mad = diff[y0:y1].mean(axis=0)
    cols = np.where(col_mad > thr)[0]
    x0, x1 = (int(cols[0]), int(cols[-1]) + 1) if cols.size else (0, a.shape[1])
    return {"available": True, "detected": True,
            "box": [x0, y0, x1 - x0, y1 - y0],
            "box_source": "pixel_difference_vs_no_subtitle_reference",
            "row_threshold": round(thr, 3),
            "max_row_mad": round(float(row_mad.max()), 3),
            "band_row_mad": round(float(row_mad[y0:y1].mean()), 3),
            "band_height_px": y1 - y0,
            "frame_size": [a.shape[1], a.shape[0]]}


# ---------------------------------------------------------------------------
# New automatic measurements added in WB-VIDEO-004
# ---------------------------------------------------------------------------
def _text_mask_from_diff(frame, reference, box, np):
    ca, c = _crop(frame, box)
    cb, _ = _crop(reference, box)
    if ca is None or cb is None or c is None:
        return None, None, None, None
    d = np.abs(ca.astype("float32") - cb.astype("float32")).mean(axis=2)
    mask = (d > 10.0).astype("uint8")
    gray = None
    try:
        import cv2
        gray = cv2.cvtColor(ca, cv2.COLOR_BGR2GRAY)
    except Exception:
        gray = ca.mean(axis=2).astype("uint8")
    return mask, gray, ca, d


def measure_text_contrast(frame_path, reference_path, box) -> dict:
    """Measure TEXT pixels vs ADJACENT BACKGROUND pixels, not band statistics.

    The text mask comes from the pixel difference between the subtitle frame
    and a no-subtitle reference frame. A dilated ring around that mask is used
    as the local background sample. Luminance is an sRGB grey proxy, so this
    is an estimate, not a certified WCAG measurement.
    """
    a, b, np, err = _load_frame_pair(frame_path, reference_path)
    if err or a is None or b is None:
        return {"available": False, "note": err or "frame pair unavailable"}
    mask, gray, _ca, _d = _text_mask_from_diff(a, b, box, np)
    if mask is None:
        return {"available": False, "note": "empty subtitle band"}
    n_text = int(mask.sum())
    if n_text < MIN_TEXT_MASK_PIXELS:
        return {"available": True, "text_pixels": n_text,
                "verdict": "NEEDS_MANUAL_REVIEW",
                "note": "too few text pixels in the difference mask; contrast cannot be measured reliably"}
    try:
        import cv2
        ring = cv2.dilate(mask, np.ones((5, 5), "uint8"), iterations=1) - mask
    except Exception:
        ring = mask * 0
    n_bg = int(ring.sum())
    if n_bg < MIN_TEXT_MASK_PIXELS:
        return {"available": True, "text_pixels": n_text, "background_pixels": n_bg,
                "verdict": "NEEDS_MANUAL_REVIEW",
                "note": "no usable adjacent background sample"}
    t = float(np.median(gray[mask > 0]))
    g = float(np.median(gray[ring > 0]))

    def rel_lum(v: float) -> float:
        s = max(0.0, min(255.0, v)) / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

    hi, lo = max(rel_lum(t), rel_lum(g)), min(rel_lum(t), rel_lum(g))
    ratio = (hi + 0.05) / (lo + 0.05)
    delta = abs(t - g)
    ok = ratio >= MIN_TEXT_CONTRAST_RATIO and delta >= MIN_TEXT_LUMA_DELTA
    return {
        "available": True, "verdict": "PASS" if ok else "FAIL",
        "method": "text_mask_from_frame_difference_vs_adjacent_background_ring",
        "measurement_confidence": "estimate_srgb_gray_proxy_not_certified_wcag",
        "text_pixels": n_text, "background_pixels": n_bg,
        "median_text_luma": round(t, 2), "median_adjacent_background_luma": round(g, 2),
        "contrast_ratio": round(float(ratio), 3),
        "abs_luma_delta": round(float(delta), 2),
        "minimum_contrast_ratio": MIN_TEXT_CONTRAST_RATIO,
        "minimum_abs_luma_delta": MIN_TEXT_LUMA_DELTA,
    }


def measure_font_px_from_frame(frame_path, reference_path, box) -> dict:
    """Estimate glyph height from the longest run of changed pixel rows.

    This is an ESTIMATE of the burned-in glyph bounding height, not the
    renderer's font size and not a ground-truth typographic measurement.
    """
    a, b, np, err = _load_frame_pair(frame_path, reference_path)
    if err or a is None or b is None:
        return {"available": False, "note": err or "frame pair unavailable"}
    mask, _gray, _ca, _d = _text_mask_from_diff(a, b, box, np)
    if mask is None:
        return {"available": False, "note": "empty subtitle band"}
    rows = np.where(mask.sum(axis=1) >= max(2, int(0.01 * mask.shape[1])))[0]
    if rows.size == 0:
        return {"available": True, "verdict": "NEEDS_MANUAL_REVIEW",
                "note": "no text row detected in the difference mask"}
    groups, cur = [], [int(rows[0])]
    for r in rows[1:]:
        if int(r) - cur[-1] <= 2:
            cur.append(int(r))
        else:
            groups.append(cur)
            cur = [int(r)]
    groups.append(cur)
    height = max(len(g) for g in groups)
    return {"available": True, "font_px_measured": height,
            "method": "longest_changed_row_run_in_difference_mask",
            "measurement_confidence": "estimate_glyph_height_not_font_size_truth",
            "text_row_groups": len(groups)}


def occlusion_metrics(subtitle_box, subjects) -> dict:
    """Report several coverage signals; IoU alone misses small occluders."""
    x, y, w, h = subtitle_box
    area_sub = max(1.0, float(w * h))
    pairs = []
    for s in subjects:
        bx, by, bw, bh = s
        ix = max(0, min(x + w, bx + bw) - max(x, bx))
        iy = max(0, min(y + h, by + bh) - max(y, by))
        inter = float(ix * iy)
        area_obj = max(1.0, float(bw * bh))
        pairs.append({
            "box": list(s),
            "intersection_px": inter,
            "iou": _box_overlap(subtitle_box, s),
            "intersection_over_subject": round(inter / area_obj, 4),
            "intersection_over_subtitle": round(inter / area_sub, 4),
            "subject_contained_in_subtitle": bool(inter >= area_obj * 0.999),
        })
    max_iou = max((p["iou"] for p in pairs), default=0.0)
    max_cov_subject = max((p["intersection_over_subject"] for p in pairs), default=0.0)
    max_cov_subtitle = max((p["intersection_over_subtitle"] for p in pairs), default=0.0)
    legacy_would_fail = max_iou > OCCLUSION_IOU_FAIL
    new_fail = (legacy_would_fail or max_cov_subject >= OCCLUSION_COVERAGE_FAIL
                or max_cov_subtitle >= OCCLUSION_COVERAGE_FAIL)
    return {"pairs": pairs, "max_iou": max_iou,
            "max_intersection_over_subject": max_cov_subject,
            "max_intersection_over_subtitle": max_cov_subtitle,
            "legacy_iou_would_pass": not legacy_would_fail,
            "coverage_signal_detected": bool(max_cov_subject >= OCCLUSION_COVERAGE_FAIL
                                             or max_cov_subtitle >= OCCLUSION_COVERAGE_FAIL),
            "verdict": "FAIL" if new_fail else "PASS"}


# ---------------------------------------------------------------------------
# Automatic inspection
# ---------------------------------------------------------------------------
def inspect_subtitle(spec: dict) -> dict:
    """Run all automatic checks. Never auto-PASS a manual-only item."""
    W, H = spec["canvas"]
    x, y, w, h = spec["declared_box"]
    orient = spec.get("orientation", "horizontal")
    if orient not in ("horizontal", "vertical"):
        raise ValueError("orientation must be horizontal or vertical")

    auto: dict[str, dict] = {}
    manual: dict[str, dict] = {}
    frame_p = Path(spec["frame_path"])
    ref = spec.get("reference_frame_path")

    auto["artifact_exists"] = {
        "verdict": "PASS" if frame_p.exists() and frame_p.stat().st_size > 0 else "FAIL",
        "frame_bytes": frame_p.stat().st_size if frame_p.exists() else 0,
        "decision_weight": 0,
        "note": "proves a render was produced; proves NOTHING about subtitle quality",
    }

    srt = parse_srt(spec["srt_path"])
    auto["srt_parse"] = {
        "verdict": "PASS" if srt.get("valid") else "FAIL",
        "exists": srt.get("exists"), "entry_count": srt.get("entry_count", 0),
        "note": "a valid SRT file is necessary but not sufficient",
    }

    within = x >= 0 and y >= 0 and w > 0 and h > 0 and (x + w) <= W and (y + h) <= H
    auto["box_within_canvas"] = {
        "verdict": "PASS" if within else "FAIL",
        "box": [x, y, w, h], "canvas": [W, H],
        "overflow_right": max(0, x + w - W), "overflow_bottom": max(0, y + h - H),
    }

    if orient == "horizontal":
        top, bottom = HORIZONTAL_SAFE_TOP, HORIZONTAL_SAFE_BOTTOM
    else:
        top, bottom = VERTICAL_SAFE_TOP, VERTICAL_SAFE_BOTTOM
    cy = y + h / 2.0
    in_safe = (y >= H * top) and ((y + h) <= H * bottom)
    midframe = orient == "vertical" and (
        H * VERTICAL_MIDFRAME_BAND[0] <= cy <= H * VERTICAL_MIDFRAME_BAND[1])
    auto["safe_area"] = {
        "verdict": "FAIL" if (not in_safe or midframe) else "PASS",
        "orientation": orient,
        "allowed_band_fraction": [top, bottom],
        "box_center_y_fraction": round(cy / H, 4),
        "midframe_defect": bool(midframe),
        "reason": ("vertical subtitle sits in the middle of the frame" if midframe
                   else "subtitle band outside the declared safe area" if not in_safe
                   else "inside safe area"),
    }

    # --- font size: three separate values, only frame measurement can PASS --
    render_fp = spec.get("font_px")
    m = measure_font_px_from_frame(frame_p, ref, (x, y, w, h))
    font_entry = {
        "font_px_render_param": render_fp,
        "render_param_used_for_verdict": False,
        "render_param_decision_weight": 0,
        "font_px_measured": m.get("font_px_measured"),
        "font_px_human_confirmed": None,
        "measurement_method": m.get("method"),
        "measurement_confidence": m.get("measurement_confidence"),
        "measurement_note": m.get("note"),
        "minimum_px": MIN_FONT_PX[orient],
        "three_states_recorded_separately": True,
    }
    if not m.get("available") or m.get("font_px_measured") is None:
        font_entry["verdict"] = "NEEDS_MANUAL_REVIEW"
        font_entry["reason"] = "no reliable frame measurement; renderer parameter is not evidence"
    else:
        font_entry["verdict"] = "PASS" if m["font_px_measured"] >= MIN_FONT_PX[orient] else "FAIL"
        if render_fp is not None and render_fp > 0:
            font_entry["render_vs_measured_discrepancy_pct"] = round(
                abs(render_fp - m["font_px_measured"]) / render_fp * 100, 1)
    auto["font_size"] = font_entry

    # --- contrast: real text-vs-adjacent-background measurement -------------
    stats = _band_stats(frame_p, (x, y, w, h)) if frame_p.exists() else {"available": False}
    c = measure_text_contrast(frame_p, ref, (x, y, w, h))
    contrast_entry = {
        "method": c.get("method"),
        "measurement_confidence": c.get("measurement_confidence"),
        "band_spread_diagnostic_only": stats.get("contrast_spread"),
        "band_spread_used_for_verdict": False,
        "whole_band_spread_is_not_text_contrast": True,
        "minimum_spread_diagnostic_only": MIN_CONTRAST_SPREAD,
        "text_pixels": c.get("text_pixels"),
        "background_pixels": c.get("background_pixels"),
        "median_text_luma": c.get("median_text_luma"),
        "median_adjacent_background_luma": c.get("median_adjacent_background_luma"),
        "contrast_ratio": c.get("contrast_ratio"),
        "abs_luma_delta": c.get("abs_luma_delta"),
        "minimum_contrast_ratio": MIN_TEXT_CONTRAST_RATIO,
    }
    if not c.get("available") or "verdict" not in c:
        contrast_entry["verdict"] = "NEEDS_MANUAL_REVIEW"
        contrast_entry["note"] = c.get("note", "contrast not measurable")
    else:
        contrast_entry["verdict"] = c["verdict"]
        contrast_entry["note"] = c.get("note")
    auto["contrast"] = contrast_entry

    # --- occlusion: multi-signal --------------------------------------------
    subjects = spec.get("subject_boxes") or []
    if not subjects:
        auto["subject_overlap"] = {
            "verdict": "NEEDS_MANUAL_REVIEW",
            "note": "no subject/UI boxes declared; occlusion cannot be ruled out automatically",
        }
    else:
        auto["subject_overlap"] = occlusion_metrics((x, y, w, h), subjects)

    # --- burn-in pixel proof ------------------------------------------------
    if not ref or not Path(ref).exists():
        auto["burned_in_evidence"] = {
            "verdict": "NEEDS_MANUAL_REVIEW",
            "note": "no no-subtitle reference frame; cannot prove the subtitle is really on screen",
        }
    else:
        d = _burn_in_diff(frame_p, ref, (x, y, w, h)) if frame_p.exists() else {"available": False}
        if not d.get("available"):
            auto["burned_in_evidence"] = {"verdict": "NEEDS_MANUAL_REVIEW", "note": d.get("note")}
        else:
            auto["burned_in_evidence"] = {
                "verdict": "PASS" if d["subtitle_visible_in_frame"] else "FAIL",
                **d,
                "note": ("subtitle pixels differ from the no-subtitle reference"
                         if d["subtitle_visible_in_frame"] else
                         "SRT exists but the rendered frame is identical to the no-subtitle frame"),
            }

    for item in MANUAL_ITEMS:
        manual[item] = {
            "verdict": "NEEDS_MANUAL_REVIEW",
            "reason": {
                "text_content_matches_srt": "requires OCR or a human reading the burned-in text",
                "semantic_readability": "legibility / wording / rhythm requires human judgement",
                "occlusion_by_undeclared_content": "undeclared subjects or UI cannot be enumerated reliably",
            }[item],
        }

    auto_failures = [k for k, v in auto.items() if v["verdict"] == "FAIL"]
    auto_manual = [k for k, v in auto.items() if v["verdict"] == "NEEDS_MANUAL_REVIEW"]
    automatic_verdict = ("FAIL" if auto_failures else
                         "NEEDS_MANUAL_REVIEW" if auto_manual else "PASS")
    return {
        "spec": {k: v for k, v in spec.items() if k != "manual_review"},
        "automatic": {"verdict": automatic_verdict, "checks": auto,
                      "failures": auto_failures, "needs_review": auto_manual},
        "manual_review": {"policy": "per_item_signoff_v1", "items": manual,
                          "verdict": "NOT_PERFORMED"},
        "artifact_only_weight": 0,
    }


# ---------------------------------------------------------------------------
# Per-item human sign-off (the P0 fix)
# ---------------------------------------------------------------------------
def _is_synthetic(record: dict) -> tuple[bool, list[str]]:
    reasons = []
    reviewer = str(record.get("reviewer") or "").strip().lower()
    if record.get("test_only") is True:
        reasons.append("test_only_flag_true")
    if str(record.get("review_source") or "").strip().lower() in {"unit_test", "mock", "synthetic", "simulation"}:
        reasons.append("review_source_is_synthetic")
    if reviewer in MOCK_REVIEWER_TOKENS:
        reasons.append("reviewer_is_mock_or_anonymous")
    if any(tok in reviewer for tok in ("test_", "mock", "simulat", "dummy", "fake")):
        reasons.append("reviewer_name_contains_synthetic_token")
    return bool(reasons), reasons


def _validate_evidence(value) -> tuple[bool, str]:
    if isinstance(value, dict):
        text = " ".join(str(v) for v in value.values())
        if not value.get("observation"):
            return False, "evidence dict must contain an 'observation' field"
    else:
        text = str(value or "")
    t = text.strip()
    if len(t) < 12:
        return False, "evidence text shorter than 12 characters"
    if t.lower() in EVIDENCE_PLACEHOLDERS:
        return False, "evidence is a placeholder word"
    return True, "substantive evidence text"


def _validate_reviewed_at(value) -> tuple[bool, str]:
    if not value or not isinstance(value, str):
        return False, "reviewed_at missing or not a string"
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return False, "reviewed_at is not valid ISO-8601"
    if dt.tzinfo is None:
        return False, "reviewed_at has no timezone"
    now = datetime.now(TZ)
    if dt > now + timedelta(minutes=5):
        return False, "reviewed_at is in the future"
    if dt < EARLIEST_VALID_REVIEW:
        return False, "reviewed_at implausibly old"
    return True, dt.isoformat(timespec="seconds")


def validate_signoff_record(record, spec: dict, context: str = "production") -> dict:
    """Validate ONE item's review record. Fail-closed on anything suspicious."""
    errors: list[str] = []
    if not isinstance(record, dict):
        return {"valid": False, "verdict": "INVALID", "errors": ["record is not an object"],
                "item_id": None, "synthetic": False}
    item_id = record.get("item_id")

    for f in SIGNOFF_REQUIRED_FIELDS:
        if f not in record:
            errors.append(f"missing_required_field:{f}")
    for f in SIGNOFF_BINDING_FIELDS:
        if f not in record:
            errors.append(f"missing_binding_field:{f}")

    reviewer = str(record.get("reviewer") or "").strip()
    if not reviewer:
        errors.append("empty_reviewer")
    elif len(reviewer) < 3:
        errors.append("reviewer_too_short")

    ok_ev, ev_note = _validate_evidence(record.get("evidence"))
    if not ok_ev:
        errors.append(f"invalid_evidence:{ev_note}")

    ok_time, time_note = _validate_reviewed_at(record.get("reviewed_at"))
    if not ok_time:
        errors.append(f"invalid_reviewed_at:{time_note}")

    if item_id not in MANUAL_ITEMS:
        errors.append(f"unknown_or_missing_item_id:{item_id}")

    if str(record.get("verdict") or "").upper() != "APPROVED":
        errors.append("verdict_is_not_APPROVED")

    # --- explicit frame / time / video version / subtitle version binding ---
    binding = {}
    for f in SPEC_BINDING_FIELDS:
        if f not in spec or spec.get(f) in (None, ""):
            errors.append(f"spec_missing_binding_anchor:{f}")
    if "frame_ref" in record and "frame_id" in spec:
        binding["frame_ref_matches"] = str(record["frame_ref"]) == str(spec["frame_id"])
        if not binding["frame_ref_matches"]:
            errors.append("frame_ref_does_not_match_specified_frame")
    for rf, sf in (("video_version", "video_version"), ("subtitle_version", "subtitle_version")):
        if rf in record and sf in spec:
            binding[f"{rf}_matches"] = str(record[rf]) == str(spec[sf])
            if not binding[f"{rf}_matches"]:
                errors.append(f"{rf}_does_not_match_spec")
    tr = record.get("time_range")
    allowed = spec.get("review_time_range")
    if isinstance(tr, (list, tuple)) and len(tr) == 2:
        try:
            a, b = float(tr[0]), float(tr[1])
            binding["time_range"] = [a, b]
            if not (0 <= a < b):
                errors.append("time_range_not_increasing")
            if isinstance(allowed, (list, tuple)) and len(allowed) == 2:
                lo, hi = float(allowed[0]), float(allowed[1])
                binding["time_range_within_review_window"] = (a >= lo - 0.001 and b <= hi + 0.001)
                if not binding["time_range_within_review_window"]:
                    errors.append("time_range_outside_specified_review_window")
        except (TypeError, ValueError):
            errors.append("time_range_not_numeric")
    else:
        errors.append("time_range_missing_or_malformed")

    synthetic, synthetic_reasons = _is_synthetic(record)
    if context == "production" and synthetic:
        errors.append("synthetic_test_reviewer_not_admissible_in_production:" +
                      ",".join(synthetic_reasons))

    valid = not errors and str(record.get("verdict") or "").upper() == "APPROVED"
    return {
        "valid": valid,
        "verdict": "APPROVED" if valid else "REJECTED",
        "item_id": item_id,
        "errors": errors,
        "synthetic": synthetic,
        "synthetic_reasons": synthetic_reasons,
        "binding": binding,
        "reviewer": reviewer if valid else None,
        "reviewed_at": record.get("reviewed_at") if valid else None,
        "evidence": record.get("evidence") if valid else None,
        "notes": record.get("notes"),
        "record_sha256": hashlib.sha256(
            json.dumps(record, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
        ).hexdigest(),
    }


def verify_signoff_set(spec: dict, records, context: str = "production") -> dict:
    """Validate the WHOLE set of per-item records. All three must be valid."""
    if isinstance(records, dict):
        # Reject the WB-VIDEO-003 style single global APPROVED object.
        items_list = []
        extraneous = [{"record": records, "reason": "legacy_global_signoff_object_has_no_per_item_records"}]
    elif isinstance(records, list):
        items_list = list(records)
        extraneous = []
    else:
        items_list, extraneous = [], []

    by_item: dict[str, list] = {k: [] for k in MANUAL_ITEMS}
    for r in items_list:
        if isinstance(r, dict) and r.get("item_id") in MANUAL_ITEMS:
            by_item[r["item_id"]].append(r)
        else:
            extraneous.append({"record": r, "reason": "unknown_item_id_or_not_an_object"})

    items = {}
    for item in MANUAL_ITEMS:
        found = by_item[item]
        if len(found) == 0:
            items[item] = {"verdict": "NOT_REVIEWED", "valid": False,
                           "errors": ["no_review_record_for_this_item"],
                           "record_sha256": None}
        elif len(found) > 1:
            items[item] = {"verdict": "REJECTED", "valid": False,
                           "errors": [f"duplicate_records_for_item:{len(found)}"],
                           "record_sha256": None}
        else:
            v = validate_signoff_record(found[0], spec, context)
            v["independent_status"] = True
            v["independent_evidence"] = v.get("evidence")
            items[item] = v

    approved = [k for k, v in items.items() if v["valid"]]
    missing = [k for k, v in items.items() if not v["valid"]]
    all_ok = len(approved) == len(MANUAL_ITEMS)
    canonical = [items[k]["record_sha256"] for k in MANUAL_ITEMS if items[k].get("record_sha256")]
    signoff_hash = hashlib.sha256("|".join(canonical).encode("utf-8")).hexdigest() if all_ok else None
    binding_valid = all(
        all(v for k, v in items[item].get("binding", {}).items() if k.endswith("_matches"))
        for item in MANUAL_ITEMS
    ) and all_ok
    synthetic_records = sum(1 for v in items.values() if v.get("synthetic"))

    return {
        "policy": "per_item_signoff_v1",
        "context": context,
        "required_items": list(MANUAL_ITEMS),
        "items": items,
        "approved_items": approved,
        "missing_or_invalid_items": missing,
        "all_items_approved": all_ok,
        "extraneous_records": extraneous,
        "verdict": "APPROVED" if all_ok else ("REJECTED" if any(
            items[k]["verdict"] == "REJECTED" for k in MANUAL_ITEMS) else "NOT_PERFORMED"),
        "signoff_integrity": {
            "signoff_hash": signoff_hash,
            "binding_valid": binding_valid,
            "synthetic_records": synthetic_records,
            "production_admissible": bool(all_ok and context == "production" and synthetic_records == 0),
            "automatic_and_manual_recorded_separately": True,
        },
    }


def append_production_signoff(ledger_path, spec: dict, records) -> dict:
    """Write validated per-item sign-off to a production JSONL ledger.

    Synthetic/test reviewers are rejected here as well: a unit-test reviewer
    must never enter a real production sign-off record.
    """
    result = verify_signoff_set(spec, records, context="production")
    if not result["all_items_approved"] or not result["signoff_integrity"]["production_admissible"]:
        raise SignoffError("production sign-off refused: " + json.dumps(
            {"missing_or_invalid_items": result["missing_or_invalid_items"],
             "synthetic_records": result["signoff_integrity"]["synthetic_records"]},
            ensure_ascii=False))
    p = Path(ledger_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps({
        "written_at": datetime.now(TZ).isoformat(timespec="seconds"),
        "video_version": spec.get("video_version"),
        "subtitle_version": spec.get("subtitle_version"),
        "frame_id": spec.get("frame_id"),
        "signoff_hash": result["signoff_integrity"]["signoff_hash"],
        "items": {k: {"reviewer": result["items"][k]["reviewer"],
                      "reviewed_at": result["items"][k]["reviewed_at"],
                      "evidence": result["items"][k]["evidence"],
                      "record_sha256": result["items"][k]["record_sha256"]}
                  for k in MANUAL_ITEMS},
    }, ensure_ascii=False, sort_keys=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    return {"written": True, "lines_appended": 1, "signoff_hash":
            result["signoff_integrity"]["signoff_hash"], "ledger": "production"}


def evaluate_subtitle_fix(spec: dict, context: str | None = None) -> dict:
    """Decide whether a subtitle defect may be marked FIXED.

    FIXED requires ALL of: no automatic FAIL, positive burn-in pixel proof, a
    produced render, a FRAME-MEASURED font size PASS, a real text-vs-background
    contrast PASS, and THREE individually validated human sign-off records
    bound to the exact frame / time range / video version / subtitle version.
    """
    report = inspect_subtitle(spec)
    supplied = spec.get("manual_review") or {}
    ctx = context or supplied.get("context") or "production"
    records = supplied.get("items")
    review = verify_signoff_set(spec, records, context=ctx)
    report["manual_review"] = review

    checks = report["automatic"]["checks"]
    auto_fail = report["automatic"]["verdict"] == "FAIL"
    burn_ok = checks["burned_in_evidence"]["verdict"] == "PASS"
    artifact_ok = checks["artifact_exists"]["verdict"] == "PASS"
    font_ok = checks["font_size"]["verdict"] == "PASS"
    contrast_ok = checks["contrast"]["verdict"] == "PASS"
    human_ok = review["all_items_approved"] and review["signoff_integrity"]["binding_valid"]

    prerequisites = {
        "no_automatic_failure": not auto_fail,
        "burned_in_pixel_proof": burn_ok,
        "render_produced": artifact_ok,
        "font_size_frame_measured_pass": font_ok,
        "text_contrast_measured_pass": contrast_ok,
        "all_three_manual_items_individually_approved": human_ok,
        "signoff_binding_valid": review["signoff_integrity"]["binding_valid"],
    }
    can_mark_fixed = all(prerequisites.values())

    if auto_fail:
        fix_result = "STILL_FAILING"
    elif not human_ok or not can_mark_fixed:
        fix_result = "NEEDS_MANUAL_REVIEW"
    else:
        fix_result = "FIXED"

    report.update({
        "can_mark_fixed": can_mark_fixed,
        "fix_result": fix_result,
        "prerequisites": prerequisites,
        "decision_rule": (
            "FIXED requires: no automatic FAIL + burned-in pixel proof + produced render "
            "+ FRAME-MEASURED font PASS + measured text/background contrast PASS "
            "+ 3 independent per-item human APPROVED records, each with a named reviewer, "
            "timestamp, substantive evidence, and a matching frame, time range, video "
            "version and subtitle version. Automatic PASS is NOT a human PASS and a human "
            "APPROVED cannot override an automatic FAIL. artifact_exists decision_weight=0."),
        "automatic_and_manual_recorded_separately": True,
        "auto_pass_is_not_human_pass": True,
        "human_cannot_override_automatic_fail": True,
        "unverified_items": review["missing_or_invalid_items"],
        "font_size_states": {
            "render_parameter": checks["font_size"].get("font_px_render_param"),
            "frame_measured": checks["font_size"].get("font_px_measured"),
            "human_confirmed": None,
            "note": "human_confirmed is populated only by a real production sign-off record, never by a test",
        },
    })
    return report


def legacy_d004_verdict(render_path) -> dict:
    """Reproduce the WB-VIDEO-002 defective decision, for before/after evidence ONLY."""
    p = Path(render_path)
    fixed = bool(p.exists() and p.stat().st_size > 0)
    return {
        "legacy_expression": "bool(v2.exists() and v2.stat().st_size > 0)",
        "file_exists": p.exists(),
        "size_bytes": p.stat().st_size if p.exists() else 0,
        "legacy_result": "FIXED" if fixed else "STILL_FAILING",
        "warning": "This is the DEFECTIVE behaviour; never use it as a decision.",
    }


def legacy_wb003_signoff_gate(review: dict) -> dict:
    """Reproduce WB-VIDEO-003's GLOBAL sign-off gate, for before/after evidence.

    Source: WB-VIDEO-003/subtitle_checks.py lines 319-320::

        signed = bool(review.get("verdict") == "APPROVED" and review.get("reviewer")
                      and review.get("evidence"))

    One global APPROVED object was enough; the three MANUAL_ITEMS were never
    checked individually.
    """
    signed = bool(review.get("verdict") == "APPROVED" and review.get("reviewer")
                  and review.get("evidence"))
    return {
        "source": "WB-VIDEO-003/subtitle_checks.py:319-320",
        "input": review,
        "signed_off": signed,
        "per_item_records_checked": 0,
        "warning": "This is the DEFECTIVE behaviour; reproduced for evidence only.",
    }
