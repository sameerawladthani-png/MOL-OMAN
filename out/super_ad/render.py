"""SUPER by O&B Land - 12s vertical motion ad, rendered frame by frame (free: Python + ffmpeg)."""
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS, DUR = 1080, 1920, 30, 12.0
BEAT = 60 / 128
N = int(DUR * FPS)
rng = np.random.default_rng(7)

GOLD_HI = np.array([255, 228, 160], float)
GOLD_LO = np.array([176, 122, 52], float)


def P(name):
    return os.path.join(HERE, name)


def font(name, size, wght=None):
    f = ImageFont.truetype(P("fonts/" + name), size)
    if wght:
        try:
            f.set_variation_by_axes([wght])
        except Exception:
            pass
    return f


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def seg(t, a, b):
    return min(max((t - a) / (b - a), 0.0), 1.0)


# ---------------------------------------------------------------- assets
poster = Image.open(P("poster.png")).convert("RGB")
logo = Image.open(P("logo_official.png")).convert("L")  # official O&B Land line logo (from brand PDF)


def fit_cover(img, w, h, scale=1.0, cx=0.5, cy=0.5):
    s = max(w / img.width, h / img.height) * scale
    rw, rh = int(img.width * s), int(img.height * s)
    r = img.resize((rw, rh), Image.LANCZOS)
    x = int(cx * rw - w / 2)
    y = int(cy * rh - h / 2)
    x = min(max(x, 0), rw - w)
    y = min(max(y, 0), rh - h)
    return r.crop((x, y, x + w, y + h))


def arr(img):
    return np.asarray(img, dtype=np.float32) / 255.0


