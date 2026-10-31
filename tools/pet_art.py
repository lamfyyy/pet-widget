"""Рисование персонажа: подготовка головы из tools/character.jpg + процедурные тело, руки, ноги, лицо, реквизит.
Всё рисуется в координатах исходной картинки (736x732), в конце кадр обрезается и уменьшается."""
import os, math
import numpy as np
from PIL import Image, ImageDraw, ImageChops
from scipy import ndimage as ndi

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "character.jpg")

WORK = (780, 900)                    # рабочий холст (координаты = координаты исходной картинки)
CROP = (-55, 10, 775, 840)          # квадрат 830x830 вокруг персонажа (центр по x = 360)
FW = 180                             # ширина итогового кадра (меньше = легче для памяти виджета)
FH = round((CROP[3] - CROP[1]) * FW / (CROP[2] - CROP[0]))

INK = (22, 22, 24, 255)
HAIR = (233, 232, 188)
SKIN = (240, 223, 200)
SHIRT = (12, 12, 14, 255)
SHIRT_HI = (52, 52, 60, 255)
PANTS = (62, 62, 76, 255)
SHOE = (44, 44, 54, 255)
SOLE = (150, 150, 158, 255)
RED = (214, 40, 36, 255)

NECK = (360, 530)                    # центр поворота головы
FOOT_Y = 790                         # линия земли
PIV = (360, FOOT_Y)                  # центр наклона/сплющивания всего тела
LE, RE = (310, 381), (414, 384)      # центры глаз
EYE_RX, EYE_RY = 54, 60
MOUTH = (358, 500)


# ---------------------------------------------------------------- подготовка головы
def prepare_head():
    """Вырезает фон, оставляет голову (волосы + лицо) без глаз/бровей/рта. Возвращает (RGBA, маска лица)."""
    a = np.array(Image.open(SRC).convert("RGB")).astype(float)
    dist = np.sqrt(((255 - a) ** 2).sum(2))
    lab, _ = ndi.label(dist < 14)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    fg = ~np.isin(lab, list(border))
    lab2, n2 = ndi.label(fg)
    sizes = ndi.sum(fg, lab2, range(1, n2 + 1))
    fg = np.isin(lab2, [i + 1 for i, s in enumerate(sizes) if s > 200])
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    lum = 0.3 * r + 0.59 * g + 0.11 * b
    hair = fg & (g - b > 33) & (lum > 170)
    skin = fg & (np.abs(r - 240) < 8) & (np.abs(g - 223) < 9) & (np.abs(b - 200) < 10)
    lab, _ = ndi.label(skin)
    face = ndi.binary_fill_holes(lab == lab[480, 300])
    lab, n = ndi.label(hair)
    sizes = ndi.sum(hair, lab, range(1, n + 1))
    hair = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s > 500])
    head = face | hair
    st = ndi.iterate_structure(ndi.generate_binary_structure(2, 1), 14)
    closed = ndi.binary_closing(np.pad(head, 20), structure=st)[20:-20, 20:-20]
    add = closed & ~head
    add[505:, :] = False; add[:, :140] = False; add[:, 560:] = False
    head2 = ndi.binary_fill_holes(head | add)
    H, W = head2.shape
    col = np.zeros((H, W, 4), np.uint8)
    col[..., :3] = HAIR
    col[face, :3] = SKIN
    alpha = ndi.gaussian_filter(head2.astype(float), 0.8)
    col[..., 3] = (np.clip((alpha - 0.35) / 0.5, 0, 1) * 255).astype(np.uint8)
    return col, face


def outline_under(img, r, color=(20, 20, 22)):
    """Подкладывает под картинку тёмный контур толщиной r пикселей (с гладким краем)."""
    a = np.array(img.getchannel("A")) > 24
    d = ndi.distance_transform_edt(~a)
    al = np.clip(r + 0.5 - d, 0, 1) * (~a)
    ring = np.zeros(a.shape + (4,), np.uint8)
    ring[..., 0], ring[..., 1], ring[..., 2] = color
    ring[..., 3] = (al * 255).astype(np.uint8)
    out = Image.fromarray(ring)
    out.alpha_composite(img)
    return out


