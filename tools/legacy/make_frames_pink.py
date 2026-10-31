#!/usr/bin/env python3
"""Генерирует все кадры анимации из tools/05_neutral.png в Shared/Assets.xcassets.
Запуск:  python3 tools/make_frames.py   (нужны Pillow и numpy)"""
import os, json, math, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageChops, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "Shared", "Assets.xcassets")
PX, PY, PAD_R, PAD_B = 200, 300, 200, 40          # поля холста вокруг рисунка
FW = 360                                           # ширина итоговых кадров

src = Image.open(os.path.join(HERE, "05_neutral.png")).convert("RGBA")
W, H = src.size
CW, CH = W + PX + PAD_R, H + PY + PAD_B
FH = round(CH * FW / CW)
INK = (22, 22, 24, 255)

# ---------- подготовка: стираем зрачки, строим маски лица ----------
a = np.array(src)
yy, xx = np.mgrid[0:H, 0:W]
for cx, cy in [(670, 857), (898, 857)]:
    a[(xx - cx) ** 2 + (yy - cy) ** 2 <= 34 ** 2] = [239, 238, 239, 255]
base = Image.fromarray(a)
R, G, B, A = [a[..., i].astype(int) for i in range(4)]
box = np.zeros((H, W), bool); box[470:1250, 470:1130] = True
nonpink = ((G > 140) | ((B < 70) & (R > 150) & (G > 50))) & (A > 128) & box
FM = Image.fromarray((nonpink * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.MinFilter(9))
WS = Image.fromarray((((G > 150) & (B > 120) & (A > 128) & box) * 255).astype(np.uint8))   # белки+кожа

# ---------- рисование ----------
def lerp(x, y, t): return x + (y - x) * t

def thick(d, pts, w, fill):
    d.line(pts, fill=fill, width=int(w), joint="curve")
    r = w / 2
    for (x, y) in (pts[0], pts[-1]):
        d.ellipse((x - r, y - r, x + r, y + r), fill=fill)

def layer(size, fn, alpha=1.0):
    l = Image.new("RGBA", size, (0, 0, 0, 0)); fn(ImageDraw.Draw(l))
    if alpha < 1: l.putalpha(l.getchannel("A").point(lambda v: int(v * alpha)))
    return l

EYES = [(670, 857), (898, 857)]
EWC = [(640, 850), (940, 850)]

def face_overlay(f):
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    r = 25 * f["pr"]
    for (cx, cy), (wx, wy) in zip(EYES, EWC):
        px, py = cx + f["pdx"], cy + f["pdy"]
        lid_y = cy - 42 + f["lid"] * 50
        if f["lid"] < 0.92:
            d.ellipse((px - r, py - r, px + r, py + r), fill=INK)
            d.rectangle((px - 60, py - 60, px + 60, lid_y), fill=(0, 0, 0, 0))
        if f["lid"] > 0.04:
            w = 18 * min(1, f["lid"] * 4); sag = 30 * f["lid"] ** 2
            pts = [(wx - 100 + 10 * i, lid_y + sag * (1 - (i / 10 - 1) ** 2)) for i in range(21)]
            thick(d, pts, w, INK)
    if f["brow_vis"] > 0.04:
        def brows(dd):
            yb, k = 735 + f["brow_y"], f["brow"]
            thick(dd, [(535, yb - 30 * k), (748, yb + 50 * k)], 28, INK)
            thick(dd, [(1045, yb - 30 * k), (832, yb + 50 * k)], 28, INK)
        ov.alpha_composite(layer((W, H), brows, min(1, f["brow_vis"])))
    if f["m_vis"] > 0.04:
        def mouth(dd):
            cx, y0 = 790, 1100
            op = f["m_open"]; hw = lerp(55, 95, op); Aa = 34 * f["m_curve"]; h = op * 135
            us = [i / 10 - 1 for i in range(21)]
            top = [(cx + hw * u, y0 - Aa * u * u) for u in us]
            if h < 6:
                thick(dd, top, 14, INK); return
            bot = [(cx + hw * u, y0 - Aa * u * u + h * (1 - u * u)) for u in reversed(us)]
            poly = top + bot
            dd.polygon(poly, fill=(150, 22, 34, 255))
            pm = Image.new("L", (W, H), 0); ImageDraw.Draw(pm).polygon(poly, fill=255)
            tg = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(tg).ellipse((cx - hw * .6, y0 + h * .55, cx + hw * .6, y0 + h * 1.05), fill=(232, 96, 120, 255))
            tg.putalpha(ImageChops.multiply(tg.getchannel("A"), pm))
            dd._image.alpha_composite(tg)
            dd.line(poly + [poly[0]], fill=INK, width=12, joint="curve")
        ov.alpha_composite(layer((W, H), mouth, min(1, f["m_vis"])))
    if f["tears"] > 0.03:
        def tears(dd):
            L = 170 * f["tears"]
            for x0, ph in ((628, f["tphase"]), (952, (f["tphase"] + .5) % 1)):
                dd.rounded_rectangle((x0 - 17, 925, x0 + 17, 925 + L), radius=17, fill=(104, 190, 236, 255))
                if 925 + L * .8 > 950: dd.rounded_rectangle((x0 - 9, 940, x0 - 3, 925 + L * .8), radius=3, fill=(190, 230, 250, 255))
                y = 925 + L - 10 + ph * 230
                dd.ellipse((x0 - 16, y - 16, x0 + 16, y + 16), fill=(104, 190, 236, 255))
        ov.alpha_composite(layer((W, H), tears))
    ov.putalpha(ImageChops.multiply(ov.getchannel("A"), FM))
    return ov

def draw_puff(d, x, y, r):
    parts = [(-.55, .2, .7), (.5, .25, .65), (0, -.3, .85), (.05, .4, .6)]
    for ox, oy, rr in parts:
        d.ellipse((x + ox * r - rr * r - 9, y + oy * r - rr * r - 9, x + ox * r + rr * r + 9, y + oy * r + rr * r + 9), fill=INK)
    for ox, oy, rr in parts:
        d.ellipse((x + ox * r - rr * r, y + oy * r - rr * r, x + ox * r + rr * r, y + oy * r + rr * r), fill=(255, 255, 255, 255))

def draw_z(d, x, y, s):
    pts = [(x, y), (x + s, y), (x, y + s), (x + s, y + s)]
    d.line(pts, fill=(255, 255, 255, 255), width=int(s * .5), joint="curve")
    d.line(pts, fill=INK, width=max(2, int(s * .22)), joint="curve")

def xform(img, b):
    th = math.radians(b["rot"]); c, s = math.cos(th), math.sin(th)
    M = np.array([[c, s], [-s, c]]) @ np.diag([b["sx"], b["sy"]])
    Mi = np.linalg.inv(M); p = np.array(b["pivot"], float); t = np.array([b["dx"], b["dy"]], float)
    c0 = p - Mi @ (p + t)
    return img.transform(img.size, Image.AFFINE, (Mi[0, 0], Mi[0, 1], c0[0], Mi[1, 0], Mi[1, 1], c0[1]), resample=Image.BICUBIC)

PC = (790 + PX, H + PY)
PL, PR = (560 + PX, H + PY), (1020 + PX, H + PY)

def render(f, b):
    face = base.copy()
    if f["red"] > 0.02:
        tint = Image.new("RGBA", (W, H), (232, 40, 36, 255))
        tint.putalpha(ImageChops.multiply(WS, Image.new("L", (W, H), int(150 * f["red"]))))
        face.alpha_composite(tint)
    face.alpha_composite(face_overlay(f))
    canvas = Image.new("RGBA", (CW, CH), (255, 255, 255, 0))
    canvas.alpha_composite(face, (PX, PY))
    canvas = xform(canvas, b)
    d = ImageDraw.Draw(canvas)
    if f["steam"] > 0.03:
        for side, x0, dxs in ((0, 640, -70), (1, 1380, 70)):
            for k in range(2):
                ph = (f["sphase"] + .5 * k + .25 * side) % 1
                r = (14 + 62 * math.sin(math.pi * ph)) * f["steam"]
                if r > 8: draw_puff(d, x0 + dxs * ph, 330 - 280 * ph, r)
    if f["zzz"] > 0.03:
        for k in range(3):
            ph = (f["zphase"] + k / 3) % 1
            s = (45 + 85 * ph) * math.sqrt(math.sin(math.pi * ph)) * f["zzz"]
            if s > 10: draw_z(d, 1480 + 150 * ph, 640 - 460 * ph, s)
    return canvas.resize((FW, FH), Image.LANCZOS)

# ---------- параметры эмоций ----------
F0 = dict(lid=0, pdx=0, pdy=0, pr=1.0, brow=0, brow_vis=0, brow_y=0, m_vis=0, m_open=0, m_curve=0,
          tears=0, tphase=0, red=0, zzz=0, zphase=0, steam=0, sphase=0)
B0 = dict(dx=0, dy=0, rot=0, sx=1, sy=1, pivot=PC)

def mood_params(m, i, n):
    f, b = dict(F0), dict(B0); t = i / n; s = math.sin
    if m == "calm":
        f["lid"] = {11: .6, 12: 1.0, 13: .5}.get(i, 0)
        b["dy"] = -5 * s(2 * math.pi * t); b["sy"] = 1 + .006 * s(2 * math.pi * t)
    elif m == "sleep":
        f.update(lid=1, m_vis=1, m_open=.22 + .1 * s(2 * math.pi * t), zzz=1, zphase=t)
        b["sy"] = 1 + .012 * s(2 * math.pi * t); b["rot"] = 1.2 * s(2 * math.pi * t)
    elif m == "sad":
        f.update(brow=-.9, brow_vis=1, brow_y=10, m_vis=1, m_open=.35, m_curve=-1, tears=1, tphase=t, pdy=14)
        bounce = max(0, s(4 * math.pi * t))
        b["dy"] = -10 * bounce; b["sy"] = 1 - .015 * bounce
    elif m == "annoyed":
        f.update(brow=.55, brow_vis=1, brow_y=25, lid=.45, m_vis=1, m_open=0, m_curve=-.15, pdx=22 * s(2 * math.pi * t))
        b["rot"] = 2.0 * s(2 * math.pi * t); b["dy"] = -4 * abs(s(2 * math.pi * t))
    elif m == "angry":
        sg = 1 if i % 2 == 0 else -1
        f.update(brow=1, brow_vis=1, brow_y=30, pr=.75, red=.75, m_vis=1, m_open=1, m_curve=-.6, steam=1, sphase=t)
        b["dx"] = 16 * sg; b["rot"] = 2.5 * sg; b["dy"] = -28 if i % 2 else 0; b["sy"] = 1 if i % 2 else .97
    return f, b

def walk_params(i, direction):
    f, b = dict(F0), dict(B0)
    ph = i / 8; f["pdx"] = 18 * direction
    if ph < .5: b["rot"] = 5 * math.sin(math.pi * ph / .5); b["pivot"] = PL
    else: b["rot"] = -5 * math.sin(math.pi * (ph - .5) / .5); b["pivot"] = PR
    return f, b

LEVEL = {"sleep": 0, "calm": 1, "sad": 2, "annoyed": 3, "angry": 4}
def mix(d0, d1, t):
    return {k: (lerp(d0[k], d1[k], t) if k != "pivot" else d0[k]) for k in d0}

def trans_params(a_, b_, k, n=4):
    s = (k + 1) / (n + 1); e = s * s * (3 - 2 * s)
    f0, b0 = mood_params(a_, 0, 6); f1, b1 = mood_params(b_, 0, 6)
    f, b = mix(f0, f1, e), mix(b0, b1, e)
    amp = 70 if LEVEL[b_] > LEVEL[a_] else 22
    b["dy"] += -amp * math.sin(math.pi * s); b["sy"] *= 1 + .06 * math.sin(math.pi * s); b["sx"] *= 1 - .03 * math.sin(math.pi * s)
    return f, b

def poke_params(m, k):
    f, b = mood_params(m, 0, 6)
    sq = [(1.05, .92, 0), (.97, 1.05, -35), (1, 1, -10)][k]
    b["sx"] *= sq[0]; b["sy"] *= sq[1]; b["dy"] += sq[2]
    return f, b

TRANS = [("sleep", "calm"), ("calm", "sad"), ("sad", "annoyed"), ("annoyed", "angry"), ("sad", "calm"),
         ("annoyed", "calm"), ("angry", "calm"), ("calm", "sleep"), ("sad", "sleep"), ("annoyed", "sleep"), ("angry", "sleep")]
LOOPS = {"calm": 14, "sleep": 6, "sad": 6, "annoyed": 6, "angry": 6}

def all_frames():
    for m, n in LOOPS.items():
        for i in range(n): yield f"{m}_{i}", mood_params(m, i, n)
    for i in range(8):
        yield f"walkR_{i}", walk_params(i, 1); yield f"walkL_{i}", walk_params(i, -1)
    for a_, b_ in TRANS:
        for k in range(4): yield f"t_{a_}_{b_}_{k}", trans_params(a_, b_, k)
    for m in ("sad", "annoyed", "angry"):
        for k in range(3): yield f"poke_{m}_{k}", poke_params(m, k)

if __name__ == "__main__":
    keep = os.path.join(OUT, "AppIcon.appiconset")
    tmp = None
    if os.path.isdir(keep): tmp = "/tmp/_appicon"; shutil.rmtree(tmp, ignore_errors=True); shutil.copytree(keep, tmp)
    shutil.rmtree(OUT, ignore_errors=True); os.makedirs(OUT)
    json.dump({"info": {"version": 1, "author": "xcode"}}, open(os.path.join(OUT, "Contents.json"), "w"))
    n = 0
    for name, (f, b) in all_frames():
        d = os.path.join(OUT, f"{name}.imageset"); os.makedirs(d)
        render(f, b).save(os.path.join(d, f"{name}.png"), optimize=True)
        json.dump({"images": [{"idiom": "universal", "filename": f"{name}.png"}], "info": {"version": 1, "author": "xcode"}},
                  open(os.path.join(d, "Contents.json"), "w"))
        n += 1
    # иконка приложения
    d = keep; os.makedirs(d, exist_ok=True)
    bb = src.getbbox(); ch = src.crop(bb); sc = 880 / ch.height
    ch = ch.resize((round(ch.width * sc), 880), Image.LANCZOS)
    ic = Image.new("RGB", (1024, 1024), "white"); ic.paste(ch, ((1024 - ch.width) // 2, 72), ch)
    ic.save(os.path.join(d, "icon.png"))
    json.dump({"images": [{"filename": "icon.png", "idiom": "universal", "platform": "ios", "size": "1024x1024"}],
               "info": {"version": 1, "author": "xcode"}}, open(os.path.join(d, "Contents.json"), "w"), indent=2)
    print("frames:", n, "size", FW, FH)
