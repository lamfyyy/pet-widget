#!/usr/bin/env python3
"""Генерирует все кадры из tools/character.jpg:
  Shared/Assets.xcassets/<кадр>.imageset/<кадр>.png   — картинки
  Shared/FrameManifest.swift                          — таблица «имя → число кадров» для Swift
  tools/preview/*.png                                 — контрольные листы (в проект Xcode не попадают)
Запуск из корня проекта:  python3 tools/make_frames.py     (нужны Pillow, numpy, scipy)
"""
import os, json, math, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pet_art import *

ROOT = os.path.join(HERE, "..")
OUT = os.path.join(ROOT, "Shared", "Assets.xcassets")
MANIFEST = os.path.join(ROOT, "Shared", "FrameManifest.swift")
PREVIEW = os.path.join(HERE, "preview")
s = math.sin
TAU = 2 * math.pi

# ------------------------------------------------------------------ лица (общие заготовки)
FACE_CALM = dict(mouth="line", mcurve=.35, fangs=1.0)
FACE_SAD = dict(brow=-1, browVis=1, browY=14, pdy=14, mouth="open", mopen=.4, mcurve=-1, tears=1.0, wrink=.5)
FACE_ANNOYED = dict(lid=.42, tilt=10, brow=.55, browVis=1, browY=24, mouth="line", mcurve=-.35, fangs=0, wrink=.4)
FACE_ANGRY = dict(lid=.28, tilt=22, brow=1, browVis=1, browY=24, pr=.8, red=.85, mouth="grit", mopen=.7, mcurve=-1, wrink=1, veins=1, spit=1)

def H(face=None, **kw): return dict(face=face or {}, **kw)

# ------------------------------------------------------------------ циклы покоя (4 кадра)
def idle(mood, i):
    t = i / 4
    if mood == "sleep":
        return pose(face=dict(eyes="closed", mouth="o", mopen=.2 + .15 * s(TAU * t), drool=[.4, .7, 1, .6][i]), fx=dict(zzz=t),
                    body=dict(sy=1 + .012 * s(TAU * t), rot=0), head=dict(rot=2 * s(TAU * t), dy=4 + 3 * s(TAU * t)))
    if mood == "calm":
        f = dict(FACE_CALM, pdx=[0, 8, 0, -8][i])
        if i == 2: f["eyes"] = "closed"
        return pose(face=f, body=dict(dy=-4 * s(TAU * t), sy=1 + .006 * s(TAU * t)))
    if mood == "sad":
        up = i % 2 == 1
        f = dict(FACE_SAD, tphase=t)
        return pose(face=f, head=dict(rot=-3 if up else 3, dy=6), body=dict(dy=-8 if up else 0, sy=.985 if up else 1),
                    hands=((226, 560), (496, 560)) if i in (1, 3) else ((196, 656), (526, 656)))
    if mood == "annoyed":
        f = dict(FACE_ANNOYED, pdx=[-18, 0, 18, 0][i])
        return pose(face=f, hands=((176, 600), (546, 600)), legs=((0, 0), (0, 14 if i % 2 else 0)),
                    head=dict(rot=2 * s(TAU * t)), body=dict(rot=1.5 * s(TAU * t)),
                    fx=dict(anger=t) if i == 3 else {})
    if mood == "angry":
        sg = 1 if i % 2 == 0 else -1
        return pose(face=FACE_ANGRY, hands=((178, 560), (544, 560)),
                    fx=dict(steam=(1, t), anger=t), body=dict(dx=9 * sg, rot=1.6 * sg, dy=-14 if i % 2 else 0),
                    head=dict(rot=-2 * sg, dy=-4))
    raise ValueError(mood)

# ------------------------------------------------------------------ ходьба вправо (влево = зеркало в SwiftUI)
STEP = [((30, 0), (-30, 0), 0), ((0, 0), (0, 26), -8), ((-30, 0), (30, 0), 0), ((0, 26), (0, 0), -8)]

