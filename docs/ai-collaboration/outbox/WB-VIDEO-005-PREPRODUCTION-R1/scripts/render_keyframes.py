#!/usr/bin/env python3
"""Render ORIGINAL motion-graphic key frames for the R1 first cut (S14-S17).

What this produces: 9 still PNG frames at 1920x1080, showing successive
animation states (cards landing, lines fading in, tick appearing). They are
SOURCE ASSETS / design proof, NOT an exported video. No MP4 is written, no
audio is written, no third-party image is used, nothing is downloaded.

All typography is drawn with the locally installed Microsoft YaHei font via
FFmpeg drawtext; all shapes with drawbox. Every frame carries permanent
"模拟界面 / 非真机录屏" or "原创动态图形" labels so it can never be
mistaken for a real product capture.
"""
from __future__ import annotations

import hashlib
import json
import os
import struct
import subprocess
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_deliverables_r1 import R1_OUT

ASSETS = os.path.join(R1_OUT, "assets", "keyframes")
EVID = os.path.join(R1_OUT, "evidence")
FONT = "C\\:/Windows/Fonts/msyh.ttc"
W, H = 1920, 1080

BG = "0xF6F1E8"
INK = "0x33312E"
MUTED = "0x6B655C"
WOOD = "0xC8A98A"
GREEN = "0x7E9B86"
CLAY = "0xD98E5F"
CARD = "0xFFFCF6"
GREY = "0xD9D2C6"

# Each frame = one animation STATE. The sequence is the motion design.
FRAMES = [
    dict(name="s14-state1.png", shot="S14", state="card 1 landed",
         tag="原创动态图形 · 章节卡", title="", badge="",
         lines=[], cards=[("早", 0)], footer="原创图形 · 非产品画面",
         note="三张卡片依次落位：第 1 张"),
    dict(name="s14-state2.png", shot="S14", state="cards 1-2 landed",
         tag="原创动态图形 · 章节卡", title="", badge="",
         lines=[], cards=[("早", 0), ("午", 1)], footer="原创图形 · 非产品画面",
         note="三张卡片依次落位：第 2 张"),
    dict(name="s14-state3.png", shot="S14", state="all 3 cards landed",
         tag="原创动态图形 · 章节卡", title="", badge="",
         lines=[], cards=[("早", 0), ("午", 1), ("晚", 2)], footer="原创图形 · 非产品画面",
         note="三张卡片落位完成 · 方形接下一镜功能编号方形（匹配切）"),
    dict(name="s15-state1.png", shot="S15", state="user line appeared",
         tag="模拟界面 · 非真机录屏", title="功能 01 一句话建档", badge="01",
         lines=[("早饭后的那一次，帮我记上。", 0)], footer="功能对话示例 · 非用药建议 · 模拟界面",
         note="对话行淡入（6 帧）"),
    dict(name="s15-state2.png", shot="S15", state="confirmation line appeared",
         tag="模拟界面 · 非真机录屏", title="功能 01 一句话建档", badge="01",
         lines=[("早饭后的那一次，帮我记上。", 0),
                ("您听听对不对：早饭后的那一次。", 1)],
         footer="功能对话示例 · 非用药建议 · 模拟界面",
         note="复述确认行淡入 · 对应 med_plan_save 的 confirm_text"),
    dict(name="s16-state1.png", shot="S16", state="question line appeared",
         tag="模拟界面 · 非真机录屏", title="功能 02 按餐次查询", badge="02",
         lines=[("早上该吃什么？", 0)], footer="功能对话示例 · 示意数据 · 模拟界面",
         note="只列早饭一组 · 对应 med_plan_list / groupPlans"),
    dict(name="s16-state2.png", shot="S16", state="only breakfast group shown",
         tag="模拟界面 · 非真机录屏", title="功能 02 按餐次查询", badge="02",
         lines=[("早上该吃什么？", 0), ("早饭这一段，就这些。", 1),
                ("午饭 · 晚饭 未展开", 2)],
         footer="功能对话示例 · 示意数据 · 模拟界面",
         note="其余餐次灰掉不显示 · 两条对白各有唯一 cue ID"),
    dict(name="s17-state1.png", shot="S17", state="check-in line appeared",
         tag="模拟界面 · 非真机录屏", title="功能 03 吃过就记上", badge="03",
         lines=[("我吃过了。", 0)], footer="功能对话示例 · 示意数据 · 模拟界面",
         note="打卡输入 · 对应 med_take"),
    dict(name="s17-state2.png", shot="S17", state="tick + gentle feedback appeared",
         tag="模拟界面 · 非真机录屏", title="功能 03 吃过就记上", badge="03",
         lines=[("我吃过了。", 0), ("记上了，慢慢来。", 1)],
         footer="功能对话示例 · 示意数据 · 模拟界面",
         note="勾选动效 6 帧完成 · 温和反馈，不用成功提示电子音"),
]


def esc(text: str) -> str:
    """Keep drawtext text safe: no ASCII colon, comma, quote, percent or backslash."""
    # Spaces are safe inside the single-quoted drawtext value; only the
    # filter-chain separators and quote/percent/backslash are dangerous.
    bad = [c for c in text if c in ":,%'\\\""]
    if bad:
        raise ValueError(f"unsafe drawtext characters {bad} in {text!r}")
    return text


def dt(text: str, size: int, color: str, x: int, y: int) -> str:
    return (f"drawtext=fontfile='{FONT}':text='{esc(text)}':fontsize={size}"
            f":fontcolor={color}:x={x}:y={y}")


