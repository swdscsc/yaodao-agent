# -*- coding: utf-8 -*-
"""WB-VIDEO-006 renderer: original motion graphics + simulated UI + burned-in
subtitles, encoded to real H.264/AAC MP4 through an FFmpeg rawvideo pipe.

Everything drawn here is ORIGINAL artwork produced by this script. No real
device footage exists in the project; every product screen carries a persistent
"模拟界面 / 非真机录屏 / 示意数据" label. Nothing claims medical efficacy.

Usage:
  python render.py main      -> final_main.mp4
  python render.py vertical  -> final_vertical.mp4
"""
from __future__ import annotations
import json, math, os, subprocess, sys, time
from functools import lru_cache
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import data

FFMPEG = r"C:\Users\asus\AppData\Roaming\npm\ffmpeg.exe"
FONT_R = r"C:\Windows\Fonts\msyh.ttc"
FONT_B = r"C:\Windows\Fonts\msyhbd.ttc"

INK = (46, 42, 38)
MUTED = (128, 118, 106)
LIGHT = (250, 246, 239)
WHITE = (255, 253, 249)
ACCENT = (214, 92, 58)
ACCENT2 = (232, 172, 74)
GREEN = (92, 138, 120)
BLUE = (143, 169, 196)
PAPER = (255, 252, 245)
SHADOW = (214, 201, 181)
LINE = (226, 216, 200)

PALETTES = {
    "warm":   ((252, 247, 238), (233, 220, 201), (255, 226, 178)),
    "cool":   ((247, 247, 243), (222, 228, 228), (206, 226, 229)),
    "bright": ((255, 251, 242), (243, 229, 205), (255, 233, 190)),
    "dusk":   ((250, 238, 224), (226, 204, 186), (255, 205, 158)),
    "neutral": ((252, 250, 245), (236, 232, 224), (246, 238, 224)),
}

KIND_PALETTE = {
    "table": "warm", "paper": "warm", "clock": "warm", "call": "cool",
    "details": "warm", "chat": "cool", "table_wide": "warm", "voice": "bright",
    "reply": "neutral", "brand": "bright", "device_outline": "neutral",
    "principles": "neutral", "wave": "neutral", "meals": "bright",
    "ui_save": "neutral", "ui_list": "neutral", "ui_check": "neutral",
    "ui_report": "neutral", "ui_clock": "neutral", "ui_reminder": "neutral",
    "photo": "warm", "ui_question": "neutral", "ui_confirm": "neutral",
    "day": "warm", "commute": "cool", "still_life": "warm",
    "ui_refusal": "neutral", "safety_list": "neutral", "table_warm": "dusk",
    "closing": "bright",
}


def ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def rgb_lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# --------------------------------------------------------------------------
# Layout: native 16:9 and 9:16 designs, NOT a crop
# --------------------------------------------------------------------------
class Layout:
    def __init__(self, W, H, vertical):
        self.W, self.H, self.V = W, H, vertical
        self.s = W / (1080 if vertical else 1920)
        self.margin = int(W * (0.055 if vertical else 0.05))
        self.badge_y = int(H * (0.025 if vertical else 0.035))
        self.footer_y = int(H * (0.965 if vertical else 0.958))
        self.sub_y = int(H * (0.755 if vertical else 0.775))
        self.sub_h = int(H * (0.115 if vertical else 0.145))
        self.body_top = int(H * (0.155 if vertical else 0.155))
        self.body_bot = int(H * (0.725 if vertical else 0.735))
        self.f_sub = int(W * (0.046 if vertical else 0.0245))
        self.f_badge = int(W * (0.021 if vertical else 0.0105))
        self.f_footer = int(W * (0.0185 if vertical else 0.0100))
        self.f_title = int(W * (0.066 if vertical else 0.036))
        self.f_body = int(W * (0.040 if vertical else 0.0215))
        self.card_w = W * (0.86 if vertical else 0.64)
        self.card_h = H * (0.44 if vertical else 0.52)

    def X(self, f):
        return int(self.W * f)

    def Y(self, f):
        return int(self.H * f)


@lru_cache(maxsize=1024)
def font(size, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT_R, max(8, int(size)))


