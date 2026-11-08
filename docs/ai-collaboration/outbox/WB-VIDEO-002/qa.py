"""WB-VIDEO-002 audiovisual QA module (FFmpeg / ffprobe).

Checks: decodability, resolution, fps, black frames, silence, audio peak &
clipping, duration, frozen frames, A/V sync. Also extracts keyframes and
computes a perceptual duplicate/black-screen scan for the AI visual review.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


def _run(cmd: list[str], timeout: int = 240):
    try:
        p = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
        return p.returncode, p.stdout or "", p.stderr or ""
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as exc:
        return -1, "", f"{type(exc).__name__}: {exc}"


def probe(ffprobe: str, path) -> dict:
    rc, out, err = _run([
        ffprobe, "-v", "error", "-show_format", "-show_streams",
        "-of", "json", str(path),
    ])
    if rc != 0 or not out.strip():
        return {"ok": False, "error": err[-400:]}
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return {"ok": False, "error": "ffprobe returned non-JSON"}
    fmt = data.get("format", {})
    vs = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    aus = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), {})
    r_fps = vs.get("avg_frame_rate") or vs.get("r_frame_rate") or "0/1"
    try:
        num, den = r_fps.split("/")
        fps = round(float(num) / float(den), 3) if float(den) else 0.0
    except Exception:
        fps = 0.0
    return {
        "ok": True,
        "duration_seconds": round(float(fmt.get("duration") or vs.get("duration") or 0), 3),
        "width": vs.get("width"), "height": vs.get("height"), "fps": fps,
        "video_codec": vs.get("codec_name"),
        "audio_codec": aus.get("codec_name"),
        "video_duration": _f(vs.get("duration")),
        "audio_duration": _f(aus.get("duration")),
        "size_bytes": int(fmt.get("size") or 0),
        "bit_rate": fmt.get("bit_rate"),
    }


def _f(v):
    try:
        return round(float(v), 3)
    except (TypeError, ValueError):
        return None


def _detect(ffmpeg: str, path, afilter: str, label: str) -> dict:
    rc, _, err = _run([
        ffmpeg, "-hide_banner", "-nostats", "-i", str(path),
        "-vf" if label.startswith("black") or label.startswith("freeze") else "-af",
        afilter, "-an" if label.startswith("black") or label.startswith("freeze") else "-vn",
        "-f", "null", "-",
    ])
    text = err or ""
    if "TIMEOUT" in text or rc == -1:
        return {"available": False, "detected": None, "intervals": [], "note": text[-200:]}
    intervals = []
    if label == "black":
        for m in re.finditer(r"black_start:([\d.]+)\s+black_end:([\d.]+)\s+black_duration:([\d.]+)", text):
            intervals.append({"start": float(m.group(1)), "end": float(m.group(2)), "duration": float(m.group(3))})
    elif label == "silence":
        starts = [float(m) for m in re.findall(r"silence_start:\s*([\d.]+)", text)]
        ends = [float(m) for m in re.findall(r"silence_end:\s*([\d.]+)", text)]
        for i, s in enumerate(starts):
            e = ends[i] if i < len(ends) else None
            intervals.append({"start": s, "end": e, "duration": (e - s) if e else None})
        if starts and not ends:
            intervals.append({"start": starts[-1], "end": None, "duration": None, "note": "silence until EOF"})
    elif label == "freeze":
        # FFmpeg emits "lavfi.freezedetect.freeze_start: 0" and, when the
        # freeze lasts until EOF, only a start (no freeze_end/duration).
        # Requiring all three fields silently produced false negatives.
        starts = [float(x) for x in re.findall(r"freeze_start:\s*([\d.]+)", text)]
        ends = [float(x) for x in re.findall(r"freeze_end:\s*([\d.]+)", text)]
        durs = [float(x) for x in re.findall(r"freeze_duration:\s*([\d.]+)", text)]
        for idx, e in enumerate(ends):
            intervals.append({
                "start": starts[idx] if idx < len(starts) else 0.0,
                "end": e,
                "duration": durs[idx] if idx < len(durs) else (e - starts[idx] if idx < len(starts) else None),
            })
        if len(starts) > len(ends):
            intervals.append({"start": starts[-1], "end": None, "duration": None,
                              "note": "freeze until EOF (no freeze_end emitted)"})
    return {"available": True, "detected": bool(intervals), "intervals": intervals,
            "filter_error": ("No such filter" in text or "Invalid" in text or "Error" in text and not intervals)}


def _volume(ffmpeg: str, path) -> dict:
    rc, _, err = _run([
        ffmpeg, "-hide_banner", "-nostats", "-i", str(path),
        "-af", "volumedetect", "-vn", "-f", "null", "-",
    ])
    peak = re.search(r"max_volume:\s*(-?[\d.]+) dB", err or "")
    mean = re.search(r"mean_volume:\s*(-?[\d.]+) dB", err or "")
    return {
        "peak_db": float(peak.group(1)) if peak else None,
        "mean_db": float(mean.group(1)) if mean else None,
        "clipping_risk": bool(peak and float(peak.group(1)) > -0.5),
        "available": bool(peak),
    }


def extract_frames(ffmpeg: str, path, out_dir, tag: str, times: list[float]) -> list[str]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    made = []
    for i, t in enumerate(times):
        out = out_dir / f"{tag}_f{i:02d}_{t:.1f}s.jpg"
        rc, _, err = _run([
            ffmpeg, "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}",
            "-i", str(path), "-frames:v", "1", "-q:v", "3", "-y", str(out),
        ])
        if rc == 0 and out.exists() and out.stat().st_size > 0:
            made.append(str(out))
    return made


def visual_scan(frame_paths: list[str]) -> dict:
    """Quantitative support for duplicate-shot / black-frame / subtitle-area checks."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return {"available": False, "note": "cv2/numpy unavailable"}
    rows = []
    for p in frame_paths:
        img = cv2.imread(str(p))
        if img is None:
            continue
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (32, 32)).astype("float32")
        rows.append({
            "file": Path(p).name,
            "mean_luma": round(float(gray.mean()), 2),
            "black_ratio": round(float((gray < 16).mean()), 4),
            "bottom_text_band_luma": round(float(gray[int(h * 0.80):, :].mean()), 2),
            "signature": small.tolist(),
            "file_bytes": Path(p).stat().st_size,
        })
    duplicates = []
    for i in range(1, len(rows)):
        a = np.array(rows[i - 1]["signature"], dtype="float32")
        b = np.array(rows[i]["signature"], dtype="float32")
        mad = float(np.abs(a - b).mean())
        if mad < 3.0:
            duplicates.append({"pair": [rows[i - 1]["file"], rows[i]["file"]], "mean_abs_diff": round(mad, 3)})
    for r in rows:
        r.pop("signature", None)
    return {
        "available": True,
        "frames": rows,
        "near_duplicate_pairs": duplicates,
        "all_black": all(r["black_ratio"] > 0.95 for r in rows) if rows else None,
    }