# smoke textures
def noise_tex(w, h, seed):
    r = np.random.default_rng(seed)
    acc = np.zeros((h, w), np.float32)
    for octave, amp in ((8, 1.0), (16, 0.5), (32, 0.25), (64, 0.12)):
        small = Image.fromarray((r.random((octave * h // w + 1, octave)) * 255).astype("uint8"))
        acc += amp * arr(small.resize((w, h), Image.BICUBIC))
    acc = acc / acc.max()
    acc = np.clip((acc - 0.45) * 2.2, 0, 1) ** 1.6
    return arr(Image.fromarray((acc * 255).astype("uint8")).filter(ImageFilter.GaussianBlur(18)))


SMOKE_A = noise_tex(1400, 2600, 1)
SMOKE_B = noise_tex(1400, 2600, 2)
SMOKE_COL = np.array([0.18, 0.32, 1.0], np.float32)

yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
VIGNETTE = np.clip(1.15 - (((xx - W / 2) / (W * 0.75)) ** 2 + ((yy - H / 2) / (H * 0.62)) ** 2), 0.25, 1)[..., None]
BG = (np.array([0.008, 0.02, 0.09]) + (1 - yy / H)[..., None] * np.array([0.02, 0.05, 0.2])).astype(np.float32)


def smoke(t, strength=0.5):
    ya = int(500 - t * 38) % 600
    yb = int(100 + t * 22) % 600
    xa = int(150 + 30 * math.sin(t * 0.5))
    a = SMOKE_A[ya:ya + H, xa:xa + W]
    b = SMOKE_B[yb:yb + H, 160:160 + W]
    m = (a * 0.6 + b * 0.5)[..., None]
    return m * SMOKE_COL * strength


# embers
NP = 260
P_X = rng.random(NP) * W
P_Y = rng.random(NP) * H
P_VY = 40 + rng.random(NP) * 120
P_VX = (rng.random(NP) - 0.5) * 30
P_R = 1.5 + rng.random(NP) ** 3 * 5
P_PH = rng.random(NP) * 6.28
P_BLUE = rng.random(NP) < 0.35


def embers(t, amount=1.0, burst=None):
    layer = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(layer)
    for i in range(NP):
        x = (P_X[i] + P_VX[i] * t + 20 * math.sin(t * 1.3 + P_PH[i])) % W
        y = (P_Y[i] - P_VY[i] * t) % H
        fl = 0.55 + 0.45 * math.sin(t * 6 + P_PH[i] * 3)
        a = fl * amount
        if a <= 0.02:
            continue
        col = (90, 140, 255) if P_BLUE[i] else (255, 205, 120)
        c = tuple(int(v * a) for v in col)
        r = P_R[i]
        d.ellipse((x - r, y - r, x + r, y + r), fill=c)
    if burst is not None:  # (cx, cy, progress)
        cx, cy, p = burst
        br = np.random.default_rng(3)
        for k in range(180):
            ang = br.random() * 6.283
            sp = 200 + br.random() * 900
            dist = sp * ease_out(p)
            x = cx + math.cos(ang) * dist
            y = cy + math.sin(ang) * dist + 200 * p * p
            a = (1 - p) * (0.6 + 0.4 * br.random())
            r = 1.5 + br.random() * 4
            c = (int(255 * a), int(210 * a), int(130 * a))
            d.ellipse((x - r, y - r, x + r, y + r), fill=c)
    sharp = arr(layer)
    glow = arr(layer.filter(ImageFilter.GaussianBlur(7)))
    return sharp + glow * 1.6


def add(base, layer, a=1.0):
    return base + layer * a


def screen(base, layer, a=1.0):
    return 1 - (1 - base) * (1 - np.clip(layer * a, 0, 1))


def over(base, rgb, alpha):
    return base * (1 - alpha) + rgb * alpha


def gold_fill(h, w, t):
    g = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    shimmer = 0.5 + 0.5 * np.sin(np.linspace(0, 6, w)[None, :, None] + t * 3)
    col = GOLD_HI * (1 - g) + GOLD_LO * g
    return (col / 255.0) * (0.85 + 0.15 * shimmer)


def glint(h, w, p, width=0.12, angle=0.35):
    """diagonal light band sweeping left->right, p in [0,1]"""
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    u = (x / w + angle * y / h) / (1 + angle)
    c = -0.2 + 1.4 * p
    return np.exp(-((u - c) / width) ** 2)[..., None]


# ---------------------------------------------------------------- logo
def logo_layer(t, size, reveal, glint_p=None, burst=0.0):
    """returns (rgb, alpha) full frame of the O&B LAND logo, gold, centred."""
    lw = int(size)
    lh = int(lw * logo.height / logo.width)
    m = arr(logo.resize((lw, lh), Image.LANCZOS))
    ccx, ccy = 0.5 * lw, 0.375 * lh
    y, x = np.mgrid[0:lh, 0:lw].astype(np.float32)
    ang = (np.arctan2(x - ccx, -(y - ccy)) / (2 * math.pi)) % 1.0  # 0 at top, clockwise
    circle_zone = y < 0.70 * lh
    rc = ease(seg(reveal, 0.0, 0.72))
    rl = ease(seg(reveal, 0.45, 1.0))
    soft = 0.035
    vis_c = np.clip((rc * 1.04 - ang) / soft, 0, 1)
    vis_l = np.clip((rl * 1.1 - x / lw) / 0.06, 0, 1)
    vis = np.where(circle_zone, vis_c, vis_l)
    a = m * vis
    col = gold_fill(lh, lw, t)
    if glint_p is not None and 0 < glint_p < 1:
        col = col + glint(lh, lw, glint_p) * 0.9
    full_rgb = np.zeros((H, W, 3), np.float32)
    full_a = np.zeros((H, W, 1), np.float32)
    ox, oy = (W - lw) // 2, int(H * 0.44 - lh / 2)
    full_rgb[oy:oy + lh, ox:ox + lw] = col
    full_a[oy:oy + lh, ox:ox + lw, 0] = a
    # glow
    gl = Image.fromarray((full_a[..., 0] * 255).astype("uint8")).filter(ImageFilter.GaussianBlur(22))
    glow = arr(gl)[..., None] * np.array([1.0, 0.72, 0.3], np.float32) * 0.9
    # spark at the sweep head
    spark = None
    if 0 < rc < 1:
        th = rc * 2 * math.pi
        rad = 0.485 * lw
        sx = ox + ccx + math.sin(th) * rad
        sy = oy + ccy - math.cos(th) * rad
        spark = (sx, sy)
    elif 0 < rl < 1:
        spark = (ox + rl * 1.1 * lw, oy + 0.87 * lh)
    return full_rgb, full_a, glow, spark, (ox + ccx, oy + ccy)


def spark_layer(pt, strength=1.0):
    if pt is None:
        return 0
    sx, sy = pt
    d2 = (xx - sx) ** 2 + (yy - sy) ** 2
    core = np.exp(-d2 / (2 * 9 ** 2)) * 1.5 + np.exp(-d2 / (2 * 60 ** 2)) * 0.5
    return (core[..., None] * np.array([1.0, 0.85, 0.55], np.float32)) * strength


# ---------------------------------------------------------------- text
F_CIN = lambda s: font("Cinzel.ttf", s, 600)
F_OSW = lambda s: font("Oswald.ttf", s, 600)
F_AR_B = lambda s: font("Tajawal-Bold.ttf", s)
F_AR_M = lambda s: font("Tajawal-Medium.ttf", s)


def text_layer(items):
    """items: list of (text, font, cx, cy, rgb(0-255), alpha(0-1), tracking, rtl)"""
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for txt, f, cx, cy, rgb, a, track, rtl in items:
        if a <= 0.01:
            continue
        kw = dict(direction="rtl", language="ar") if rtl else {}
        fill = tuple(rgb) + (int(255 * a),)
        if track and not rtl:
            widths = [d.textlength(ch, font=f) + track for ch in txt]
            tw = sum(widths) - track
            x = cx - tw / 2
            for ch, wch in zip(txt, widths):
                d.text((x, cy), ch, font=f, fill=fill, anchor="lm")
                x += wch
        else:
            d.text((cx, cy), txt, font=f, fill=fill, anchor="mm", **kw)
    a = arr(layer)
    return a[..., :3], a[..., 3:4]


def composite_text(frame, items, glow=0.0):
    rgb, a = text_layer(items)
    out = over(frame, rgb, a)
    if glow:
        g = arr(Image.fromarray((a[..., 0] * 255).astype("uint8")).filter(ImageFilter.GaussianBlur(14)))[..., None]
        out = out + g * np.array([1.0, 0.75, 0.35], np.float32) * glow
    return out


# ---------------------------------------------------------------- shots
CAP_BOX = (380, 430, 700, 640)
LABEL_BOX = (395, 735, 665, 875)
BOTTLE_BOX = (300, 420, 760, 1160)


def crop_scene(box, t0, t1, t, s0, s1, w=W, h=H, cx=0.5, cy=0.5):
    p = ease(seg(t, t0, t1))
    s = s0 + (s1 - s0) * p
    c = poster.crop(box)
    return arr(fit_cover(c, w, h, s, cx, cy))


def poster_full(t, p_zoom):
    """poster fitted to width on blurred extension background; p_zoom 0 -> zoomed on bottle, 1 -> full"""
    s = 1.0 + 0.85 * (1 - ease_out(p_zoom))
    pw = int(W * s)
    ph = int(poster.height * pw / poster.width)
    big = poster.resize((pw, ph), Image.LANCZOS)
    # focus point: bottle centre (530, 790) in poster coords
    fx, fy = 530 / poster.width * pw, 790 / poster.height * ph
    tx = W / 2 + (fx - W / 2) * 0  # keep centred horizontally
    ox = int(W / 2 - fx * (1 - p_zoom) - (pw / 2) * p_zoom)
    oy = int(H / 2 - fy * (1 - p_zoom) - (ph / 2) * p_zoom)
    bg = poster.resize((W, H), Image.BILINEAR).filter(ImageFilter.GaussianBlur(40))
    canvas = bg.copy()
    canvas.paste(big, (ox, oy))
    out = arr(canvas)
    # feather the poster edges into the blurred bg
    edge = np.ones((H, W, 1), np.float32)
    top, bot = oy, oy + ph
    edge *= np.clip((yy[..., None] - top) / 80, 0, 1) * np.clip((bot - yy[..., None]) / 80, 0, 1)
    return out * edge + arr(bg) * (1 - edge)


NOTES = [
    ("مقدمة العطر", "البرغموت"),
    ("قلب العطر", "فلفل الأسود · اليانسون النجمي · جوزة الطيب"),
    ("قاعدة العطر", "الأمبر وكسان · الفانيلا · ليمون غراس"),
]


def frame_at(t):
    f = BG.copy()
    f = add(f, smoke(t, 0.55))

    # S1 logo reveal 0 - 2.35
    if t < 2.6:
        rev = seg(t, 0.15, 1.9)
        gp = seg(t, 1.88, 2.3)
        burst = seg(t, 2.2, 2.75)
        rgb, a, glow, spk, ctr = logo_layer(t, 560 * (1 + 0.25 * ease(burst)), rev, gp)
        fade = 1 - ease(burst)
        f = over(f, rgb, a * fade)
        f = add(f, glow, fade * (0.8 + 0.4 * math.sin(t * 5) ** 2))
        f = add(f, spark_layer(spk, 1.0))
        f = add(f, embers(t, 0.5, (ctr[0], ctr[1], burst) if burst > 0 else None))
        ta = ease(seg(t, 1.35, 1.9)) * fade
        f = composite_text(f, [("O&B LAND", F_CIN(58), W / 2, H * 0.44 + 460, (240, 210, 150), ta, 18, False)], glow=0.4 * ta)

    # S2 macro cap 2.35 - 4.2
    if 2.2 < t < 4.45:
        sc = crop_scene((330, 420, 730, 1130), 2.35, 4.45, t, 1.25, 1.05, cy=0.42)
        sc = sc + glint(H, W, seg(t, 2.8, 3.6), 0.08) * np.array([1, 0.85, 0.55], np.float32) * 0.35
        a = ease(seg(t, 2.25, 2.55)) * (1 - ease(seg(t, 4.1, 4.45)))
        f = over(f, sc, a)
        f = add(f, smoke(t * 1.6, 0.45), a)
        f = add(f, embers(t, 0.9), a)
        ta = ease(seg(t, 3.05, 3.4)) * (1 - ease(seg(t, 4.0, 4.3)))
        f = composite_text(f, [("SUPER", F_OSW(230), W / 2, H * 0.80, (245, 220, 165), ta * 0.95, 30, False),
                               ("EAU DE PARFUM", F_CIN(40), W / 2, H * 0.88, (230, 200, 140), ta, 14, False)], glow=0.5 * ta)

    # S3 notes 4.2 - 7.05
    if 4.1 < t < 7.3:
        bb = crop_scene(BOTTLE_BOX, 4.2, 7.3, t, 1.0, 1.12)
        bb = arr(Image.fromarray((bb * 255).astype("uint8")).filter(ImageFilter.GaussianBlur(12))) * 0.42
        a = ease(seg(t, 4.15, 4.45)) * (1 - ease(seg(t, 6.95, 7.3)))
        f = over(f, bb + smoke(t, 0.6), a)
        f = add(f, embers(t * 1.2, 1.0), a)
        items = []
        for i, (head, body) in enumerate(NOTES):
            t0 = 4.4 + i * BEAT * 2
            p = ease_out(seg(t, t0, t0 + 0.45))
            out_a = 1 - ease(seg(t, 6.85, 7.15))
            y = H * 0.36 + i * 250 + (1 - p) * 40
            items.append((head, F_AR_B(64), W / 2, y, (240, 205, 130), p * out_a, 0, True))
            items.append((body, F_AR_M(50 if i else 60), W / 2, y + 82, (235, 238, 255), p * out_a, 0, True))
        f = composite_text(f, items, glow=0.25)
        # gold rules
        for i in range(3):
            t0 = 4.4 + i * BEAT * 2
            pr = ease_out(seg(t, t0 + 0.1, t0 + 0.6)) * (1 - ease(seg(t, 6.85, 7.15)))
            y = int(H * 0.36 + i * 250 + 140)
            half = int(160 * pr)
            if half > 0:
                f[y:y + 3, W // 2 - half:W // 2 + half] = np.array([0.85, 0.66, 0.32])

    # S4 label macro with logo 7.05 - 8.6
    if 6.95 < t < 8.85:
        pl = ease(seg(t, 7.0, 8.85))
        sc = arr(fit_cover(poster.crop(BOTTLE_BOX), W, H, 1.4).filter(ImageFilter.GaussianBlur(16))) * 0.5
        lw = int(W * (0.88 + 0.1 * pl))
        lab = poster.crop(LABEL_BOX)
        lh = int(lw * lab.height / lab.width)
        la = arr(lab.resize((lw, lh), Image.LANCZOS))
        lg = glint(lh, lw, seg(t, 7.45, 8.3), 0.07) * np.array([1, 0.9, 0.65], np.float32) * 0.75
        ox, oy = (W - lw) // 2, int(H * 0.47 - lh / 2)
        sc[oy:oy + lh, ox:ox + lw] = la + lg

        a = ease(seg(t, 7.0, 7.25)) * (1 - ease(seg(t, 8.5, 8.85)))
        f = over(f, sc, a)
        f = add(f, embers(t, 0.6), a)

    # S5 poster pull-back 8.6 - 10.5
    if 8.5 < t < 10.75:
        pf = poster_full(t, seg(t, 8.6, 10.1))
        a = ease(seg(t, 8.55, 8.75)) * (1 - ease(seg(t, 10.35, 10.75)))
        f = over(f, pf, a)
        f = add(f, smoke(t * 1.3, 0.25), a)
        f = add(f, embers(t, 0.5), a)
        flash = math.exp(-((t - 8.62) / 0.08) ** 2)
        f = f + flash * 0.55

    # S6 end card 10.45 - 12
    if t > 10.4:
        a_in = ease(seg(t, 10.4, 10.8))
        rgb, la, glow, spk, ctr = logo_layer(t, 400, 1.0, seg(t, 11.0, 11.5))
        f = over(f, rgb, la * a_in)
        f = add(f, glow, a_in * 0.8)
        f = add(f, embers(t, 0.5 * a_in))
        ta = ease(seg(t, 10.7, 11.1))
        tb = ease(seg(t, 11.0, 11.4))
        cy_ = H * 0.44
        f = composite_text(f, [
            ("OUD & BEAUTY LAND", F_CIN(50), W / 2, cy_ + 330, (240, 210, 150), ta, 20, False),
            ("أرض العود والجمال", F_AR_M(44), W / 2, cy_ + 405, (225, 195, 135), ta, 0, True),
            ("حضورك يبدأ من رائحتك.", F_AR_B(66), W / 2, cy_ + 530, (245, 245, 255), tb, 0, True),
            ("SUPER  ·  EAU DE PARFUM  ·  100ML", F_CIN(34), W / 2, cy_ + 630, (205, 180, 130), tb, 6, False),
        ], glow=0.3 * ta)
        f = f * (1 - ease(seg(t, 11.75, 12.0)))

    f = f * VIGNETTE
    # gentle filmic tone curve
    f = np.clip(f, 0, None)
    f = 1 - np.exp(-f * 1.25)
    return (np.clip(f, 0, 1) * 255).astype(np.uint8)


def main():
    only = sys.argv[1:]
    if only:
        for s in only:
            Image.fromarray(frame_at(float(s))).save(P(f"preview_{s}.jpg"), quality=88)
        return
    out = P("super_silent.mp4")
    proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium",
                             "-crf", "18", "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    for i in range(N):
        proc.stdin.write(frame_at(i / FPS).tobytes())
        if i % 30 == 0:
            print("frame", i, flush=True)
    proc.stdin.close()
    proc.wait()


if __name__ == "__main__":
    main()