def walk(mood, i):
    L, R, bob = STEP[i]
    t = i / 4
    swing = [14, 0, -14, 0][i]
    base = dict(calm=FACE_CALM, sad=FACE_SAD, annoyed=FACE_ANNOYED, angry=FACE_ANGRY)[mood]
    f = dict(base, pdx=16, tphase=t)
    p = pose(face=f, legs=(L, R), body=dict(dy=bob, rot=4), head=dict(rot=-2),
             hands=((196 - swing, 656), (526 + swing, 656)))
    if mood == "calm":
        if i == 2: f["eyes"] = "closed"
    elif mood == "sad":
        p["body"].update(dy=bob * .5, rot=2); p["head"].update(rot=4, dy=10)
        f["pdy"] = 18
        p["legs"] = ((L[0] * .6, L[1] * .6), (R[0] * .6, R[1] * .6))
    elif mood == "annoyed":
        p["legs"] = ((L[0], L[1] * 1.3), (R[0], R[1] * 1.3)); p["body"].update(dy=bob * 1.4, rot=6)
        p["hands"] = ((176 - swing, 610), (546 + swing, 610))
    elif mood == "angry":
        sg = 1 if i % 2 == 0 else -1
        p["legs"] = ((L[0] * 1.2, L[1] * 1.6), (R[0] * 1.2, R[1] * 1.6)); p["body"].update(dy=bob * 2, rot=8, dx=6 * sg)
        p["hands"] = ((178 - swing, 570), (544 + swing, 570)); p["fx"] = dict(steam=(1, t))
    return p

# ------------------------------------------------------------------ дополнительные эмоции (случайные «вставки» в покое)
def fidget(kind, i):
    t = i / 4
    if kind == "happy":
        up = i % 2 == 1
        return pose(face=dict(eyes="happy", mouth="open", mopen=.45, mcurve=1, fangs=1, blush=.8),
                    body=dict(dy=-18 if up else 0, sy=1.03 if up else .98),
                    hands=((170, 470), (552, 470)) if up else ((190, 600), (532, 600)))
    if kind == "love":
        return pose(face=dict(eyes="heart", pdx=0, mouth="line", mcurve=.9, fangs=1, blush=1),
                    head=dict(rot=5 * s(TAU * t)), body=dict(dy=-5 * s(TAU * t)), fx=dict(hearts=t))
    if kind == "curious":
        px = [-20, 0, 20, 0][i]
        return pose(face=dict(pdx=px, pdy=-4, mouth="line", mcurve=-.1, brow=0, browVis=1, browY=-4, browL=-30, browR=4),
                    head=dict(rot=[6, 4, -4, -6][i]), body=dict(rot=[-2, -1, 1, 2][i]))
    if kind == "yawn":
        op = [.3, .9, .9, .4][i]
        return pose(face=dict(eyes="closed", mouth="open", mopen=op, mcurve=0, fangs=1, brow=-.3, browVis=1, browY=10),
                    hands=((172, 480), (550, 480)) if i in (1, 2) else ((196, 656), (526, 656)),
                    body=dict(sy=1.03 if i in (1, 2) else 1), head=dict(rot=-4 if i in (1, 2) else 0, dy=-6 if i in (1, 2) else 0))
    raise ValueError(kind)

# ------------------------------------------------------------------ реакции и переходы (по 2 кадра)
def wake(i):
    f = dict(erx=1.1, ery=1.1, pr=.5, mouth="o", mopen=.9, brow=-.2, browVis=1, browY=-8)
    return pose(face=f, fx=dict(bang=True), body=dict(dy=-46, sy=1.06, sx=.97) if i == 0 else dict(dy=-10, sy=1.01),
                hands=((170, 520), (552, 520)) if i == 0 else ((190, 600), (532, 600)))