def cross_asset_duplicate_scan(labeled_frames: dict, threshold: float = 3.0) -> dict:
    """Perceptual duplicate detection ACROSS different shot assets."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return {"available": False, "note": "cv2/numpy unavailable"}
    sigs = {}
    for label, p in labeled_frames.items():
        im = cv2.imread(str(p))
        if im is None:
            continue
        g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
        sigs[label] = cv2.resize(g, (32, 32)).astype("float32")
    pairs = []
    keys = list(sigs)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            diff = float(np.abs(sigs[keys[i]] - sigs[keys[j]]).mean())
            pairs.append({"a": keys[i], "b": keys[j],
                          "mean_abs_diff": round(diff, 3),
                          "duplicate": diff < threshold})
    return {"available": True, "threshold": threshold, "pairs": pairs,
            "duplicates": [p for p in pairs if p["duplicate"]]}


def qa_media(ffmpeg: str, ffprobe: str, path, *, tag: str = "asset",
             frame_dir=None, frame_times=None, expect=None,
             static_material_expected: bool = False) -> dict:
    expect = expect or {}
    info = probe(ffprobe, path)
    result = {"path": str(path), "tag": tag, "probe": info}
    if not info["ok"]:
        result.update({"verdict": "FAIL", "problems": ["ffprobe_failed"]})
        return result

    rc, _, err = _run([ffmpeg, "-hide_banner", "-v", "error", "-i", str(path), "-f", "null", "-"])
    decode_ok = rc == 0 and "TIMEOUT" not in err
    black = _detect(ffmpeg, path, "blackdetect=d=0.30:pix_th=0.10", "black")
    silence = _detect(ffmpeg, path, "silencedetect=noise=-45dB:d=0.30", "silence")
    freeze = _detect(ffmpeg, path, "freezedetect=n=-60dB:d=0.30", "freeze")
    vol = _volume(ffmpeg, path)
    vd, ad = info["video_duration"], info["audio_duration"]
    delta = round(abs(vd - ad), 3) if (vd is not None and ad is not None) else None
    av_ok = delta is not None and delta <= 0.6

    problems = []
    if not decode_ok:
        problems.append("decode_failed")
    if black["detected"]:
        problems.append("black_frames")
    if silence["detected"]:
        problems.append("silence")
    if vol.get("clipping_risk"):
        problems.append("audio_clipping")
    # Static graphics (title cards, test patterns) are legitimately frozen.
    # Keep the raw detection visible but do not fail the pipeline for them.
    freeze_is_defect = freeze["detected"] and not static_material_expected
    if freeze_is_defect:
        problems.append("frozen_frames")
    if not av_ok:
        problems.append("av_sync_mismatch")
    if expect.get("width") and info["width"] != expect["width"]:
        problems.append("width_mismatch")
    if expect.get("height") and info["height"] != expect["height"]:
        problems.append("height_mismatch")
    if expect.get("fps") and abs(float(info["fps"]) - float(expect["fps"])) > 0.6:
        problems.append("fps_mismatch")

    checks = {
        "decode": "PASS" if decode_ok else "FAIL",
        "resolution": "PASS" if info["width"] and info["height"] else "FAIL",
        "fps": "PASS" if info["fps"] else "FAIL",
        "black_screen": "PASS" if not black["detected"] else "FAIL",
        "silence": "PASS" if not silence["detected"] else "FAIL",
        "audio_peak": "PASS" if vol["available"] and not vol["clipping_risk"] else "FAIL",
        "duration": "PASS" if info["duration_seconds"] > 0 else "FAIL",
        "frozen_frame": ("PASS" if not freeze["detected"]
                         else ("EXPECTED_STATIC" if static_material_expected else "FAIL")),
        "av_sync": "PASS" if av_ok else "FAIL",
    }
    result["qa_policy"] = {
        "static_material_expected": static_material_expected,
        "freeze_detector_hit": freeze["detected"],
        "note": ("A freeze was detected but this asset is declared static. "
                 "The raw interval data is retained above; production footage "
                 "must NOT set this flag." if static_material_expected and freeze["detected"] else None),
    }
    result.update({
        "decode_ok": decode_ok, "decode_stderr": err[-300:],
        "black": black, "silence": silence, "freeze": freeze, "volume": vol,
        "av_sync": {"ok": av_ok, "video_duration": vd, "audio_duration": ad, "delta_seconds": delta},
        "checks": checks, "problems": problems,
        "verdict": "PASS" if not problems else "FAIL",
    })
    if frame_dir and frame_times:
        frames = extract_frames(ffmpeg, path, frame_dir, tag, frame_times)
        result["keyframes"] = [Path(f).name for f in frames]
        result["visual_scan"] = visual_scan(frames)
    return result
