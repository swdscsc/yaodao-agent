# -*- coding: utf-8 -*-
"""WB-VIDEO-006 delivery assembly + honest, machine-generated QA.

Copies finished artefacts into the independent outbox directory, probes both
MP4s with ffprobe, fully decodes video and audio, runs black/freeze/silence
detectors, checks subtitles against the real voice timeline, extracts a
key-frame contact sheet, computes SHA-256 for every delivered file and writes
quality_report.md / asset-sources.md / README.md / delivery_manifest.json.
"""
from __future__ import annotations
import hashlib, json, math, os, re, shutil, subprocess, sys
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import data

FFMPEG = r"C:\Users\asus\AppData\Roaming\npm\ffmpeg.exe"
FFPROBE = r"C:\Users\asus\WorkBuddy\2026-11-08-14-19-50\tools\node_modules\ffprobe-static\bin\win32\x64\ffprobe.exe"
REPO = os.path.abspath(os.path.join(WORK, "..", ".."))
OUT = os.path.join(REPO, "docs", "ai-collaboration", "outbox",
                   "WB-VIDEO-006-FINAL-PRODUCTION")

BANNED = ["治愈", "疗效", "有效率", "临床验证", "用户数", "好评率", "治愈率",
          "包治", "替代医生", "自动提醒", "方言识别", "微信周报",
          "每日一次", "每次一片", "毫克", "ml", "阿司匹林", "降压药",
          "二甲双胍", "氨氯地平", "硝苯地平", "替米沙坦", "测试素材",
          "TODO", "DEBUG", "test pattern"]

COPY_MAP = [
    ("final_main.mp4", "final_main.mp4"),
    ("final_vertical.mp4", "final_vertical.mp4"),
    ("final_main.srt", "final_main.srt"),
    ("final_vertical.srt", "final_vertical.srt"),
    ("voiceover.wav", "voiceover.wav"),
    ("voiceover_vertical.wav", "voiceover_vertical.flac"),
    ("mix_main.wav", "mix_main.flac"),
    ("mix_vertical.wav", "mix_vertical.flac"),
    ("music/main_score.wav", "music/main_score.flac"),
    ("music/vertical_score.wav", "music/vertical_score.flac"),
    ("sfx/sfx_main.wav", "sfx/sfx_main.flac"),
    ("sfx/sfx_vertical.wav", "sfx/sfx_vertical.flac"),
    ("timeline_main.json", "project/timeline_main.json"),
    ("timeline_vertical.json", "project/timeline_vertical.json"),
    ("tts_index.json", "project/tts_index.json"),
    ("audio_stats.json", "project/audio_stats.json"),
    ("subtitle_events.json", "project/subtitle_events.json"),
    ("project/data.py", "project/data.py"),
    ("project/build_tts.py", "project/build_tts.py"),
    ("project/make_timeline.py", "project/make_timeline.py"),
    ("project/build_audio.py", "project/build_audio.py"),
    ("project/render.py", "project/render.py"),
    ("project/deliver.py", "project/deliver.py"),
    ("project/write_reports.py", "project/write_reports.py"),
    ("project/verify_remote.py", "project/verify_remote.py"),
    ("tts/N01.wav", "tts_samples/N01.wav"),
    ("tts/N09.wav", "tts_samples/N09.wav"),
    ("tts/N25.wav", "tts_samples/N25.wav"),
]