def to(mood, i):
    j = i  # 0 или 1
    if mood == "calm":    # от злости/грусти к спокойствию — выдох облегчения
        if j == 0:
            return pose(face=dict(eyes="closed", mouth="open", mopen=.3, mcurve=0, fangs=1), fx=dict(sweat=(1, 0)),
                        body=dict(sy=.97, dy=4), head=dict(rot=-3, dy=6))
        return pose(face=dict(FACE_CALM, lid=.35), body=dict(dy=-6), fx=dict(sweat=(1, 1)))
    if mood == "sad":
        if j == 0:
            return pose(face=dict(erx=1.08, ery=1.08, pr=.5, mouth="o", mopen=.4, brow=-.7, browVis=1, browY=0),
                        body=dict(dy=-30, sy=1.05), hands=((200, 600), (522, 600)))
        return pose(face=dict(FACE_SAD, tears=.6, tphase=.2), body=dict(dy=0, sy=.96, sx=1.03), head=dict(rot=-4, dy=10))
    if mood == "annoyed":
        if j == 0:
            return pose(face=dict(FACE_ANNOYED, lid=.1, tilt=4, pdx=-10, mcurve=-.8), body=dict(dx=-8, rot=-3), fx=dict(anger=.0))
        return pose(face=FACE_ANNOYED, hands=((176, 600), (546, 600)), body=dict(dy=-10, rot=3), fx=dict(anger=.25))
    if mood == "angry":
        if j == 0:
            return pose(face=dict(FACE_ANGRY, red=.5, mopen=.35, lid=.2, tilt=14), hands=((190, 600), (532, 600)),
                        body=dict(dx=-12, rot=-3, dy=-24, sy=1.04), fx=dict(anger=.0))
        return pose(face=dict(FACE_ANGRY, mopen=1.0), hands=((178, 540), (544, 540)),
                    body=dict(dx=12, rot=3, dy=-8, sy=.97), fx=dict(steam=(1.2, .3), anger=.25))
    if mood == "sleep":
        if j == 0:
            return pose(face=dict(eyes="closed", mouth="open", mopen=.8, mcurve=0, fangs=1), hands=((172, 500), (550, 500)),
                        body=dict(sy=1.03), head=dict(rot=-4))
        return pose(face=dict(lid=.75, tilt=0, mouth="o", mopen=.15), head=dict(rot=7, dy=8), body=dict(sy=.98, dy=4), fx=dict(zzz=.2))
    raise ValueError(mood)

def poke(mood, i):
    if mood == "sad":
        if i == 0:
            return pose(face=dict(FACE_SAD, eyes="closed", mouth="open", mopen=.7, mcurve=-.6, tears=1), body=dict(sx=1.06, sy=.93),
                        hands=((226, 540), (496, 540)))
        return pose(face=dict(FACE_SAD, tphase=.5, mopen=.3), body=dict(dy=-22, sy=1.04, sx=.98), head=dict(rot=-5))
    if mood == "annoyed":
        if i == 0:
            return pose(face=dict(FACE_ANNOYED, lid=.6, tilt=14, brow=.9, mouth="grit", mopen=.3, mcurve=-.8), body=dict(sx=1.05, sy=.95, rot=-4),
                        hands=((180, 590), (542, 590)), fx=dict(anger=.0))
        return pose(face=dict(FACE_ANNOYED, brow=.8, pdx=24), body=dict(dy=-16, rot=4), hands=((176, 600), (546, 600)), fx=dict(anger=.25))
    if mood == "angry":
        sg = -1 if i == 0 else 1
        return pose(face=dict(FACE_ANGRY, mopen=1.0, pr=.6, red=1.0), hands=((172, 520), (550, 520)),
                    body=dict(dx=14 * sg, rot=4 * sg, dy=-30 if i else 0, sy=.94 if i == 0 else 1.05), fx=dict(steam=(1.3, .1 + .4 * i), anger=.25 * i))
    raise ValueError(mood)

# ------------------------------------------------------------------ события: пистолет / граната / РПГ
SMIRK = dict(mouth="line", mcurve=.9, fangs=1.0, brow=.8, browVis=1, browY=20, lid=.25, tilt=12, red=.35)

