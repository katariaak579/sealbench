"""Builds assets/img/og-card.png (1200x630 social preview) from the paper's Figure 1."""
from PIL import Image, ImageDraw, ImageFont
SRC = __import__("os").environ.get("SEALBENCH_PAPER", "../paper") + "/fig/fig1_protocol.png"
import os
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets/img/og-card.png")
W, H = 1200, 630
BG, INK, MUTED, RULE = (250, 249, 246), (24, 24, 27), (88, 88, 96), (210, 207, 200)
serif_b = "/usr/share/fonts/google-noto/NotoSerif-SemiBold.ttf"
serif = "/usr/share/fonts/google-noto/NotoSerif-Regular.ttf"
sans = "/usr/share/fonts/liberation-sans/LiberationSans-Regular.ttf"
card = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(card)
# figure on the right
fig = Image.open(SRC).convert("RGB")
fw = 700; fh = round(fig.height * fw / fig.width)
fig = fig.resize((fw, fh), Image.LANCZOS)
fx, fy = W - fw - 40, (H - fh) // 2
card.paste(fig, (fx, fy))
d.rectangle([fx - 1, fy - 1, fx + fw, fy + fh], outline=RULE, width=1)
# text on the left
x = 56
d.text((x, 150), "SEALBench", font=ImageFont.truetype(serif_b, 64), fill=INK)
f2 = ImageFont.truetype(serif, 25)
for i, line in enumerate(["A benchmark for image", "watermark detection,", "robustness, and recovery"]):
    d.text((x, 248 + i * 36), line, font=f2, fill=INK)
d.line([x, 380, x + 330, 380], fill=RULE, width=2)
f3 = ImageFont.truetype(sans, 18)
for i, line in enumerate(["11 post-hoc and 4 in-generation methods", "52 attack conditions in 4 categories",
                          "Detection, attribution, message recovery"]):
    d.text((x, 400 + i * 28), line, font=f3, fill=MUTED)
card.save(OUT, optimize=True)
print(OUT, card.size)
