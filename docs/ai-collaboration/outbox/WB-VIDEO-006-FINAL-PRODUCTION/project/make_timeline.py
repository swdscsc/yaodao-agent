# -*- coding: utf-8 -*-
"""Build the FINAL timeline from MEASURED TTS durations (not estimates).

Every subtitle cue is derived from the exact [start,end] of the real WAV that
will be placed on the audio track, so subtitles cannot end before the voice.
Writes: timeline_main.json, timeline_vertical.json, final_main.srt,
final_vertical.srt, subtitle_events.json
"""
from __future__ import annotations
import json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import data

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
IDX = json.load(open(os.path.join(WORK, "tts_index.json"), encoding="utf-8"))

NARR = dict(data.NARRATION)
VNArr = dict(data.VERTICAL_NARRATION)
DLG = {c[0]: c for c in data.DIALOGUE}
VDLG = {c[0]: c for c in data.VERTICAL_DIALOGUE}


def srt_ts(s: float) -> str:
    ms = int(round(s * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    sec, ms = divmod(ms, 1000)
    return "%02d:%02d:%02d,%03d" % (h, m, sec, ms)


def build(shots, narr_map, dlg_map, *, vertical: bool, target_max=None):
    lead = 0.16 if vertical else 0.55
    gap_v = 0.12 if vertical else 0.38
    tail = 0.14 if vertical else 0.55
    out_shots, voices, subs = [], [], []
    cursor = 0.0
    for row in shots:
        if vertical:
            sid, plan, kind, badge, nid, cues, heading, lines = row
            chapter = "竖屏浓缩叙事"
        else:
            sid, chapter, plan, kind, badge, nid, cues, heading, lines = row
        seq = []                       # ordered voice events inside this shot
        t = lead
        if nid:
            d = IDX[nid]["duration_s"]
            seq.append((nid, "narration", t, t + d, narr_map[nid]))
            t += d + gap_v
        for cid in cues:
            d = IDX[cid]["duration_s"]
            seq.append((cid, "dialogue", t, t + d, dlg_map[cid][2]))
            t += d + gap_v
        needed = (t - gap_v if seq else 0.0) + tail + lead * 0.5
        dur = max(plan, needed)
        dur = math.ceil(dur * 4) / 4.0          # align to 1/4 s (6 frames @24fps)
        start = cursor
        pad_in = 0.02 if vertical else 0.06
        pad_out = 0.02 if vertical else 0.10
        for cid, typ, a, b, text in seq:
            voices.append(dict(id=cid, type=typ, shot=sid,
                               start=round(start + a, 4),
                               end=round(start + b, 4),
                               text=text,
                               wav=IDX[cid]["wav"],
                               duration_s=IDX[cid]["duration_s"]))
            subs.append(dict(id=cid, type=typ, shot=sid,
                             start=round(start + a - pad_in, 4),
                             end=round(start + b + pad_out, 4), text=text))
        out_shots.append(dict(id=sid, chapter=chapter, kind=kind, badge=badge,
                              heading=heading, lines=lines,
                              narration=nid, dialogues=cues,
                              start=round(start, 4), end=round(start + dur, 4),
                              dur=round(dur, 4), planned_dur=plan))
        cursor += dur
    total = round(cursor, 4)
    if target_max and total > target_max:
        raise RuntimeError("timeline %.2fs exceeds %.2fs" % (total, target_max))
    # hard assertion: no two subtitle events overlap
    ordered = sorted(subs, key=lambda e: e["start"])
    overlaps = []
    for a, b in zip(ordered, ordered[1:]):
        if b["start"] < a["end"] - 1e-3:
            overlaps.append((a["id"], b["id"], a["end"], b["start"]))
    assert not overlaps, "subtitle overlap: %r" % overlaps
    # hard assertion: subtitle covers its voice
    vd = {v["id"]: v for v in voices}
    for s in subs:
        v = vd[s["id"]]
        assert s["start"] <= v["start"] and s["end"] >= v["end"], s["id"]
    return dict(fps=data.FPS, sr=data.SR,
                width=1080 if vertical else 1920,
                height=1920 if vertical else 1080,
                duration_s=total, shots=out_shots, voices=voices,
                subtitles=subs, overlaps=overlaps,
                subtitle_events=len(subs))


def write_srt(tl, path):
    lines = []
    for i, e in enumerate(sorted(tl["subtitles"], key=lambda x: x["start"]), 1):
        lines += [str(i), "%s --> %s" % (srt_ts(e["start"]), srt_ts(e["end"])),
                  e["text"], ""]
    open(path, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
    return len(lines)


def main():
    main_tl = build(data.SHOTS, NARR, DLG, vertical=False, target_max=300.0)
    vert_tl = build(data.VERTICAL_SHOTS, VNArr, VDLG, vertical=True, target_max=60.0)
    for name, tl in (("timeline_main.json", main_tl),
                     ("timeline_vertical.json", vert_tl)):
        json.dump(tl, open(os.path.join(WORK, name), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
    json.dump(dict(main=main_tl["subtitles"], vertical=vert_tl["subtitles"]),
              open(os.path.join(WORK, "subtitle_events.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print("MAIN  dur=%.2fs shots=%d voices=%d subs=%d overlaps=%d" % (
        main_tl["duration_s"], len(main_tl["shots"]), len(main_tl["voices"]),
        main_tl["subtitle_events"], len(main_tl["overlaps"])))
    print("VERT  dur=%.2fs shots=%d voices=%d subs=%d overlaps=%d" % (
        vert_tl["duration_s"], len(vert_tl["shots"]), len(vert_tl["voices"]),
        vert_tl["subtitle_events"], len(vert_tl["overlaps"])))
    # SRT copies are written later into the delivery dir by encode.py as well
    write_srt(main_tl, os.path.join(WORK, "final_main.srt"))
    write_srt(vert_tl, os.path.join(WORK, "final_vertical.srt"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
