#!/usr/bin/env python3
"""Draw the repo banner. Pure PIL, no generated imagery — RyanAI Lab house style.

Concept: a context window stretched from 262K to 1M by static YaRN (factor 4).
Left = wordmark. Right = a 262K bar and a 4× taller 1M bar, 01/02 annotations,
a dashed up-flow labelled YaRN×4, and a single orange tick marking the measured
1M window this cookbook validates.
"""
import pathlib
from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 640
BG = (10, 10, 10)
WHITE = (245, 245, 245)
GREY = (140, 140, 140)
DIM = (70, 70, 70)
ORANGE = (255, 122, 26)
OUT = pathlib.Path(__file__).resolve().parents[1] / "docs/assets/banner.png"

HN = "/System/Library/Fonts/HelveticaNeue.ttc"
MENLO = "/System/Library/Fonts/Menlo.ttc"

def font(path, size, index=0):
    try:
        return ImageFont.truetype(path, size, index=index)
    except Exception:
        return ImageFont.load_default()

f_title = font(HN, 88, 7)     # Light
f_tag = font(HN, 30, 7)
f_mono = font(MENLO, 17)
f_label = font(MENLO, 15)

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

# crosshair corners
for cx, cy in ((40, 40), (W - 40, H - 40)):
    d.line([(cx - 11, cy), (cx + 11, cy)], fill=DIM, width=1)
    d.line([(cx, cy - 11), (cx, cy + 11)], fill=DIM, width=1)

# 5x3 dot lattices
for ox, oy in ((72, 78), (1150, 536)):
    for r in range(3):
        for c in range(5):
            x, y = ox + c * 15, oy + r * 12
            d.ellipse([x, y, x + 1.6, y + 1.6], fill=DIM)

# wordmark
d.text((80, 196), "1M CONTEXT", font=f_title, fill=WHITE)
d.text((80, 288), "WITH YARN", font=f_title, fill=WHITE)
d.text((82, 414), "Two Dell Pro Max with GB10. 262K to 1M via static YaRN.", font=f_tag, fill=WHITE)
d.text((82, 462), "QWEN3.8-FLASH-NEXT · TP2 ROCE · FP8 KV · MTP4 · MEASURED AT 1M", font=f_mono, fill=GREY)

# right: two context bars — 262K baseline and 4x taller 1M YaRN window
SX, SY = 860, 150
bar_w, base_h, gap = 96, 96, 40
y_base = SY + 3 * (base_h + gap)        # bottom-aligned bars
x_base = SX + 120
x_1m = SX + 250
h_base = base_h
h_1m = base_h * 4                       # YaRN factor 4

# 262K bar (01)
d.rectangle([x_base, y_base - h_base, x_base + bar_w, y_base], outline=(96, 96, 96), width=1)
d.text((x_base, y_base + 10), "262K", font=f_label, fill=GREY)
d.text((x_base + bar_w + 12, y_base - h_base + 6), "01", font=f_label, fill=DIM)

# 1M bar (02)
top_1m = y_base - h_1m
d.rectangle([x_1m, top_1m, x_1m + bar_w, y_base], outline=(96, 96, 96), width=1)
d.text((x_1m, y_base + 10), "1M", font=f_label, fill=GREY)
d.text((x_1m + bar_w + 12, top_1m + 6), "02", font=f_label, fill=DIM)

# dashed up-flow (YaRN factor 4) between the bar tops
def dashed(p0, p1, dash=6, gap_=6, fill=DIM):
    x0, y0 = p0; x1, y1 = p1
    L = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    n = int(L // (dash + gap_))
    for k in range(n):
        t0 = k * (dash + gap_) / L; t1 = (k * (dash + gap_) + dash) / L
        d.line([(x0 + (x1 - x0) * t0, y0 + (y1 - y0) * t0), (x0 + (x1 - x0) * t1, y0 + (y1 - y0) * t1)], fill=fill, width=1)

mid_top = top_1m + 24
dashed((x_base + bar_w, y_base - h_base), (x_1m, mid_top))
d.text((x_base + bar_w + 6, (y_base - h_base + mid_top) // 2 - 18), "YARN x4", font=f_label, fill=DIM)

# single orange tick marking the measured 1M window (the path we validate)
d.line([(x_1m + bar_w // 2, y_base), (x_1m + bar_w // 2, top_1m)], fill=ORANGE, width=2)
d.ellipse([x_1m + bar_w // 2 - 5, top_1m - 5, x_1m + bar_w // 2 + 5, top_1m + 5], fill=ORANGE)
d.text((x_1m + bar_w + 14, top_1m - 8), "MEASURED", font=f_label, fill=ORANGE)

# footer rule + labels
d.line([(80, 560), (W - 80, 560)], fill=(40, 40, 40), width=1)
d.text((80, 576), "RYANAI LAB", font=f_label, fill=GREY)
d.text((W - 80 - 250, 576), "DELL PRO MAX WITH GB10", font=f_label, fill=GREY)

OUT.parent.mkdir(parents=True, exist_ok=True)
img.save(OUT)
print("wrote", OUT)