def pistol(stage, i):
    hand = (548, 470)
    if stage == "aim":
        dx = 5 * s(TAU * i / 2)
        h = (hand[0] + dx, hand[1])
        return pose(face=dict(SMIRK, eyes="wink_l", pdx=10), hands=((186, 620), h), hand_vis=(True, False),
                    prop=lambda d, h=h: prop_pistol(d, h), head=dict(rot=-5), body=dict(rot=2, dx=-6))
    if stage == "fire":
        fl = 1.0 if i == 0 else .45
        h = (hand[0] - 6, hand[1] + (18 if i == 0 else 8))
        return pose(face=dict(SMIRK, eyes="wink_l", mopen=0), hands=((186, 620), h), hand_vis=(True, False),
                    prop=lambda d, h=h, fl=fl: prop_pistol(d, h, flash=fl),
                    head=dict(rot=-9, dy=-6), body=dict(rot=-4, dx=-16, sy=1.02),
                    fx=dict(puffs=[(h[0] + 30, h[1] - 120, 22)]) if i == 1 else {})
    if stage == "smoke":
        h = (hand[0], hand[1] + 14)
        return pose(face=dict(SMIRK, mouth="o", mopen=.2, eyes="open", lid=.3), hands=((186, 620), h), hand_vis=(True, False),
                    prop=lambda d, h=h: prop_pistol(d, h), head=dict(rot=-4), body=dict(rot=1, dx=-4),
                    fx=dict(puffs=[(h[0] + 10, h[1] - 120, 18), (h[0] + 26, h[1] - 160, 26)]))

def grenade(stage, i):
    if stage == "pin":
        if i == 0:   # держит чеку зубами
            gh = (548, 380)
            return pose(face=dict(FACE_ANGRY, red=.5, mopen=.25, mouth="grit", eyes="open"), hands=((330, 520), gh),
                        hand_vis=(True, False), prop=lambda d, gh=gh: (prop_grenade(d, (gh[0], gh[1] - 36), pin=True), prop_ring(d, (320, 512))),
                        body=dict(rot=-2))
        gh = (548, 372)
        return pose(face=dict(SMIRK, mopen=0), hands=((232, 560), gh), hand_vis=(True, False),
                    prop=lambda d, gh=gh: (prop_grenade(d, (gh[0], gh[1] - 36), pin=False), prop_ring(d, (214, 556))),
                    body=dict(rot=-3, dy=-6), head=dict(rot=-4))
    if stage == "throw":
        if i == 0:   # замах
            gh = (600, 310)
            return pose(face=dict(FACE_ANGRY, mopen=.9, red=.7), hands=((190, 640), gh), hand_vis=(True, False),
                        prop=lambda d, gh=gh: prop_grenade(d, (gh[0], gh[1] - 36), pin=False),
                        body=dict(rot=-8, dx=-14), head=dict(rot=-6), legs=((-14, 0), (24, 0)))
        return pose(face=dict(FACE_ANGRY, mopen=1.0, red=.8, eyes="closed", pr=1), hands=((190, 640), (470, 520)), hand_scale=1.0,
                    body=dict(rot=9, dx=14, sy=.98), head=dict(rot=6), legs=((24, 0), (-18, 0)))
    if stage == "cover":
        sh = i % 2 == 1
        return pose(face=dict(eyes="closed", mouth="wavy", brow=-.6, browVis=1, browY=10), hands=((296, 330), (426, 330)), hand_vis=(False, False),
                    prop=lambda d: (front_arm(d, 0, (300, 318)), front_arm(d, 1, (422, 318))),
                    body=dict(sy=.94, dy=16 if not sh else 20, dx=4 if sh else -4), head=dict(dy=14, rot=2 if sh else -2),
                    fx=dict(sweat=(1, i)))