_HEAD_CACHE = {}
def head_image(face_rgb):
    """Голова с заданным цветом кожи (для покраснения от гнева)."""
    if "base" not in _HEAD_CACHE:
        _HEAD_CACHE["base"] = prepare_head()
    base, face = _HEAD_CACHE["base"]
    arr = base.copy()
    arr[face, :3] = face_rgb
    out = Image.new("RGBA", WORK, (0, 0, 0, 0))
    out.paste(Image.fromarray(arr), (0, 0))
    return out


# ---------------------------------------------------------------- примитивы
def lerp(a, b, t): return a + (b - a) * t
def clamp(v, lo=0.0, hi=1.0): return max(lo, min(hi, v))

def newlayer(): return Image.new("RGBA", WORK, (0, 0, 0, 0))

def thick(d, pts, w, fill):
    pts = [tuple(p) for p in pts]
    d.line(pts, fill=fill, width=int(w), joint="curve")
    r = w / 2
    for (x, y) in (pts[0], pts[-1]):
        d.ellipse((x - r, y - r, x + r, y + r), fill=fill)

def ell(d, c, rx, ry, fill, outline=None, width=0):
    d.ellipse((c[0] - rx, c[1] - ry, c[0] + rx, c[1] + ry), fill=fill, outline=outline, width=width)

def capsule(d, p, q, w, fill):
    thick(d, [p, q], w, fill)

def mask_composite(dst, src, mask):
    """dst.alpha_composite(src), но src виден только там, где mask."""
    s = src.copy()
    s.putalpha(ImageChops.multiply(s.getchannel("A"), mask))
    dst.alpha_composite(s)

def xform(img, rot=0.0, sx=1.0, sy=1.0, dx=0.0, dy=0.0, pivot=PIV):
    th = math.radians(rot); c, s = math.cos(th), math.sin(th)
    M = np.array([[c, s], [-s, c]]) @ np.diag([sx, sy])
    Mi = np.linalg.inv(M); p = np.array(pivot, float); t = np.array([dx, dy], float)
    c0 = p - Mi @ (p + t)
    return img.transform(img.size, Image.AFFINE, (Mi[0, 0], Mi[0, 1], c0[0], Mi[1, 0], Mi[1, 1], c0[1]), resample=Image.BICUBIC)

def heart(d, c, s, fill, outline=None):
    x, y = c
    pts = []
    for i in range(41):
        t = i / 40 * 2 * math.pi
        hx = 16 * math.sin(t) ** 3
        hy = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
        pts.append((x + hx * s / 16, y + hy * s / 16))
    d.polygon(pts, fill=fill, outline=outline)

def star(d, c, r_out, r_in, n, fill, rot=0.0, outline=None):
    pts = []
    for i in range(n * 2):
        rr = r_out if i % 2 == 0 else r_in
        a = rot + math.pi * i / n
        pts.append((c[0] + rr * math.cos(a), c[1] + rr * math.sin(a)))
    d.polygon(pts, fill=fill, outline=outline)

def puff(d, x, y, r, fill=(255, 255, 255, 255)):
    parts = [(-.55, .2, .7), (.5, .25, .65), (0, -.3, .85), (.05, .4, .6)]
    for ox, oy, rr in parts:
        ell(d, (x + ox * r, y + oy * r), rr * r + 7, rr * r + 7, INK)
    for ox, oy, rr in parts:
        ell(d, (x + ox * r, y + oy * r), rr * r, rr * r, fill)

def draw_z(d, x, y, s):
    pts = [(x, y), (x + s, y), (x, y + s), (x + s, y + s)]
    d.line(pts, fill=(255, 255, 255, 255), width=int(s * .5), joint="curve")
    d.line(pts, fill=INK, width=max(3, int(s * .22)), joint="curve")

def bang(d, c, s):
    """Восклицательный знак."""
    x, y = c
    d.rounded_rectangle((x - s * .22, y - s, x + s * .22, y + s * .35), radius=s * .2, fill=RED, outline=INK, width=4)
    ell(d, (x, y + s * .7), s * .24, s * .24, RED, INK, 4)

def sweat(d, c, s):
    x, y = c
    d.polygon([(x, y - s), (x + s * .5, y + s * .2), (x + s * .35, y + s * .6), (x, y + s * .75), (x - s * .35, y + s * .6), (x - s * .5, y + s * .2)],
              fill=(104, 190, 236, 255), outline=INK)

def spiral(d, c, r, fill, turns=2.2, w=6, ph=0.0):
    pts = []
    for i in range(60):
        t = i / 59
        a = ph + t * turns * 2 * math.pi
        pts.append((c[0] + r * t * math.cos(a), c[1] + r * t * math.sin(a)))
    d.line(pts, fill=fill, width=w, joint="curve")


