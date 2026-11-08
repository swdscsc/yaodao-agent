#!/usr/bin/env python3
"""Build EDITABLE source assets for the R1 first cut (S14-S17).

Outputs:
  assets/s14-chapter-cards.svg       original vector, editable text
  assets/s15-mockui-save.svg         labelled mock UI, editable
  assets/s16-mockui-query.svg        labelled mock UI, editable
  assets/s17-mockui-checkin.svg      labelled mock UI, editable
  assets/subtitle-safe-area.svg      dual-track subtitle safe-area diagram
  assets/first-cut-mockui.html       editable HTML with CSS animation preview
  first-cut-timeline.csv             27 s shot-by-shot editing timeline
  first-cut-subtitles.srt            track A (3 narration cues, relative TC)
  first-cut-dialogue.srt             track B (4 dialogue cues, unique cue IDs)
  evidence/asset-source-manifest.json

Everything is original text/vector content. No template, no stock asset, no
download, no video export.
"""
from __future__ import annotations

import csv
import hashlib
import html
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_deliverables_r1 import SHOTS, R1_OUT, R1_EVID, char_count, timecode

ASSETS = os.path.join(R1_OUT, "assets")
EVID = R1_EVID
SEGMENT = ["S14", "S15", "S16", "S17"]
BY_ID = {s["id"]: s for s in SHOTS}
BASE_TIN = BY_ID["S14"]["tin"]  # 96 s
BASE_TOUT = BY_ID["S17"]["tout"]  # 123 s
DURATION = BASE_TOUT - BASE_TIN  # 27 s

PALETTE = {"bg": "#F6F1E8", "card": "#FFFCF6", "ink": "#33312E",
           "muted": "#6B655C", "wood": "#C8A98A", "green": "#7E9B86",
           "clay": "#D98E5F", "grey": "#D9D2C6"}
FONT = "'Microsoft YaHei','Noto Sans SC',sans-serif"


def sha256(p: str) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def svg_frame(title: str, badge: str | None, lines: list[str],
              footer: str, tag: str, note: str) -> str:
    e = html.escape
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" '
        f'viewBox="0 0 1920 1080" role="img" aria-label="{e(title or note)}">',
        f'  <rect width="1920" height="1080" fill="{PALETTE["bg"]}"/>',
        f'  <rect width="1920" height="8" fill="{PALETTE["wood"]}"/>',
        f'  <text x="120" y="80" font-family="{FONT}" font-size="30" '
        f'fill="{PALETTE["muted"]}">{e(tag)}</text>',
        f'  <text x="1420" y="80" font-family="{FONT}" font-size="30" '
        f'fill="{PALETTE["muted"]}">药到 · 不用学，只要说</text>',
    ]
    if badge and title:
        parts += [
            f'  <rect x="120" y="200" width="90" height="90" fill="{PALETTE["green"]}"/>',
            f'  <text x="145" y="262" font-family="{FONT}" font-size="52" '
            f'fill="{PALETTE["card"]}">{e(badge)}</text>',
            f'  <text x="240" y="262" font-family="{FONT}" font-size="60" '
            f'fill="{PALETTE["ink"]}">{e(title)}</text>',
            f'  <rect x="120" y="340" width="1680" height="520" fill="{PALETTE["card"]}"/>',
            f'  <rect x="120" y="340" width="1680" height="8" fill="{PALETTE["clay"]}"/>',
        ]
        for i, line in enumerate(lines):
            color = PALETTE["muted"] if i == 2 else PALETTE["ink"]
            size = 38 if i == 2 else 46
            parts.append(f'  <text x="180" y="{450 + i * 130}" font-family="{FONT}" '
                         f'font-size="{size}" fill="{color}">{e(line)}</text>')
    else:
        parts.append(f'  <text x="120" y="320" font-family="{FONT}" font-size="64" '
                     f'fill="{PALETTE["ink"]}">一天还是那些事</text>')
        for i, label in enumerate(lines):
            x = 220 + i * 500
            parts += [
                f'  <rect x="{x}" y="400" width="340" height="340" fill="{PALETTE["card"]}"/>',
                f'  <rect x="{x}" y="400" width="340" height="10" fill="{PALETTE["green"]}"/>',
                f'  <text x="{x + 110}" y="570" font-family="{FONT}" font-size="130" '
                f'fill="{PALETTE["ink"]}">{e(label)}</text>',
            ]
    parts += [
        f'  <rect x="120" y="920" width="1680" height="2" fill="{PALETTE["wood"]}"/>',
        f'  <text x="120" y="970" font-family="{FONT}" font-size="30" '
        f'fill="{PALETTE["muted"]}">{e(footer)}</text>',
        f'  <text x="120" y="1020" font-family="{FONT}" font-size="26" '
        f'fill="{PALETTE["muted"]}">WB-VIDEO-005-R1 · 预制作素材 · 非成片 · {e(note)}</text>',
        '</svg>',
    ]
    return "\n".join(parts) + "\n"


