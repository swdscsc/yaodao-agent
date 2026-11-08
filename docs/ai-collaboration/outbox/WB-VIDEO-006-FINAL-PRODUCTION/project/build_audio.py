# -*- coding: utf-8 -*-
"""WB-VIDEO-006 original score, sound design and final mix.

ALL music and SFX here are ORIGINAL, synthesised by this script with numpy.
No third-party audio, no test tones, no unlicensed material. The score has
section-level dynamics and is automatically ducked by -12 dB under every real
voice-over segment. Output WAVs are 48 kHz stereo 16-bit.

Usage: python build_audio.py
"""
from __future__ import annotations
import json, math, os, sys, wave
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
SR = 48000
for sub in ("music", "sfx"):
    os.makedirs(os.path.join(WORK, sub), exist_ok=True)

MOOD_BY_CHAPTER = {
    "C0 冷开场": "sparse_piano", "C1 痛点": "low_strings",
    "C2 转折": "piano_bright", "C3 产品形态": "minimal",
    "C4 核心功能": "steady_pulse", "C5 一天": "theme_full",
    "C6 安全边界": "near_silence", "C7 落版": "resolve",
}

CHORDS = [
    (174.61, 261.63, 349.23),   # F  (warm)
    (130.81, 261.63, 392.00),   # C
    (146.83, 293.66, 440.00),   # Dm colour, pentatonic-safe
    (220.00, 349.23, 523.25),   # Am colour
]
PENTA = (349.23, 392.00, 440.00, 523.25, 587.33, 698.46)


def read_wav(path):
    with wave.open(path, "rb") as w:
        assert w.getframerate() == SR, (path, w.getframerate())
        n = w.getnframes()
        raw = w.readframes(n)
    a = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if w.getnchannels() == 2:
        a = a.reshape(-1, 2).mean(axis=1)
    return a