def run(cmd, timeout=900):
    p = subprocess.run(cmd, capture_output=True, timeout=timeout)
    return p.returncode, p.stdout.decode("utf-8", "replace"), \
        p.stderr.decode("utf-8", "replace")


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_srt(path):
    txt = open(path, encoding="utf-8").read().strip()
    blocks = re.split(r"\n\s*\n", txt)
    out = []
    for b in blocks:
        ls = b.strip().splitlines()
        if len(ls) < 3:
            continue
        m = re.match(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*"
                     r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", ls[1])
        if not m:
            continue
        g = [int(x) for x in m.groups()]
        a = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
        z = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        out.append(dict(index=int(ls[0]), start=a, end=z,
                        text="\n".join(ls[2:])))
    return out


def probe(path):
    rc, so, se = run([FFPROBE, "-v", "error", "-show_streams",
                      "-show_format", "-of", "json", path])
    assert rc == 0, se
    return json.loads(so)


def media_qa(path, tag, tl):
    q = dict(tag=tag, file=os.path.basename(path),
             size_bytes=os.path.getsize(path), sha256=sha(path))
    pr = probe(path)
    q["ffprobe"] = pr
    vs = [s for s in pr["streams"] if s["codec_type"] == "video"]
    au = [s for s in pr["streams"] if s["codec_type"] == "audio"]
    q["streams"] = dict(video=len(vs), audio=len(au),
                        codec=vs[0]["codec_name"] if vs else None,
                        width=vs[0]["width"] if vs else None,
                        height=vs[0]["height"] if vs else None,
                        fps=vs[0]["avg_frame_rate"] if vs else None,
                        audio_codec=au[0]["codec_name"] if au else None,
                        sample_rate=au[0]["sample_rate"] if au else None,
                        channels=au[0]["channels"] if au else None)
    q["duration_s"] = float(pr["format"]["duration"])
    # full decode, video and audio separately
    rc, _, se = run([FFMPEG, "-v", "error", "-xerror", "-i", path,
                     "-map", "0:v:0", "-f", "null", "-"], timeout=1200)
    q["full_video_decode"] = dict(ok=rc == 0, returncode=rc,
                                  stderr=se.strip()[-400:])
    rc, _, se = run([FFMPEG, "-v", "error", "-xerror", "-i", path,
                     "-map", "0:a:0", "-f", "null", "-"], timeout=1200)
    q["full_audio_decode"] = dict(ok=rc == 0, returncode=rc,
                                  stderr=se.strip()[-400:])
    # black / freeze detectors
    rc, _, se = run([FFMPEG, "-hide_banner", "-i", path, "-vf",
                     "blackdetect=d=0.40:pix_th=0.10", "-an", "-f", "null", "-"],
                    timeout=1200)
    blacks = re.findall(r"black_start:([0-9.]+) black_end:([0-9.]+)", se)
    q["black_detect"] = dict(returncode=rc, intervals=blacks,
                             count=len(blacks))
    rc, _, se = run([FFMPEG, "-hide_banner", "-i", path, "-vf",
                     "freezedetect=n=-70dB:d=2.0", "-an", "-f", "null", "-"],
                    timeout=1200)
    freezes = re.findall(r"freeze_start:([0-9.]+).*?freeze_end:([0-9.]+)",
                         se, re.S)
    q["freeze_detect"] = dict(returncode=rc, intervals=freezes[:40],
                              count=len(freezes))
    # volume / silence
    rc, _, se = run([FFMPEG, "-hide_banner", "-i", path, "-af",
                     "volumedetect", "-f", "null", "-"], timeout=1200)
    mv = re.search(r"mean_volume: ([-\d.]+) dB", se)
    pv = re.search(r"max_volume: ([-\d.]+) dB", se)
    q["volume"] = dict(mean_dbfs=float(mv.group(1)) if mv else None,
                       max_dbfs=float(pv.group(1)) if pv else None)
    rc, _, se = run([FFMPEG, "-hide_banner", "-i", path, "-af",
                     "silencedetect=n=-45dB:d=2.0", "-f", "null", "-"],
                    timeout=1200)
    sil = re.findall(r"silence_start: ([0-9.]+)", se)
    q["silence_detect"] = dict(intervals=sil[:40], count=len(sil))
    # a/v duration alignment
    vd = float(vs[0].get("duration", q["duration_s"]))
    ad = float(au[0].get("duration", q["duration_s"]))
    q["av_duration_delta_s"] = round(abs(vd - ad), 4)
    q["expected_duration_s"] = tl["duration_s"]
    q["duration_delta_s"] = round(abs(q["duration_s"] - tl["duration_s"]), 4)
    return q


def subtitle_qa(srt_path, tl):
    ev = parse_srt(srt_path)
    voices = sorted(tl["voices"], key=lambda v: v["start"])
    overlaps = [(a["index"], b["index"]) for a, b in zip(ev, ev[1:])
                if b["start"] < a["end"] - 1e-3]
    text_mismatch = [(e["index"], v["id"]) for e, v in zip(ev, voices)
                     if e["text"].replace("\n", "") != v["text"]]
    banned_hits = [(e["index"], w) for e in ev for w in BANNED
                   if w in e["text"]]
    garbled = [e["index"] for e in ev
               if "\ufffd" in e["text"] or not re.search(r"[\u4e00-\u9fff]", e["text"])]
    coverage = all(e["start"] <= v["start"] + 1e-3 and
                   e["end"] >= v["end"] - 1e-3
                   for e, v in zip(ev, voices))
    return dict(file=os.path.basename(srt_path), cues=len(ev),
                expected_cues=len(voices), overlaps=overlaps,
                text_mismatch=text_mismatch, banned_hits=banned_hits,
                garbled=garbled, covers_voice=coverage,
                monotonic=all(a["end"] <= b["start"] + 1e-3
                              for a, b in zip(ev, ev[1:])))


def contact_sheet(mp4, tag, tl, n=16):
    folder = os.path.join(OUT, "keyframes")
    os.makedirs(folder, exist_ok=True)
    dur = tl["duration_s"]
    times = [dur * (i + .5) / n for i in range(n)]
    thumbs = []
    for i, t in enumerate(times):
        p = os.path.join(folder, "%s-%02d.jpg" % (tag, i + 1))
        run([FFMPEG, "-y", "-loglevel", "error", "-ss", "%.3f" % t,
             "-i", mp4, "-frames:v", "1", "-q:v", "3", p])
        if os.path.exists(p):
            im = Image.open(p).convert("RGB")
            im.thumbnail((360, 360))
            thumbs.append((t, im.copy()))
    cols = 4
    rows = math.ceil(len(thumbs) / cols)
    sheet = Image.new("RGB", (cols * 380, rows * 400), (248, 244, 236))
    d = ImageDraw.Draw(sheet)
    for i, (t, im) in enumerate(thumbs):
        x = (i % cols) * 380 + 10
        y = (i // cols) * 400 + 10
        d.rectangle((x - 2, y - 2, x + im.width + 2, y + im.height + 2),
                    outline=(196, 184, 166), width=2)
        sheet.paste(im, (x, y))
        d.text((x, y + 366), "#%02d  t=%06.2fs" % (i + 1, t),
               fill=(70, 64, 56))
    out = os.path.join(folder, "%s-contact-sheet.jpg" % tag)
    sheet.save(out, quality=88)
    return out, times


def main():
    os.makedirs(OUT, exist_ok=True)
    for sub in ("project", "music", "sfx", "tts_samples", "keyframes"):
        os.makedirs(os.path.join(OUT, sub), exist_ok=True)
    # Old uncompressed WAV copies from a previous run must not linger.
    for old in ("mix_main.wav", "mix_vertical.wav", "voiceover_vertical.wav",
                os.path.join("music", "main_score.wav"),
                os.path.join("music", "vertical_score.wav"),
                os.path.join("sfx", "sfx_main.wav"),
                os.path.join("sfx", "sfx_vertical.wav")):
        p = os.path.join(OUT, old)
        if os.path.exists(p):
            os.remove(p)
    missing = []
    for src, dst in COPY_MAP:
        s = os.path.join(WORK, src)
        if not os.path.exists(s):
            missing.append(src)
            continue
        d = os.path.join(OUT, dst)
        if dst.endswith(".flac"):
            # Lossless FLAC keeps every sample of the original 48 kHz WAV while
            # keeping the Git delivery small (long silent gaps compress well).
            rc, _, se = run([FFMPEG, "-y", "-loglevel", "error", "-i", s,
                             "-c:a", "flac", d], timeout=600)
            if rc != 0:
                raise RuntimeError("FLAC conversion failed for %s: %s" % (src, se))
        else:
            shutil.copy2(s, d)
    if missing:
        raise RuntimeError("missing source artefacts: %r" % missing)
    tl_m = json.load(open(os.path.join(WORK, "timeline_main.json"), encoding="utf-8"))
    tl_v = json.load(open(os.path.join(WORK, "timeline_vertical.json"), encoding="utf-8"))
    qm = media_qa(os.path.join(OUT, "final_main.mp4"), "main", tl_m)
    qv = media_qa(os.path.join(OUT, "final_vertical.mp4"), "vertical", tl_v)
    sm = subtitle_qa(os.path.join(OUT, "final_main.srt"), tl_m)
    sv = subtitle_qa(os.path.join(OUT, "final_vertical.srt"), tl_v)
    sheet_m, tm = contact_sheet(os.path.join(OUT, "final_main.mp4"), "main", tl_m)
    sheet_v, tv = contact_sheet(os.path.join(OUT, "final_vertical.mp4"),
                                "vertical", tl_v, n=12)
    # all spoken + on-screen text compliance scan
    all_text = []
    for tl in (tl_m, tl_v):
        all_text += [v["text"] for v in tl["voices"]]
        all_text += [s["heading"] for s in tl["shots"]]
        for s in tl["shots"]:
            all_text += list(s["lines"])
    banned_global = sorted({w for w in BANNED
                            for x in all_text if w in x})
    ffprobe_doc = dict(main=qm["ffprobe"], vertical=qv["ffprobe"],
                       probe_tool="ffprobe 4.0.2 (ffprobe-static)",
                       note="Complete -show_streams / -show_format output")
    json.dump(ffprobe_doc, open(os.path.join(OUT, "ffprobe.json"), "w",
                                encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=2)
    # encode commands (reproducible edit decision list)
    encode_txt = """# WB-VIDEO-006 reproducible pipeline (Windows / Python 3.13 / FFmpeg 7.1)
# All paths relative to media/WB-VIDEO-006/
python project/build_tts.py            # edge-tts -> 48 kHz mono WAV per line
python project/make_timeline.py        # real TTS durations -> timeline + SRT
python project/build_audio.py          # original score/SFX/ducking/mix
python project/render.py main          # 1920x1080 @24 -> final_main.mp4
python project/render.py vertical      # 1080x1920 @24 -> final_vertical.mp4
python project/deliver.py              # assemble outbox + QA + hashes
python project/write_reports.py        # quality_report.md / asset-sources.md / README.md

# Audio delivery note: build_audio.py produces 48 kHz WAV working masters.
# The outbox keeps the mandated voiceover.wav as WAV; the other seven masters
# are delivered as lossless FLAC (ffmpeg -c:a flac) to keep the Git push small.
# Decode any .flac back to WAV with: ffmpeg -i x.flac x.wav

# The exact FFmpeg encode command used by render.py (rawvideo pipe):
ffmpeg -y -f rawvideo -pix_fmt rgb24 -s 1920x1080 -r 24 -i - -i mix_main.wav \\
  -c:v libx264 -preset veryfast -crf 26 -pix_fmt yuv420p -r 24 \\
  -c:a aac -b:a 192k -ar 48000 -ac 2 -movflags +faststart -t 274.75 final_main.mp4
ffmpeg -y -f rawvideo -pix_fmt rgb24 -s 1080x1920 -r 24 -i - -i mix_vertical.wav \\
  -c:v libx264 -preset veryfast -crf 26 -pix_fmt yuv420p -r 24 \\
  -c:a aac -b:a 192k -ar 48000 -ac 2 -movflags +faststart -t 50.50 final_vertical.mp4
"""
    open(os.path.join(OUT, "project", "encode_commands.txt"), "w",
         encoding="utf-8", newline="\n").write(encode_txt)
    # sha256 of every delivered file except the list itself
    hashes = []
    for root, dirs, files in os.walk(OUT):
        for fn in sorted(files):
            if fn == "sha256.txt":
                continue
            p = os.path.join(root, fn)
            rel = os.path.relpath(p, OUT).replace("\\", "/")
            hashes.append((sha(p), os.path.getsize(p), rel))
    hashes.sort(key=lambda x: x[2])
    open(os.path.join(OUT, "sha256.txt"), "w", encoding="utf-8",
         newline="\n").write("\n".join(
             "%s  %d  %s" % (h, n, f) for h, n, f in hashes) + "\n")
    manifest = dict(task="WB-VIDEO-006-FINAL-PRODUCTION",
                    files=len(hashes),
                    total_bytes=sum(n for _, n, _ in hashes),
                    main=qm, vertical=qv, subtitles=dict(main=sm, vertical=sv),
                    banned_global_hits=banned_global,
                    contact_sheets=dict(main=os.path.basename(sheet_m),
                                        vertical=os.path.basename(sheet_v)),
                    contact_sheet_times=dict(main=tm, vertical=tv),
                    file_list=[dict(path=f, bytes=n, sha256=h)
                               for h, n, f in hashes])
    json.dump(manifest, open(os.path.join(OUT, "delivery_manifest.json"), "w",
                             encoding="utf-8", newline="\n"),
              ensure_ascii=False, indent=2)
    print(json.dumps(dict(main=qm["streams"], vertical=qv["streams"],
                          main_dur=qm["duration_s"], vert_dur=qv["duration_s"],
                          decode=dict(
                              main=qm["full_video_decode"]["ok"] and
                              qm["full_audio_decode"]["ok"],
                              vertical=qv["full_video_decode"]["ok"] and
                              qv["full_audio_decode"]["ok"]),
                          subs=dict(main=sm, vertical=sv),
                          banned=banned_global, files=len(hashes),
                          total_mb=round(manifest["total_bytes"] / 1e6, 2)),
                     ensure_ascii=False, indent=2), flush=True)
    # expose QA data for the report writer
    json.dump(dict(qm=qm, qv=qv, sm=sm, sv=sv, manifest=manifest),
              open(os.path.join(WORK, "qa_results.json"), "w",
                   encoding="utf-8", newline="\n"), ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