# ---------------------------------------------------------------- лицо
F0 = dict(lid=0.0, tilt=0.0, lower=0.0, pdx=0.0, pdy=0.0, pr=1.0, erx=1.0, ery=1.0,
          eyes="open",          # open | closed | happy | heart | spiral | wink_l | wink_r
          brow=0.0, browY=0.0, browL=0.0, browR=0.0, browVis=0.0, wrink=0.0,
          mouth="line", mopen=0.0, mcurve=0.0, mw=1.0, fangs=0.0,
          tears=0.0, tphase=0.0, blush=0.0, red=0.0, veins=0.0, spit=0.0, drool=0.0)
SHADE = (196, 166, 140, 255)     # тень на коже (морщины, складки)

def brow_shape(d, p0, p1, w):
    """Бровь South Park: плотная чёрная «колбаска», чуть утолщённая к середине."""
    x0, y0 = p0; x1, y1 = p1
    dx, dy = x1 - x0, y1 - y0
    n = math.hypot(dx, dy) or 1
    nx, ny = -dy / n, dx / n
    top, bot = [], []
    for i in range(11):
        u = i / 10
        wd = (0.62 + 0.38 * math.sin(math.pi * u)) * w / 2
        x, y = x0 + dx * u, y0 + dy * u
        top.append((x + nx * wd, y + ny * wd)); bot.append((x - nx * wd, y - ny * wd))
    d.polygon(top + bot[::-1], fill=INK)
    for (x, y) in (p0, p1):
        ell(d, (x, y), w * .31, w * .31, INK)

