"""WB-VIDEO-003 strict audiovisual QA module (P0-1 fix).

This is the CORRECTED replacement for WB-VIDEO-002/qa.py.

P0-1 defect that is fixed here
--------------------------------
WB-VIDEO-002 exposed ``static_material_expected=True`` which exempted the
WHOLE video from freeze detection. A genuinely frozen dynamic shot could
therefore be reported as PASS. WB-VIDEO-002/rework.py used that flag for the
final renders.

What this module does instead
-----------------------------
* The global exemption parameter is REMOVED. Passing it raises ValueError,
  so no caller can silently bypass freeze detection any more.
* Static content (title cards, chapter cards, plain-text cards) may only be
  exempted inside EXPLICIT, VALIDATED time intervals supplied per asset via
  ``static_intervals``.
* Whitelist intervals are fail-closed validated: numeric, 0 <= start < end,
  must carry a reason, must not overlap, must not extend past the media
  duration, and must not cover more than 50% of the video.
* Any freeze outside the whitelist produces ``FAIL`` plus
  ``needs_manual_review=True`` and retains the exact interval and reason.
* Dynamic intervals are ALWAYS checked. There is no whole-video switch.

No credential, token or machine-specific absolute path is embedded here.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

# A whitelist may never be used as a disguised whole-video exemption.
MAX_WHITELIST_COVERAGE = 0.50
WHITELIST_TOLERANCE_SECONDS = 0.05


class WhitelistError(ValueError):
    """Raised when a static-interval whitelist is invalid / out of range."""


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
        "video_codec": vs.get("codec_name"), "audio_codec": aus.get("codec_name"),
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
            intervals.append({"start": float(m.group(1)), "end": float(m.group(2)),
                              "duration": float(m.group(3))})
    elif label == "silence":
        starts = [float(m) for m in re.findall(r"silence_start:\s*([\d.]+)", text)]
        ends = [float(m) for m in re.findall(r"silence_end:\s*([\d.]+)", text)]
        for i, s in enumerate(starts):
            e = ends[i] if i < len(ends) else None
            intervals.append({"start": s, "end": e, "duration": (e - s) if e else None})
        if starts and not ends:
            intervals.append({"start": starts[-1], "end": None, "duration": None,
                              "note": "silence until EOF"})
    elif label == "freeze":
        # FFmpeg emits only freeze_start when the freeze lasts until EOF.
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
            "filter_error": ("No such filter" in text or "Invalid" in text
                             or ("Error" in text and not intervals))}


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
            duplicates.append({"pair": [rows[i - 1]["file"], rows[i]["file"]],
                               "mean_abs_diff": round(mad, 3)})
    for r in rows:
        r.pop("signature", None)
    return {"available": True, "frames": rows, "near_duplicate_pairs": duplicates,
            "all_black": all(r["black_ratio"] > 0.95 for r in rows) if rows else None}


def cross_asset_duplicate_scan(labeled_frames: dict, threshold: float = 3.0) -> dict:
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


# ---------------------------------------------------------------------------
# P0-1: explicit, validated static-interval whitelist
# ---------------------------------------------------------------------------

def validate_static_whitelist(intervals, duration: float | None,
                              max_coverage: float = MAX_WHITELIST_COVERAGE):
    """Return (normalised_intervals, errors). Fail-closed on ANY problem."""
    errors: list[str] = []
    norm: list[dict] = []
    if intervals is None:
        return [], []
    if not isinstance(intervals, (list, tuple)):
        return [], ["WHITELIST_NOT_A_LIST"]
    if duration is None or duration <= 0:
        return [], ["MEDIA_DURATION_UNKNOWN_CANNOT_VALIDATE_WHITELIST"]

    for i, iv in enumerate(intervals):
        tag = f"interval[{i}]"
        if not isinstance(iv, dict):
            errors.append(f"{tag}: must be an object with start/end/reason")
            continue
        s, e = iv.get("start"), iv.get("end")
        if not isinstance(s, (int, float)) or isinstance(s, bool) or \
           not isinstance(e, (int, float)) or isinstance(e, bool):
            errors.append(f"{tag}: start/end must be finite numbers")
            continue
        s, e = float(s), float(e)
        if s < 0:
            errors.append(f"{tag}: OUT_OF_RANGE start {s} < 0")
            continue
        if e <= s:
            errors.append(f"{tag}: CONFIG_ERROR end {e} <= start {s}")
            continue
        if e > duration + WHITELIST_TOLERANCE_SECONDS:
            errors.append(f"{tag}: OUT_OF_RANGE end {e} exceeds media duration {duration}")
            continue
        reason = iv.get("reason") or iv.get("label")
        if not reason or not str(reason).strip():
            errors.append(f"{tag}: CONFIG_ERROR missing reason (only CONFIRMED static cards are allowed)")
            continue
        norm.append({"start": round(s, 3), "end": round(min(e, duration), 3),
                     "reason": str(reason)})

    norm.sort(key=lambda x: x["start"])
    for i in range(1, len(norm)):
        if norm[i]["start"] < norm[i - 1]["end"] - WHITELIST_TOLERANCE_SECONDS:
            errors.append(f"interval[{i}]: CONFIG_ERROR overlaps interval[{i-1}]")

    if norm:
        coverage = sum(x["end"] - x["start"] for x in norm) / duration
        if coverage > max_coverage:
            errors.append(
                f"CONFIG_ERROR whitelist covers {coverage:.1%} of the video, "
                f"exceeds {max_coverage:.0%} limit (whole-video exemption is forbidden)")
    return norm, errors


def evaluate_freeze(freeze: dict, whitelist: list[dict], whitelist_errors: list[str],
                    duration: float | None) -> dict:
    """Classify EVERY detected freeze interval against the whitelist."""
    evaluated = []
    tol = WHITELIST_TOLERANCE_SECONDS
    for iv in freeze.get("intervals", []):
        s = float(iv.get("start") or 0.0)
        e = iv.get("end")
        e = float(e) if e is not None else (duration if duration is not None else s)
        covered_by = None
        # Whitelist is ignored entirely when it failed validation (fail-closed).
        if not whitelist_errors:
            for w in whitelist:
                if s >= w["start"] - tol and e <= w["end"] + tol:
                    covered_by = w
                    break
        if freeze.get("available") is False:
            decision, reason = "NEEDS_MANUAL_REVIEW", "freeze detector unavailable"
        elif whitelist_errors:
            decision, reason = "FAIL", "invalid whitelist: fail-closed, no exemption applied"
        elif covered_by:
            decision = "ALLOWED_STATIC"
            reason = f"fully inside confirmed static interval [{covered_by['start']}, {covered_by['end']}]: {covered_by['reason']}"
        else:
            decision = "FAIL"
            reason = "freeze outside every confirmed static interval; dynamic footage must not freeze"
        evaluated.append({
            "start": round(s, 3), "end": round(e, 3),
            "duration": round(e - s, 3), "raw_interval": iv,
            "covered_by": covered_by, "decision": decision, "reason": reason,
        })
    outside = [x for x in evaluated if x["decision"] in ("FAIL", "NEEDS_MANUAL_REVIEW")]
    return {
        "policy": "explicit_static_interval_whitelist_v1",
        "global_exemption_available": False,
        "whitelist": whitelist,
        "whitelist_errors": whitelist_errors,
        "whitelist_coverage_ratio": (
            round(sum(x["end"] - x["start"] for x in whitelist) / duration, 4)
            if whitelist and duration else 0.0),
        "raw_intervals": freeze.get("intervals", []),
        "evaluated_intervals": evaluated,
        "intervals_outside_whitelist": outside,
        "detector_available": freeze.get("available"),
        "dynamic_footage_always_checked": True,
    }


def qa_media(ffmpeg: str, ffprobe: str, path, *, tag: str = "asset",
             frame_dir=None, frame_times=None, expect=None,
             static_intervals=None, **legacy_kwargs) -> dict:
    """Strict QA. ``static_material_expected`` is deliberately NOT accepted."""
    if legacy_kwargs:
        if "static_material_expected" in legacy_kwargs:
            raise ValueError(
                "P0-1: the whole-video freeze exemption 'static_material_expected' "
                "has been REMOVED. Use explicit static_intervals=[{start,end,reason}].")
        raise ValueError(f"unknown qa_media arguments: {sorted(legacy_kwargs)}")
    expect = expect or {}
    info = probe(ffprobe, path)
    result = {"path": str(path), "tag": tag, "probe": info}
    if not info["ok"]:
        result.update({"verdict": "FAIL", "problems": ["ffprobe_failed"]})
        return result

    duration = info["duration_seconds"]
    whitelist, wl_errors = validate_static_whitelist(static_intervals, duration)

    rc, _, err = _run([ffmpeg, "-hide_banner", "-v", "error", "-i", str(path), "-f", "null", "-"])
    decode_ok = rc == 0 and "TIMEOUT" not in err
    black = _detect(ffmpeg, path, "blackdetect=d=0.30:pix_th=0.10", "black")
    silence = _detect(ffmpeg, path, "silencedetect=noise=-45dB:d=0.30", "silence")
    freeze = _detect(ffmpeg, path, "freezedetect=n=-60dB:d=0.30", "freeze")
    vol = _volume(ffmpeg, path)
    vd, ad = info["video_duration"], info["audio_duration"]
    delta = round(abs(vd - ad), 3) if (vd is not None and ad is not None) else None
    av_ok = delta is not None and delta <= 0.6

    freeze_policy = evaluate_freeze(freeze, whitelist, wl_errors, duration)

    problems = []
    if not decode_ok:
        problems.append("decode_failed")
    if black["detected"]:
        problems.append("black_frames")
    if silence["detected"]:
        problems.append("silence")
    if vol.get("clipping_risk"):
        problems.append("audio_clipping")
    if wl_errors:
        problems.append("invalid_static_whitelist")
    if freeze_policy["intervals_outside_whitelist"]:
        problems.append("frozen_frames_outside_whitelist")
    if freeze.get("available") is False:
        problems.append("freeze_detector_unavailable")
    if not av_ok:
        problems.append("av_sync_mismatch")
    if expect.get("width") and info["width"] != expect["width"]:
        problems.append("width_mismatch")
    if expect.get("height") and info["height"] != expect["height"]:
        problems.append("height_mismatch")
    if expect.get("fps") and abs(float(info["fps"]) - float(expect["fps"])) > 0.6:
        problems.append("fps_mismatch")

    if wl_errors:
        frozen_check = "FAIL_INVALID_WHITELIST"
    elif freeze_policy["intervals_outside_whitelist"]:
        frozen_check = "FAIL"
    elif freeze.get("available") is False:
        frozen_check = "NEEDS_MANUAL_REVIEW"
    elif freeze["detected"]:
        frozen_check = "PASS_ALLOWED_STATIC"
    else:
        frozen_check = "PASS"

    checks = {
        "decode": "PASS" if decode_ok else "FAIL",
        "resolution": "PASS" if info["width"] and info["height"] else "FAIL",
        "fps": "PASS" if info["fps"] else "FAIL",
        "black_screen": "PASS" if not black["detected"] else "FAIL",
        "silence": "PASS" if not silence["detected"] else "FAIL",
        "audio_peak": "PASS" if vol["available"] and not vol["clipping_risk"] else "FAIL",
        "duration": "PASS" if info["duration_seconds"] > 0 else "FAIL",
        "frozen_frame": frozen_check,
        "static_whitelist": "FAIL" if wl_errors else ("PASS" if whitelist else "NOT_USED"),
        "av_sync": "PASS" if av_ok else "FAIL",
    }
    result.update({
        "qa_policy_version": "P0-1-strict-v1",
        "freeze_policy": freeze_policy,
        "needs_manual_review": bool(freeze_policy["intervals_outside_whitelist"]
                                    or freeze.get("available") is False),
        "decode_ok": decode_ok, "decode_stderr": err[-300:],
        "black": black, "silence": silence, "freeze": freeze, "volume": vol,
        "av_sync": {"ok": av_ok, "video_duration": vd, "audio_duration": ad,
                    "delta_seconds": delta},
        "checks": checks, "problems": problems,
        "verdict": "FAIL" if problems else "PASS",
    })
    if frame_dir and frame_times:
        frames = extract_frames(ffmpeg, path, frame_dir, tag, frame_times)
        result["keyframes"] = [Path(f).name for f in frames]
        result["visual_scan"] = visual_scan(frames)
    return result
