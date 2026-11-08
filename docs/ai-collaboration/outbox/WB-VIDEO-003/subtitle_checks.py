"""WB-VIDEO-003 subtitle quality inspection (P0-2 fix).

P0-2 defect that is fixed here
--------------------------------
WB-VIDEO-002/rework.py resolved defect D004 with::

    fixed = bool(v2.exists() and v2.stat().st_size > 0)

i.e. file existence was treated as proof that the subtitle was correctly
positioned, legible and unobstructed. It is not.

What this module does instead
-----------------------------
* ``artifact_exists`` is recorded as EVIDENCE OF PRODUCTION ONLY and is given
  ZERO weight in the fix decision.
* Automatic checks: canvas bounds, horizontal/vertical subtitle safe area,
  font size, local contrast, overlap with declared subject/UI boxes, and a
  pixel-level burn-in proof (subtitle frame vs. a NO-SUBTITLE reference frame).
* Anything a program cannot reliably decide (whether the text actually says
  the right thing, semantic readability, occlusion by undeclared content) is
  recorded as ``NEEDS_MANUAL_REVIEW`` and NEVER auto-PASSED.
* A defect may be marked ``FIXED`` only when every automatic check passes AND
  every manual item is explicitly signed off by a named reviewer with evidence.
  Automatic results and the human review are stored in SEPARATE fields.
"""
from __future__ import annotations

import re
from pathlib import Path

# Safe-area policy (fraction of frame height).
HORIZONTAL_SAFE_TOP = 0.70
HORIZONTAL_SAFE_BOTTOM = 0.94
VERTICAL_SAFE_TOP = 0.72
VERTICAL_SAFE_BOTTOM = 0.94
VERTICAL_MIDFRAME_BAND = (0.35, 0.65)   # a subtitle centred here is a defect
MIN_FONT_PX = {"horizontal": 24, "vertical": 32}
MIN_CONTRAST_SPREAD = 55.0              # p95-p5 luma spread inside the subtitle band
MIN_BURN_IN_MAD = 2.0                  # mean abs pixel diff vs no-subtitle reference

MANUAL_ITEMS = [
    "text_content_matches_srt",       # needs OCR / human reading
    "semantic_readability",           # needs a human judgement
    "occlusion_by_undeclared_content" # subject/UI boxes may be incomplete
]


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


def _burn_in_diff(frame_path, reference_path, box) -> dict:
    try:
        import cv2
        import numpy as np
    except ImportError:
        return {"available": False, "note": "cv2/numpy unavailable"}
    a, b = cv2.imread(str(frame_path)), cv2.imread(str(reference_path))
    if a is None or b is None:
        return {"available": False, "note": "frame or reference missing/undecodable"}
    if a.shape != b.shape:
        return {"available": False, "note": "frame and reference have different dimensions"}
    x, y, w, h = [int(round(v)) for v in box]
    H, W = a.shape[:2]
    x, y = max(0, x), max(0, y)
    w, h = min(w, W - x), min(h, H - y)
    if w <= 0 or h <= 0:
        return {"available": False, "note": "empty subtitle band"}
    d = np.abs(a[y:y + h, x:x + w].astype("float32") -
               b[y:y + h, x:x + w].astype("float32"))
    mad = float(d.mean())
    return {"available": True, "mean_abs_diff": round(mad, 3),
            "threshold": MIN_BURN_IN_MAD,
            "subtitle_visible_in_frame": mad >= MIN_BURN_IN_MAD}


def detect_subtitle_band(frame_path, reference_path) -> dict:
    """Locate the ACTUAL burned-in subtitle band by pixel difference.

    This avoids guessing the subtitle geometry from renderer parameters: the
    box used by inspect_subtitle can be derived from real frame evidence.
    """
    try:
        import cv2
        import numpy as np
    except ImportError:
        return {"available": False, "note": "cv2/numpy unavailable"}
    a, b = cv2.imread(str(frame_path)), cv2.imread(str(reference_path))
    if a is None or b is None:
        return {"available": False, "note": "frame or reference missing/undecodable"}
    if a.shape != b.shape:
        return {"available": False, "note": "frame and reference have different dimensions"}
    diff = np.abs(a.astype("float32") - b.astype("float32")).mean(axis=2)
    row_mad = diff.mean(axis=1)
    thr = max(6.0, float(row_mad.mean() + 3 * row_mad.std()))
    rows = np.where(row_mad > thr)[0]
    if rows.size == 0:
        return {"available": True, "detected": False,
                "row_threshold": round(thr, 3),
                "max_row_mad": round(float(row_mad.max()), 3),
                "note": "no row shows a significant subtitle-shaped difference"}
    # longest consecutive run of differing rows
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