def draw_face(img, f, skin):
    d = ImageDraw.Draw(img)
    skin_rgba = tuple(skin) + (255,)
    # ---- глаза
    for side, (cx, cy) in enumerate((LE, RE)):
        sg = 1 if side == 0 else -1                    # +1 левый глаз (внутренний край справа)
        mode = f["eyes"]
        if mode == "wink_l" and side == 0: mode = "closed"
        elif mode == "wink_r" and side == 1: mode = "closed"
        elif mode in ("wink_l", "wink_r"): mode = "open"
        rx, ry = EYE_RX * f["erx"], EYE_RY * f["ery"]
        if mode in ("closed", "happy"):
            up = mode == "happy"
            pts = []
            for i in range(21):
                u = i / 10 - 1
                curve = (1 - u * u) * 22
                pts.append((cx + rx * .85 * u, cy + (-curve if up else curve) + (12 if up else -4)))
            thick(d, pts, 12, INK)
            # ресницы-засечки на внешнем крае
            ex, ey = pts[0] if sg == 1 else pts[-1]
            for k in (-1, 0, 1):
                d.line([(ex, ey), (ex - sg * 16, ey + 8 * k - (6 if up else -6))], fill=INK, width=5)
            continue
        tmp = Image.new("RGBA", WORK, (255, 255, 255, 0))
        td = ImageDraw.Draw(tmp)
        td.rectangle((cx - rx - 4, cy - ry - 4, cx + rx + 4, cy + ry + 4), fill=(255, 255, 255, 255))
        if f["veins"] > 0.05:                          # красные прожилки на белках (злость)
            for a in (-0.9, -0.3, 0.45, 1.0):
                ang = a + (0 if sg == 1 else math.pi - 2 * a + 0)
                x1, y1 = cx + sg * rx * math.cos(a), cy + ry * math.sin(a)
                td.line([(x1, y1), (cx + sg * rx * .45 * math.cos(a), cy + ry * .45 * math.sin(a))],
                        fill=(226, 70, 64, int(255 * f["veins"])), width=4)
        if mode == "heart":
            heart(td, (cx + f["pdx"], cy + f["pdy"] + 4), 62 * f["pr"], (230, 40, 80, 255), INK)
        elif mode == "spiral":
            spiral(td, (cx, cy), rx * .95, INK, w=7, ph=f["tphase"] * 2 * math.pi * sg)
        else:
            pr = 10 * f["pr"]
            ell(td, (cx + f["pdx"], cy + f["pdy"]), pr, pr, INK)
        # верхнее веко: прямая линия, внутренний край ниже при tilt>0
        if f["lid"] > 0.01:
            yl = cy - ry + f["lid"] * 2 * ry
            yo, yi = yl - f["tilt"], yl + f["tilt"]
            xo, xi = cx - sg * (rx + 6), cx + sg * (rx + 6)
            td.polygon([(xo, cy - ry - 30), (xi, cy - ry - 30), (xi, yi), (xo, yo)], fill=skin_rgba)
            td.line([(xo, yo), (xi, yi)], fill=INK, width=11)
            td.line([(xo, yo + 11), (xi, yi + 11)], fill=SHADE, width=4)      # тень под веком
        if f["lower"] > 0.01:
            yl = cy + ry - f["lower"] * ry * 1.1
            td.polygon([(cx - rx - 6, yl), (cx + rx + 6, yl), (cx + rx + 6, cy + ry + 30), (cx - rx - 6, cy + ry + 30)], fill=skin_rgba)
            td.line([(cx - rx - 6, yl), (cx + rx + 6, yl)], fill=INK, width=9)
        m = Image.new("L", WORK, 0)
        ImageDraw.Draw(m).ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=255)
        mask_composite(img, tmp, m)
        d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), outline=INK, width=6)
    # ---- брови и морщины на лбу
    if f["browVis"] > 0.04:
        k = f["brow"]
        for side, (cx, cy) in enumerate((LE, RE)):
            sg = 1 if side == 0 else -1
            yb = cy - 90 + f["browY"] + (f["browL"] if side == 0 else f["browR"])
            xo, xi = cx - sg * 58, cx + sg * 48
            brow_shape(d, (xo, yb - 26 * k), (xi, yb + 26 * k), 24)
    if f["wrink"] > 0.05:                          # складки между бровями
        a_ = int(255 * min(1, f["wrink"]))
        for xx in (351, 371):
            d.line([(xx, 302), (xx + (3 if xx > 360 else -3), 334)], fill=(150, 112, 92, a_), width=5)
    # ---- щёки, слёзы
    if f["blush"] > 0.03:
        bl = Image.new("RGBA", WORK, (0, 0, 0, 0))
        bd = ImageDraw.Draw(bl)
        for cx in (268, 458):
            ell(bd, (cx, 462), 36, 19, (240, 120, 130, int(150 * f["blush"])))
        img.alpha_composite(bl)
    if f["tears"] > 0.03:
        L = 150 * f["tears"]
        for x0, ph in ((LE[0] - 38, f["tphase"]), (RE[0] + 38, (f["tphase"] + .5) % 1)):
            y0 = LE[1] + EYE_RY - 8
            d.rounded_rectangle((x0 - 17, y0, x0 + 17, y0 + L), radius=17, fill=(104, 190, 236, 255), outline=(40, 110, 170, 255), width=3)
            d.rounded_rectangle((x0 - 9, y0 + 6, x0 - 3, y0 + L * .75), radius=3, fill=(196, 232, 250, 255))
            yy = y0 + L - 6 + ph * 70
            ell(d, (x0, yy), 17, 17, (104, 190, 236, 255), (40, 110, 170, 255), 3)
            ell(d, (x0 - 5, yy - 5), 4, 4, (214, 240, 252, 255))
    # ---- рот
    draw_mouth(d, img, f)