def build_svgs() -> list[str]:
    specs = [
        ("s14-chapter-cards.svg", None, None, ["早", "午", "晚"],
         "原创图形 · 非产品画面", "原创动态图形 · 章节卡",
         "S14 三张卡片依次落位 · 可编辑矢量"),
        ("s15-mockui-save.svg", "功能 01 一句话建档", "01",
         ["早饭后的那一次，帮我记上。", "您听听对不对：早饭后的那一次。"],
         "功能对话示例 · 非用药建议 · 模拟界面", "模拟界面 · 非真机录屏",
         "S15 复述确认 · 对应 med_plan_save"),
        ("s16-mockui-query.svg", "功能 02 按餐次查询", "02",
         ["早上该吃什么？", "早饭这一段，就这些。", "午饭 · 晚饭 未展开"],
         "功能对话示例 · 示意数据 · 模拟界面", "模拟界面 · 非真机录屏",
         "S16 按餐次分组 · 对应 med_plan_list"),
        ("s17-mockui-checkin.svg", "功能 03 吃过就记上", "03",
         ["我吃过了。", "记上了，慢慢来。"],
         "功能对话示例 · 示意数据 · 模拟界面", "模拟界面 · 非真机录屏",
         "S17 打卡与温和反馈 · 对应 med_take"),
    ]
    out = []
    for name, title, badge, lines, footer, tag, note in specs:
        p = os.path.join(ASSETS, name)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(svg_frame(title, badge, lines, footer, tag, note))
        out.append(p)
    return out


def build_safe_area() -> str:
    p = os.path.join(ASSETS, "subtitle-safe-area.svg")
    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" '
        'viewBox="0 0 1920 1080">',
        f'<rect width="1920" height="1080" fill="{PALETTE["bg"]}"/>',
        # left/right 10% safe margins
        f'<rect x="0" y="0" width="192" height="1080" fill="{PALETTE["grey"]}" '
        'fill-opacity="0.55"/>',
        f'<rect x="1728" y="0" width="192" height="1080" fill="{PALETTE["grey"]}" '
        'fill-opacity="0.55"/>',
        # 0.72H dialogue track, 0.86H narration track, 0.90H hard limit
        f'<rect x="192" y="720" width="1536" height="60" fill="{PALETTE["green"]}" '
        'fill-opacity="0.28"/>',
        f'<rect x="192" y="870" width="1536" height="70" fill="{PALETTE["clay"]}" '
        'fill-opacity="0.28"/>',
        f'<line x1="0" y1="972" x2="1920" y2="972" stroke="{PALETTE["clay"]}" '
        'stroke-width="4" stroke-dasharray="16 12"/>',
    ]
    for y, label in ((760, "画内对白轨 0.72 H · 与旁白不同行"),
                     (915, "主旁白轨 0.86 H · 字号 >= 40 px · 单行 <= 20 字"),
                     (1010, "硬限制 0.90 H · 基线不越过 0.88 H")):
        lines.append(f'<text x="220" y="{y}" font-family="{FONT}" font-size="36" '
                     f'fill="{PALETTE["ink"]}">{html.escape(label)}</text>')
    lines.append(f'<text x="220" y="120" font-family="{FONT}" font-size="46" '
                 f'fill="{PALETTE["ink"]}">字幕安全区示意 · 原创图示 · 非成片</text>')
    lines.append('</svg>')
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    return p