@lru_cache(maxsize=2048)
def text_img(text, size, color, bold=False, maxw=0, stroke=0, tracking=1.22):
    f = font(size, bold)
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur); cur = ""; continue
        trial = cur + ch
        if maxw and f.getlength(trial) > maxw and cur:
            lines.append(cur); cur = ch
        else:
            cur = trial
    if cur:
        lines.append(cur)
    if not lines:
        lines = [""]
    lh = int(size * tracking)
    w = max(int(f.getlength(s)) for s in lines) + 8 + stroke * 2
    h = lh * len(lines) + 8 + stroke * 2
    im = Image.new("RGBA", (max(1, w), max(1, h)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, s in enumerate(lines):
        d.text((4 + stroke, 4 + i * lh + stroke), s, font=f, fill=color,
               stroke_width=stroke, stroke_fill=(255, 255, 255, 255))
    return im


def put(im, text, x, y, size, color=INK, bold=False, maxw=0, anchor="lt",
        opacity=1.0, stroke=0):
    ti = text_img(text, int(size), color, bool(bold), int(maxw), int(stroke))
    w, h = ti.size
    ax = x - (w / 2 if "m" in anchor[:1] or anchor[0] == "m" else (w if anchor[0] == "r" else 0))
    ay = y - (h / 2 if anchor[1] == "m" else (h if anchor[1] == "b" else 0))
    if opacity < 0.999:
        ti = ti.copy()
        ti.putalpha(ti.getchannel("A").point(lambda v: int(v * opacity)))
    im.paste(ti, (int(ax), int(ay)), ti)


def rr(d, box, r, fill=None, outline=None, width=1):
    d.rounded_rectangle(tuple(int(v) for v in box), radius=int(r), fill=fill,
                        outline=outline, width=width)


def card(im, L, box, r=None, fill=PAPER, outline=LINE, shadow=True):
    d = ImageDraw.Draw(im)
    if shadow:
        off = int(9 * L.s)
        rr(d, (box[0] + off, box[1] + off, box[2] + off, box[3] + off),
           r or int(18 * L.s), SHADOW)
    rr(d, box, r or int(18 * L.s), fill, outline, max(1, int(1.5 * L.s)))


def make_base(pal, W, H):
    """Pre-rendered 1.18x background: gradient + light blooms + fine grain."""
    bw, bh = int(W * 1.18), int(H * 1.18)
    top, bot, glow = PALETTES[pal]
    yy = np.linspace(0, 1, bh, dtype=np.float32)[:, None, None]
    xx = np.linspace(0, 1, bw, dtype=np.float32)[None, :, None]
    a = np.array(top, dtype=np.float32)[None, None, :]
    b = np.array(bot, dtype=np.float32)[None, None, :]
    arr = a + (b - a) * (yy * 0.75 + xx * 0.25)
    for cx, cy, rad, strength in ((0.78, 0.22, 0.48, 0.42),
                                  (0.18, 0.78, 0.42, 0.18),
                                  (0.50, 0.10, 0.34, 0.12)):
        d2 = ((xx - cx) ** 2 + (yy - cy) ** 2) / (rad ** 2)
        arr += (np.array(glow, dtype=np.float32)[None, None, :] - arr) * \
               np.clip(1 - d2, 0, 1) * strength
    rng = np.random.default_rng(20261109)
    arr += rng.normal(0, 1.7, (bh, bw, 1)).astype(np.float32)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


_BASES = {}
_FLAT = {}


def ken_burns(L, pal, p, t, phase=0.0):
    if pal not in _BASES:
        _BASES[pal] = make_base(pal, L.W, L.H)
    base = _BASES[pal]
    bw, bh = base.size
    zoom = 1.0 + 0.055 * ease(p)
    cw, ch = bw / zoom * 0.94, bh / zoom * 0.94
    dx = (bw - cw) * (0.5 + 0.42 * math.sin(phase + t * 0.10))
    dy = (bh - ch) * (0.5 + 0.38 * math.cos(phase * 0.7 + t * 0.08))
    crop = base.crop((int(dx), int(dy), int(dx + cw), int(dy + ch)))
    return crop.resize((L.W, L.H), Image.BILINEAR)


# --------------------------------------------------------------------------
# Small reusable drawing pieces
# --------------------------------------------------------------------------
def pillbox(d, L, x, y, w, h, color, bob=0.0, label_lines=2):
    y += bob
    r = int(12 * L.s)
    rr(d, (x - w / 2 + 7 * L.s, y - h / 2 + 7 * L.s,
           x + w / 2 + 7 * L.s, y + h / 2 + 7 * L.s), r, SHADOW)
    rr(d, (x - w / 2, y - h / 2, x + w / 2, y + h / 2), r, color, rgb_lerp(color, INK, .18), 2)
    rr(d, (x - w * .38, y - h * .06, x + w * .38, y + h * .30), int(6 * L.s), PAPER)
    for i in range(label_lines):
        ly = y - h * .005 + i * h * .085
        d.line((x - w * .30, ly, x + w * (.30 - i * .09), ly),
               fill=(206, 199, 187), width=max(2, int(3 * L.s)))


def waveform(d, L, cx, cy, w, h, t, amp=1.0, color=ACCENT, bars=34, phase=0.0):
    for i in range(bars):
        f = i / (bars - 1)
        a = (0.22 + 0.78 * abs(math.sin(f * 6.2 + t * 3.1 + phase)) *
             (0.55 + 0.45 * math.sin(f * 2.4 + t * 1.7))) * amp
        bh = max(3, h * a)
        x = cx - w / 2 + f * w
        bw = max(2, int(w / bars * .48))
        rr(d, (x - bw / 2, cy - bh / 2, x + bw / 2, cy + bh / 2),
           bw / 2, color)


def ui_frame(im, L, heading, p, t, *, accent=ACCENT, compact=False):
    """Simulated product screen shell. Never presented as a real recording."""
    d = ImageDraw.Draw(im)
    cw = L.card_w
    ch = L.card_h * (0.82 if compact else 1.0)
    x0 = (L.W - cw) / 2
    y0 = L.body_top + (L.body_bot - L.body_top - ch) / 2
    slide = (1 - ease(min(1.0, p / .22))) * (L.W * .10)
    x0 += slide
    card(im, L, (x0, y0, x0 + cw, y0 + ch), fill=PAPER)
    # device status strip
    strip = int(52 * L.s)
    rr(d, (x0, y0, x0 + cw, y0 + strip), int(18 * L.s), (245, 240, 231))
    d.rectangle((x0, y0 + strip - 6, x0 + cw, y0 + strip), fill=(245, 240, 231))
    for i, c in enumerate(((214, 92, 58), (232, 172, 74), (92, 138, 120))):
        cx = x0 + (26 + i * 24) * L.s
        d.ellipse((cx - 5 * L.s, y0 + strip / 2 - 5 * L.s,
                   cx + 5 * L.s, y0 + strip / 2 + 5 * L.s), fill=c)
    put(im, "模拟界面 · 示意数据", x0 + cw - 20 * L.s, y0 + strip / 2,
        L.f_badge * .85, MUTED, anchor="rm", maxw=cw * .5)
    if heading:
        put(im, heading, x0 + 34 * L.s, y0 + strip + 26 * L.s,
            L.f_body * (1.05 if L.V else 1.0), INK, bold=True,
            maxw=cw - 60 * L.s, opacity=ease(min(1.0, p / .18)))
    return d, x0, y0, cw, ch, strip


def list_row(d, im, L, x0, y, w, h, text, *, active=False, appear=1.0,
             num=None):
    if appear <= 0:
        return
    dx = (1 - ease(appear)) * w * .12
    x0 += dx
    rr(d, (x0, y, x0 + w, y + h), int(12 * L.s),
       (252, 238, 224) if active else (248, 246, 241),
       ACCENT if active else LINE, max(1, int(2 * L.s)))
    if num is not None:
        rr(d, (x0 + 12 * L.s, y + h * .24, x0 + 12 * L.s + h * .52,
               y + h * .76), int(7 * L.s), ACCENT if active else (222, 216, 205))
        put(im, str(num), x0 + 12 * L.s + h * .26, y + h * .5, h * .34,
            WHITE if active else MUTED, bold=True, anchor="mm")
        tx = x0 + 24 * L.s + h * .52
    else:
        tx = x0 + 24 * L.s
    put(im, text, tx, y + h * .5, L.f_body * (.92 if L.V else .84),
        INK if active else MUTED, anchor="lm", maxw=w - (tx - x0) - 20 * L.s,
        opacity=ease(appear))


# --------------------------------------------------------------------------
# Shot renderers
# --------------------------------------------------------------------------
def draw_kind(im, L, shot, p, t):
    k = shot["kind"]
    d = ImageDraw.Draw(im)
    lines = shot["lines"]
    V = L.V
    # ---------- everyday-life dramatizations ----------
    if k in ("table", "table_wide", "table_warm", "still_life"):
        ty = L.Y(.66 if not V else .60)
        d.rectangle((0, ty, L.W, L.H), fill=(223, 201, 172))
        d.line((0, ty, L.W, ty), fill=(246, 231, 208), width=max(2, int(4 * L.s)))
        gl = L.X(.74) + math.sin(t * .22) * L.X(.03)
        d.ellipse((gl - L.W * .22, ty - L.H * .42, gl + L.W * .22, ty + L.H * .02),
                  fill=(240, 222, 194))
        ws = L.W * (.20 if V else .115)
        hs = L.H * (.105 if V else .145)
        xs = (.26, .50, .74) if V else (.34, .50, .66)
        cols = (ACCENT2, BLUE, GREEN)
        for i, (xf, c) in enumerate(zip(xs, cols)):
            bob = math.sin(t * .9 + i * 1.7) * 3 * L.s
            pillbox(d, L, L.X(xf), ty - hs * .46 + bob, ws, hs, c, 0, 2)
        # reading glasses
        gx, gy = L.X(.80 if V else .79), ty - hs * .25
        gr = L.W * (.052 if V else .034)
        for ox in (-gr * 1.15, gr * 1.15):
            d.ellipse((gx + ox - gr, gy - gr, gx + ox + gr, gy + gr),
                      outline=(150, 138, 122), width=max(2, int(4 * L.s)))
        d.line((gx - gr * .15, gy, gx + gr * .15, gy), fill=(150, 138, 122),
               width=max(2, int(4 * L.s)))
        # handwritten note with a crossed-out line
        pw, ph = L.W * (.40 if V else .25), L.H * (.15 if V else .20)
        px, py = L.X(.24 if V else .20), ty - ph * .85
        card(im, L, (px - pw / 2, py - ph / 2, px + pw / 2, py + ph / 2), fill=PAPER)
        for i in range(3):
            ly = py - ph * .28 + i * ph * .26
            d.line((px - pw * .38, ly, px + pw * (.36 - i * .10), ly),
                   fill=(196, 187, 172), width=max(2, int(3 * L.s)))
        cross = ease(min(1.0, max(0.0, (p - .28) / .32)))
        if cross > 0:
            y2 = py - ph * .28 + ph * .26
            d.line((px - pw * .38, y2, px - pw * .38 + pw * .52 * cross, y2),
                   fill=ACCENT, width=max(2, int(4 * L.s)))
        if lines:
            put(im, lines[0], L.W / 2, L.Y(.16 if V else .18), L.f_body,
                MUTED, anchor="mt", maxw=L.W - 2 * L.margin,
                opacity=ease(min(1.0, p / .3)))
        if k == "still_life":
            rr(d, (L.X(.60), ty - hs * 1.75, L.X(.60) + ws * .8, ty - hs * .55),
               int(14 * L.s), (70, 68, 64), (48, 46, 42), 3)
            rr(d, (L.X(.60) + 8 * L.s, ty - hs * 1.66,
                   L.X(.60) + ws * .8 - 8 * L.s, ty - hs * .64),
               int(8 * L.s), (246, 241, 231))
            put(im, "你 说 一 句", L.X(.60) + ws * .4, ty - hs * 1.14,
                L.f_badge, MUTED, anchor="mm")
        return

    if k == "paper":
        pw, ph = L.W * (.78 if V else .60), L.H * (.48 if V else .60)
        x0, y0 = (L.W - pw) / 2, L.body_top + (L.body_bot - L.body_top - ph) / 2
        card(im, L, (x0, y0, x0 + pw, y0 + ph), fill=PAPER)
        for i, s in enumerate(("早", "午", "晚")):
            ly = y0 + ph * (.22 + i * .24)
            put(im, s, x0 + pw * .14, ly, L.f_title * .72, INK, bold=True,
                anchor="lm", opacity=ease(min(1., (p - i * .10) / .25)))
            d.line((x0 + pw * .30, ly, x0 + pw * (.86 - i * .08), ly),
                   fill=(206, 198, 184), width=max(2, int(4 * L.s)))
            d.line((x0 + pw * (.42 + i * .06), ly - ph * .035,
                    x0 + pw * (.42 + i * .06), ly + ph * .035),
                   fill=(226, 218, 204), width=max(2, int(3 * L.s)))
        cross = ease(min(1., max(0., (p - .35) / .35)))
        ly = y0 + ph * .46
        d.line((x0 + pw * .30, ly, x0 + pw * .30 + pw * .5 * cross, ly),
               fill=ACCENT, width=max(3, int(7 * L.s)))
        fy = y0 + ph * (.18 + .24 * min(2., p * 3.2))
        rr(d, (x0 + pw * .10, fy - ph * .05, x0 + pw * .30, fy + ph * .05),
           ph * .05, (238, 204, 178))
        put(im, "字太小 · 划掉的那一行", L.W / 2, L.body_top - L.H * .02,
            L.f_body, MUTED, anchor="mt", maxw=L.W - 2 * L.margin,
            opacity=ease(min(1., p / .25)))
        return

    if k == "clock":
        cx, cy = L.W / 2, (L.body_top + L.body_bot) / 2
        r = min(L.W, L.H) * (.30 if V else .27)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=PAPER,
                  outline=(214, 198, 176), width=max(3, int(7 * L.s)))
        for i in range(12):
            a = i * math.pi / 6
            x1, y1 = cx + math.sin(a) * r * .86, cy - math.cos(a) * r * .86
            x2, y2 = cx + math.sin(a) * r * .95, cy - math.cos(a) * r * .95
            d.line((x1, y1, x2, y2), fill=(171, 158, 140),
                   width=max(2, int(4 * L.s)))
        a1 = t * .06 + .4
        d.line((cx, cy, cx + math.sin(a1) * r * .52, cy - math.cos(a1) * r * .52),
               fill=INK, width=max(3, int(8 * L.s)))
        a2 = t * .5 + 1.8
        d.line((cx, cy, cx + math.sin(a2) * r * .74, cy - math.cos(a2) * r * .74),
               fill=ACCENT, width=max(2, int(5 * L.s)))
        d.ellipse((cx - 9 * L.s, cy - 9 * L.s, cx + 9 * L.s, cy + 9 * L.s), fill=INK)
        put(im, "没有台词的几秒", L.W / 2, L.body_bot + L.H * .04,
            L.f_body, MUTED, anchor="mt", opacity=ease(min(1., p / .3)))
        return

    if k in ("call", "commute"):
        if k == "call":
            d.rectangle((0, 0, L.W * .5, L.H), fill=(238, 226, 208))
            d.rectangle((L.W * .5, 0, L.W, L.H), fill=(219, 229, 231))
            d.line((L.W * .5, 0, L.W * .5, L.H), fill=WHITE,
                   width=max(2, int(4 * L.s)))
            for cx, col, sc in ((.25, (196, 164, 132), 1.0), (.75, (154, 178, 188), .92)):
                bx, by = L.X(cx), L.Y(.52 if not V else .46)
                bw = L.W * (.19 if V else .13) * sc
                d.ellipse((bx - bw / 2, by - bw * 1.4, bx + bw / 2, by - bw * .4),
                          fill=col)
                d.ellipse((bx - bw * .95, by - bw * .2, bx + bw * .95, by + bw * 1.8),
                          fill=col)
            for i, (xf, yf, c) in enumerate(((.16, .30, ACCENT), (.60, .66, BLUE))):
                bx, by = L.X(xf if V else xf), L.Y(yf)
                bw, bh = L.W * (.52 if V else .30), L.H * (.085 if V else .11)
                a = ease(min(1., max(0., (p - .12 - i * .28) / .25)))
                if a <= 0:
                    continue
                rr(d, (bx, by, bx + bw, by + bh), int(16 * L.s), PAPER,
                   rgb_lerp(c, WHITE, .4), max(2, int(3 * L.s)))
                waveform(d, L, bx + bw / 2, by + bh / 2, bw * .68, bh * .44,
                         t + i, .6 * a, c, bars=18)
            put(im, "一通电话，两个空间", L.W / 2, L.body_top - L.H * .03,
                L.f_body, MUTED, anchor="mt", opacity=ease(min(1., p / .3)))
        else:
            d.rounded_rectangle((L.W * .06, L.Y(.22), L.W * .94, L.Y(.66)),
                                radius=int(40 * L.s), fill=(224, 233, 236),
                                outline=(196, 210, 216), width=max(2, int(5 * L.s)))
            for i in range(22):
                x = ((i * 0.137 + t * .06) % 1.0) * L.W
                y = L.Y(.30 + ((i * 0.071) % .30))
                rr(d, (x, y, x + 7 * L.s, y + 7 * L.s), 4 * L.s,
                   (255, 236, 190))
            bx, by = L.X(.62), L.Y(.55)
            rr(d, (bx, by, bx + L.W * .10, by + L.H * .20), int(14 * L.s),
               (70, 68, 64))
            put(im, "肩膀松下来", L.W / 2, L.body_bot + L.H * .02, L.f_body,
                MUTED, anchor="mt", opacity=ease(min(1., p / .3)))
        return

    if k == "details":
        items = lines or ["字太小", "规矩太多", "一天好几回"]
        n = len(items)
        cw = L.W * (.84 if V else .26)
        ch = L.H * (.16 if V else .24)
        gap = L.W * (.035 if V else .045)
        total = n * cw + (n - 1) * gap
        x = (L.W - total) / 2
        y = (L.body_top + L.body_bot - (ch if V else 0)) / 2
        for i, s in enumerate(items):
            a = ease(min(1., max(0., (p - i * .18) / .34)))
            if a <= 0:
                continue
            bx = x + i * (cw + gap)
            by = y + (i * ch * 1.12 if V else 0) + (1 - a) * (-L.H * .10)
            card(im, L, (bx, by, bx + cw, by + ch))
            rr(d, (bx + cw * .10, by + ch * .18,
                   bx + cw * .10 + ch * .30, by + ch * .18 + ch * .30),
               int(10 * L.s), (ACCENT2, BLUE, GREEN)[i % 3])
            put(im, s, bx + cw / 2, by + ch * .72, L.f_body * (1.0 if V else .9),
                INK, bold=True, anchor="mm", opacity=a)
        return

    if k == "chat":
        cw, ch = L.W * (.84 if V else .40), L.H * (.62 if V else .68)
        x0, y0 = (L.W - cw) / 2, (L.body_top + L.body_bot - ch) / 2
        card(im, L, (x0, y0, x0 + cw, y0 + ch), fill=(250, 248, 243))
        rr(d, (x0 + cw * .36, y0 + 12 * L.s, x0 + cw * .64, y0 + 20 * L.s),
           6 * L.s, (226, 220, 209))
        for i in range(3):
            a = ease(min(1., max(0., (p - .10 - i * .20) / .28)))
            if a <= 0:
                continue
            by = y0 + ch * (.18 + i * .18)
            bw, bh = cw * .66, ch * .13
            rr(d, (x0 + cw * .08 + (1 - a) * (-cw * .08), by,
                   x0 + cw * .08 + bw, by + bh), int(14 * L.s),
               (232, 235, 233))
            put(im, "记得吃药", x0 + cw * .11, by + bh / 2, L.f_body * .8,
                MUTED, anchor="lm", opacity=a)
        iy = y0 + ch * .82
        rr(d, (x0 + cw * .07, iy, x0 + cw * .93, iy + ch * .10),
           int(12 * L.s), PAPER, LINE, 2)
        put(im, "又打了几个字，又删掉", x0 + cw * .11, iy + ch * .05,
            L.f_badge, MUTED, anchor="lm")
        if int(t * 2) % 2 == 0:
            d.rectangle((x0 + cw * .60, iy + ch * .03,
                         x0 + cw * .60 + 3 * L.s, iy + ch * .07), fill=ACCENT)
        put(im, "模拟聊天界面 · 示意内容", L.W / 2, L.body_top - L.H * .02,
            L.f_badge, MUTED, anchor="mt")
        return

    if k == "voice":
        cx, cy = L.X(.30 if not V else .34), L.Y(.52)
        r = L.W * (.17 if V else .12)
        d.ellipse((cx - r, cy - r * 1.5, cx + r, cy + r * .5), fill=(206, 180, 152))
        d.ellipse((cx - r * 1.6, cy + r * .3, cx + r * 1.6, cy + r * 2.6),
                  fill=(206, 180, 152))
        dw, dh = L.W * (.30 if V else .20), L.H * (.20 if V else .26)
        dx, dy = L.X(.66 if not V else .62), L.Y(.60)
        card(im, L, (dx - dw / 2, dy - dh / 2, dx + dw / 2, dy + dh / 2),
             fill=(70, 68, 64), outline=(48, 46, 42))
        rr(d, (dx - dw * .42, dy - dh * .36, dx + dw * .42, dy + dh * .36),
           int(8 * L.s), (246, 241, 231))
        waveform(d, L, dx, dy, dw * .66, dh * .32, t, .85, GREEN, bars=24)
        for i in range(3):
            a = (p * 1.4 + i / 3) % 1.0
            rad = r * (1.0 + a * 1.7)
            d.arc((cx - rad, cy - rad * .5 - rad, cx + rad, cy - rad * .5 + rad),
                  290, 430, fill=rgb_lerp(ACCENT, WHITE, a),
                  width=max(2, int(4 * L.s)))
        put(im, "只是说了一句话", L.W / 2, L.body_top - L.H * .02, L.f_body,
            MUTED, anchor="mt", opacity=ease(min(1., p / .3)))
        return

    if k == "photo":
        fw, fh = L.W * (.72 if V else .42), L.H * (.40 if V else .48)
        x0, y0 = (L.W - fw) / 2, (L.body_top + L.body_bot - fh) / 2
        rr(d, (x0, y0, x0 + fw, y0 + fh), int(20 * L.s), (238, 231, 218))
        for i, (xf, c) in enumerate(((.30, ACCENT2), (.52, BLUE), (.72, GREEN))):
            bw, bh = fw * .18, fh * .46
            bx, by = x0 + fw * xf, y0 + fh * .52
            rr(d, (bx - bw / 2, by - bh / 2, bx + bw / 2, by + bh / 2),
               int(12 * L.s), c, rgb_lerp(c, INK, .2), 3)
            rr(d, (bx - bw * .36, by - bh * .06, bx + bw * .36, by + bh * .22),
               int(5 * L.s), PAPER)
        # viewfinder corners
        m = fw * .08
        for sx, sy, ex, ey in ((x0, y0, x0 + m, y0), (x0, y0, x0, y0 + m),
                               (x0 + fw, y0, x0 + fw - m, y0),
                               (x0 + fw, y0, x0 + fw, y0 + m),
                               (x0, y0 + fh, x0 + m, y0 + fh),
                               (x0, y0 + fh, x0, y0 + fh - m),
                               (x0 + fw, y0 + fh, x0 + fw - m, y0 + fh),
                               (x0 + fw, y0 + fh, x0 + fw, y0 + fh - m)):
            d.line((sx, sy, ex, ey), fill=ACCENT, width=max(3, int(6 * L.s)))
        sy = y0 + (p % 1.0) * fh
        d.line((x0, sy, x0 + fw, sy), fill=rgb_lerp(ACCENT, WHITE, .45),
               width=max(2, int(4 * L.s)))
        put(im, "药盒只保留色块与形状", L.W / 2, L.body_top - L.H * .02,
            L.f_badge, MUTED, anchor="mt")
        return

    if k == "day":
        light = t * .18
        d.rectangle((0, 0, L.W, L.H), fill=(246, 232, 212))
        for i in range(9):
            a = (i / 8)
            d.rectangle((0, L.Y(.58 + a * .04), L.W, L.H),
                        fill=rgb_lerp((236, 214, 184), (216, 176, 142), a))
        cx = L.X(.22 + .10 * math.sin(light))
        cy = L.Y(.18)
        d.ellipse((cx - L.W * .10, cy - L.W * .10, cx + L.W * .10,
                   cy + L.W * .10), fill=(255, 240, 205))
        for i, c in enumerate((ACCENT2, BLUE, GREEN)):
            x = L.X(.32 + i * .19)
            y = L.Y(.60)
            rr(d, (x - L.W * .045, y - L.H * .07, x + L.W * .045,
                   y + L.H * .07), int(12 * L.s), c)
            rr(d, (x - L.W * .03, y - L.H * .01, x + L.W * .03,
                   y + L.H * .03), int(5 * L.s), PAPER)
        put(im, lines[0] if lines else "", L.W / 2, L.body_top, L.f_title * .8,
            MUTED, anchor="mt", opacity=ease(min(1., p / .3)))
        return

    if k == "brand":
        a = ease(min(1., p / .45))
        size = L.f_title * (2.6 if not V else 2.1)
        put(im, "药到", L.W / 2, L.Y(.43 if not V else .40), size, INK,
            bold=True, anchor="mm", opacity=a)
        d.rectangle((L.W / 2 - L.W * .045, L.Y(.545 if not V else .475),
                     L.W / 2 + L.W * .045, L.Y(.549 if not V else .478)),
                    fill=ACCENT)
        put(im, data.TAGLINE, L.W / 2, L.Y(.585 if not V else .515),
            L.f_title * (.72 if not V else .66), MUTED, anchor="mt", opacity=a)
        put(im, "原创图形 · 设计示意", L.W / 2, L.Y(.69 if not V else .60),
            L.f_badge, MUTED, anchor="mt", opacity=a * .8)
        return

    if k == "device_outline":
        a = ease(min(1., p / .4))
        bw, bh = L.W * (.46 if V else .26), L.H * (.34 if V else .42)
        x0, y0 = (L.W - bw) / 2, (L.body_top + L.body_bot - bh) / 2
        seg = min(1., p / .55)
        # progressive line-art outline
        pts = [(x0, y0 + bh * .12), (x0, y0), (x0 + bw, y0),
               (x0 + bw, y0 + bh), (x0, y0 + bh), (x0, y0 + bh * .88)]
        total = len(pts) - 1
        for i in range(total):
            f = max(0., min(1., seg * total - i))
            if f <= 0:
                continue
            p1, p2 = pts[i], pts[i + 1]
            d.line((p1[0], p1[1], p1[0] + (p2[0] - p1[0]) * f,
                    p1[1] + (p2[1] - p1[1]) * f), fill=INK,
                   width=max(3, int(6 * L.s)))
        rr(d, (x0 + bw * .08, y0 + bh * .10, x0 + bw * .92, y0 + bh * .74),
           int(16 * L.s), outline=(190, 178, 160), width=max(2, int(4 * L.s)))
        d.ellipse((x0 + bw * .46, y0 + bh * .84, x0 + bw * .54, y0 + bh * .92),
                  fill=(190, 178, 160))
        put(im, lines[0] if lines else "只保留轮廓与留白", L.W / 2,
            L.body_bot + L.H * .02, L.f_body, MUTED, anchor="mt", opacity=a)
        return

    if k == "principles":
        items = lines or ["一次只说一件事", "说完等你", "不打断"]
        cw = L.W * (.80 if V else .56)
        x0 = (L.W - cw) / 2
        rh = L.H * (.105 if V else .115)
        y0 = (L.body_top + L.body_bot - rh * len(items) * 1.35) / 2
        for i, s in enumerate(items):
            a = ease(min(1., max(0., (p - .10 - i * .22) / .3)))
            if a <= 0:
                continue
            y = y0 + i * rh * 1.35 + (1 - a) * (-rh * .3)
            rr(d, (x0, y, x0 + rh * .62, y + rh * .62), int(10 * L.s), ACCENT)
            put(im, "0%d" % (i + 1), x0 + rh * .31, y + rh * .31,
                rh * .30, WHITE, bold=True, anchor="mm", opacity=a)
            put(im, s, x0 + rh * .90, y + rh * .31, L.f_body * (1.0 if V else .95),
                INK, anchor="lm", opacity=a, maxw=cw - rh)
        return

    if k == "wave":
        cw, ch = L.W * (.80 if V else .22), L.H * (.22 if V else .24)
        gap = L.W * (.06 if V else .035)
        labels = lines or ["药名", "时间", "您听听对不对？"]
        total = len(labels) * cw + (len(labels) - 1) * gap
        x0 = (L.W - total) / 2
        y0 = (L.body_top + L.body_bot - (ch * len(labels) * 1.3 if V else ch)) / 2
        for i, s in enumerate(labels):
            a = ease(min(1., max(0., (p - .08 - i * .22) / .3)))
            if a <= 0:
                continue
            bx = x0 + i * (cw + gap) + (1 - a) * (L.W * .06 if V else 0)
            by = y0 + (i * ch * 1.3 if V else 0)
            card(im, L, (bx, by, bx + cw, by + ch))
            if i == 0:
                waveform(d, L, bx + cw / 2, by + ch * .55, cw * .76, ch * .42,
                         t, .8 * a, ACCENT, bars=20)
            else:
                put(im, s, bx + cw / 2, by + ch * .5, L.f_body * .9, INK,
                    bold=(i == 2), anchor="mm", maxw=cw * .86, opacity=a)
        return

    if k == "meals":
        items = lines or ["早", "午", "晚"]
        cw = L.W * (.24 if V else .16)
        ch = L.H * (.20 if V else .26)
        gap = L.W * (.05 if V else .05)
        total = len(items) * cw + (len(items) - 1) * gap
        x0 = (L.W - total) / 2
        y0 = (L.body_top + L.body_bot - (ch * len(items) * 1.25 if V else ch)) / 2
        for i, s in enumerate(items):
            a = ease(min(1., max(0., (p - .06 - i * .22) / .28)))
            if a <= 0:
                continue
            bx = x0 + i * (cw + gap)
            by = y0 + (i * ch * 1.25 if V else 0) + (1 - a) * (-L.H * .18)
            card(im, L, (bx, by, bx + cw, by + ch),
                 fill=(ACCENT2, BLUE, GREEN)[i % 3])
            put(im, s, bx + cw / 2, by + ch / 2, L.f_title * .9, WHITE,
                bold=True, anchor="mm", opacity=a)
        return

    if k == "safety_list":
        items = lines or ["不推荐药物 / 剂量 / 疗程", "不舒服建议联系家人或就医",
                          "紧急情况建议拨打 120"]
        cw = L.W * (.84 if V else .68)
        x0 = (L.W - cw) / 2
        rh = L.H * (.115 if V else .14)
        y0 = (L.body_top + L.body_bot - rh * len(items) * 1.25) / 2
        for i, s in enumerate(items):
            a = ease(min(1., max(0., (p - .08 - i * .25) / .3)))
            if a <= 0:
                continue
            y = y0 + i * rh * 1.25
            d.rectangle((x0, y, x0 + 5 * L.s, y + rh * .66), fill=ACCENT)
            put(im, s, x0 + 26 * L.s, y + rh * .33, L.f_body * (1.0 if V else .94),
                INK, anchor="lm", maxw=cw - 40 * L.s, opacity=a)
        return

    if k == "closing":
        a = ease(min(1., p / .35))
        put(im, "今天，给爸妈打个电话", L.W / 2, L.Y(.34 if not V else .32),
            L.f_title * (1.0 if V else 1.15), INK, bold=True, anchor="mm",
            maxw=L.W - 2 * L.margin, opacity=a)
        put(im, "问一句：今天吃药了吗。", L.W / 2, L.Y(.44 if not V else .40),
            L.f_title * (.78 if V else .9), ACCENT, bold=True, anchor="mm",
            maxw=L.W - 2 * L.margin, opacity=a)
        fy = L.Y(.60 if not V else .55)
        small = L.f_badge * (1.0 if V else .95)
        notes = ["情景演绎 · 模拟界面 · 非真机录屏 · 示意数据",
                 "本片为功能演示，不提供诊断、治疗建议或疗效承诺",
                 "项目说明见仓库文档（开发者信息）"]
        for i, s in enumerate(notes):
            put(im, s, L.W / 2, fy + i * small * 1.9, small, MUTED,
                anchor="mt", maxw=L.W - 2 * L.margin, opacity=a)
        return

    # ---------- simulated product UI ----------
    d, x0, y0, cw, ch, strip = ui_frame(im, L, shot["heading"], p, t,
                                        compact=(k == "ui_confirm"))
    top = y0 + strip + (L.H * .11 if not V else L.H * .075)
    rowh = L.H * (.075 if not V else .055)
    content_w = cw - 60 * L.s

    if k == "ui_save":
        rows = lines or ["早饭后的那一次，帮我记上。", "已复述：早饭后那一次"]
        for i, s in enumerate(rows):
            a = ease(min(1., max(0., (p - .10 - i * .30) / .32)))
            list_row(d, im, L, x0 + 30 * L.s, top + i * rowh * 1.55,
                     content_w, rowh, s, active=(i == 1), appear=a, num=i + 1)
        put(im, "未替您猜测 · 先复述再确认", x0 + 34 * L.s,
            y0 + ch - 46 * L.s, L.f_badge * .9, MUTED, maxw=content_w)
    elif k == "ui_list":
        rows = lines or ["早饭这一段", "午饭 · 不显示", "晚饭 · 不显示"]
        for i, s in enumerate(rows):
            a = ease(min(1., max(0., (p - .06 - i * .19) / .28)))
            list_row(d, im, L, x0 + 30 * L.s, top + i * rowh * 1.32,
                     content_w, rowh, s, active=(i == 0), appear=a, num=i + 1)
        put(im, "其余餐次灰掉不显示", x0 + 34 * L.s, y0 + ch - 46 * L.s,
            L.f_badge * .9, MUTED)
    elif k == "ui_check":
        cx, cy = x0 + cw * .5, y0 + ch * .54
        r = min(cw, ch) * (.16 if not V else .13)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=GREEN,
                  width=max(4, int(9 * L.s)))
        a = ease(min(1., max(0., (p - .18) / .42)))
        p1 = (cx - r * .42, cy + r * .02)
        p2 = (cx - r * .08, cy + r * .38)
        p3 = (cx + r * .48, cy - r * .36)
        for q1, q2, f0 in ((p1, p2, .0), (p2, p3, .5)):
            f = max(0., min(1., (a - f0) * 2))
            if f > 0:
                d.line((q1[0], q1[1], q1[0] + (q2[0] - q1[0]) * f,
                        q1[1] + (q2[1] - q1[1]) * f), fill=GREEN,
                       width=max(4, int(10 * L.s)))
        put(im, lines[-1] if lines else "记上了，慢慢来", cx, y0 + ch * .82,
            L.f_body * .9, INK, anchor="mt", maxw=content_w,
            opacity=ease(min(1., max(0., (p - .45) / .3))))
    elif k == "ui_report":
        vals = (3, 2, 1)
        lbls = ("应服", "已服", "还差")
        bw = (content_w - 2 * 24 * L.s) / 3
        for i in range(3):
            a = ease(min(1., max(0., (p - .08 - i * .20) / .3)))
            if a <= 0:
                continue
            bx = x0 + 30 * L.s + i * (bw + 24 * L.s)
            by = top + rowh * .3
            card(im, L, (bx, by, bx + bw, by + rowh * 2.3),
                 fill=(250, 244, 234) if i < 2 else (252, 238, 224))
            put(im, lbls[i], bx + bw / 2, by + rowh * .5, L.f_body * .78,
                MUTED, anchor="mm", opacity=a)
            put(im, str(int(vals[i] * a)), bx + bw / 2, by + rowh * 1.5,
                L.f_title * .8, ACCENT if i == 2 else INK, bold=True,
                anchor="mm", opacity=a)
        put(im, "示意数据 · 本地计算示例", x0 + 34 * L.s, y0 + ch - 46 * L.s,
            L.f_badge * .9, MUTED)
    elif k == "ui_clock":
        cx, cy = x0 + cw * .5, y0 + ch * .55
        r = min(cw, ch) * (.19 if not V else .15)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=PAPER,
                  outline=LINE, width=max(3, int(6 * L.s)))
        for i in range(12):
            a = i * math.pi / 6
            d.line((cx + math.sin(a) * r * .84, cy - math.cos(a) * r * .84,
                    cx + math.sin(a) * r * .95, cy - math.cos(a) * r * .95),
                   fill=MUTED, width=max(2, int(3 * L.s)))
        ang = ease(min(1., max(0., (p - .12) / .55))) * math.pi / 3
        d.line((cx, cy, cx + math.sin(ang) * r * .66,
                cy - math.cos(ang) * r * .66), fill=ACCENT,
               width=max(3, int(7 * L.s)))
        put(im, "稍后再来", cx, y0 + ch * .84, L.f_body * .9, INK,
            anchor="mt", opacity=ease(min(1., max(0., (p - .45) / .3))))
    elif k == "ui_reminder":
        a = ease(min(1., max(0., (p - .10) / .3)))
        bx = x0 + 30 * L.s + (1 - a) * cw * .3
        by = top + rowh * .2
        rr(d, (bx, by, bx + content_w, by + rowh * 1.5), int(14 * L.s),
           (252, 238, 224), ACCENT, max(2, int(3 * L.s)))
        put(im, lines[0] if lines else "下次唤醒时，先提一句",
            bx + 22 * L.s, by + rowh * .75, L.f_body * .85, INK,
            anchor="lm", maxw=content_w - 44 * L.s, opacity=a)
        put(im, lines[1] if len(lines) > 1 else "无人唤醒时设备不会自己开口",
            x0 + 34 * L.s, y0 + ch - 70 * L.s, L.f_badge * 1.0, ACCENT,
            maxw=content_w, opacity=ease(min(1., max(0., (p - .35) / .3))))
    elif k == "ui_question":
        a = ease(min(1., max(0., (p - .08) / .3)))
        for i in range(3):
            by = top + (i + 1) * rowh * 1.3
            rr(d, (x0 + 30 * L.s, by, x0 + 30 * L.s + content_w,
                   by + rowh * .8), int(10 * L.s),
               (252, 238, 224) if i == 0 else (250, 248, 244),
               ACCENT if i == 0 else LINE, max(2, int(2 * L.s)))
            if i == 0:
                put(im, lines[0] if lines else "是饭前吃还是饭后吃呀？",
                    x0 + 46 * L.s, by + rowh * .4, L.f_body * .85, INK,
                    anchor="lm", maxw=content_w - 32 * L.s, opacity=a)
            else:
                d.line((x0 + 46 * L.s, by + rowh * .4,
                        x0 + 46 * L.s + content_w * .42, by + rowh * .4),
                       fill=(224, 218, 207), width=max(2, int(4 * L.s)))
        put(im, "其余字段保持空白 · 一次只问一件", x0 + 34 * L.s,
            y0 + ch - 46 * L.s, L.f_badge * .9, MUTED, maxw=content_w)
    elif k == "ui_confirm":
        a = ease(min(1., p / .35))
        put(im, lines[0] if lines else "识别结果需您确认",
            x0 + cw / 2, y0 + ch * .55, L.f_title * .72, INK, bold=True,
            anchor="mm", maxw=content_w, opacity=a)
    elif k == "ui_refusal":
        rows = lines or ["这药能停了吗？", "这事得问您大夫，我不敢替您拿主意。"]
        for i, s in enumerate(rows):
            a = ease(min(1., max(0., (p - .08 - i * .28) / .3)))
            by = top + i * rowh * 1.7
            put(im, s, x0 + 34 * L.s, by, L.f_body * (.92 if V else .88),
                ACCENT if i == 0 else INK, anchor="lt",
                maxw=content_w, opacity=a)
            d.line((x0 + 34 * L.s, by + rowh * .95,
                    x0 + 34 * L.s + content_w * (.36 + .5 * a),
                    by + rowh * .95), fill=LINE, width=max(1, int(2 * L.s)))
        put(im, "功能对话示例 · 非用药建议", x0 + 34 * L.s,
            y0 + ch - 46 * L.s, L.f_badge * .9, MUTED)
    elif k == "reply":
        rows = lines or ["早饭后那一次", "您听听对不对？"]
        waveform(d, L, x0 + cw / 2, y0 + ch * .36, cw * .60, ch * .13,
                 t, .75, GREEN, bars=26)
        for i, s in enumerate(rows):
            a = ease(min(1., max(0., (p - .12 - i * .28) / .3)))
            put(im, s, x0 + cw / 2, y0 + ch * (.56 + i * .13),
                L.f_body * .95, INK if i == 0 else ACCENT, bold=(i == 1),
                anchor="mt", maxw=content_w, opacity=a)
    else:  # generic labelled graphic
        for i, s in enumerate(lines or []):
            a = ease(min(1., max(0., (p - .08 - i * .2) / .3)))
            put(im, s, x0 + cw / 2, top + i * rowh * 1.3, L.f_body, INK,
                anchor="mt", maxw=content_w, opacity=a)