def draw_mouth(d, img, f):
    cx, y0 = MOUTH
    st, op, cv, hw = f["mouth"], f["mopen"], f["mcurve"], 52 * f["mw"]
    fang = f["fangs"]
    if st == "line":
        pts = [(cx + hw * (i / 10 - 1), y0 + 22 * cv * (1 - (i / 10 - 1) ** 2)) for i in range(21)]
        thick(d, pts, 10, INK)
        for sgn in (-1, 1):                       # складки у уголков рта
            ex, ey = pts[0] if sgn < 0 else pts[-1]
            d.arc((ex - 14 + sgn * 6, ey - 20, ex + 14 + sgn * 6, ey + 8), 200 if sgn < 0 else 300, 340 if sgn < 0 else 80, fill=SHADE, width=4)
        if fang > 0.05:
            for fx in (-20, 20):
                x = cx + fx
                yb = y0 + 22 * cv * (1 - (fx / hw) ** 2)
                d.polygon([(x - 8, yb + 4), (x + 8, yb + 4), (x, yb + 6 + 24 * fang)], fill=(255, 255, 255, 255), outline=INK, width=3)
    elif st == "o":
        ell(d, (cx, y0 + 8), 24 + 12 * op, 20 + 28 * op, (110, 20, 30, 255), INK, 7)
        ell(d, (cx, y0 + 8 + (14 + 28 * op) * .45), (24 + 12 * op) * .55, (20 + 28 * op) * .3, (232, 96, 120, 255))
        if f["drool"] > 0.05:
            L = 40 * f["drool"]
            d.rounded_rectangle((cx + 8, y0 + 34 + 28 * op, cx + 22, y0 + 34 + 28 * op + L), radius=7, fill=(205, 232, 250, 255), outline=(120, 170, 210, 255), width=3)
    elif st in ("open", "grit"):
        h = 26 + 95 * op
        w = hw * (1.0 + .5 * op)
        us = [i / 10 - 1 for i in range(21)]
        top = [(cx + w * u, y0 + 18 * cv * (1 - u * u)) for u in us]
        bot = [(cx + w * u, y0 + 18 * cv * (1 - u * u) + h * (1 - u * u) ** .7) for u in reversed(us)]
        poly = top + bot
        d.polygon(poly, fill=(104, 14, 28, 255))
        pm = Image.new("L", WORK, 0)
        ImageDraw.Draw(pm).polygon(poly, fill=255)
        ins = Image.new("RGBA", WORK, (0, 0, 0, 0))
        idr = ImageDraw.Draw(ins)
        ymid = y0 + 18 * cv
        if st == "grit":
            idr.rectangle((cx - w, ymid - 24, cx + w, ymid + h * .55), fill=(255, 255, 255, 255))
            n_t = 8
            for i in range(1, n_t):
                xx = cx - w + 2 * w * i / n_t
                idr.line([(xx, ymid - 24), (xx, ymid + h * .55)], fill=(70, 60, 60, 255), width=4)
            idr.line([(cx - w, ymid + h * .22), (cx + w, ymid + h * .22)], fill=(70, 60, 60, 255), width=5)
        else:
            idr.rectangle((cx - w, ymid - 24, cx + w, ymid + 10 + h * .18), fill=(255, 255, 255, 255))
            for i in range(1, 7):
                xx = cx - w + 2 * w * i / 7
                idr.line([(xx, ymid - 24), (xx, ymid + 10 + h * .18)], fill=(70, 60, 60, 255), width=3)
            ell(idr, (cx, ymid + h * .85), w * .6, h * .4, (232, 96, 120, 255))
            idr.line([(cx, ymid + h * .55), (cx, ymid + h * .85)], fill=(180, 60, 84, 255), width=4)
        mask_composite(img, ins, pm)
        d.line(poly + [poly[0]], fill=INK, width=10, joint="curve")
        for fx in (-w * .52, w * .52):
            x = cx + fx
            yb = y0 + 18 * cv * (1 - (fx / w) ** 2)
            d.polygon([(x - 11, yb - 6), (x + 11, yb - 6), (x, yb + 36 + 16 * op)], fill=(255, 255, 255, 255), outline=INK, width=4)
        if f["spit"] > 0.05:
            for (dx_, dy_, r_) in ((-w - 18, 30, 9), (w + 24, 18, 7), (-w - 36, 6, 6), (w + 12, 54, 8)):
                ell(d, (cx + dx_, y0 + dy_), r_ * f["spit"], r_ * f["spit"], (214, 238, 252, 255), (120, 170, 210, 255), 2)
    elif st == "wavy":
        pts = []
        for i in range(25):
            u = i / 24
            pts.append((cx - hw + 2 * hw * u, y0 + 7 * math.sin(u * 4 * math.pi)))
        thick(d, pts, 10, INK)


# ---------------------------------------------------------------- тело
def draw_legs(d, p):
    lg = p["legs"]            # ((x_off, lift) левая, (x_off, lift) правая)
    for side, (xo, lift) in enumerate(lg):
        bx = 300 if side == 0 else 420
        top = (bx, 680)
        foot = (bx + xo, FOOT_Y - 24 - lift)
        capsule(d, top, foot, 94, INK)             # контур
        capsule(d, top, foot, 82, PANTS)
        d.line([(bx - 8, 700), (foot[0] - 8, foot[1] - 6)], fill=(96, 96, 112, 255), width=4)   # складка штанины
        fx0 = foot[0] + (6 if xo >= 0 else -6)
        ell(d, (fx0, foot[1] + 14), 62, 28, SHOE, INK, 6)
        d.chord((fx0 - 40, foot[1] - 4, fx0 + 40, foot[1] + 26), 190, 350, fill=(70, 70, 84, 255))   # носок
        d.line([(fx0 - 56, foot[1] + 33), (fx0 + 56, foot[1] + 33)], fill=SOLE, width=8)