def inspect_subtitle(spec: dict) -> dict:
    """Run all automatic subtitle checks. Never auto-PASS a manual-only item."""
    W, H = spec["canvas"]
    x, y, w, h = spec["declared_box"]
    orient = spec.get("orientation", "horizontal")
    if orient not in ("horizontal", "vertical"):
        raise ValueError("orientation must be horizontal or vertical")

    auto: dict[str, dict] = {}
    manual: dict[str, dict] = {}

    # --- artifact existence: EVIDENCE ONLY, zero decision weight ------------
    frame_p = Path(spec["frame_path"])
    auto["artifact_exists"] = {
        "verdict": "PASS" if frame_p.exists() and frame_p.stat().st_size > 0 else "FAIL",
        "frame_bytes": frame_p.stat().st_size if frame_p.exists() else 0,
        "decision_weight": 0,
        "note": "proves a render was produced; proves NOTHING about subtitle quality",
    }

    # --- subtitle file content ---------------------------------------------
    srt = parse_srt(spec["srt_path"])
    auto["srt_parse"] = {
        "verdict": "PASS" if srt.get("valid") else "FAIL",
        "exists": srt.get("exists"), "entry_count": srt.get("entry_count", 0),
        "note": "a valid SRT file is necessary but not sufficient",
    }

    # --- canvas bounds ------------------------------------------------------
    within = x >= 0 and y >= 0 and w > 0 and h > 0 and (x + w) <= W and (y + h) <= H
    auto["box_within_canvas"] = {
        "verdict": "PASS" if within else "FAIL",
        "box": [x, y, w, h], "canvas": [W, H],
        "overflow_right": max(0, x + w - W), "overflow_bottom": max(0, y + h - H),
    }

    # --- safe area ----------------------------------------------------------
    if orient == "horizontal":
        top, bottom = HORIZONTAL_SAFE_TOP, HORIZONTAL_SAFE_BOTTOM
    else:
        top, bottom = VERTICAL_SAFE_TOP, VERTICAL_SAFE_BOTTOM
    cy = y + h / 2.0
    in_safe = (y >= H * top) and ((y + h) <= H * bottom)
    midframe = orient == "vertical" and (H * VERTICAL_MIDFRAME_BAND[0] <= cy <= H * VERTICAL_MIDFRAME_BAND[1])
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

    # --- font size ----------------------------------------------------------
    fp = spec.get("font_px")
    if fp is None:
        auto["font_size"] = {"verdict": "NEEDS_MANUAL_REVIEW", "note": "font_px not supplied"}
    else:
        need = MIN_FONT_PX[orient]
        auto["font_size"] = {"verdict": "PASS" if fp >= need else "FAIL",
                             "font_px": fp, "minimum_px": need}

    # --- contrast -----------------------------------------------------------
    stats = _band_stats(frame_p, (x, y, w, h)) if frame_p.exists() else {"available": False}
    if not stats.get("available"):
        auto["contrast"] = {"verdict": "NEEDS_MANUAL_REVIEW", "note": stats.get("note", "no frame")}
    else:
        auto["contrast"] = {"verdict": "PASS" if stats["contrast_spread"] >= MIN_CONTRAST_SPREAD else "FAIL",
                            **stats, "minimum_spread": MIN_CONTRAST_SPREAD}

    # --- occlusion by declared subject / UI boxes ---------------------------
    subjects = spec.get("subject_boxes") or []
    if not subjects:
        auto["subject_overlap"] = {
            "verdict": "NEEDS_MANUAL_REVIEW",
            "note": "no subject/UI boxes declared; occlusion cannot be ruled out automatically",
        }
    else:
        overlaps = [{"box": list(s), "iou": _box_overlap((x, y, w, h), s)} for s in subjects]
        worst = max(o["iou"] for o in overlaps)
        auto["subject_overlap"] = {"verdict": "FAIL" if worst > 0.02 else "PASS",
                                   "pairs": overlaps, "max_iou": worst}

    # --- burn-in pixel proof ------------------------------------------------
    ref = spec.get("reference_frame_path")
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

    # --- items a program cannot decide --------------------------------------
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
    if auto_failures:
        automatic_verdict = "FAIL"
    elif auto_manual:
        automatic_verdict = "NEEDS_MANUAL_REVIEW"
    else:
        automatic_verdict = "PASS"

    return {
        "spec": {k: v for k, v in spec.items() if k != "manual_review"},
        "automatic": {"verdict": automatic_verdict, "checks": auto,
                      "failures": auto_failures, "needs_review": auto_manual},
        "manual_review": {"items": manual, "signed_off": False, "reviewer": None,
                          "evidence": None, "verdict": "NOT_PERFORMED"},
        "artifact_only_weight": 0,
    }


def evaluate_subtitle_fix(spec: dict) -> dict:
    """Decide whether a subtitle defect may be marked FIXED.

    File existence is NEVER sufficient. Both automatic evidence and an
    explicit, named human sign-off are required.
    """
    report = inspect_subtitle(spec)
    review = spec.get("manual_review") or {}
    signed = bool(review.get("verdict") == "APPROVED" and review.get("reviewer")
                  and review.get("evidence"))
    report["manual_review"] = {
        "items": report["manual_review"]["items"],
        "signed_off": signed,
        "reviewer": review.get("reviewer") if signed else None,
        "evidence": review.get("evidence") if signed else None,
        "verdict": "APPROVED" if signed else "NOT_PERFORMED",
        "note": ("separate human review record; automatic checks are stored above independently"
                 if signed else "no human sign-off: defect MUST NOT be marked FIXED"),
    }
    auto = report["automatic"]["verdict"]
    burn_ok = report["automatic"]["checks"]["burned_in_evidence"]["verdict"] == "PASS"
    can_mark_fixed = (auto != "FAIL") and signed and burn_ok and \
        report["automatic"]["checks"]["artifact_exists"]["verdict"] == "PASS"

    if auto == "FAIL":
        fix_result = "STILL_FAILING"
    elif not signed:
        fix_result = "NEEDS_MANUAL_REVIEW"
    elif not can_mark_fixed:
        fix_result = "NEEDS_MANUAL_REVIEW"
    else:
        fix_result = "FIXED"

    report.update({
        "can_mark_fixed": can_mark_fixed,
        "fix_result": fix_result,
        "decision_rule": (
            "FIXED requires: no automatic FAIL + explicit named human APPROVED sign-off "
            "+ positive burn-in pixel proof + produced render. "
            "File existence alone has decision_weight=0."),
        "automatic_and_manual_recorded_separately": True,
        "unverified_items": [k for k, v in report["manual_review"]["items"].items()
                             if v["verdict"] == "NEEDS_MANUAL_REVIEW"],
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