def build_html() -> str:
    p = os.path.join(ASSETS, "first-cut-mockui.html")
    doc = """<!DOCTYPE html>
<!-- WB-VIDEO-005-PREPRODUCTION-R1 | EDITABLE SOURCE, NOT AN EXPORTED VIDEO.
     Every screen below is a LABELLED MOCK UI. No real device capture. -->
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>药到 · 首段 S14–S17 模拟界面（可编辑源文件）</title>
<style>
  :root { --bg:#F6F1E8; --card:#FFFCF6; --ink:#33312E; --muted:#6B655C;
          --wood:#C8A98A; --green:#7E9B86; --clay:#D98E5F; --grey:#D9D2C6; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--ink);
         font-family:"Microsoft YaHei","Noto Sans SC",sans-serif; }
  .note { max-width:1100px; margin:28px auto 8px; padding:14px 18px;
          border-left:6px solid var(--clay); background:var(--card); font-size:15px; }
  .scene { position:relative; width:960px; height:540px; margin:22px auto;
           background:var(--bg); border-top:4px solid var(--wood); overflow:hidden; }
  .tag { position:absolute; top:22px; left:60px; font-size:15px; color:var(--muted); }
  .brand { position:absolute; top:22px; right:60px; font-size:15px; color:var(--muted); }
  .footer { position:absolute; bottom:26px; left:60px; font-size:15px; color:var(--muted); }
  .stamp { position:absolute; bottom:8px; left:60px; font-size:12px; color:var(--muted); }
  h2 { position:absolute; top:100px; left:60px; font-size:30px; font-weight:600; }
  .num { display:inline-block; width:45px; height:45px; line-height:45px;
         text-align:center; background:var(--green); color:var(--card);
         font-size:26px; margin-right:12px; vertical-align:middle; }
  .panel { position:absolute; left:60px; top:170px; width:840px; height:260px;
           background:var(--card); border-top:4px solid var(--clay); padding:22px 30px; }
  .line { font-size:23px; margin:18px 0; opacity:0; animation:fade .35s ease forwards; }
  .line:nth-child(1){animation-delay:.1s} .line:nth-child(2){animation-delay:.7s}
  .line:nth-child(3){animation-delay:1.3s; color:var(--muted); font-size:19px}
  @keyframes fade { to { opacity:1 } }
  .cards { position:absolute; top:200px; left:110px; display:flex; gap:40px; }
  .card { width:170px; height:170px; background:var(--card);
          border-top:5px solid var(--green); font-size:65px; text-align:center;
          line-height:170px; opacity:0; animation:land .4s ease forwards; }
  .card:nth-child(1){animation-delay:.1s} .card:nth-child(2){animation-delay:.6s}
  .card:nth-child(3){animation-delay:1.1s}
  @keyframes land { from{transform:translateY(-40px);opacity:0} to{transform:none;opacity:1} }
  .tick { display:inline-block; width:22px; height:22px; background:var(--green);
          margin-right:10px; opacity:0; animation:fade .2s ease 1.1s forwards; }
</style>
</head>
<body>
<div class="note">
  <strong>这是可编辑的原创模拟界面源文件，不是成片，也不是真机录屏。</strong><br>
  对应首段 S14–S17（27 s）。动画仅为状态预览：卡片落位、逐行淡入、勾选动效。<br>
  每一屏都常驻「模拟界面 · 非真机录屏」；涉及对白的屏另标「功能对话示例 · 非用药建议」。<br>
  本文件不含任何外部资源、脚本请求或联网调用；0 个 MP4、0 个音频文件。
</div>

<div class="scene">
  <div class="tag">原创动态图形 · 章节卡</div><div class="brand">药到 · 不用学，只要说</div>
  <h2 style="top:120px">一天还是那些事</h2>
  <div class="cards"><div class="card">早</div><div class="card">午</div><div class="card">晚</div></div>
  <div class="footer">原创图形 · 非产品画面</div>
  <div class="stamp">S14 · 三张卡片依次落位 · 预制作素材 · 非成片</div>
</div>

<div class="scene">
  <div class="tag">模拟界面 · 非真机录屏</div><div class="brand">药到 · 不用学，只要说</div>
  <h2><span class="num">01</span>功能 01 一句话建档</h2>
  <div class="panel"><div class="line">早饭后的那一次，帮我记上。</div>
    <div class="line">您听听对不对：早饭后的那一次。</div></div>
  <div class="footer">功能对话示例 · 非用药建议 · 模拟界面</div>
  <div class="stamp">S15 · 复述确认 · 对应 med_plan_save</div>
</div>

<div class="scene">
  <div class="tag">模拟界面 · 非真机录屏</div><div class="brand">药到 · 不用学，只要说</div>
  <h2><span class="num">02</span>功能 02 按餐次查询</h2>
  <div class="panel"><div class="line">早上该吃什么？</div>
    <div class="line">早饭这一段，就这些。</div>
    <div class="line">午饭 · 晚饭 未展开</div></div>
  <div class="footer">功能对话示例 · 示意数据 · 模拟界面</div>
  <div class="stamp">S16 · 按餐次分组 · 对应 med_plan_list</div>
</div>

<div class="scene">
  <div class="tag">模拟界面 · 非真机录屏</div><div class="brand">药到 · 不用学，只要说</div>
  <h2><span class="num">03</span>功能 03 吃过就记上</h2>
  <div class="panel"><div class="line">我吃过了。</div>
    <div class="line"><span class="tick"></span>记上了，慢慢来。</div></div>
  <div class="footer">功能对话示例 · 示意数据 · 模拟界面</div>
  <div class="stamp">S17 · 打卡与温和反馈 · 对应 med_take</div>
</div>
</body>
</html>
"""
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(doc)
    return p