def draw_shirt(d):
    pts = [(222, 492), (498, 492), (512, 672), (500, 694), (220, 694), (208, 672)]
    d.polygon(pts, fill=SHIRT)
    d.line(pts + [pts[0]], fill=(58, 58, 68, 255), width=5, joint="curve")     # светлый кант, чтобы чёрное читалось
    d.line([(236, 560), (250, 650)], fill=SHIRT_HI, width=6)
    d.line([(484, 560), (472, 650)], fill=SHIRT_HI, width=6)
    d.line([(330, 600), (322, 664)], fill=(34, 34, 42, 255), width=5)          # складки
    d.line([(398, 612), (410, 668)], fill=(34, 34, 42, 255), width=5)
    d.arc((300, 470, 420, 550), 20, 160, fill=(70, 70, 82, 255), width=6)      # воротник
    d.line([(222, 686), (498, 686)], fill=(76, 76, 90, 255), width=7)          # низ рубашки

def hand(d, c, r=36, thumb=1, skin=SKIN, scale=1.0):
    r *= scale
    ell(d, (c[0] + thumb * r * .78, c[1] - r * .45), r * .42, r * .42, skin + (255,), INK, 5)
    ell(d, c, r, r, skin + (255,), INK, 6)
    ell(d, (c[0] + thumb * r * .62, c[1] - r * .3), r * .26, r * .26, skin + (255,))     # стык большого пальца
    for k in (-1, 0, 1):                                                                 # пальцы
        d.line([(c[0] - r * .55 * thumb, c[1] + r * .15 * k + r * .1), (c[0] - r * .05 * thumb, c[1] + r * .2 * k + r * .15)],
               fill=(150, 120, 98, 255), width=3)

def draw_arms(d, p):
    for side in (0, 1):
        sx = 238 if side == 0 else 484
        sh = (sx, 528)
        hx, hy = p["hands"][side]
        w = 66 * p.get("armw", 1.0)
        capsule(d, sh, (hx, hy), w, SHIRT)
        dx, dy = hx - sh[0], hy - sh[1]
        n = math.hypot(dx, dy) or 1
        nx, ny = -dy / n, dx / n
        d.line([(sh[0] + nx * 18 + dx * .15, sh[1] + ny * 18 + dy * .15), (hx + nx * 18 - dx * .25, hy + ny * 18 - dy * .25)], fill=SHIRT_HI, width=6)
        ell(d, (hx - dx / n * 26, hy - dy / n * 26), w * .52, w * .52, (30, 30, 36, 255), (70, 70, 84, 255), 4)   # манжета
    for side in (0, 1):
        hx, hy = p["hands"][side]
        if p["hand_vis"][side]:
            hand(d, (hx, hy), thumb=(-1 if side == 0 else 1), scale=p.get("hand_scale", 1.0))


# ---------------------------------------------------------------- реквизит
def prop_pistol(d, c, flash=0.0, side=1, k=1.5):
    """Пистолет дулом в зрителя (k — масштаб). c — центр кисти."""
    x, y = c
    d.polygon([(x - 24 * k, y + 6 * k), (x + 26 * k, y + 6 * k), (x + 34 * k, y + 76 * k), (x - 10 * k, y + 82 * k)], fill=(74, 52, 42, 255), outline=INK)
    d.rounded_rectangle((x - 42 * k, y - 74 * k, x + 42 * k, y + 20 * k), radius=14 * k, fill=(104, 104, 114, 255), outline=INK, width=5)
    d.rectangle((x - 30 * k, y - 62 * k, x + 30 * k, y - 54 * k), fill=(150, 150, 160, 255))
    ell(d, (x, y - 40 * k), 30 * k, 30 * k, (56, 56, 64, 255), INK, 5)
    ell(d, (x, y - 40 * k), 15 * k, 15 * k, (6, 6, 8, 255))
    hand(d, (x - 4 * k, y + 38 * k), r=32, thumb=-side, scale=k * .85)
    if flash > 0.02:
        star(d, (x, y - 40 * k), 100 * k * flash, 46 * k * flash, 9, (255, 190, 40, 255), rot=.2, outline=INK)
        star(d, (x, y - 40 * k), 62 * k * flash, 28 * k * flash, 9, (255, 245, 170, 255), rot=.5)

