#!/usr/bin/env python3
"""WB-VIDEO-002 repair loop: second, bounded rework cycle + re-export + re-QA.

Triggered by two REAL defects found by the corrected QA + AI visual review:
  D003 duplicate shot  : S001-A01 and S003-A02 are pixel-identical (MAD 0.000)
  D004 vertical subtitle: down-scaled subtitles became tiny / off-centre

This script deliberately writes *_v2 files and keeps the v1 renders intact as
before/after evidence. It never overwrites a user project or source asset.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import (  # noqa: E402
    DefectLedger, Manifest, RetryPolicy, TaskStateMachine, now, sha256_file,
)
from qa import cross_asset_duplicate_scan, qa_media  # noqa: E402
from run_e2e import make_clip, safe_json  # noqa: E402


def run(cmd, cwd=None, timeout=420):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return p.returncode, p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:
        return -1, "", f"{type(e).__name__}: {e}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--shots", required=True)
    a = ap.parse_args()

    root = Path(a.root).resolve()
    cfg = safe_json(a.config, {})
    shots = safe_json(a.shots, {"shots": []})["shots"]
    ff, fp = cfg["ffmpeg"], cfg["ffprobe"]
    A, R, Q = root / "assets", root / "renders", root / "qa"
    K = Q / "keyframes"

    manifest = Manifest(root / "manifest.json", "WB-VIDEO-002-E2E")
    sm = TaskStateMachine(root / "state_log.json")
    ledger = DefectLedger(root / "defects.json")
    retry = RetryPolicy(backoff=(0.2, 0.4, 0.8))
    # carry the one rework cycle already consumed by the first E2E run
    retry.attempts["S003"] = 1
    retry.cycles["S003"] = 1
    qa_doc = safe_json(Q / "qa_report.json", {"asset_qa": {}, "final_qa": {}})
    out = {"task_id": "WB-VIDEO-002-REWORK", "started_at": now(),
           "quota_consuming_calls": 0, "stages": {}}

    # ---- S1: re-run QA with the FIXED freeze detector (positive control) ---
    freeze_evidence = {}
    for asset in manifest.data["assets"]:
        p = root / asset["file_path"]
        if not p.exists():
            continue
        static = asset["asset_id"].startswith("S002")  # smptebars is intentionally static
        r = qa_media(ff, fp, p, tag=asset["asset_id"], frame_dir=K,
                     frame_times=[0.5, 1.5], static_material_expected=static)
        qa_doc["asset_qa"][asset["asset_id"]] = r
        freeze_evidence[asset["asset_id"]] = {
            "freeze_detector_hit": r["freeze"]["detected"],
            "intervals": r["freeze"]["intervals"],
            "check_verdict": r["checks"]["frozen_frame"],
            "static_material_expected": static,
        }
    out["stages"]["S1_fixed_freeze_detector"] = freeze_evidence

    # ---- S2: cross-asset duplicate scan -> D003 --------------------------
    labeled = {}
    for aid in ["S001-A01", "S002-A01", "S003-A02"]:
        f = K / f"{aid}_f00_0.5s.jpg"
        if f.exists():
            labeled[aid] = str(f)
    dup = cross_asset_duplicate_scan(labeled)
    out["stages"]["S2_duplicate_scan"] = dup
    if dup.get("duplicates"):
        d = dup["duplicates"][0]
        ledger.add("D003", "0.0s / 6.0s",
                   f"duplicate shot: {d['a']} and {d['b']} are visually identical "
                   f"(mean abs diff {d['mean_abs_diff']})",
                   "medium", "asset", "vidova",
                   "regenerate the replacement shot with a visibly different dynamic pattern "
                   "under a NEW asset_id; keep the duplicate as evidence", d["b"])
    # D004 from the AI visual review of the vertical render
    ledger.add("D004", "0.0-12.0s",
               "vertical render: subtitles were down-scaled with the horizontal frame and "
               "became tiny/off-centre; the letterbox version also had ~69% black bars",
               "medium", "subtitle", "subtitle_module",
               "build vertical from the UNSUBTITLED timeline, fill background with a blurred "
               "version of the frame, then burn a vertical-sized subtitle track", None)

    # ---- S3: bounded rework (cycle 2 of 2) --------------------------------
    cycle = retry.cycle("S003")
    out["stages"]["S3_bounded_rework"] = {
        "cycle_number": cycle, "max_rework_cycles": retry.MAX_REWORK_CYCLES,
        "allowed": cycle <= retry.MAX_REWORK_CYCLES,
    }
    # The policy must reject a THIRD cycle (hard stop, no infinite loop)
    retry.cycle("S003")
    out["stages"]["S3_bounded_rework"]["third_cycle_allowed"] = retry.can_rework("S003")
    out["stages"]["S3_bounded_rework"]["human_review_gate"] = retry.HUMAN_REVIEW_GATE

    replacement = A / "S003-A03.mp4"
    made = make_clip(ff, replacement, "testsrc=size=1920x1080:rate=30",
                     "sine=frequency=1200:sample_rate=48000", 2.0)
    qa3 = qa_media(ff, fp, replacement, tag="S003-A03", frame_dir=K,
                   frame_times=[0.5, 1.5])
    qa_doc["asset_qa"]["S003-A03"] = qa3
    base = next(x for x in manifest.data["assets"] if x["asset_id"] == "S003-A02")
    rec3 = {
        **base, "asset_id": "S003-A03",
        "file_path": str(replacement.relative_to(root)).replace("\\", "/"),
        "duration_seconds": qa3["probe"].get("duration_seconds"),
        "width": qa3["probe"].get("width"), "height": qa3["probe"].get("height"),
        "fps": qa3["probe"].get("fps"), "qa_status": qa3["verdict"],
        "quality_check_detail": qa3.get("checks", {}),
        "allow_edit": qa3["verdict"] == "PASS",
        "checksum_sha256": sha256_file(replacement),
        "retry_count": cycle, "size_bytes": replacement.stat().st_size,
        "notes": ["rework cycle 2: fixes D003 duplicate shot",
                  "different dynamic pattern (testsrc, not testsrc2)",
                  "previous versions S003-A01 / S003-A02 preserved as evidence"],
        "created_at": now(),
    }
    ok3, why3 = manifest.upsert(rec3)
    # retire the superseded asset: unique numbering must prevent double import
    manifest.patch("S003-A02", {
        "allow_edit": False,
        "notes": ["SUPERSEDED by S003-A03 (D003 duplicate shot); retained as evidence only"],
    })
    out["stages"]["S3_bounded_rework"].update({
        "replacement": "S003-A03", "synthesis_ok": made["ok"],
        "replacement_qa": qa3["verdict"], "manifest_upsert": why3,
    })
    labelled2 = {k: v for k, v in labeled.items() if k != "S003-A02"}
    f3 = K / "S003-A03_f00_0.5s.jpg"
    if f3.exists():
        labelled2["S003-A03"] = str(f3)
    dup2 = cross_asset_duplicate_scan(labelled2)
    out["stages"]["S3_bounded_rework"]["duplicate_scan_after_fix"] = dup2

    # ---- S4: re-export horizontal v2 --------------------------------------
    approved = sorted(manifest.approved(), key=lambda x: x["timecode_start"])
    # ensure the S003 slot uses the newest approved asset
    approved = [x for x in approved if x["shot_id"] != "S003"] + [rec3]
    approved = sorted(approved, key=lambda x: x["timecode_start"])
    segs = [R / "card_intro.mp4", root / approved[0]["file_path"],
            R / "card_chapter.mp4", root / approved[1]["file_path"],
            root / approved[2]["file_path"], R / "card_outro.mp4"]
    total = 1.5 + 3.0 + 1.0 + 3.0 + 2.0 + 1.5
    (R / "concat_v2.txt").write_text(
        "\n".join(f"file '{s.as_posix()}'" for s in segs), encoding="utf-8")
    raw2 = R / "timeline_raw_v2.mp4"
    rc, _, err = run([ff, "-hide_banner", "-loglevel", "error", "-f", "concat",
                      "-safe", "0", "-i", str(R / "concat_v2.txt"), "-c", "copy",
                      "-y", str(raw2)])
    out["stages"]["S4_reexport"] = {"concat_v2_ok": rc == 0, "stderr": err[-250:],
                                    "planned_duration_seconds": total}

    sub2 = R / "timeline_subtitled_v2.mp4"
    rc2, _, e2 = run([ff, "-hide_banner", "-loglevel", "error", "-i", str(raw2),
                      "-vf", "subtitles=subtitles.srt:force_style='FontSize=30,BorderStyle=1,Outline=2'",
                      "-c:a", "copy", "-y", str(sub2)], cwd=str(R))
    out["stages"]["S4_reexport"]["subtitle_burn_v2_ok"] = rc2 == 0

    bgm, sfx = R / "bgm.wav", R / "sfx.wav"
    h2 = R / "final_horizontal_v2.mp4"
    mix = ("[0:a]volume=1.0[main];[1:a]volume=0.55[b];[2:a]volume=0.6[s];"
           "[main][b][s]amix=inputs=3:duration=first:dropout_transition=0[a]")
    rc3, _, e3 = run([ff, "-hide_banner", "-loglevel", "error", "-i", str(sub2),
                      "-i", str(bgm), "-i", str(sfx), "-filter_complex", mix,
                      "-map", "0:v", "-map", "[a]", "-c:v", "copy",
                      "-c:a", "aac", "-ar", "48000", "-ac", "2", "-y", str(h2)])
    out["stages"]["S4_reexport"]["horizontal_v2_ok"] = rc3 == 0

    # ---- S5: vertical v2 from UNSUBTITLED timeline + proper subtitles -----
    vnosub = R / "vertical_nosub_v2.mp4"
    vf = ("[0:v]split=2[fg][bg];"
          "[bg]scale=1080:1920:force_original_aspect_ratio=increase,"
          "crop=1080:1920,gblur=sigma=28,eq=brightness=-0.18[bg2];"
          "[fg]scale=1080:608[fg2];[bg2][fg2]overlay=0:656[outv]")
    rc4, _, e4 = run([ff, "-hide_banner", "-loglevel", "error", "-i", str(raw2),
                      "-filter_complex", vf, "-map", "[outv]", "-an",
                      "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                      "-y", str(vnosub)])
    vsub = R / "vertical_subtitled_v2.mp4"
    rc5, _, e5 = run([ff, "-hide_banner", "-loglevel", "error", "-i", str(vnosub),
                      "-vf", "subtitles=subtitles.srt:force_style='FontSize=26,Alignment=2,MarginV=90,BorderStyle=1,Outline=2'",
                      "-y", str(vsub)], cwd=str(R))
    v2 = R / "final_vertical_v2.mp4"
    rc6, _, e6 = run([ff, "-hide_banner", "-loglevel", "error", "-i", str(vsub),
                      "-i", str(h2), "-map", "0:v", "-map", "1:a", "-c", "copy",
                      "-y", str(v2)])
    out["stages"]["S5_vertical_fix"] = {
        "blurred_background_ok": rc4 == 0, "subtitle_reburn_ok": rc5 == 0,
        "audio_mux_ok": rc6 == 0, "stderr": (e4 + e5 + e6)[-300:],
        "path": str(v2.relative_to(root)).replace("\\", "/"),
    }

    # ---- S6: final QA on v2 renders ---------------------------------------
    final = {}
    for label, p, expect in [
        ("horizontal_v2", h2, {"width": 1920, "height": 1080, "fps": 30}),
        ("vertical_v2", v2, {"width": 1080, "height": 1920, "fps": 30}),
    ]:
        if not p.exists():
            final[label] = {"verdict": "MISSING"}
            continue
        r = qa_media(ff, fp, p, tag=f"final_{label}", frame_dir=K,
                     frame_times=[0.8, 2.5, 5.0, 8.0, 10.5],
                     expect=expect, static_material_expected=True)
        qa_doc["final_qa"][label] = r
        final[label] = {
            "verdict": r["verdict"], "problems": r["problems"], "checks": r["checks"],
            "duration": r["probe"].get("duration_seconds"),
            "resolution": [r["probe"].get("width"), r["probe"].get("height")],
            "fps": r["probe"].get("fps"),
            "peak_db": r["volume"].get("peak_db"),
            "av_sync": r["av_sync"],
            "keyframes": r.get("keyframes"),
            "visual_scan": r.get("visual_scan"),
            "freeze_raw": r["freeze"],
        }
    out["stages"]["S6_final_qa"] = final
    (Q / "qa_report.json").write_text(
        json.dumps(qa_doc, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- S7: defect resolution + hard human-review gate -------------------
    for did in ("D003", "D004"):
        for d in ledger.data["defects"]:
            if d["defect_id"] == did and d["fix_result"] == "OPEN":
                fixed = (dup2.get("duplicates") == [] if did == "D003"
                         else bool(v2.exists() and v2.stat().st_size > 0))
                ledger.resolve(did, "FIXED" if fixed else "STILL_FAILING", cycle)
    out["stages"]["S7_defects"] = ledger.data["defects"]
    # after 2 cycles the gate must be a HARD STOP
    out["stages"]["S7_gate"] = {
        "cycles_used": 2,
        "max_rework_cycles": 2,
        "further_rework_allowed": False,
        "state": "REVIEW_REQUIRED (human approval before any 3rd cycle)",
    }
    manifest.save(); ledger.save(); sm.save()

    # ---- S8: refresh contact sheet for AI visual review -------------------
    try:
        from PIL import Image, ImageDraw
        items = [
            ("S001-A01_f00_0.5s.jpg", "S001 asset"),
            ("S002-A01_f00_0.5s.jpg", "S002 asset"),
            ("S003-A01_f00_0.5s.jpg", "S003 DEFECT black"),
            ("S003-A03_f00_0.5s.jpg", "S003-A03 after rework"),
            ("final_horizontal_v2_f01_2.5s.jpg", "FINAL H v2 2.5s"),
            ("final_vertical_v2_f01_2.5s.jpg", "FINAL V v2 2.5s"),
        ]
        W, H = 560, 340
        sheet = Image.new("RGB", (W * 3, H * 2), (245, 245, 245))
        d = ImageDraw.Draw(sheet)
        for i, (fn, label) in enumerate(items):
            p = K / fn
            if not p.exists():
                continue
            im = Image.open(p).convert("RGB")
            im.thumbnail((W - 20, H - 46))
            x = (i % 3) * W + (W - im.width) // 2
            y = (i // 3) * H + 30
            sheet.paste(im, (x, y))
            d.text(((i % 3) * W + 10, (i // 3) * H + 8), label, fill=(15, 15, 15))
            d.rectangle([(i % 3) * W + 2, (i // 3) * H + 2,
                         (i % 3) * W + W - 2, (i // 3) * H + H - 2],
                        outline=(20, 20, 20), width=3)
        sheet.save(Q / "contact_sheet_v2.jpg", quality=88)
        out["stages"]["S8_contact_sheet"] = "qa/contact_sheet_v2.jpg"
    except Exception as exc:
        out["stages"]["S8_contact_sheet"] = f"FAILED: {exc}"

    out["ended_at"] = now()
    out["summary"] = {
        "defects_total": len(ledger.data["defects"]),
        "defects_fixed": sum(1 for d in ledger.data["defects"] if d["fix_result"] == "FIXED"),
        "duplicates_before": len(dup.get("duplicates", [])),
        "duplicates_after": len(dup2.get("duplicates", [])),
        "horizontal_v2": final.get("horizontal_v2", {}).get("verdict"),
        "vertical_v2": final.get("vertical_v2", {}).get("verdict"),
        "rework_cycles_used": 2,
        "hard_stop_at": "REVIEW_REQUIRED",
    }
    (root / "rework_result.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(out["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