def rpg(stage, i):
    lh, rh = (336, 556), (440, 548)
    if stage == "aim":
        w = 4 * s(TAU * i / 2)
        return pose(face=dict(SMIRK, eyes="wink_l", mopen=0, mcurve=1, red=.5), hands=((lh[0], lh[1] + w), (rh[0], rh[1] + w)), hand_vis=(True, True),
                    prop=lambda d, w=w: (prop_rpg(d), hand(d, (lh[0], lh[1] + w), thumb=-1), hand(d, (rh[0], rh[1] + w), thumb=1)),
                    head=dict(rot=-4), body=dict(rot=1, dx=-8))
    if stage == "fire":
        fl = 1.0 if i == 0 else .5
        sg = i
        return pose(face=dict(FACE_ANGRY, eyes="closed", mopen=1.0, red=.8), hands=((lh[0] - 10, lh[1] + 14), (rh[0] - 10, rh[1] + 14)), hand_vis=(True, True),
                    prop=lambda d, fl=fl: (prop_rpg(d, loaded=False, flash=fl), hand(d, (lh[0] - 10, lh[1] + 14), thumb=-1), hand(d, (rh[0] - 10, rh[1] + 14), thumb=1)),
                    body=dict(rot=-9, dx=-22 - 8 * sg, dy=-6, sx=.98), head=dict(rot=-9),
                    fx=dict(flame=(190, 745, .9 - .3 * i), puffs=[(130, 705, 52), (205, 785, 40)] + ([(112, 640, 56)] if i else [])))
    if stage == "smoke":
        return pose(face=dict(FACE_ANGRY, mouth="line", mcurve=.8, mopen=0, red=.2, eyes="open", pr=.8, lid=.3, tilt=10), hands=((lh[0] - 6, lh[1] + 8), (rh[0] - 6, rh[1] + 8)), hand_vis=(True, True),
                    prop=lambda d: (prop_rpg(d, loaded=False), hand(d, (lh[0] - 6, lh[1] + 8), thumb=-1), hand(d, (rh[0] - 6, rh[1] + 8), thumb=1)),
                    body=dict(rot=-3, dx=-14), head=dict(rot=-3),
                    fx=dict(puffs=[(130 + 20 * i, 690 - 20 * i, 46), (572, 360 - 24 * i, 32 + 6 * i)]))

def laugh(i):
    up = i % 2 == 1
    return pose(face=dict(eyes="happy", mouth="open", mopen=.95, mcurve=1, fangs=1, blush=.6, red=.2),
                hands=((300, 640), (424, 640)), body=dict(dy=-12 if up else 0, rot=2 if up else -2, sy=.98 if up else 1.02),
                head=dict(rot=-8 if up else 6, dy=-6 if up else 0))

def dizzy(i):
    t = i / 4
    return pose(face=dict(eyes="spiral", tphase=t, mouth="wavy", mcurve=0), body=dict(rot=6 * s(TAU * t), dx=10 * s(TAU * t)),
                head=dict(rot=-8 * s(TAU * t)), fx=dict(stars=t), hands=((190, 660), (532, 660)))

# ------------------------------------------------------------------ каталог кадров
def catalog():
    c = {}
    for m in ("sleep", "calm", "sad", "annoyed", "angry"):
        c[f"{m}_idle"] = [idle(m, i) for i in range(4)]
    for m in ("calm", "sad", "annoyed", "angry"):
        c[f"{m}_walk"] = [walk(m, i) for i in range(4)]
    for k in ("happy", "love", "curious", "yawn"):
        c[f"fid_{k}"] = [fidget(k, i) for i in range(4)]
    c["wake"] = [wake(i) for i in range(2)]
    for m in ("sleep", "calm", "sad", "annoyed", "angry"):
        c[f"to_{m}"] = [to(m, i) for i in range(2)]
    for m in ("sad", "annoyed", "angry"):
        c[f"poke_{m}"] = [poke(m, i) for i in range(2)]
    c["pistol_aim"] = [pistol("aim", i) for i in range(2)]
    c["pistol_fire"] = [pistol("fire", i) for i in range(2)]
    c["pistol_smoke"] = [pistol("smoke", 0)]
    c["grenade_pin"] = [grenade("pin", i) for i in range(2)]
    c["grenade_throw"] = [grenade("throw", i) for i in range(2)]
    c["grenade_cover"] = [grenade("cover", i) for i in range(2)]
    c["rpg_aim"] = [rpg("aim", i) for i in range(2)]
    c["rpg_fire"] = [rpg("fire", i) for i in range(2)]
    c["rpg_smoke"] = [rpg("smoke", i) for i in range(2)]
    c["laugh"] = [laugh(i) for i in range(4)]
    c["dizzy"] = [dizzy(i) for i in range(4)]
    return c