def prop_grenade(d, c, pin=True):
    x, y = c
    ell(d, (x, y), 40, 48, (86, 108, 52, 255), INK, 5)
    for k in (-1, 0, 1):
        d.line([(x - 36, y + 16 * k), (x + 36, y + 16 * k)], fill=(52, 70, 34, 255), width=4)
    d.line([(x, y - 44), (x, y + 44)], fill=(52, 70, 34, 255), width=4)
    d.rounded_rectangle((x - 16, y - 70, x + 16, y - 42), radius=5, fill=(140, 140, 148, 255), outline=INK, width=4)
    d.arc((x - 6, y - 76, x + 56, y - 8), 200, 330, fill=(170, 170, 178, 255), width=7)
    if pin:
        ell(d, (x + 26, y - 78), 13, 13, (0, 0, 0, 0), (200, 200, 208, 255), 5)
    hand(d, (x - 2, y + 40), r=30, thumb=1)

def prop_ring(d, c):
    ell(d, c, 14, 14, (0, 0, 0, 0), (200, 200, 208, 255), 5)
    d.line([(c[0] + 12, c[1] + 6), (c[0] + 34, c[1] + 22)], fill=(200, 200, 208, 255), width=5)

def prop_rpg(d, loaded=True, flash=0.0):
    rear, front = (226, 650), (556, 420)
    # заднее раструбное сопло
    ell(d, rear, 46, 46, (58, 66, 46, 255), INK, 5)
    ell(d, rear, 28, 28, (14, 14, 16, 255))
    capsule(d, (rear[0] + 30, rear[1] - 22), (front[0] - 20, front[1] + 14), 60, (86, 98, 66, 255))
    dx, dy = front[0] - rear[0], front[1] - rear[1]
    n = math.hypot(dx, dy)
    ux, uy = dx / n, dy / n
    for t in (.3, .55, .8):
        px, py = rear[0] + dx * t, rear[1] + dy * t
        d.line([(px - uy * 32, py + ux * 32 - 12), (px + uy * 32, py - ux * 32 - 12)], fill=(52, 60, 40, 255), width=7)
    # рукоять и прицел
    d.rounded_rectangle((420, 520, 462, 590), radius=8, fill=(30, 30, 34, 255), outline=INK, width=4)
    d.rounded_rectangle((340, 462, 392, 486), radius=6, fill=(40, 40, 44, 255), outline=INK, width=3)
    if loaded:
        d.polygon([(front[0] - 30, front[1] + 36), (front[0] + 30, front[1] - 34), (front[0] + 84, front[1] - 70)],
                  fill=(206, 72, 40, 255), outline=INK)
        ell(d, front, 36, 36, (120, 128, 98, 255), INK, 5)
        ell(d, (front[0] + 6, front[1] - 6), 22, 22, (206, 72, 40, 255), INK, 4)
    else:
        ell(d, front, 38, 38, (58, 66, 46, 255), INK, 5)
        ell(d, front, 24, 24, (14, 14, 16, 255))
    if flash > 0.02:
        star(d, (front[0] + 20, front[1] - 20), 120 * flash, 54 * flash, 10, (255, 190, 40, 255), rot=.1, outline=INK)
        star(d, (front[0] + 20, front[1] - 20), 72 * flash, 32 * flash, 10, (255, 245, 170, 255), rot=.4)


def front_arm(d, side, h, scale=1.0):
    """Рука поверх головы (для жестов у лица): рукав + кисть."""
    sx = 238 if side == 0 else 484
    capsule(d, (sx, 528), h, 66, SHIRT)
    hand(d, h, thumb=(-1 if side == 0 else 1), scale=scale)


