#!/usr/bin/env python3
"""WB-VIDEO-002 minimal end-to-end run.

Pipeline (zero hosted quota, zero paid credits, zero destructive operations):
  AI-director shotlist -> FFmpeg-synthesised local assets -> QA -> manifest
  -> bounded defect repair loop -> Vidova MCP timeline orchestration
  -> FFmpeg reference render (horizontal + vertical) -> final QA + keyframes.

Usage:
  python run_e2e.py --root <local pipeline dir> --config <local config json>
                    --shots <shotlist.json>
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import (  # noqa: E402
    DefectLedger, Manifest, RetryPolicy, TaskStateMachine, VidovaMCP,
    now, sha256_file,
)
from qa import qa_media  # noqa: E402


def run(cmd, timeout=420):
    try:
        p = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
        return p.returncode, (p.stdout or ""), (p.stderr or "")
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as exc:
        return -1, "", f"{type(exc).__name__}: {exc}"


def safe_json(path, fallback):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return fallback


def make_clip(ffmpeg, out: Path, visual: str, audio: str, dur: float,
              w=1920, h=1080, fps=30) -> dict:
    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error",
        "-f", "lavfi", "-i", visual,
        "-f", "lavfi", "-i", audio,
        "-t", str(dur),
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-r", str(fps), "-c:a", "aac", "-ar", "48000", "-ac", "2",
        "-b:a", "128k", "-shortest", "-y", str(out),
    ]
    rc, _, err = run(cmd)
    return {"ok": rc == 0 and out.exists(), "cmd": " ".join(cmd[:8]) + " ...",
            "stderr": err[-300:]}


def make_card(cfg, out_png: Path, title: str, subtitle: str, accent=(255, 214, 0)) -> dict:
    """Comic-book-flavoured title card (high-saturation, hard shadow, thick border)."""
    from PIL import Image, ImageDraw, ImageFont
    W, H = 1920, 1080
    img = Image.new("RGB", (W, H), (255, 245, 225))
    d = ImageDraw.Draw(img)
    d.rectangle([60, 60, W - 60, H - 60], fill=accent, outline=(15, 15, 15), width=18)
    d.rectangle([92, 92, W - 28, H - 28], fill=(20, 20, 20))
    d.rectangle([60, 60, W - 60, H - 60], outline=(15, 15, 15), width=18)
    font_candidates = [cfg.get("font_msyh", "C:/Windows/Fonts/msyh.ttc"),
                       cfg.get("font", "C:/Windows/Fonts/arial.ttf")]
    f_big = f_small = None
    for fp in font_candidates:
        if Path(fp).exists():
            try:
                f_big = ImageFont.truetype(fp, 108)
                f_small = ImageFont.truetype(fp, 46)
                break
            except Exception:
                continue
    if f_big is None:
        f_big = f_small = ImageFont.load_default()
        title, subtitle = title.encode("ascii", "ignore").decode(), subtitle.encode("ascii", "ignore").decode()
    d.text((150, 320), title, font=f_big, fill=(15, 15, 15), stroke_width=0)
    d.text((160, 330), title, font=f_big, fill=(255, 255, 255))
    d.text((160, 500), subtitle, font=f_small, fill=(255, 90, 60))
    for i in range(0, W, 96):
        d.line([(i, 90), (i + 44, 150)], fill=(255, 255, 255), width=4)
    img.save(out_png)
    return {"ok": out_png.exists(), "path": str(out_png)}


def card_to_clip(ffmpeg, png: Path, out: Path, dur: float, freq=330) -> dict:
    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error",
        "-loop", "1", "-framerate", "30", "-i", str(png),
        "-f", "lavfi", "-i", f"sine=frequency={freq}:sample_rate=48000",
        "-t", str(dur),
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-r", "30", "-c:a", "aac", "-ar", "48000", "-ac", "2",
        "-b:a", "128k", "-shortest", "-y", str(out),
    ]
    rc, _, err = run(cmd)
    return {"ok": rc == 0 and out.exists(), "stderr": err[-300:]}


def write_srt(path: Path, shots, offset: float) -> None:
    """offset = duration of the intro card."""
    lines = []
    t = offset
    for i, s in enumerate(shots, 1):
        start, end = t, t + float(s["duration_seconds"])
        def fmt(x):
            h = int(x // 3600); m = int((x % 3600) // 60); sec = x % 60
            return f"{h:02d}:{m:02d}:{sec:06.3f}".replace(".", ",")
        lines += [str(i), f"{fmt(start)} --> {fmt(end)}", s["subtitle"], ""]
        t = end + (1.0 if i == 1 else 0)  # chapter card inserted after shot 1
    path.write_text("\n".join(lines), encoding="utf-8")


def asset_count(text: str) -> int:
    m = re.search(r"(\d+)\s+assets", text or "")
    return int(m.group(1)) if m else -1


def asset_json(result: dict) -> list:
    for c in (result.get("raw") or {}).get("content", []):
        t = c.get("text", "")
        if t.strip().startswith("["):
            try:
                parsed = json.loads(t)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                pass
    return []


# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--shots", required=True)
    ap.add_argument("--skip-mcp", action="store_true")
    ap.add_argument("--skip-render", action="store_true")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    cfg = safe_json(args.config, {})
    ffmpeg = cfg.get("ffmpeg", "ffmpeg")
    ffprobe = cfg.get("ffprobe", "ffprobe")
    shots_doc = safe_json(args.shots, {"shots": []})
    shots = shots_doc["shots"]
    A = root / "assets"; R = root / "renders"; Q = root / "qa"
    for d in (A, R, Q):
        d.mkdir(parents=True, exist_ok=True)

    result = {
        "task_id": "WB-VIDEO-002", "started_at": now(), "root": str(root),
        "policy": {"hosted_quota_calls": 0, "paid_credits": 0,
                   "existing_projects_modified": False, "source_assets_deleted": False},
        "stages": {},
    }
    manifest = Manifest(root / "manifest.json", "WB-VIDEO-002-E2E")
    sm = TaskStateMachine(root / "state_log.json")
    ledger = DefectLedger(root / "defects.json")
    retry = RetryPolicy(backoff=(0.2, 0.4, 0.8))

    # ---------------- Stage A: synthesise local test assets ----------------
    visuals = [
        "testsrc2=size=1920x1080:rate=30",
        "smptebars=size=1920x1080:rate=30",
        "color=c=black:s=1920x1080:r=30",
    ]
    audios = [
        "sine=frequency=440:sample_rate=48000",
        "sine=frequency=660:sample_rate=48000",
        "anullsrc=channel_layout=stereo:sample_rate=48000",
    ]
    synth = []
    for i, s in enumerate(shots):
        out = A / f"{s['shot_id']}-A01.mp4"
        sm.move(s["shot_id"], "GENERATING", "local FFmpeg synthesis (no hosted quota)")
        r = make_clip(ffmpeg, out, visuals[i], audios[i], float(s["duration_seconds"]))
        sm.move(s["shot_id"], "COMPLETED" if r["ok"] else "FAILED", "synthesis")
        synth.append({"shot_id": s["shot_id"], "path": str(out), **r})
    result["stages"]["A_synthesise"] = synth

    # ---------------- Stage B: QA + manifest --------------------------------
    qa_by_asset = {}
    for i, s in enumerate(shots):
        p = A / f"{s['shot_id']}-A01.mp4"
        sm.move(s["shot_id"], "VALIDATING", "ffmpeg automated QA")
        qa = qa_media(ffmpeg, ffprobe, p, tag=f"{s['shot_id']}-A01",
                      frame_dir=Q / "keyframes", frame_times=[0.5, min(1.5, s["duration_seconds"] - 0.2)])
        qa_by_asset[f"{s['shot_id']}-A01"] = qa
        rec = {
            "asset_id": f"{s['shot_id']}-A01", "shot_id": s["shot_id"],
            "purpose": s["purpose"], "prompt": s["prompt"],
            "file_path": str(p.relative_to(root)).replace("\\", "/"),
            "file_type": "video/mp4",
            "duration_seconds": qa["probe"].get("duration_seconds"),
            "width": qa["probe"].get("width"), "height": qa["probe"].get("height"),
            "fps": qa["probe"].get("fps"),
            "source_type": s["source_type"], "source": "ffmpeg_local_synthesis",
            "is_ai_generated": False, "is_real_footage": False,
            "generation_status": "COMPLETED", "qa_status": qa["verdict"],
            "quality_checks": list(qa.get("checks", {}).keys()),
            "quality_check_detail": qa.get("checks", {}),
            "allow_edit": qa["verdict"] == "PASS",
            "checksum_sha256": sha256_file(p) if p.exists() else None,
            "retry_count": 0, "timecode_start": s["timecode_start"],
            "size_bytes": p.stat().st_size if p.exists() else 0,
            "notes": ["synthetic test material, not AI-generated", "problems: " + ",".join(qa.get("problems", []))],
            "created_at": now(),
        }
        ok, why = manifest.upsert(rec)
        if not ok:
            rec["notes"].append(f"upsert={why}")
        sm.move(s["shot_id"], "APPROVED" if qa["verdict"] == "PASS" else "REVIEW_REQUIRED",
                f"QA {qa['verdict']}: {','.join(qa.get('problems', []))}")
    result["stages"]["B_qa_manifest"] = {
        "assets": len(manifest.data["assets"]),
        "approved": [a["asset_id"] for a in manifest.approved()],
        "failed": [a["asset_id"] for a in manifest.data["assets"] if a["qa_status"] == "FAIL"],
    }

    # ---------------- Stage C: bounded defect / repair loop ----------------
    bad = [a for a in manifest.data["assets"] if a["qa_status"] == "FAIL"]
    repair = {"defects": [], "cycles_used": 0, "bounded_verified": None}
    for a in bad:
        problems = qa_by_asset[a["asset_id"]].get("problems", [])
        owners = {"asset": "vidova", "audio": "audio_module"}
        for j, prob in enumerate(problems):
            cat = "audio" if prob == "silence" else "asset"
            ledger.add(
                f"D{len(ledger.data['defects'])+1:03d}",
                f"{a['timecode_start']:.1f}s", f"{a['asset_id']}: {prob}",
                "high" if prob in ("decode_failed", "black_frames") else "medium",
                cat, owners.get(cat, "vidova"),
                "regenerate this shot under a NEW asset_id; never overwrite the defective source",
                a["asset_id"],
            )
        cycle = retry.cycle(a["shot_id"])
        repair["cycles_used"] = max(repair["cycles_used"], cycle)
        if not retry.can_rework(a["shot_id"]) or cycle > 2:
            sm.move(a["shot_id"], "ESCALATED", "rework budget exhausted -> human review")
            repair["bounded_verified"] = "ESCALATED"
            continue
        sm.move(a["shot_id"], "PENDING", "repair: regenerate asset")
        sm.move(a["shot_id"], "GENERATING", "regenerate with valid video+audio")
        newp = A / f"{a['shot_id']}-A02.mp4"
        made = make_clip(ffmpeg, newp, "testsrc2=size=1920x1080:rate=30",
                         "sine=frequency=880:sample_rate=48000", 2.0)
        qa2 = qa_media(ffmpeg, ffprobe, newp, tag=f"{a['shot_id']}-A02",
                       frame_dir=Q / "keyframes", frame_times=[0.5, 1.5])
        qa_by_asset[f"{a['shot_id']}-A02"] = qa2
        sm.move(a["shot_id"], "COMPLETED", "regenerated")
        sm.move(a["shot_id"], "VALIDATING", "re-QA")
        rec2 = {
            **a, "asset_id": f"{a['shot_id']}-A02",
            "file_path": str(newp.relative_to(root)).replace("\\", "/"),
            "duration_seconds": qa2["probe"].get("duration_seconds"),
            "width": qa2["probe"].get("width"), "height": qa2["probe"].get("height"),
            "fps": qa2["probe"].get("fps"), "qa_status": qa2["verdict"],
            "quality_check_detail": qa2.get("checks", {}),
            "allow_edit": qa2["verdict"] == "PASS",
            "checksum_sha256": sha256_file(newp) if newp.exists() else None,
            "retry_count": cycle, "size_bytes": newp.stat().st_size if newp.exists() else 0,
            "notes": ["repair output of " + a["asset_id"], "original defective asset preserved"],
            "created_at": now(),
        }
        ok2, why2 = manifest.upsert(rec2)
        sm.move(a["shot_id"], "APPROVED" if qa2["verdict"] == "PASS" else "REVIEW_REQUIRED",
                f"re-QA {qa2['verdict']}")
        for d in ledger.data["defects"]:
            if d.get("asset_id") == a["asset_id"] and d["fix_result"] == "OPEN":
                ledger.resolve(d["defect_id"], "FIXED" if qa2["verdict"] == "PASS" else "STILL_FAILING", cycle)
        repair["defects"].append({"source": a["asset_id"], "replacement": rec2["asset_id"],
                                  "re_qa": qa2["verdict"], "upsert": why2, "synthesis": made["ok"]})
    # verify the retry ceiling really closes (no infinite loop)
    probe_entity = "BOUNDARY_PROBE"
    cycle_counts = [retry.cycle(probe_entity) for _ in range(3)]
    repair["bounded_verified"] = {
        "max_rework_cycles": retry.MAX_REWORK_CYCLES,
        "consecutive_cycle_numbers": cycle_counts,
        "third_cycle_allowed": retry.can_rework(probe_entity),
        "max_generation_attempts": retry.MAX_GENERATION_ATTEMPTS,
        "human_review_gate": retry.HUMAN_REVIEW_GATE,
    }
    result["stages"]["C_repair_loop"] = repair
    result["stages"]["C_repair_loop"]["defect_ledger"] = ledger.data["defects"]

    # ---------------- Stage D: Vidova MCP orchestration --------------------
    mcp_stage = {"attempted": not args.skip_mcp}
    if not args.skip_mcp:
        mcp = VidovaMCP(cfg.get("mcp_url", "http://127.0.0.1:17373/mcp"))
        original_project_id = None
        try:
            mcp_stage["initialize"] = mcp.initialize()
            tool_names = [t["name"] for t in mcp.list_tools()]
            mcp_stage["tool_count"] = len(tool_names)
            mcp_stage["tools"] = tool_names
            orig = mcp.call("get_active_project")
            try:
                original_project_id = json.loads(orig["text"]).get("id")
            except Exception:
                original_project_id = None
            mcp_stage["original_active_project"] = original_project_id

            created = mcp.call("create_project", {"name": "WB-E2E-20261108-TEST"})
            mcp_stage["create_project"] = created["ok"]
            mcp_stage["create_project_excerpt"] = created["text"][:400]
            before = mcp.call("asset", {"action": "list"})
            n_before = asset_count(before["text"])
            files = [str((root / a["file_path"]).resolve()) for a in manifest.approved()]
            candidates = [
                {"action": "local", "paths": files},
                {"action": "local", "files": files},
                {"action": "local", "filePaths": files},
                {"action": "local", "path": files[0] if files else ""},
                {"action": "local", "absolutePaths": files},
            ]
            probe_rows = []
            winning = None
            for cand in candidates:
                r = mcp.call("import_asset", cand)
                after = mcp.call("asset", {"action": "list"})
                n_after = asset_count(after["text"])
                probe_rows.append({
                    "param_keys": [k for k in cand if k != "action"],
                    "ok": r["ok"], "assets_before": n_before, "assets_after": n_after,
                    "response_excerpt": r["text"][:300],
                })
                if r["ok"] and n_after > n_before:
                    winning = cand
                    n_before = n_after
                    break
            mcp_stage["import_param_probe"] = probe_rows
            mcp_stage["import_working_arguments"] = (
                {k: ("<3 absolute paths>" if isinstance(v, list) else "<absolute path>")
                 for k, v in winning.items()} if winning else None
            )
            assets = asset_json(mcp.call("asset", {"action": "list"}))
            mcp_stage["asset_count_after_import"] = len(assets)
            # place shots on the timeline by timecode
            placements = []
            approved = manifest.approved()
            for idx, a in enumerate(approved):
                match = [x for x in assets if Path(x.get("name", "")).name == Path(a["file_path"]).name]
                if not match:
                    placements.append({"asset_id": a["asset_id"], "ok": False,
                                       "reason": "assetId not found in Vidova project"})
                    continue
                r = mcp.call("timeline_edit", {
                    "action": "addClip", "type": "video", "assetId": match[0]["id"],
                    "start": float(a["timecode_start"]), "duration": float(a["duration_seconds"]),
                    "name": a["asset_id"],
                })
                placements.append({"asset_id": a["asset_id"], "vidova_asset_id": match[0]["id"],
                                   "start": a["timecode_start"], "duration": a["duration_seconds"],
                                   "ok": r["ok"], "response_excerpt": r["text"][:260]})
            mcp_stage["timeline_placements"] = placements
            state = mcp.call("timeline_get_state")
            mcp_stage["timeline_state_excerpt"] = state["text"][:900]
            preview = mcp.call("preview", {"action": "captureFrame", "timecode": 1.0})
            mcp_stage["preview_capture_frame"] = {
                "ok": preview["ok"],
                "content_types": [c.get("type") for c in (preview.get("raw") or {}).get("content", [])],
                "excerpt": preview["text"][:250],
            }
        except Exception as exc:
            mcp_stage["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            if original_project_id:
                restored = mcp.call("set_active_project", {"projectId": original_project_id})
                mcp_stage["active_project_restored"] = restored["ok"]
            mcp.save_log(root / "mcp_call_log.json")
            mcp_stage["call_count"] = len(mcp.call_log)
            mcp_stage["quota_consuming_calls"] = [
                c["tool"] + ":" + str(c["arguments"].get("kind") or c["arguments"].get("action"))
                for c in mcp.call_log
                if c["tool"] in ("generate_asset",) or
                (c["tool"] == "asset" and c["arguments"].get("action") == "transcribe")
            ]
    result["stages"]["D_vidova_mcp"] = mcp_stage
    for a in manifest.approved():
        try:
            if sm.state(a["shot_id"]) == "APPROVED":
                sm.move(a["shot_id"], "EDITING", "handed to editor stage")
        except ValueError:
            pass

    # ---------------- Stage E: reference render ----------------------------
    render = {"attempted": not args.skip_render}
    if not args.skip_render:
        from PIL import Image  # noqa: F401  (ensures card generator dependency present)
        cards = [
            ("card_intro.png", "YAODAO / WB-VIDEO-002", "MINIMAL END-TO-END TEST", (255, 214, 0), 1.5, 330),
            ("card_chapter.png", "CHAPTER 01", "ONE SENTENCE IS ENOUGH", (255, 96, 72), 1.0, 520),
            ("card_outro.png", "REMINDER ONLY", "ASK YOUR DOCTOR ABOUT MEDICINE", (108, 220, 180), 1.5, 260),
        ]
        card_rows = []
        for fn, title, sub, color, dur, freq in cards:
            png = R / fn
            card_meta = make_card(cfg, png, title, sub, color)
            mp4 = R / (fn.replace(".png", ".mp4"))
            card_rows.append({"card": fn, "png": card_meta,
                              "clip": card_to_clip(ffmpeg, png, mp4, dur, freq)})
        render["cards"] = card_rows
        approved = sorted(manifest.approved(), key=lambda x: x["timecode_start"])
        segments = [R / "card_intro.mp4",
                    root / approved[0]["file_path"],
                    R / "card_chapter.mp4",
                    root / approved[1]["file_path"],
                    root / approved[2]["file_path"],
                    R / "card_outro.mp4"]
        render["segments"] = [str(s.relative_to(root)).replace("\\", "/") for s in segments
                              if isinstance(s, Path) and s.is_relative_to(root)] or [str(s) for s in segments]
        total = 1.5 + approved[0]["duration_seconds"] + 1.0 + approved[1]["duration_seconds"] \
                + approved[2]["duration_seconds"] + 1.5
        render["planned_duration_seconds"] = round(total, 2)
        listfile = R / "concat.txt"
        listfile.write_text("\n".join(f"file '{s.as_posix()}'" for s in segments), encoding="utf-8")
        raw = R / "timeline_raw.mp4"
        rc, _, err = run([ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "concat",
                          "-safe", "0", "-i", str(listfile), "-c", "copy", "-y", str(raw)])
        render["concat_demuxer"] = {"ok": rc == 0 and raw.exists(), "stderr": err[-300:]}
        if not render["concat_demuxer"]["ok"]:
            # fallback: filter_complex concat (full re-encode)
            ins = []
            for s in segments:
                ins += ["-i", str(s)]
            fc = "".join(f"[{i}:v][{i}:a]" for i in range(len(segments))) + \
                 f"concat=n={len(segments)}:v=1:a=1[outv][outa]"
            rc2, _, err2 = run([ffmpeg, "-hide_banner", "-loglevel", "error", *ins,
                                "-filter_complex", fc, "-map", "[outv]", "-map", "[outa]",
                                "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                                "-r", "30", "-c:a", "aac", "-ar", "48000", "-ac", "2",
                                "-y", str(raw)])
            render["concat_filter_fallback"] = {"ok": rc2 == 0, "stderr": err2[-300:]}

        # subtitle + narration deliverables (text only; TTS not available)
        srt = R / "subtitles.srt"
        write_srt(srt, shots, 1.5)
        (R / "narration.txt").write_text(
            "\n".join(f"[{s['shot_id']}] {s['narration']}" for s in shots), encoding="utf-8")
        render["subtitle_file"] = str(srt.relative_to(root)).replace("\\", "/")
        render["narration_file"] = "renders/narration.txt"

        subbed = R / "timeline_subtitled.mp4"
        # relative filename avoids Windows drive-colon escaping in the subtitles filter
        rc3, _, err3 = run([ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(raw),
                            "-vf", "subtitles=subtitles.srt:force_style='FontSize=30,BorderStyle=1,Outline=2'",
                            "-c:a", "copy", "-y", str(subbed)], timeout=420)
        # cwd for the filter is the renders dir
        rc3b = -1
        if rc3 != 0 or not subbed.exists():
            r = subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(raw),
                                "-vf", "subtitles=subtitles.srt", "-c:a", "copy", "-y", str(subbed)],
                               cwd=str(R), capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=420)
            rc3b, err3 = r.returncode, (r.stderr or "")[-300:]
        render["subtitle_burn_in"] = {
            "ok": (rc3 == 0 or rc3b == 0) and subbed.exists(),
            "stderr": (err3 or "")[-300:],
            "note": "if false, the .srt is still delivered but NOT burned into the video",
        }
        video_for_audio = subbed if subbed.exists() else raw

        # BGM + transition SFX + labelled narration placeholder
        bgm = R / "bgm.wav"; sfx = R / "sfx.wav"
        run([ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
             "sine=frequency=220:sample_rate=48000", "-t", f"{total:.2f}",
             "-af", f"volume=0.05,afade=t=in:st=0:d=0.4,afade=t=out:st={total-0.5:.2f}:d=0.5",
             "-ac", "2", "-y", str(bgm)])
        run([ffmpeg, "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i",
             "sine=frequency=1200:sample_rate=48000", "-t", "0.4",
             "-af", "volume=0.10,afade=t=in:st=0:d=0.02,afade=t=out:st=0.2:d=0.2",
             "-ac", "2", "-y", str(sfx)])
        final_h = R / "final_horizontal.mp4"
        mix = ("[0:a]volume=1.0[main];[1:a]volume=0.55[b];[2:a]volume=0.6[s];"
               "[main][b][s]amix=inputs=3:duration=first:dropout_transition=0[a]")
        rc4, _, err4 = run([ffmpeg, "-hide_banner", "-loglevel", "error",
                            "-i", str(video_for_audio), "-i", str(bgm), "-i", str(sfx),
                            "-filter_complex", mix, "-map", "0:v", "-map", "[a]",
                            "-c:v", "copy", "-c:a", "aac", "-ar", "48000", "-ac", "2",
                            "-y", str(final_h)])
        render["horizontal"] = {"path": str(final_h.relative_to(root)).replace("\\", "/"),
                                "ok": rc4 == 0 and final_h.exists(), "stderr": err4[-300:]}

        final_v = R / "final_vertical.mp4"
        # Blurred-background fill: a plain letterbox produced ~69% pure black in
        # visual QA, which is not an acceptable vertical deliverable.
        vfilter = ("[0:v]split=2[fg][bg];"
                   "[bg]scale=1080:1920:force_original_aspect_ratio=increase,"
                   "crop=1080:1920,gblur=sigma=28,eq=brightness=-0.18[bg2];"
                   "[fg]scale=1080:608[fg2];[bg2][fg2]overlay=0:656[outv]")
        rc5, _, err5 = run([ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(final_h),
                            "-filter_complex", vfilter, "-map", "[outv]", "-map", "0:a",
                            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                            "-c:a", "copy", "-y", str(final_v)])
        render["vertical"] = {"path": str(final_v.relative_to(root)).replace("\\", "/"),
                              "ok": rc5 == 0 and final_v.exists(), "stderr": err5[-300:],
                              "method": "blurred-background fill reference render (not a native vertical re-layout)"}
        render["narration_audio"] = "LABELLED_PLACEHOLDER_ONLY — no TTS engine was verified in this stage"
        for a in manifest.approved():
            try:
                if sm.state(a["shot_id"]) == "EDITING":
                    sm.move(a["shot_id"], "EXPORTED", "reference renderer")
            except ValueError:
                pass
    result["stages"]["E_render"] = render

    # ---------------- Stage F: final QA + keyframes -------------------------
    final_qa = {}
    if not args.skip_render:
        for label, rel in [("horizontal", "renders/final_horizontal.mp4"),
                           ("vertical", "renders/final_vertical.mp4")]:
            p = root / rel
            if not p.exists():
                final_qa[label] = {"verdict": "MISSING"}
                continue
            times = [0.8, 2.5, 5.0, 8.0, 10.5]
            final_qa[label] = qa_media(
                ffmpeg, ffprobe, p, tag=f"final_{label}",
                frame_dir=Q / "keyframes", frame_times=times,
                expect={"width": 1920 if label == "horizontal" else 1080,
                        "height": 1080 if label == "horizontal" else 1920, "fps": 30},
            )
            entity = "FINAL_" + label.upper()
            if final_qa[label]["verdict"] == "PASS":
                for st in ("GENERATING", "COMPLETED", "VALIDATING", "APPROVED",
                           "EDITING", "EXPORTED", "QA_CHECKING", "DELIVERED"):
                    sm.move(entity, st, "final render QA chain")
            else:
                sm.move(entity, "REVIEW_REQUIRED", "final QA flagged issues")
    (Q / "qa_report.json").write_text(
        json.dumps({"asset_qa": qa_by_asset, "final_qa": final_qa},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    result["stages"]["F_final_qa"] = {
        k: {"verdict": v.get("verdict"), "problems": v.get("problems"),
            "checks": v.get("checks"), "duration": v.get("probe", {}).get("duration_seconds"),
            "resolution": [v.get("probe", {}).get("width"), v.get("probe", {}).get("height")],
            "fps": v.get("probe", {}).get("fps"),
            "keyframes": v.get("keyframes"), "visual_scan": v.get("visual_scan")}
        for k, v in final_qa.items()
    }

    # ---------------- Stage G: state finalisation ---------------------------
    manifest.save(); ledger.save(); sm.save()
    result["ended_at"] = now()
    result["outputs"] = {
        "manifest": "manifest.json", "defects": "defects.json",
        "state_log": "state_log.json", "mcp_call_log": "mcp_call_log.json",
        "qa_report": "qa/qa_report.json",
    }
    result["summary"] = {
        "assets_total": len(manifest.data["assets"]),
        "assets_approved": len(manifest.approved()),
        "defects_found": len(ledger.data["defects"]),
        "defects_fixed": sum(1 for d in ledger.data["defects"] if d["fix_result"] == "FIXED"),
        "state_transitions": len(sm.data["transitions"]),
        "quota_consuming_calls": (result["stages"].get("D_vidova_mcp", {}).get("quota_consuming_calls") or []),
        "render_files": [render.get("horizontal", {}).get("path"), render.get("vertical", {}).get("path")]
        if not args.skip_render else [],
    }
    (root / "e2e_result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