def build_filters(f: dict) -> str:
    parts = [f"drawbox=x=0:y=0:w={W}:h=8:color={WOOD}:t=fill"]
    parts.append(dt(f["tag"], 30, MUTED, 120, 60))
    parts.append(dt("药到 · 不用学，只要说", 30, MUTED, 1420, 60))

    cards = f.get("cards", [])
    if cards:
        parts.append(dt("一天还是那些事", 64, INK, 120, 240))
        for label, idx in cards:
            x = 220 + idx * 500
            parts.append(f"drawbox=x={x}:y=400:w=340:h=340:color={CARD}:t=fill")
            parts.append(f"drawbox=x={x}:y=400:w=340:h=10:color={GREEN}:t=fill")
            parts.append(dt(label, 130, INK, x + 110, 480))
        # the not-yet-landed cards are drawn as faint placeholders
        for idx in range(3):
            if idx not in [c[1] for c in f["cards"]]:
                x = 220 + idx * 500
                parts.append(f"drawbox=x={x}:y=400:w=340:h=340:color={GREY}:t=fill")
    else:
        parts.append(f"drawbox=x=120:y=200:w=90:h=90:color={GREEN}:t=fill")
        parts.append(dt(f["badge"], 52, CARD, 145, 218))
        parts.append(dt(f["title"], 60, INK, 240, 210))
        parts.append(f"drawbox=x=120:y=340:w=1680:h=520:color={CARD}:t=fill")
        parts.append(f"drawbox=x=120:y=340:w=1680:h=8:color={CLAY}:t=fill")
        for text, row in f["lines"]:
            color = MUTED if row == 2 else INK
            parts.append(dt(text, 46 if row < 2 else 38, color, 180, 400 + row * 130))
        if len(f["lines"]) >= 2 and f["shot"] == "S17":
            parts.append(f"drawbox=x=180:y=560:w=44:h=44:color={GREEN}:t=fill")

    parts.append(f"drawbox=x=120:y=920:w=1680:h=2:color={WOOD}:t=fill")
    parts.append(dt(f["footer"], 30, MUTED, 120, 950))
    parts.append(dt("WB-VIDEO-005-R1 · 预制作素材 · 非成片", 26, MUTED, 120, 1000))
    parts.append(dt(f["shot"] + " / " + f["state"], 26, MUTED, 1320, 1000))
    return ",".join(parts)


def png_size(path: str) -> tuple[int, int]:
    with open(path, "rb") as f:
        head = f.read(24)
    assert head[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    return struct.unpack(">II", head[16:24])


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main() -> None:
    os.makedirs(ASSETS, exist_ok=True)
    os.makedirs(EVID, exist_ok=True)
    records = []
    for f in FRAMES:
        out = os.path.join(ASSETS, f["name"])
        vf = build_filters(f)
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error",
               "-f", "lavfi", "-i", f"color=c={BG}:s={W}x{H}:d=1",
               "-vf", vf, "-frames:v", "1", "-y", out]
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=90)
        rec = {
            "file": "assets/keyframes/" + f["name"],
            "shot": f["shot"], "animation_state": f["state"],
            "design_note": f["note"],
            "exit_code": p.returncode,
            "stderr": p.stderr.decode("utf-8", "replace").strip()[:400],
            "ffmpeg_filter": vf,
            "command_head": "ffmpeg -f lavfi -i color=<bg> -vf <drawbox+drawtext> "
                            "-frames:v 1 -y <out.png>",
        }
        if p.returncode == 0 and os.path.isfile(out):
            w, h = png_size(out)
            rec.update({"bytes": os.path.getsize(out), "sha256": sha256(out),
                        "width": w, "height": h, "format": "PNG",
                        "kind": "ORIGINAL_MOTION_GRAPHIC_KEYFRAME",
                        "is_video": False, "is_final_film": False})
        else:
            rec.update({"bytes": 0, "sha256": "", "render_failed": True})
        records.append(rec)
        print(f"{f['name']}: exit={p.returncode} bytes={rec['bytes']} "
              f"size={rec.get('width')}x{rec.get('height')}")

    out = {
        "render_id": "R1-KEYFRAME-RENDER-001",
        "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "purpose": "Original editable motion-graphic key frames for the 27 s first cut "
                   "S14-S17. These are animation STATE frames, not an exported video.",
        "tool": "FFmpeg (locally installed 7.1) drawbox + drawtext, no external assets",
        "font": "C:/Windows/Fonts/msyh.ttc (locally installed Microsoft YaHei)",
        "resolution": f"{W}x{H}",
        "frame_count": len(records),
        "frames_ok": sum(1 for r in records if not r.get("render_failed")),
        "mp4_written": 0,
        "audio_written": 0,
        "downloads": 0,
        "third_party_assets": 0,
        "permanent_labels": ["模拟界面 · 非真机录屏", "原创动态图形",
                             "功能对话示例 · 非用药建议", "示意数据",
                             "预制作素材 · 非成片"],
        "records": records,
    }
    path = os.path.join(EVID, "keyframe-render-log.json")
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(json.dumps({"frames_ok": out["frames_ok"], "total": len(records),
                      "mp4_written": 0, "log": path}, ensure_ascii=False))
    assert out["frames_ok"] == len(records), "some key frames failed to render"


if __name__ == "__main__":
    main()