# ---------------------------------------------------------------- эффекты поверх кадра
def draw_fx(img, fx):
    d = ImageDraw.Draw(img)
    if fx.get("steam"):
        amt, ph = fx["steam"]
        for side, x0, dxs in ((0, 150, -60), (1, 600, 60)):
            for k in range(2):
                p = (ph + .5 * k + .25 * side) % 1
                r = (12 + 40 * math.sin(math.pi * p)) * amt
                if r > 9: puff(d, x0 + dxs * p, 330 - 230 * p, r)
    if fx.get("zzz") is not None:
        ph = fx["zzz"]
        for k in range(3):
            p = (ph + k / 3) % 1
            s = (34 + 64 * p) * math.sqrt(math.sin(math.pi * p))
            if s > 9: draw_z(d, 560 + 90 * p, 250 - 150 * p, s)
    if fx.get("hearts") is not None:
        ph = fx["hearts"]
        for k in range(3):
            p = (ph + k / 3) % 1
            s = (22 + 30 * p) * math.sqrt(math.sin(math.pi * p))
            if s > 6: heart(d, (150 + 350 * ((k * .37 + p * .3) % 1) + 60 * math.sin(p * 6), 200 - 120 * p), s, (240, 70, 110, 255), INK)
    if fx.get("bang"):
        bang(d, (600, 190), 56)
    if fx.get("sweat"):
        sweat(d, (498, 262 + 12 * fx["sweat"][1]), 28)
        if fx["sweat"][0] > 1: sweat(d, (230, 252), 22)
    if fx.get("stars") is not None:
        ph = fx["stars"]
        for k in range(3):
            a = ph * 2 * math.pi + k * 2 * math.pi / 3
            star(d, (365 + 200 * math.cos(a), 175 + 38 * math.sin(a)), 24, 10, 4, (255, 214, 40, 255), rot=a, outline=INK)
    if fx.get("anger") is not None:
        s = 1 + .25 * math.sin(fx["anger"] * 2 * math.pi)
        c = (600, 190)
        for ang in (0, 90, 180, 270):
            a = math.radians(ang + 45)
            p1 = (c[0] + 14 * s * math.cos(a), c[1] + 14 * s * math.sin(a))
            p2 = (c[0] + 46 * s * math.cos(a), c[1] + 46 * s * math.sin(a))
            thick(d, [p1, p2], 11 * s, RED)
    if fx.get("puffs"):
        for (x, y, r) in fx["puffs"]:
            puff(d, x, y, r, (232, 232, 236, 255))
    if fx.get("flame"):
        x, y, s = fx["flame"]
        star(d, (x, y), 110 * s, 50 * s, 9, (255, 150, 30, 255), rot=.3, outline=INK)
        star(d, (x, y), 66 * s, 30 * s, 9, (255, 240, 150, 255), rot=.6)
    if fx.get("sparks"):
        for (x, y, r) in fx["sparks"]:
            star(d, (x, y), r, r * .4, 4, (255, 214, 40, 255), rot=.3, outline=INK)


# ---------------------------------------------------------------- сборка кадра
P0 = dict(face=F0, head=dict(rot=0, sx=1, sy=1, dx=0, dy=0), body=dict(rot=0, sx=1, sy=1, dx=0, dy=0),
          legs=((0, 0), (0, 0)), hands=((196, 656), (526, 656)), hand_vis=(True, True),
          hand_scale=1.0, armw=1.0, prop=None, fx={}, flip=False)

def pose(**kw):
    p = {k: (dict(v) if isinstance(v, dict) else v) for k, v in P0.items()}
    for k, v in kw.items():
        if k in ("face", "head", "body", "fx") and isinstance(v, dict):
            p[k].update(v) if k != "face" else p[k].update(v)
        else:
            p[k] = v
    return p

def render(p):
    f = dict(F0); f.update(p["face"])
    body = newlayer(); d = ImageDraw.Draw(body)
    draw_legs(d, p)
    draw_shirt(d)
    draw_arms(d, p)
    k = clamp(f["red"])
    skin = tuple(int(lerp(a, b, k)) for a, b in zip(SKIN, (236, 112, 98)))
    head = head_image(skin)
    draw_face(head, f, skin)
    head = outline_under(head, 9)                 # контур головы (как у вырезных фигурок South Park)
    h = p["head"]
    head = xform(head, rot=h["rot"], sx=h["sx"], sy=h["sy"], dx=h["dx"], dy=h["dy"], pivot=NECK)
    body.alpha_composite(head)
    pr = p.get("prop")
    if pr:                                    # реквизит рисуем ПОВЕРХ головы (волосы не должны его закрывать)
        front = newlayer()
        pr(ImageDraw.Draw(front))
        body.alpha_composite(front)
    body = outline_under(body, 7)                 # общий контур фигуры
    b = p["body"]
    out = xform(body, rot=b["rot"], sx=b["sx"], sy=b["sy"], dx=b["dx"], dy=b["dy"], pivot=PIV)
    draw_fx(out, p["fx"])
    out = out.crop(CROP).resize((FW, FH), Image.LANCZOS)
    return out