def write_swift_manifest(counts):
    lines = ["// АВТОГЕНЕРАЦИЯ: tools/make_frames.py. Не редактируйте вручную.", "enum FrameManifest {",
             "    /// имя набора → сколько кадров (файлы <имя>_0 … <имя>_N-1 в Assets.xcassets)",
             "    static let counts: [String: Int] = ["]
    for k in sorted(counts): lines.append(f'        "{k}": {counts[k]},')
    lines += ["    ]", "}", ""]
    open(MANIFEST, "w").write("\n".join(lines))

def save_asset(name, img):
    d = os.path.join(OUT, f"{name}.imageset"); os.makedirs(d)
    img.save(os.path.join(d, f"{name}.png"), optimize=True)
    json.dump({"images": [{"idiom": "universal", "filename": f"{name}.png"}], "info": {"version": 1, "author": "xcode"}},
              open(os.path.join(d, "Contents.json"), "w"))

def make_icon(keep):
    os.makedirs(keep, exist_ok=True)
    img = render(idle("calm", 0))
    big = render_icon_source()
    big.save(os.path.join(keep, "icon.png"))
    json.dump({"images": [{"filename": "icon.png", "idiom": "universal", "platform": "ios", "size": "1024x1024"}],
               "info": {"version": 1, "author": "xcode"}}, open(os.path.join(keep, "Contents.json"), "w"), indent=2)

def render_icon_source():
    import pet_art
    p = idle("angry", 1); p["fx"] = {}
    old = (pet_art.FW, pet_art.FH)
    pet_art.FW, pet_art.FH = 900, round(900 * (CROP[3] - CROP[1]) / (CROP[2] - CROP[0]))
    try:
        im = pet_art.render(p)
    finally:
        pet_art.FW, pet_art.FH = old
    ic = Image.new("RGB", (1024, 1024), (236, 236, 242))
    ic.paste(im, ((1024 - im.width) // 2, (1024 - im.height) // 2 + 20), im)
    return ic

if __name__ == "__main__":
    cat = catalog()
    keep = os.path.join(OUT, "AppIcon.appiconset")
    shutil.rmtree(OUT, ignore_errors=True); os.makedirs(OUT)
    json.dump({"info": {"version": 1, "author": "xcode"}}, open(os.path.join(OUT, "Contents.json"), "w"))
    shutil.rmtree(PREVIEW, ignore_errors=True); os.makedirs(PREVIEW)
    counts, n, rendered = {}, 0, {}
    for name, poses in cat.items():
        counts[name] = len(poses)
        rendered[name] = []
        for i, p in enumerate(poses):
            im = render(p)
            save_asset(f"{name}_{i}", im); rendered[name].append(im); n += 1
    write_swift_manifest(counts)
    make_icon(keep)
    # контрольные листы
    names = list(rendered)
    per = 6
    for sheet_i in range(0, len(names), per):
        group = names[sheet_i:sheet_i + per]
        cols = max(len(rendered[g]) for g in group)
        sheet = Image.new("RGBA", (FW * cols, FH * len(group)), (90, 200, 120, 255))
        for r, g in enumerate(group):
            for c, im in enumerate(rendered[g]): sheet.alpha_composite(im, (c * FW, r * FH))
        sheet.convert("RGB").save(os.path.join(PREVIEW, f"sheet_{sheet_i // per + 1}_{group[0]}.png"))
    tot = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(OUT) for f in fs)
    print(f"кадров: {n}, размер {FW}x{FH}, ассеты {tot/1024:.0f} КБ, декодированные в памяти ~{n*FW*FH*4/1024/1024:.1f} МБ (если загрузить ВСЕ сразу)")
