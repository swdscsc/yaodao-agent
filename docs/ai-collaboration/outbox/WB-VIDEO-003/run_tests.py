#!/usr/bin/env python3
"""WB-VIDEO-003 automated regression tests for P0-1 and P0-2.

All test media is generated locally with FFmpeg / PIL. No hosted quota, no
paid service, no network call, no modification of existing user projects.

Outputs ``test-results.json`` (committed) plus small evidence thumbnails.
Machine-specific absolute paths are replaced with placeholders.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent
sys.path.insert(0, str(HERE))

import qa as strict_qa  # noqa: E402
from subtitle_checks import (  # noqa: E402
    detect_subtitle_band, evaluate_subtitle_fix, legacy_d004_verdict,
)

TZ = timezone(timedelta(hours=8))
NOW = lambda: datetime.now(TZ).isoformat(timespec="seconds")  # noqa: E731


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def run(cmd, timeout=300):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return p.returncode, p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:
        return -1, "", f"{type(e).__name__}: {e}"


class Suite:
    def __init__(self):
        self.cases = []

    def add(self, group, name, expected, actual, passed, evidence):
        self.cases.append({
            "group": group, "name": name, "expected": expected,
            "actual": actual, "passed": bool(passed),
            "evidence": evidence,
        })

    @property
    def summary(self):
        return {"total": len(self.cases),
                "passed": sum(1 for c in self.cases if c["passed"]),
                "failed": sum(1 for c in self.cases if not c["passed"]),
                "all_passed": all(c["passed"] for c in self.cases)}


# ---------------------------------------------------------------------------
# Test media generation (FFmpeg, local, zero quota)
# ---------------------------------------------------------------------------

def make_video(ffmpeg, path: Path, duration: float, vf: str, freq: int = 440) -> dict:
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error",
           "-f", "lavfi", "-i", vf,
           "-f", "lavfi", "-i", f"sine=frequency={freq}:sample_rate=48000:duration={duration}",
           "-t", f"{duration:.3f}", "-c:v", "libx264", "-preset", "ultrafast",
           "-pix_fmt", "yuv420p", "-r", "30", "-af", "volume=0.25",
           "-c:a", "aac", "-ar", "48000", "-ac", "2", "-y", str(path)]
    rc, _, err = run(cmd)
    return {"ok": rc == 0 and path.exists() and path.stat().st_size > 0,
            "stderr": err[-250:], "bytes": path.stat().st_size if path.exists() else 0,
            "vf": vf, "duration": duration}


def make_freeze_video(ffmpeg, path: Path, dyn_duration: float, first: int,
                      last: int, audio_duration: float, intro: float | None = None) -> dict:
    """Build a real mid-clip freeze using freezeframes (2 video inputs).

    Input 0 = dynamic source, input 1 = replacement (still) frame source,
    input 2 = audio, input 3 (optional) = static intro card which is
    concatenated in front. ``replace=0`` takes frame 0 of input 1.
    """
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error",
           "-f", "lavfi", "-i",
           f"testsrc2=size=320x180:rate=30:duration={dyn_duration}",
           "-f", "lavfi", "-i",
           f"color=c=0x2F6FA8:s=320x180:r=30:duration={dyn_duration}",
           "-f", "lavfi", "-i",
           f"sine=frequency=440:sample_rate=48000:duration={audio_duration}"]
    fc = f"[0:v][1:v]freezeframes=first={first}:last={last}:replace=0[v]"
    vmap = "[v]"
    if intro:
        cmd += ["-f", "lavfi", "-i",
                f"color=c=0x2F6FA8:s=320x180:r=30:duration={intro}"]
        fc += ";[3:v][v]concat=n=2:v=1:a=0[outv]"
        vmap = "[outv]"
    cmd += ["-filter_complex", fc, "-map", vmap, "-map", "2:a",
            "-t", f"{audio_duration:.3f}", "-c:v", "libx264", "-preset", "ultrafast",
            "-pix_fmt", "yuv420p", "-r", "30", "-af", "volume=0.25",
            "-c:a", "aac", "-ar", "48000", "-ac", "2", "-y", str(path)]
    rc, _, err = run(cmd)
    return {"ok": rc == 0 and path.exists() and path.stat().st_size > 0,
            "stderr": err[-250:], "bytes": path.stat().st_size if path.exists() else 0,
            "duration": audio_duration, "freeze_frames": [first, last],
            "static_intro_seconds": intro}


def make_two_source_video(ffmpeg, path: Path, dur_a: float, dur_b: float,
                          src_a: str, src_b: str, freq: int = 440) -> dict:
    total = dur_a + dur_b
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error",
           "-f", "lavfi", "-i", src_a,
           "-f", "lavfi", "-i", src_b,
           "-f", "lavfi", "-i", f"sine=frequency={freq}:sample_rate=48000:duration={total}",
           "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
           "-map", "[v]", "-map", "2:a", "-t", f"{total:.3f}",
           "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
           "-r", "30", "-af", "volume=0.25",
           "-c:a", "aac", "-ar", "48000", "-ac", "2", "-y", str(path)]
    rc, _, err = run(cmd)
    return {"ok": rc == 0 and path.exists() and path.stat().st_size > 0,
            "stderr": err[-250:], "bytes": path.stat().st_size if path.exists() else 0,
            "duration": total}


def make_frame_pair(path_frame: Path, path_ref: Path, size, box, *,
                    draw_subtitle=True, subject=None, vertical=False) -> dict:
    from PIL import Image, ImageDraw
    W, H = size
    bg = (38, 52, 78)
    a = Image.new("RGB", size, bg)
    b = Image.new("RGB", size, bg)
    da, db = ImageDraw.Draw(a), ImageDraw.Draw(b)
    # a visually distinct "subject" in the upper half (never overlapping a
    # bottom subtitle band) so the picture is not a flat colour
    for d in (da, db):
        d.rectangle([int(W * 0.18), int(H * 0.12), int(W * 0.82), int(H * 0.55)],
                    fill=(196, 214, 238))
        d.rectangle([int(W * 0.24), int(H * 0.18), int(W * 0.76), int(H * 0.48)],
                    fill=(86, 124, 168))
    if subject:
        pass  # subject boxes are metadata for the overlap check, not drawn
    x, y, w, h = box
    if draw_subtitle:
        da.rectangle([x, y, x + w, y + h], fill=(12, 14, 20))
        # white "glyph" bars -> strong local contrast, mimics burned-in text
        n = 6
        for i in range(n):
            bx = x + int(w * (0.06 + i * 0.155))
            da.rectangle([bx, y + int(h * 0.28), bx + int(w * 0.10), y + int(h * 0.72)],
                         fill=(250, 250, 250))
    else:
        da.rectangle([x, y, x + w, y + h], fill=bg)
    a.save(path_frame, quality=88)
    b.save(path_ref, quality=88)
    return {"frame": path_frame.name, "reference": path_ref.name,
            "size": list(size), "box": list(box), "draw_subtitle": draw_subtitle}


def make_srt(path: Path, text="药到 AI 用药管家 · 测试字幕") -> None:
    path.write_text(
        "1\n00:00:00,500 --> 00:00:03,000\n" + text + "\n\n"
        "2\n00:00:03,000 --> 00:00:05,500\n每日用药提醒 · 演示文本\n",
        encoding="utf-8")


# ---------------------------------------------------------------------------
# P0-1 tests
# ---------------------------------------------------------------------------

def p0_1_tests(suite: Suite, ffmpeg, ffprobe, work: Path, legacy_qa) -> dict:
    media = {}
    v_dyn = work / "dynamic_ok.mp4"
    media["dynamic_ok"] = make_video(ffmpeg, v_dyn, 4.0,
                                     "testsrc2=size=320x180:rate=30:duration=4")
    v_mid = work / "dynamic_mid_freeze.mp4"
    media["dynamic_mid_freeze"] = make_freeze_video(
        ffmpeg, v_mid, 5.0, first=45, last=105, audio_duration=5.0)
    v_intro = work / "static_intro_dynamic.mp4"
    media["static_intro_dynamic"] = make_two_source_video(
        ffmpeg, v_intro, 1.5, 3.5,
        "color=c=0x2F6FA8:s=320x180:r=30:d=1.5",
        "testsrc2=size=320x180:rate=30:d=3.5")
    v_intro_freeze = work / "static_intro_then_freeze.mp4"
    media["static_intro_then_freeze"] = make_freeze_video(
        ffmpeg, v_intro_freeze, 4.5, first=45, last=134,
        audio_duration=6.0, intro=1.5)

    WHITELIST_INTRO = [{"start": 0.0, "end": 1.5,
                        "reason": "confirmed static intro title card"}]

    def qa(path, **kw):
        return strict_qa.qa_media(ffmpeg, ffprobe, path, **kw)

    # T1 normal dynamic video: no freeze, no whitelist -> PASS
    r1 = qa(v_dyn)
    suite.add("P0-1", "normal_dynamic_video_no_freeze", "PASS / frozen_frame=PASS",
              f"{r1['verdict']} / {r1['checks']['frozen_frame']}",
              r1["verdict"] == "PASS" and r1["checks"]["frozen_frame"] == "PASS",
              {"freeze_intervals": r1["freeze"]["intervals"],
               "problems": r1["problems"]})

    # T2 dynamic video with a freeze in the middle -> FAIL with exact interval
    r2 = qa(v_mid)
    ev2 = r2["freeze_policy"]["evaluated_intervals"]
    suite.add("P0-1", "dynamic_video_mid_freeze_detected", "FAIL + frozen_frames_outside_whitelist",
              f"{r2['verdict']} / {r2['problems']}",
              r2["verdict"] == "FAIL" and "frozen_frames_outside_whitelist" in r2["problems"]
              and len(ev2) > 0 and all(x["decision"] == "FAIL" for x in ev2),
              {"evaluated_intervals": ev2,
               "raw_intervals": r2["freeze_policy"]["raw_intervals"],
               "dynamic_footage_always_checked": r2["freeze_policy"]["dynamic_footage_always_checked"]})

    # T3 legal static intro with a matching whitelist -> allowed, PASS
    r3 = qa(v_intro, static_intervals=WHITELIST_INTRO)
    ev3 = r3["freeze_policy"]["evaluated_intervals"]
    suite.add("P0-1", "legal_static_intro_whitelisted", "PASS_ALLOWED_STATIC / verdict=PASS",
              f"{r3['checks']['frozen_frame']} / {r3['verdict']}",
              r3["verdict"] == "PASS" and r3["checks"]["frozen_frame"] == "PASS_ALLOWED_STATIC"
              and ev3 and all(x["decision"] == "ALLOWED_STATIC" for x in ev3),
              {"whitelist": r3["freeze_policy"]["whitelist"],
               "evaluated_intervals": ev3,
               "coverage": r3["freeze_policy"]["whitelist_coverage_ratio"]})

    # T4 static intro is fine, but a later dynamic shot freezes -> FAIL
    r4 = qa(v_intro_freeze, static_intervals=WHITELIST_INTRO)
    ev4 = r4["freeze_policy"]["evaluated_intervals"]
    outside = r4["freeze_policy"]["intervals_outside_whitelist"]
    suite.add("P0-1", "static_intro_then_dynamic_freeze_not_exempted",
              "FAIL with >=1 interval outside whitelist",
              f"{r4['verdict']} / outside={len(outside)}",
              r4["verdict"] == "FAIL" and len(outside) >= 1
              and r4["needs_manual_review"] is True,
              {"whitelist": r4["freeze_policy"]["whitelist"],
               "evaluated_intervals": ev4,
               "outside_whitelist": outside})

    # T5 whitelist CONFIG errors: overlapping, reversed, missing reason, over-coverage
    bad_configs = {
        "overlapping": [{"start": 0.0, "end": 1.2, "reason": "card A"},
                        {"start": 0.8, "end": 1.5, "reason": "card B"}],
        "reversed": [{"start": 1.5, "end": 0.5, "reason": "bad"}],
        "missing_reason": [{"start": 0.0, "end": 1.5}],
        "coverage_exceeds_50pct": [{"start": 0.0, "end": 4.4, "reason": "too wide"}],
    }
    cfg_results = {}
    for label, wl in bad_configs.items():
        r = qa(v_intro, static_intervals=wl)
        cfg_results[label] = {"verdict": r["verdict"],
                              "errors": r["freeze_policy"]["whitelist_errors"],
                              "frozen_frame": r["checks"]["frozen_frame"],
                              "exemptions_applied": sum(
                                  1 for x in r["freeze_policy"]["evaluated_intervals"]
                                  if x["decision"] == "ALLOWED_STATIC")}
    cfg_ok = all(v["verdict"] == "FAIL" and v["errors"]
                 and v["exemptions_applied"] == 0 for v in cfg_results.values())
    suite.add("P0-1", "whitelist_config_errors_are_fail_closed",
              "all 4 bad configs FAIL, zero exemptions applied",
              f"ok={cfg_ok}", cfg_ok, cfg_results)

    # T6 whitelist OUT OF RANGE -> FAIL
    r6 = qa(v_intro, static_intervals=[{"start": 0.0, "end": 999.0, "reason": "out of range"}])
    suite.add("P0-1", "whitelist_interval_out_of_range",
              "FAIL + OUT_OF_RANGE error", f"{r6['verdict']} / {r6['freeze_policy']['whitelist_errors']}",
              r6["verdict"] == "FAIL" and any("OUT_OF_RANGE" in e
                                              for e in r6["freeze_policy"]["whitelist_errors"]),
              {"whitelist_errors": r6["freeze_policy"]["whitelist_errors"],
               "media_duration": r6["probe"]["duration_seconds"]})

    # T7 the removed global exemption must be REJECTED outright
    rejected = False
    err = ""
    try:
        qa(v_mid, static_material_expected=True)
    except ValueError as exc:
        rejected = True
        err = str(exc)[:220]
    suite.add("P0-1", "legacy_global_exemption_is_removed",
              "ValueError (no caller can bypass)",
              f"rejected={rejected}", rejected, {"error": err})

    # T8 BEFORE/AFTER: reproduce the legacy false negative on the SAME file
    legacy = legacy_qa.qa_media(ffmpeg, ffprobe, v_mid, tag="legacy",
                                static_material_expected=True)
    strict = qa(v_mid)
    before_after = {
        "same_media": v_mid.name,
        "before": {"module": "WB-VIDEO-002/qa.py",
                   "call": "qa_media(..., static_material_expected=True)",
                   "frozen_frame": legacy["checks"]["frozen_frame"],
                   "verdict": legacy["verdict"],
                   "problems": legacy.get("problems", []),
                   "qa_policy": legacy.get("qa_policy", {})},
        "after": {"module": "WB-VIDEO-003/qa.py",
                  "call": "qa_media(..., static_intervals=None)",
                  "frozen_frame": strict["checks"]["frozen_frame"],
                  "verdict": strict["verdict"],
                  "problems": strict.get("problems", []),
                  "whitelist_errors": strict["freeze_policy"]["whitelist_errors"],
                  "evaluated_intervals": strict["freeze_policy"]["evaluated_intervals"]},
        "conclusion": "the legacy global flag hid a real freeze; the strict policy reports it",
    }
    suite.add("P0-1", "before_after_legacy_bypass_reproduced",
              "before hides freeze / after reports FAIL",
              f"before={legacy['checks']['frozen_frame']} after={strict['verdict']}",
              legacy["checks"]["frozen_frame"] == "EXPECTED_STATIC"
              and strict["verdict"] == "FAIL", before_after)

    return {"media": media, "before_after": before_after,
            "freeze_intervals": {
                "dynamic_mid_freeze": r2["freeze_policy"]["evaluated_intervals"],
                "static_intro_dynamic": r3["freeze_policy"]["evaluated_intervals"],
                "static_intro_then_freeze": r4["freeze_policy"]["evaluated_intervals"],
            }}


# ---------------------------------------------------------------------------
# P0-2 tests
# ---------------------------------------------------------------------------

def p0_2_tests(suite: Suite, work: Path) -> dict:
    from PIL import Image, ImageDraw
    W, H = 1920, 1080
    VW, VH = 1080, 1920
    normal_box = [160, 880, 1600, 120]        # y 880..1000 => 0.815..0.926 H (safe)
    near_bottom_box = [160, 1000, 1600, 70]  # bottom 1070/1080 = 0.991 > 0.94
    overflow_box = [1600, 880, 500, 120]     # x+w = 2100 > 1920
    vertical_box = [90, 1500, 900, 130]      # 1500..1630 => 0.781..0.849 VH (safe)
    vertical_mid_box = [90, 900, 900, 130]   # centre ~0.50 VH (defect)
    subject_safe = [100, 100, 600, 300]
    subject_overlap = [200, 850, 800, 200]

    srt = work / "test_subtitles.srt"
    make_srt(srt)
    frames = {}
    for label, size, box, drawn in [
        ("normal", (W, H), normal_box, True),
        ("overflow", (W, H), overflow_box, True),
        ("near_bottom", (W, H), near_bottom_box, True),
        ("vertical_ok", (VW, VH), vertical_box, True),
        ("vertical_midframe", (VW, VH), vertical_mid_box, True),
        ("not_rendered", (W, H), normal_box, False),
    ]:
        fp = work / f"sub_{label}.jpg"
        rp = work / f"sub_{label}_ref.jpg"
        frames[label] = make_frame_pair(fp, rp, size, box, draw_subtitle=drawn)

    def spec(label, *, canvas=(W, H), orientation="horizontal", box=None,
             font_px=40, subjects=None, reference=True, manual=None):
        f = frames[label]
        s = {
            "srt_path": str(srt),
            "frame_path": str(work / f["frame"]),
            "reference_frame_path": str(work / f["reference"]) if reference else None,
            "canvas": list(canvas), "orientation": orientation,
            "declared_box": list(box or f["box"]),
            "font_px": font_px,
            "subject_boxes": [list(x) for x in (subjects or [])],
        }
        if manual:
            s["manual_review"] = manual
        return s

    # S1 normal subtitle, no human sign-off -> automatic PASS but NOT FIXED
    e1 = evaluate_subtitle_fix(spec("normal", subjects=[subject_safe]))
    suite.add("P0-2", "normal_subtitle_automatic_pass_but_needs_human_review",
              "automatic=PASS, fix_result=NEEDS_MANUAL_REVIEW",
              f"{e1['automatic']['verdict']} / {e1['fix_result']}",
              e1["automatic"]["verdict"] == "PASS"
              and e1["fix_result"] == "NEEDS_MANUAL_REVIEW"
              and e1["manual_review"]["signed_off"] is False,
              {"automatic_failures": e1["automatic"]["failures"],
               "burned_in_evidence": e1["automatic"]["checks"]["burned_in_evidence"],
               "manual_items": list(e1["manual_review"]["items"]),
               "can_mark_fixed": e1["can_mark_fixed"]})

    # S1b normal subtitle WITH a named human sign-off -> FIXED is permitted
    e1b = evaluate_subtitle_fix(spec(
        "normal", subjects=[subject_safe],
        manual={"reviewer": "test-harness-named-reviewer",
                "verdict": "APPROVED",
                "evidence": "evidence/subtitle_contact_sheet.jpg"}))
    suite.add("P0-2", "normal_subtitle_with_human_signoff_can_be_FIXED",
              "fix_result=FIXED", e1b["fix_result"],
              e1b["fix_result"] == "FIXED" and e1b["can_mark_fixed"] is True,
              {"manual_review": e1b["manual_review"],
               "automatic": e1b["automatic"]["verdict"],
               "decision_rule": e1b["decision_rule"]})

    # S2 subtitle box outside the canvas
    e2 = evaluate_subtitle_fix(spec("overflow", subjects=[subject_safe]))
    suite.add("P0-2", "subtitle_outside_canvas_detected", "FAIL / box_within_canvas=FAIL",
              f"{e2['automatic']['verdict']} / {e2['automatic']['checks']['box_within_canvas']['verdict']}",
              e2["automatic"]["checks"]["box_within_canvas"]["verdict"] == "FAIL"
              and e2["fix_result"] == "STILL_FAILING",
              {"box_within_canvas": e2["automatic"]["checks"]["box_within_canvas"]})

    # S3 subtitle hugging the bottom edge (outside safe area)
    e3 = evaluate_subtitle_fix(spec("near_bottom", subjects=[subject_safe]))
    suite.add("P0-2", "subtitle_too_close_to_bottom_edge", "FAIL / safe_area=FAIL",
              f"{e3['automatic']['verdict']} / {e3['automatic']['checks']['safe_area']['verdict']}",
              e3["automatic"]["checks"]["safe_area"]["verdict"] == "FAIL",
              {"safe_area": e3["automatic"]["checks"]["safe_area"]})

    # S4 subtitle overlapping a declared subject / UI box
    e4 = evaluate_subtitle_fix(spec("normal", subjects=[subject_overlap]))
    suite.add("P0-2", "subtitle_overlapping_subject_detected", "FAIL / subject_overlap=FAIL",
              f"{e4['automatic']['verdict']} / {e4['automatic']['checks']['subject_overlap']['verdict']}",
              e4["automatic"]["checks"]["subject_overlap"]["verdict"] == "FAIL",
              {"subject_overlap": e4["automatic"]["checks"]["subject_overlap"]})

    # S5 vertical subtitle sitting in the middle of the frame
    e5 = evaluate_subtitle_fix(spec("vertical_midframe", canvas=(VW, VH),
                                    orientation="vertical", font_px=44,
                                    subjects=[subject_safe]))
    ev5 = evaluate_subtitle_fix(spec("vertical_ok", canvas=(VW, VH),
                                     orientation="vertical", font_px=44,
                                     subjects=[subject_safe]))
    suite.add("P0-2", "vertical_subtitle_position_and_safe_area",
              "midframe=FAIL, bottom-placed=PASS",
              f"mid={e5['automatic']['checks']['safe_area']['verdict']} "
              f"bottom={ev5['automatic']['checks']['safe_area']['verdict']}",
              e5["automatic"]["checks"]["safe_area"]["midframe_defect"] is True
              and e5["automatic"]["checks"]["safe_area"]["verdict"] == "FAIL"
              and ev5["automatic"]["checks"]["safe_area"]["verdict"] == "PASS",
              {"vertical_midframe": e5["automatic"]["checks"]["safe_area"],
               "vertical_bottom": ev5["automatic"]["checks"]["safe_area"]})

    # S6 SRT exists but no subtitle was actually burned into the frame
    e6 = evaluate_subtitle_fix(spec("not_rendered", subjects=[subject_safe]))
    suite.add("P0-2", "srt_exists_but_subtitle_not_visible_in_frame",
              "FAIL / burned_in_evidence=FAIL",
              f"{e6['automatic']['verdict']} / "
              f"{e6['automatic']['checks']['burned_in_evidence']['verdict']}",
              e6["automatic"]["checks"]["burned_in_evidence"]["verdict"] == "FAIL"
              and e6["automatic"]["checks"]["srt_parse"]["verdict"] == "PASS",
              {"srt_parse": e6["automatic"]["checks"]["srt_parse"],
               "burned_in_evidence": e6["automatic"]["checks"]["burned_in_evidence"]})

    # S7 file existence alone must NOT produce FIXED
    legacy = legacy_d004_verdict(work / "sub_normal.jpg")
    e7 = evaluate_subtitle_fix(spec("not_rendered", subjects=[subject_safe]))
    suite.add("P0-2", "file_existence_alone_never_marks_FIXED",
              "legacy=FIXED but corrected result!=FIXED",
              f"legacy={legacy['legacy_result']} corrected={e7['fix_result']}",
              legacy["legacy_result"] == "FIXED" and e7["fix_result"] != "FIXED"
              and e7["automatic"]["checks"]["artifact_exists"]["decision_weight"] == 0,
              {"legacy": legacy, "corrected_fix_result": e7["fix_result"],
               "artifact_check": e7["automatic"]["checks"]["artifact_exists"],
               "decision_rule": e7["decision_rule"]})

    # S8 automatic and manual evidence are recorded SEPARATELY
    separate = ("automatic" in e1 and "manual_review" in e1
                and isinstance(e1["manual_review"]["items"], dict)
                and e1["automatic_and_manual_recorded_separately"] is True
                and e1["manual_review"]["verdict"] == "NOT_PERFORMED")
    suite.add("P0-2", "automatic_and_manual_review_recorded_separately",
              "separate fields, manual NOT_PERFORMED", f"ok={separate}", separate,
              {"automatic_verdict": e1["automatic"]["verdict"],
               "manual_review_verdict": e1["manual_review"]["verdict"],
               "manual_items": list(e1["manual_review"]["items"]),
               "unverified_items": e1["unverified_items"]})

    # small contact sheet as visual evidence (committed, no absolute paths)
    labels = ["normal", "overflow", "near_bottom", "vertical_midframe",
              "vertical_ok", "not_rendered"]
    tile_w, tile_h = 300, 210
    sheet = Image.new("RGB", (tile_w * 3, tile_h * 2), (245, 245, 245))
    d = ImageDraw.Draw(sheet)
    for i, label in enumerate(labels):
        p = work / frames[label]["frame"]
        im = Image.open(p).convert("RGB")
        im.thumbnail((tile_w - 12, tile_h - 34))
        x = (i % 3) * tile_w + (tile_w - im.width) // 2
        y = (i // 3) * tile_h + 28
        sheet.paste(im, (x, y))
        d.text(((i % 3) * tile_w + 8, (i // 3) * tile_h + 8), label, fill=(15, 15, 15))
    sheet_path = HERE / "evidence" / "subtitle_contact_sheet.jpg"
    sheet_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(sheet_path, quality=86)

    return {
        "frames": frames,
        "detected_band_normal": detect_subtitle_band(
            work / frames["normal"]["frame"], work / frames["normal"]["reference"]),
        "contact_sheet": sheet_path.name,
        "before_after": {
            "before": legacy,
            "after": {"fix_result": e7["fix_result"],
                      "reason": "real frame evidence + no human sign-off"},
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="local scratch dir for generated test media")
    ap.add_argument("--config", required=True, help="local config.local.json (NOT committed)")
    ap.add_argument("--out", required=True, help="test-results.json output path")
    a = ap.parse_args()

    work = Path(a.root).resolve()
    work.mkdir(parents=True, exist_ok=True)
    cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
    ffmpeg, ffprobe = cfg["ffmpeg"], cfg["ffprobe"]
    legacy_qa = load_module(PARENT / "WB-VIDEO-002" / "qa.py", "qa_legacy_002")

    suite = Suite()
    p1 = p0_1_tests(suite, ffmpeg, ffprobe, work, legacy_qa)
    p2 = p0_2_tests(suite, work)

    out = {
        "task_id": "WB-VIDEO-003",
        "generated_at": NOW(),
        "timezone": "Asia/Shanghai (UTC+08:00)",
        "environment": {
            "media_generation": "local FFmpeg lavfi (testsrc2 / color / freezeframes / sine)",
            "frames": "local PIL",
            "hosted_quota_calls": 0,
            "network_calls": 0,
            "user_projects_touched": False,
            "note": "all media generated under a local scratch dir; only small JPG evidence is committed",
        },
        "summary": suite.summary,
        "groups": {
            "P0-1_freeze_whitelist": [c for c in suite.cases if c["group"] == "P0-1"],
            "P0-2_subtitle_quality": [c for c in suite.cases if c["group"] == "P0-2"],
        },
        "p0_1_media": p1["media"],
        "p0_2_frames": p2["frames"],
        "evidence_files": ["evidence/freeze_intervals.json",
                           "evidence/before_after.json",
                           "evidence/subtitle_contact_sheet.jpg"],
    }
    # committed evidence (paths are relative / placeholder only)
    ev = HERE / "evidence"
    ev.mkdir(parents=True, exist_ok=True)
    (ev / "freeze_intervals.json").write_text(
        json.dumps({"p0_1": p1["freeze_intervals"],
                    "p0_2_detected_band": p2["detected_band_normal"]},
                   ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (ev / "before_after.json").write_text(
        json.dumps({"p0_1": p1["before_after"], "p0_2": p2["before_after"]},
                   ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    BS = chr(92)
    home = str(Path.home()).replace(BS, "/")
    local_prefixes = {home, home.replace("/", BS)}

    def redact(o):
        if isinstance(o, str):
            s = o
            for prefix in local_prefixes:
                s = s.replace(prefix, "<LOCAL>")
            return s.replace(str(work), "<QA003>")
        if isinstance(o, dict):
            return {k: redact(v) for k, v in o.items()}
        if isinstance(o, list):
            return [redact(v) for v in o]
        return o

    dest = Path(a.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(redact(out), ensure_ascii=False, indent=2, default=str),
                    encoding="utf-8")
    print(json.dumps({"summary": suite.summary,
                      "failed_cases": [c["name"] for c in suite.cases if not c["passed"]]},
                     ensure_ascii=False, indent=2))
    return 0 if suite.summary["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