def write_wav(path, left, right):
    n = min(len(left), len(right))
    a = np.empty(n * 2, dtype="<i2")
    a[0::2] = np.clip(left[:n], -1, 1) * 32767
    a[1::2] = np.clip(right[:n], -1, 1) * 32767
    with wave.open(path, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(a.tobytes())
    return path


def note(L, R, start, dur, freq, kind, gain, pan=0.5):
    i0 = int(start * SR)
    n = int(dur * SR)
    if i0 >= len(L) or n <= 0:
        return
    n = min(n, len(L) - i0)
    t = np.arange(n, dtype=np.float32) / SR
    w = 2 * np.pi * freq
    if kind == "piano":
        env = np.exp(-2.1 * t) * (1 - np.exp(-110 * t))
        y = (np.sin(w * t) + .32 * np.sin(2 * w * t) + .10 * np.sin(3 * w * t)
             + .06 * np.sin(w * 1.003 * t + .4))
    elif kind == "pad":
        env = (np.hanning(n).astype(np.float32) ** .65)
        y = (np.sin(w * t) + .45 * np.sin(w * 1.004 * t + .8)
             + .30 * np.sin(w * .5 * t) + .18 * np.sin(2 * w * t + 1.1))
    elif kind == "pluck":
        env = np.exp(-7.0 * t) * (1 - np.exp(-200 * t))
        y = np.sin(w * t) + .38 * np.sin(2 * w * t) + .12 * np.sin(3 * w * t)
    elif kind == "hit":
        env = np.exp(-34.0 * t)
        rng = np.random.default_rng(int(start * 1000) % (2 ** 31))
        y = rng.normal(0, 1, n).astype(np.float32)
        y = np.diff(np.concatenate(([0], y))).astype(np.float32) * 3.0
    elif kind == "ping":
        env = np.exp(-9.0 * t) * (1 - np.exp(-300 * t))
        y = np.sin(w * t) + .25 * np.sin(2 * w * t)
    elif kind == "wood":
        env = np.exp(-16.0 * t)
        y = np.sin(w * t) + .18 * np.sin(2.76 * w * t)
    elif kind == "paper":
        env = np.exp(-22.0 * t)
        rng = np.random.default_rng(int(start * 977) % (2 ** 31))
        y = rng.normal(0, 1, n).astype(np.float32) * .7
    else:                                          # whoosh
        env = np.sin(math.pi * np.clip(t / dur, 0, 1)) ** 2
        rng = np.random.default_rng(int(start * 613) % (2 ** 31))
        y = np.diff(np.concatenate(([0], rng.normal(0, 1, n).astype(np.float32))))
    sig = y * env * gain
    gl, gr = gain * (1 - pan) / max(gain, 1e-9), gain * pan / max(gain, 1e-9)
    L[i0:i0 + n] += sig * (1 - pan)
    R[i0:i0 + n] += sig * pan
    return gl, gr


def sections_from_timeline(tl, vertical):
    if vertical:
        n = len(tl["shots"])
        return [(s["start"], s["end"],
                 "sparse_piano" if i < n * .3 else
                 ("steady_pulse" if i < n * .8 else "resolve"))
                for i, s in enumerate(tl["shots"])]
    out, cur, cs = [], None, None
    for s in tl["shots"]:
        m = MOOD_BY_CHAPTER.get(s["chapter"], "minimal")
        if m != cur:
            if cur is not None:
                out.append((cs, s["start"], cur))
            cur, cs = m, s["start"]
    out.append((cs, tl["duration_s"], cur))
    return out


def build_score(tl, vertical):
    n = int(math.ceil(tl["duration_s"] * SR))
    L = np.zeros(n, np.float32); R = np.zeros(n, np.float32)
    rng = np.random.default_rng(611 if vertical else 606)
    for a, b, mood in sections_from_timeline(tl, vertical):
        t = a
        ci = int(a / 4) % len(CHORDS)
        while t < b - .05:
            chord = CHORDS[ci % len(CHORDS)]
            ci += 1
            span = min(4.0, b - t)
            if mood == "sparse_piano":
                note(L, R, t, 1.8, chord[1], "piano", .115, .45)
                if span > 2.2:
                    note(L, R, t + 2.1, 1.4, chord[2], "piano", .075, .58)
            elif mood == "low_strings":
                for f, pan in zip(chord, (.35, .5, .65)):
                    note(L, R, t, span * .98, f, "pad", .042, pan)
                note(L, R, t, 1.6, chord[0], "piano", .070, .4)
            elif mood == "piano_bright":
                for j in range(6):
                    f = chord[j % 3] * (2 if j >= 3 else 1)
                    note(L, R, t + j * .33, 1.2, f, "piano", .105, .35 + j * .06)
                note(L, R, t, span, chord[0], "pad", .030, .5)
            elif mood == "minimal":
                note(L, R, t, 1.6, chord[2], "piano", .060, .55)
                if span > 2.0:
                    note(L, R, t + 2.0, 1.3, chord[1], "piano", .045, .45)
            elif mood == "steady_pulse":
                for f, pan in zip(chord, (.35, .5, .65)):
                    note(L, R, t, span, f, "pad", .034, pan)
                for j in range(5):
                    note(L, R, t + j * .76, .8, PENTA[(ci + j) % len(PENTA)],
                         "pluck", .052, .35 + .1 * (j % 3))
                for j in range(2):
                    note(L, R, t + j * 2.0, .25, 0, "hit", .020, .5)
            elif mood == "theme_full":
                for f, pan in zip(chord, (.32, .5, .68)):
                    note(L, R, t, span, f, "pad", .046, pan)
                for j in range(8):
                    f = chord[j % 3] * (2 if j >= 4 else 1)
                    note(L, R, t + j * .48, 1.5, f, "piano", .105, .35 + j * .04)
                for j in range(3):
                    f = PENTA[int(rng.integers(0, len(PENTA)))]
                    note(L, R, t + .6 + j * 1.2, 1.1, f, "pluck", .070, .55)
                note(L, R, t, .25, 0, "hit", .018, .5)
            elif mood == "near_silence":
                note(L, R, t, span, chord[1], "pad", .012, .5)
            elif mood == "resolve":
                for f, pan in zip(chord, (.35, .5, .65)):
                    note(L, R, t, min(3.2, span), f, "piano", .105, pan)
                note(L, R, t, span, chord[0], "pad", .028, .5)
            t += 4.0
    # global fade in / out
    fi = int(.8 * SR); fo = int(1.4 * SR)
    L[:fi] *= np.linspace(0, 1, fi, dtype=np.float32)
    R[:fi] *= np.linspace(0, 1, fi, dtype=np.float32)
    L[-fo:] *= np.linspace(1, 0, fo, dtype=np.float32)
    R[-fo:] *= np.linspace(1, 0, fo, dtype=np.float32)
    return L, R


def build_sfx(tl, vertical):
    n = int(math.ceil(tl["duration_s"] * SR))
    L = np.zeros(n, np.float32); R = np.zeros(n, np.float32)
    for s in tl["shots"]:
        k, t = s["kind"], s["start"]
        if k in ("brand", "closing"):
            for f in (261.63, 349.23):
                note(L, R, t + .1, 1.2, f, "piano", .055, .5)
        elif k.startswith("ui_") or k in ("reply", "wave", "device_outline"):
            note(L, R, t + .05, .22, 880.0, "ping", .045, .5)
            note(L, R, t + .16, .18, 1174.7, "ping", .028, .5)
        elif k in ("meals", "details", "principles"):
            for j in range(3):
                note(L, R, t + .1 + j * .5, .3, 523.25 * (1 + j * .12),
                     "wood", .040, .4 + j * .1)
        else:
            note(L, R, t + .02, .34, 0, "whoosh", .022, .5)
        if k == "ui_check":
            note(L, R, t + s["dur"] * .45, .5, 659.25, "wood", .055, .5)
        if k == "safety_list":
            for j in range(3):
                note(L, R, t + .4 + j * (s["dur"] / 4), .14, 0, "paper", .028, .5)
    return L, R


def build_voice(tl):
    n = int(math.ceil(tl["duration_s"] * SR))
    L = np.zeros(n, np.float32); R = np.zeros(n, np.float32)
    for v in tl["voices"]:
        y = read_wav(os.path.join(WORK, v["wav"]))
        i0 = int(round(v["start"] * SR))
        take = min(len(y), n - i0)
        if take <= 0:
            continue
        L[i0:i0 + take] += y[:take] * .98
        R[i0:i0 + take] += y[:take] * .98
    return L, R


def duck(n, voices):
    g = np.ones(n, np.float32)
    ramp = int(.22 * SR)
    for v in voices:
        a = max(0, int((v["start"] - .28) * SR))
        b = min(n, int((v["end"] + .38) * SR))
        seg = np.full(b - a, .251, np.float32)     # -12 dB
        if len(seg) > 2 * ramp:
            seg[:ramp] = np.linspace(1, .251, ramp, dtype=np.float32)
            seg[-ramp:] = np.linspace(.251, 1, ramp, dtype=np.float32)
        g[a:b] = np.minimum(g[a:b], seg)
    # smooth 30 ms to avoid zipper noise
    k = int(.03 * SR)
    kernel = np.ones(k, np.float32) / k
    return np.convolve(g, kernel, mode="same").astype(np.float32)


def build_one(tl, vertical, tag):
    vL, vR = build_voice(tl)
    sL, sR = build_score(tl, vertical)
    fL, fR = build_sfx(tl, vertical)
    g = duck(len(vL), tl["voices"])
    mL = vL + sL * g * .95 + fL * .85
    mR = vR + sR * g * .95 + fR * .85
    peak = float(max(np.max(np.abs(mL)), np.max(np.abs(mR))))
    if peak > .97:
        mL *= .97 / peak; mR *= .97 / peak
    suffix = "vertical" if vertical else "main"
    write_wav(os.path.join(WORK, "voiceover%s.wav" % ("_vertical" if vertical else "")), vL, vR)
    write_wav(os.path.join(WORK, "music", "%s_score.wav" % suffix), sL, sR)
    write_wav(os.path.join(WORK, "sfx", "sfx_%s.wav" % suffix), fL, fR)
    write_wav(os.path.join(WORK, "mix_%s.wav" % suffix), mL, mR)
    stats = dict(tag=tag, duration_s=tl["duration_s"],
                 voices=len(tl["voices"]),
                 voice_peak_dbfs=round(20 * math.log10(max(
                     float(np.max(np.abs(vL))), 1e-6)), 2),
                 score_peak_dbfs=round(20 * math.log10(max(
                     float(np.max(np.abs(sL))), 1e-6)), 2),
                 mix_peak_dbfs=round(20 * math.log10(max(peak, 1e-6)), 2),
                 duck_floor=0.251, duck_events=len(tl["voices"]),
                 score_source="ORIGINAL programmatic synthesis (numpy)",
                 sfx_source="ORIGINAL programmatic synthesis (numpy)")
    return stats


def main():
    out = []
    for name, vert, tag in (("timeline_main.json", False, "main"),
                            ("timeline_vertical.json", True, "vertical")):
        tl = json.load(open(os.path.join(WORK, name), encoding="utf-8"))
        out.append(build_one(tl, vert, tag))
        print("AUDIO %-8s dur=%.2fs voices=%d mix_peak=%.2f dBFS" % (
            tag, out[-1]["duration_s"], out[-1]["voices"],
            out[-1]["mix_peak_dbfs"]), flush=True)
    json.dump(out, open(os.path.join(WORK, "audio_stats.json"), "w",
                        encoding="utf-8"), ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
