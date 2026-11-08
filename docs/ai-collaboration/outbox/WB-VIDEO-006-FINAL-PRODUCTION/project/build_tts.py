# -*- coding: utf-8 -*-
"""Generate REAL Mandarin voiceover with edge-tts (free Microsoft Edge neural
voices). No credentials are read or printed. Output: 48 kHz mono WAV + index.

Usage: python build_tts.py
"""
from __future__ import annotations
import asyncio, json, os, subprocess, sys, wave
import edge_tts

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import data

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
OUT = os.path.join(WORK, "tts")
os.makedirs(OUT, exist_ok=True)
FFMPEG = r"C:\Users\asus\AppData\Roaming\npm\ffmpeg.exe"
PROXY = "http://127.0.0.1:7897"

VOICES = {
    "narration": ("zh-CN-XiaoxiaoNeural", "-9%",  "-3Hz"),
    "vnarration": ("zh-CN-XiaoxiaoNeural", "+12%", "-2Hz"),
    "elder":      ("zh-CN-XiaoxiaoNeural", "-18%", "-9Hz"),
    "child":      ("zh-CN-YunxiNeural",   "+0%",  "+0Hz"),
    "device":     ("zh-CN-YunyangNeural", "-6%",  "-2Hz"),
}

JOBS = []
for nid, text in data.NARRATION:
    JOBS.append(dict(id=nid, text=text, role="narration", kind="narration"))
for cid, shot, text, role in data.DIALOGUE:
    JOBS.append(dict(id=cid, text=text, role=role, kind="dialogue", shot=shot))
for nid, text in data.VERTICAL_NARRATION:
    JOBS.append(dict(id=nid, text=text, role="vnarration", kind="vnarration"))
for cid, shot, text, role in data.VERTICAL_DIALOGUE:
    JOBS.append(dict(id=cid, text=text, role=role, kind="vdialogue", shot=shot))


async def one(job, sem):
    async with sem:
        voice, rate, pitch = VOICES[job["role"]]
        mp3 = os.path.join(OUT, job["id"] + ".mp3")
        wav = os.path.join(OUT, job["id"] + ".wav")
        last = None
        for attempt in range(3):
            try:
                com = edge_tts.Communicate(job["text"], voice, rate=rate,
                                           pitch=pitch, proxy=PROXY)
                await com.save(mp3)
                subprocess.run(
                    [FFMPEG, "-y", "-loglevel", "error", "-i", mp3,
                     "-af", "aresample=48000", "-ar", "48000", "-ac", "1",
                     "-c:a", "pcm_s16le", wav],
                    check=True, capture_output=True)
                with wave.open(wav, "rb") as w:
                    dur = w.getnframes() / float(w.getframerate())
                if dur > 0.2:
                    return dict(job, voice=voice, rate=rate, pitch=pitch,
                                wav=os.path.relpath(wav, WORK).replace("\\", "/"),
                                duration_s=round(dur, 4))
                last = "zero duration"
            except Exception as e:                       # noqa: BLE001
                last = repr(e)
                await asyncio.sleep(1.2 * (attempt + 1))
        return dict(job, error=str(last))


async def main():
    sem = asyncio.Semaphore(4)
    results = await asyncio.gather(*(one(j, sem) for j in JOBS))
    index = {r["id"]: r for r in results}
    with open(os.path.join(WORK, "tts_index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    ok = [r for r in results if "error" not in r]
    bad = [r for r in results if "error" in r]
    print("TTS OK=%d FAILED=%d TOTAL=%.1fs" % (
        len(ok), len(bad), sum(r["duration_s"] for r in ok)))
    for r in bad:
        print("FAILED", r["id"], r.get("error"))
    return 0 if not bad else 1


if __name__ == "__main__":
    os.environ["HTTPS_PROXY"] = PROXY
    os.environ["HTTP_PROXY"] = PROXY
    sys.exit(asyncio.run(main()))