# --------------------------------------------------------------------------
# Overlays: compliance badge, footer, chapter card, subtitles
# --------------------------------------------------------------------------
def draw_overlays(im, L, shot, p, t, subs, chapter_intro=False):
    d = ImageDraw.Draw(im)
    badge = shot["badge"]
    if badge:
        bw = L.W - 2 * L.margin
        put(im, badge, L.W - L.margin, L.badge_y, L.f_badge, MUTED,
            anchor="rt", maxw=bw * .78, opacity=.92)
        d.line((L.W - L.margin - L.X(.09), L.badge_y + L.f_badge * 1.7,
                L.W - L.margin, L.badge_y + L.f_badge * 1.7),
               fill=ACCENT, width=max(2, int(3 * L.s)))
    footer = data.FOOTER_VERTICAL if L.V else data.FOOTER_MAIN
    put(im, footer, L.W / 2, L.footer_y, L.f_footer, MUTED, anchor="mb",
        maxw=L.W - 2 * L.margin, opacity=.85)
    if chapter_intro:
        a = math.sin(min(1., p / .22) * math.pi) if p < .22 else max(0., 1 - (p - .22) / .18)
        put(im, shot["chapter"], L.margin, L.Y(.085 if L.V else .10),
            L.f_body * .9, ACCENT, bold=True, maxw=L.W * .5, opacity=a * .8)
    active = [e for e in subs if e["start"] <= t < e["end"]]
    assert len(active) <= 1, "overlapping subtitles at %.2f" % t
    for e in active:
        # fade in/out 120 ms
        a = min(ease((t - e["start"]) / .12),
                ease((e["end"] - t) / .12), 1.0)
        is_dlg = e["type"] == "dialogue"
        txt = e["text"]
        maxw = L.W - 2 * L.margin - 60 * L.s
        ti = text_img(txt, L.f_sub, WHITE, True, int(maxw))
        bw = min(L.W - 2 * L.margin, ti.width + 60 * L.s)
        bh = max(L.sub_h * .62, ti.height + 30 * L.s)
        bx = (L.W - bw) / 2
        by = L.sub_y - bh / 2
        rr(d, (bx + 6 * L.s, by + 7 * L.s, bx + bw + 6 * L.s,
               by + bh + 7 * L.s), int(16 * L.s), (198, 186, 168))
        rr(d, (bx, by, bx + bw, by + bh), int(16 * L.s),
           ACCENT if is_dlg else INK)
        put(im, txt, L.W / 2, by + bh / 2, L.f_sub, WHITE, bold=True,
            maxw=maxw, anchor="mm", opacity=a)
        if is_dlg:
            put(im, "对白 · 示例", bx + 18 * L.s, by - L.f_badge * 1.35,
                L.f_badge * .9, ACCENT, bold=True, opacity=a)