def srt_time(sec: float) -> str:
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_timeline_and_subtitles() -> dict:
    rows, narr, dial = [], [], []
    for s in (BY_ID[k] for k in SEGMENT):
        tin = s["tin"] - BASE_TIN
        tout = s["tout"] - BASE_TIN
        if s["narration"]:
            start = tin + 0.4
            est = max(2.0, min(char_count(s["narration"]) / 4.0, (tout - tin) - 0.9))
            narr.append(dict(cue_id=s["nid"], shot=s["id"],
                             start=round(start, 2), end=round(min(start + est, tout - 0.2), 2),
                             text=s["narration"]))
        for idx, (text, off, dur) in enumerate(s["dialogue"], 1):
            start = tin + off
            dial.append(dict(cue_id=f"{s['id']}-D{idx:02d}", shot=s["id"],
                             start=round(start, 2), end=round(min(start + dur, tout - 0.2), 2),
                             text=text))
        rows.append({
            "shot_id": s["id"], "relative_in_s": tin, "relative_out_s": tout,
            "duration_s": tout - tin,
            "master_timecode_in": timecode(s["tin"]),
            "master_timecode_out": timecode(s["tout"]),
            "purpose": s["purpose"], "visual": s["visual"],
            "on_screen_text": s["screen"],
            "truth_label": s["truth"], "asset_source": s["source"],
            "narration_id": s["nid"], "narration_text": s["narration"],
            "dialogue_cue_ids": ",".join(
                f"{s['id']}-D{i:02d}" for i in range(1, len(s["dialogue"]) + 1)),
            "transition": s["trans"], "sound_design": s["music"],
            "edit_rhythm": s["rhythm"], "subtitle_status": "DRAFT_NOT_BURNED_IN",
            "video_exported": "NO",
        })
    with open(os.path.join(R1_OUT, "first-cut-timeline.csv"), "w",
              encoding="utf-8", newline="") as f:
        cols = list(rows[0].keys())
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

    def write_srt(path: str, cues: list[dict]) -> None:
        with open(path, "w", encoding="utf-8", newline="") as f:
            for i, c in enumerate(cues, 1):
                f.write(f"{i}\n{srt_time(c['start'])} --> {srt_time(c['end'])}\n"
                        f"{c['text']}\n\n")

    write_srt(os.path.join(R1_OUT, "first-cut-subtitles.srt"), narr)
    write_srt(os.path.join(R1_OUT, "first-cut-dialogue.srt"), dial)
    return {"rows": rows, "narration": narr, "dialogue": dial}


def main() -> None:
    os.makedirs(ASSETS, exist_ok=True)
    os.makedirs(EVID, exist_ok=True)
    files = build_svgs() + [build_safe_area(), build_html()]
    tl = build_timeline_and_subtitles()
    extra = [os.path.join(R1_OUT, "first-cut-timeline.csv"),
             os.path.join(R1_OUT, "first-cut-subtitles.srt"),
             os.path.join(R1_OUT, "first-cut-dialogue.srt")]
    kf_dir = os.path.join(ASSETS, "keyframes")
    kfs = [os.path.join(kf_dir, f) for f in sorted(os.listdir(kf_dir))
           if f.lower().endswith(".png")]

    manifest = {
        "manifest_id": "R1-ASSET-SOURCE-001",
        "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "segment": "S14-S17", "duration_s": DURATION,
        "policy": "Every asset is ORIGINAL, locally generated, editable, and explicitly "
                  "labelled as a mock UI or original graphic. No stock footage, no "
                  "third-party template, no download, no real device capture, no MP4.",
        "sources": {
            "typography": "locally installed Microsoft YaHei / Noto Sans SC",
            "vector": "hand-written SVG in this repository",
            "keyframes": "FFmpeg 7.1 drawbox + drawtext, original shapes/text",
            "html": "hand-written HTML/CSS in this repository",
            "music_sfx": "NONE PRODUCED THIS ROUND (see music-sfx-plan.md)",
            "narration_audio": "NONE PRODUCED THIS ROUND",
        },
        "counts": {"svg": 5, "html": 1, "png_keyframes": len(kfs),
                   "timeline_rows": len(tl["rows"]),
                   "narration_cues": len(tl["narration"]),
                   "dialogue_cues": len(tl["dialogue"]), "mp4": 0, "audio": 0},
        "files": [{"path": os.path.relpath(p, R1_OUT).replace("\\", "/"),
                   "bytes": os.path.getsize(p), "sha256": sha256(p),
                   "kind": ("png_keyframe" if p.lower().endswith(".png") else
                            os.path.splitext(p)[1].lstrip("."))}
                  for p in files + extra + kfs],
    }
    with open(os.path.join(EVID, "asset-source-manifest.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps({
        "svg_html_files": len(files), "png_keyframes": len(kfs),
        "timeline_rows": len(tl["rows"]),
        "narration_cues": len(tl["narration"]), "dialogue_cues": len(tl["dialogue"]),
        "mp4": 0,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