def render_frame(tl, L, t, frame_idx, subs):
    shots = tl["shots"]
    # locate shot
    lo, hi = 0, len(shots) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if shots[mid]["end"] <= t:
            lo = mid + 1
        else:
            hi = mid
    s = shots[lo]
    p = max(0., min(1., (t - s["start"]) / s["dur"]))
    pal = KIND_PALETTE.get(s["kind"], "warm")
    im = ken_burns(L, pal, p, t, phase=lo * .7)
    draw_kind(im, L, s, p, t)
    intro = (lo == 0) or (shots[lo - 1]["chapter"] != s["chapter"])
    draw_overlays(im, L, s, p, t, subs, chapter_intro=intro)
    # gentle dip-to-warm-white transition at shot boundaries (except UI grid)
    hard = s["kind"].startswith("ui_")
    if not hard:
        fade = min(ease(min(1., (t - s["start"]) / .30)),
                   ease(min(1., (s["end"] - t) / .30)), 1.0)
        if fade < .999:
            key = (L.W, L.H)
            if key not in _FLAT:
                _FLAT[key] = Image.new("RGB", key, LIGHT)
            im = Image.blend(_FLAT[key], im, fade)
    return im


def encode(tl_path, mix_path, out_path, vertical, crf=26):
    tl = json.load(open(tl_path, encoding="utf-8"))
    W, H, fps = tl["width"], tl["height"], tl["fps"]
    L = Layout(W, H, vertical)
    n = int(math.ceil(tl["duration_s"] * fps))
    subs = tl["subtitles"]
    cmd = [FFMPEG, "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H),
           "-r", str(fps), "-i", "-", "-i", mix_path,
           "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
           "-pix_fmt", "yuv420p", "-r", str(fps),
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
           "-movflags", "+faststart", "-t", "%.4f" % tl["duration_s"],
           out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    t0 = time.time()
    try:
        for i in range(n):
            t = i / fps
            im = render_frame(tl, L, t, i, subs)
            proc.stdin.write(im.tobytes())
            if i % 480 == 0:
                print("  frame %d/%d  %.1f%%  %.0fs" % (
                    i, n, 100.0 * i / n, time.time() - t0), flush=True)
        proc.stdin.close()
        err = proc.stderr.read().decode("utf-8", "replace")
        rc = proc.wait()
    except Exception:
        proc.kill()
        raise
    if rc != 0:
        raise RuntimeError("ffmpeg failed (%d): %s" % (rc, err[-2000:]))
    print("  DONE %s  frames=%d  %.1fs  %.1f MB" % (
        out_path, n, time.time() - t0, os.path.getsize(out_path) / 1e6),
        flush=True)
    return n


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "main"
    if which == "main":
        encode(os.path.join(WORK, "timeline_main.json"),
               os.path.join(WORK, "mix_main.wav"),
               os.path.join(WORK, "final_main.mp4"), False)
    elif which == "vertical":
        encode(os.path.join(WORK, "timeline_vertical.json"),
               os.path.join(WORK, "mix_vertical.wav"),
               os.path.join(WORK, "final_vertical.mp4"), True)
    elif which == "still":
        # quick single-frame smoke test
        tl = json.load(open(os.path.join(WORK, sys.argv[2]), encoding="utf-8"))
        V = "vertical" in sys.argv[2]
        L = Layout(tl["width"], tl["height"], V)
        im = render_frame(tl, L, float(sys.argv[3]), 0, tl["subtitles"])
        im.save(os.path.join(WORK, "smoke_%s.png" % ("v" if V else "m")))
        print("smoke ok")
