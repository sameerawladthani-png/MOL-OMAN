import sys, os, math, wave, subprocess, re
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.abspath(__file__))
FD = [d for d in os.listdir(f'{ROOT}/fonts') if d.startswith('fontsource-cairo') and not d.endswith('.tgz')][0]
KD = [d for d in os.listdir(f'{ROOT}/fonts') if d.startswith('fontsource-noto-kufi') and not d.endswith('.tgz')][0]
FONT = lambda sub, w: (f'{ROOT}/fonts/{KD}/files/noto-kufi-arabic-arabic-{w}-normal.woff' if sub == 'arabic' else f'{ROOT}/fonts/{FD}/files/cairo-latin-{w}-normal.woff')
W, H, FPS = 1080, 1920, 30

SAND = (241, 234, 220); INK = (30, 42, 50); GREY = (124, 128, 126); TEAL = (34, 128, 122)
RED = (205, 72, 56); DARK = (16, 32, 38); LINE = (214, 204, 184); WHITE = (250, 247, 240)
DGREY = (120, 146, 150); DLINE = (40, 62, 68); MINT = (110, 205, 190)

@lru_cache(maxsize=None)
def font(sub, w, size): return ImageFont.truetype(FONT(sub, w), size)

def runs(s):
    return [m.group(0) for m in re.finditer(r'[0-9/%.]+|[^0-9/%.]+', s)]

@lru_cache(maxsize=2048)
def text_img(s, size, w, color):
    """Mixed Arabic + Latin digits, laid out right to left."""
    parts = []
    for r in runs(s):
        lat = bool(re.match(r'[0-9/%.]', r))
        f = font('latin' if lat else 'arabic', w, size)
        kw = {} if lat else {'direction': 'rtl', 'language': 'ar'}
        bb = f.getbbox(r, **kw)
        im = Image.new('RGBA', (bb[2] - bb[0] + 4, int(size * 2.3)), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((2 - bb[0], int(size * 0.3)), r, font=f, fill=color, **kw)
        parts.append(im)
    tw = sum(p.width for p in parts); out = Image.new('RGBA', (tw, parts[0].height), (0, 0, 0, 0))
    x = tw
    for p in parts:
        x -= p.width; out.alpha_composite(p, (x, 0))
    return out

def rich_img(segs, size, w):
    """segs: list of (text, color) in logical (reading) order; joined RTL with spaces kept inside text."""
    ims = [text_img(t, size, w, c) for t, c in segs]
    tw = sum(i.width for i in ims); out = Image.new('RGBA', (tw, ims[0].height), (0, 0, 0, 0)); x = tw
    for i in ims:
        x -= i.width; out.alpha_composite(i, (x, 0))
    return out

def fade(im, a):
    if a >= 0.999: return im
    im = im.copy(); im.putalpha(im.getchannel('A').point(lambda v: int(v * max(0, a)))); return im

def paste(base, im, x, y):
    x, y = int(round(x)), int(round(y))
    if x >= base.width or y >= base.height or x + im.width <= 0 or y + im.height <= 0: return
    cx0, cy0 = max(0, -x), max(0, -y)
    cx1, cy1 = min(im.width, base.width - x), min(im.height, base.height - y)
    base.alpha_composite(im.crop((cx0, cy0, cx1, cy1)), (x + cx0, y + cy0))

def ease(x): x = max(0.0, min(1.0, x)); return 1 - (1 - x) ** 3
def back(x):
    x = max(0.0, min(1.0, x)); c = 1.7; return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2

def reveal(base, im, x, y, t, t0, anchor='r', dy=28, dur=0.45):
    p = ease((t - t0) / dur)
    if p <= 0: return
    if anchor == 'r': x = x - im.width
    elif anchor == 'c': x = x - im.width / 2
    paste(base, fade(im, p), x, y + dy * (1 - p))

# ---------- layer helpers (2x supersampled illustration canvas) ----------
S = 2
class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h; self.im = Image.new('RGBA', (w * S, h * S), (0, 0, 0, 0)); self.d = ImageDraw.Draw(self.im)
    def sc(self, pts): return [(x * S, y * S) for x, y in pts]
    def rr(self, box, r, fill=None, outline=None, width=1):
        self.d.rounded_rectangle([v * S for v in box], r * S, fill=fill, outline=outline, width=width * S)
    def ell(self, box, fill=None, outline=None, width=1):
        self.d.ellipse([v * S for v in box], fill=fill, outline=outline, width=width * S)
    def poly(self, pts, fill=None, outline=None, width=1):
        self.d.polygon(self.sc(pts), fill=fill, outline=outline, width=width * S)
    def line(self, pts, fill, width=1):
        self.d.line(self.sc(pts), fill=fill, width=width * S, joint='curve')
    def pie(self, box, a0, a1, fill):
        self.d.pieslice([v * S for v in box], a0, a1, fill=fill)
    def arc(self, box, a0, a1, fill, width):
        self.d.arc([v * S for v in box], a0, a1, fill=fill, width=width * S)
    def out(self): return self.im.resize((self.w, self.h), Image.LANCZOS)

def dashed(cv, x0, y0, x1, y1, col, w=3, dash=14, gap=10):
    L = math.hypot(x1 - x0, y1 - y0); n = int(L // (dash + gap)) + 1
    for i in range(n):
        a = i * (dash + gap) / L; b = min(1, (i * (dash + gap) + dash) / L)
        cv.line([(x0 + (x1 - x0) * a, y0 + (y1 - y0) * a), (x0 + (x1 - x0) * b, y0 + (y1 - y0) * b)], col, w)

def xmark(cv, cx, cy, r, col, w, p=1.0):
    p1 = min(1, p * 2); p2 = max(0, p * 2 - 1)
    cv.line([(cx - r, cy - r), (cx - r + 2 * r * p1, cy - r + 2 * r * p1)], col, w)
    if p2 > 0: cv.line([(cx + r, cy - r), (cx + r - 2 * r * p2, cy - r + 2 * r * p2)], col, w)

# ---------- illustrations: each returns RGBA of size (900, 900), drawn at (90, 640) ----------
IW, IH = 900, 900

def woman(cv, cx, by, sc=1.0, body=TEAL, skin=(214, 170, 130), dark=False):
    # seated woman with headscarf, side profile facing left, rounded belly
    k = sc
    shawl = INK if not dark else (226, 220, 206)
    # chair
    cv.rr((cx + 40 * k, by - 210 * k, cx + 70 * k, by - 40 * k), 10 * k, fill=(196, 184, 160) if not dark else DLINE)
    cv.rr((cx - 60 * k, by - 60 * k, cx + 70 * k, by - 36 * k), 10 * k, fill=(196, 184, 160) if not dark else DLINE)
    cv.line([(cx - 40 * k, by - 40 * k), (cx - 50 * k, by)], (170, 158, 136) if not dark else DLINE, int(8 * k))
    cv.line([(cx + 55 * k, by - 40 * k), (cx + 62 * k, by)], (170, 158, 136) if not dark else DLINE, int(8 * k))
    # legs
    cv.rr((cx - 110 * k, by - 92 * k, cx + 30 * k, by - 54 * k), 18 * k, fill=INK if not dark else (60, 90, 96))
    cv.rr((cx - 112 * k, by - 92 * k, cx - 78 * k, by - 4 * k), 16 * k, fill=INK if not dark else (60, 90, 96))
    cv.rr((cx - 140 * k, by - 18 * k, cx - 78 * k, by), 9 * k, fill=shawl)
    # torso (abaya) + belly
    cv.rr((cx - 40 * k, by - 250 * k, cx + 40 * k, by - 60 * k), 36 * k, fill=body)
    cv.ell((cx - 78 * k, by - 175 * k, cx + 10 * k, by - 72 * k), fill=body)
    # arm to desk
    cv.line([(cx - 10 * k, by - 225 * k), (cx - 40 * k, by - 150 * k), (cx - 120 * k, by - 150 * k)], body, int(26 * k))
    cv.ell((cx - 138 * k, by - 163 * k, cx - 112 * k, by - 137 * k), fill=skin)
    # head + scarf
    cv.ell((cx - 46 * k, by - 345 * k, cx + 42 * k, by - 248 * k), fill=shawl)
    cv.ell((cx - 44 * k, by - 322 * k, cx + 6 * k, by - 262 * k), fill=skin)
    cv.poly([(cx + 10 * k, by - 300 * k), (cx + 60 * k, by - 220 * k), (cx + 20 * k, by - 225 * k)], fill=shawl)

def ill_hook(t, dark=False):
    cv = Canvas(IW, IH)
    # floor + desk
    cv.line([(60, 760), (840, 760)], LINE, 4)
    cv.rr((140, 520, 520, 548), 8, fill=(200, 186, 160))
    cv.rr((170, 548, 190, 760), 6, fill=(200, 186, 160)); cv.rr((470, 548, 490, 760), 6, fill=(200, 186, 160))
    # laptop
    cv.poly([(230, 520), (420, 520), (440, 512), (210, 512)], fill=INK)
    cv.poly([(250, 512), (232, 400), (392, 400), (410, 512)], fill=(52, 66, 74))
    cv.ell((312, 445, 330, 463), fill=MINT)
    woman(cv, 640, 760, 1.25)
    # floating heart + pulse
    p = ease((t - 0.6) / 0.6); bob = math.sin(t * 3) * 8
    if p > 0:
        hx, hy, r = 600, 210 + bob, 34 * back((t - 0.6) / 0.6)
        cv.ell((hx - r, hy - r, hx, hy), fill=RED); cv.ell((hx, hy - r, hx + r, hy), fill=RED)
        cv.poly([(hx - r * 0.98, hy - r * 0.35), (hx + r * 0.98, hy - r * 0.35), (hx, hy + r * 0.95)], fill=RED)
        pts = []; n = int(60 * min(1, (t - 0.8) / 1.2))
        for i in range(max(0, n)):
            x = 300 + i * 9; u = (i % 15)
            y = 260 + bob - (40 if u == 7 else -22 if u == 8 else 0)
            pts.append((x, y))
        if len(pts) > 1: cv.line(pts, (RED[0], RED[1], RED[2], 150), 4)
    return cv.out()

def ill_calendar(t):
    cv = Canvas(IW, IH)
    x0, y0, cw, ch, gap = 70, 260, 50, 50, 6
    cols, rows = 14, 7
    cv.rr((x0 - 30, y0 - 90, x0 + cols * (cw + gap) + 24, y0 + rows * (ch + gap) + 24), 26, fill=WHITE, outline=LINE, width=3)
    cv.rr((x0 - 30, y0 - 90, x0 + cols * (cw + gap) + 24, y0 - 30), 26, fill=TEAL)
    for i, xx in enumerate((200, 700)):
        cv.rr((xx - 8, y0 - 120, xx + 8, y0 - 66), 8, fill=INK)
    n = int(98 * ease((t - 0.5) / 2.6))
    for i in range(98):
        r, c = divmod(i, cols); c = cols - 1 - c  # fill right to left
        bx, by = x0 + c * (cw + gap), y0 + r * (ch + gap)
        if i < n: cv.rr((bx, by, bx + cw, by + ch), 10, fill=TEAL if i < n - 1 else RED)
        else: cv.rr((bx, by, bx + cw, by + ch), 10, outline=LINE, width=3)
    return cv.out(), n

def ill_clock(t):
    cv = Canvas(IW, IH); cx, cy, R = 450, 470, 280
    cv.ell((cx - R - 16, cy - R - 16, cx + R + 16, cy + R + 16), fill=INK)
    cv.ell((cx - R, cy - R, cx + R, cy + R), fill=WHITE)
    p = ease((t - 0.6) / 1.6)
    if p > 0: cv.pie((cx - R + 30, cy - R + 30, cx + R - 30, cy + R - 30), -90, -90 + 30 * p, (*TEAL, 230))
    for i in range(12):
        a = math.radians(i * 30 - 90); r1 = R - 24; r2 = R - (60 if i % 3 == 0 else 44)
        cv.line([(cx + r1 * math.cos(a), cy + r1 * math.sin(a)), (cx + r2 * math.cos(a), cy + r2 * math.sin(a))], INK, 9 if i % 3 == 0 else 5)
    ah = math.radians(-90 + 30 * p); am = math.radians(-90 + 360 * p)
    cv.line([(cx, cy), (cx + 140 * math.cos(ah), cy + 140 * math.sin(ah))], INK, 16)
    cv.line([(cx, cy), (cx + 215 * math.cos(am), cy + 215 * math.sin(am))], RED, 9)
    cv.ell((cx - 18, cy - 18, cx + 18, cy + 18), fill=INK)
    # baby bottle badge
    bx, by = 735, 205; q = back((t - 1.6) / 0.5)
    if t > 1.6:
        s = q
        cv.ell((bx - 80 * s, by - 80 * s, bx + 80 * s, by + 80 * s), fill=RED)
        cv.rr((bx - 24 * s, by - 30 * s, bx + 24 * s, by + 50 * s), 14 * s, fill=WHITE)
        cv.rr((bx - 28 * s, by - 42 * s, bx + 28 * s, by - 26 * s), 6 * s, fill=(250, 214, 200))
        cv.poly([(bx - 12 * s, by - 42 * s), (bx + 12 * s, by - 42 * s), (bx + 4 * s, by - 62 * s), (bx - 4 * s, by - 62 * s)], fill=(250, 214, 200))
        for k in range(3): cv.line([(bx - 10 * s, by + (k * 14 - 4) * s), (bx + 10 * s, by + (k * 14 - 4) * s)], LINE, 3)
    return cv.out()

def ill_year(t):
    cv = Canvas(IW, IH); n = int(12 * ease((t - 0.3) / 1.4) + 0.001)
    for i in range(12):
        r, c = divmod(i, 4); c = 3 - c
        x, y = 110 + c * 180, 180 + r * 190
        q = back((t - 0.3 - i * 0.11) / 0.4) if i < 12 else 0
        if i < n:
            cv.rr((x, y, x + 140, y + 140), 30, fill=TEAL)
        else:
            cv.rr((x, y, x + 140, y + 140), 30, outline=LINE, width=4)
    return cv.out(), n

def ill_crib(t):
    cv = Canvas(IW, IH); fx = 180; fy = 620
    wood = (196, 160, 120)
    cv.rr((fx, 380, fx + 540, 410), 12, fill=wood)
    cv.rr((fx, 600, fx + 540, 630), 12, fill=wood)
    cv.rr((fx - 10, 300, fx + 30, 720), 14, fill=wood); cv.rr((fx + 510, 300, fx + 550, 720), 14, fill=wood)
    # baby inside
    cv.rr((fx + 60, 520, fx + 480, 600), 30, fill=WHITE)
    cv.rr((fx + 150, 470, fx + 420, 590), 50, fill=(160, 205, 196))
    cv.ell((fx + 70, 450, fx + 180, 560), fill=(226, 186, 150))
    cv.ell((fx + 60, 440, fx + 140, 500), fill=(160, 205, 196))
    for k in range(9): cv.rr((fx + 50 + k * 54, 410, fx + 64 + k * 54, 600), 7, fill=wood)
    # moon + stars
    sw = math.sin(t * 2) * 6
    cv.ell((650, 120 + sw, 760, 230 + sw), fill=(240, 196, 92)); cv.ell((680, 106 + sw, 790, 216 + sw), fill=SAND)
    for sx, sy in ((560, 170), (820, 290), (480, 110)):
        r = 10 + 4 * math.sin(t * 4 + sx)
        cv.poly([(sx, sy - r), (sx + r * 0.3, sy - r * 0.3), (sx + r, sy), (sx + r * 0.3, sy + r * 0.3), (sx, sy + r), (sx - r * 0.3, sy + r * 0.3), (sx - r, sy), (sx - r * 0.3, sy - r * 0.3)], fill=(240, 196, 92))
    return cv.out()

def ill_letter(t):
    cv = Canvas(IW, IH)
    cv.rr((200, 120, 700, 780), 26, fill=WHITE)
    cv.rr((200, 120, 700, 210), 26, fill=(224, 216, 200))
    for k in range(9):
        w = 360 if k % 3 else 260
        cv.rr((620 - w, 270 + k * 52, 620, 286 + k * 52), 8, fill=(206, 200, 188))
    p = ease((t - 1.0) / 0.7)
    if p > 0:
        sc = 1.4 - 0.4 * back((t - 1.0) / 0.45)
        r = 170 * sc
        cv.ell((450 - r, 450 - r, 450 + r, 450 + r), outline=(*RED, int(255 * p)), width=14)
        xmark(cv, 450, 450, 95 * sc, (*RED, int(255 * p)), 24, ease((t - 1.15) / 0.5))
    # pregnant silhouette badge
    cv.ell((90, 600, 290, 800), fill=(38, 62, 70))
    woman(cv, 205, 770, 0.52, body=MINT, dark=True)
    return cv.out()

def ill_range(t):
    cv = Canvas(IW, IH); x0, x1, y = 80, 820, 440
    cv.rr((x0, y - 18, x1, y + 18), 18, fill=DLINE)
    def xm(m): return x1 - (m / 12) * (x1 - x0)
    p = ease((t - 0.7) / 1.5); a = xm(3); b = xm(3 + 9 * p)
    if p > 0: cv.rr((min(a, b), y - 18, max(a, b) + 2, y + 18), 18, fill=RED)
    for m in range(0, 13):
        X = xm(m); hgt = 30 if m in (3, 12) else 14
        cv.line([(X, y + 34), (X, y + 34 + hgt)], DGREY if m not in (3, 12) else WHITE, 4)
    for m, c in ((3, WHITE), (12, WHITE)):
        X = xm(m) if m == 3 else b
        if m == 12 and p <= 0: continue
        cv.ell((X - 30, y - 30, X + 30, y + 30), fill=c); cv.ell((X - 14, y - 14, X + 14, y + 14), fill=RED)
    return cv.out(), xm(3), xm(12), y, p

def ill_office(t):
    cv = Canvas(IW, IH)
    # building
    cv.rr((250, 300, 650, 760), 20, fill=WHITE)
    cv.poly([(220, 310), (450, 170), (680, 310)], fill=TEAL)
    for r in range(3):
        for c in range(3): cv.rr((300 + c * 110, 370 + r * 110, 370 + c * 110, 440 + r * 110), 10, fill=(206, 222, 218))
    cv.rr((410, 650, 490, 760), 10, fill=INK)
    cv.line([(120, 760), (780, 760)], LINE, 4)
    # pin
    q = back((t - 0.7) / 0.5); bob = math.sin(t * 3) * 10
    if t > 0.7:
        px, py, r = 680, 210 + bob, 62 * q
        cv.ell((px - r, py - r, px + r, py + r), fill=RED)
        cv.poly([(px - r * 0.8, py + r * 0.5), (px + r * 0.8, py + r * 0.5), (px, py + r * 1.9)], fill=RED)
        cv.ell((px - r * 0.4, py - r * 0.4, px + r * 0.4, py + r * 0.4), fill=WHITE)
    return cv.out()

def sadu(t):
    band = Image.new('RGBA', (W, 54), (0, 0, 0, 0)); d = ImageDraw.Draw(band)
    off = (t * 40) % 54
    d.rectangle((0, 0, W, 54), fill=INK)
    for i in range(-2, W // 27 + 3):
        x = i * 27 - off
        col = RED if i % 2 else (230, 214, 180)
        d.polygon([(x, 44), (x + 13, 12), (x + 26, 44)], fill=col)
    d.rectangle((0, 0, W, 5), fill=RED); d.rectangle((0, 49, W, 54), fill=RED)
    return band

# ---------- scenes ----------
LAW = 'قانون العمل العماني 53/2023'
SC = [
    dict(bg='l', src=LAW, card='المرسوم السلطاني 53/2023', head=[[('حامل وتشتغلين؟', INK)], [('اعرفي ', INK), ('حقوقك', RED)]], cap=None, ill='hook'),
    dict(bg='l', src=LAW, card='المادة 84', head=[[('إجازة ', INK), ('الأمومة', RED)]], cap=None, ill='cal'),
    dict(bg='l', src=LAW, card='المادة 76', head=[[('بعد ما ترجعين', INK)], [('ساعة رضاعة ', RED), ('كل يوم', INK)]], cap=None, ill='clock'),
    dict(bg='l', src=LAW, card='المادة 76', head=[[('لمدة ', INK), ('سنة كاملة', RED)]], cap=None, ill='year'),
    dict(bg='l', src=LAW, card='المادة 83', head=[[('تبين وقت أكثر', INK)], [('مع ', INK), ('طفلك', RED), ('؟', INK)]], cap=[('إجازة رعاية طفل لين سنة ', INK), ('بدون أجر', RED)], ill='crib'),
    dict(bg='d', src=LAW, card='المادة 12', head=[[('فصلوك بسبب', WHITE)], [('الحمل', RED), ('؟', WHITE)]], cap=[('هذا ', WHITE), ('فصل تعسفي', RED)], ill='letter'),
    dict(bg='d', src=LAW, card='المادة 11', head=[[('من حقك ', WHITE), ('تعويض', RED)]], cap=[('أو الرجوع لعملك حسب حكم المحكمة', DGREY)], ill='range'),
    dict(bg='l', src=LAW, card='المادة 9', head=[[('ضاع حقك؟', INK)]], cap=[('تواصلي مع ', INK), ('وزارة العمل', TEAL), (' في محافظتك', INK)], ill='office'),
    dict(bg='l', src=None, card=None, head=None, cap=None, ill='end'),
]

def scene_frame(i, t, dur):
    s = SC[i]; dark = s['bg'] == 'd'
    base = Image.new('RGBA', (W, H), (*(DARK if dark else SAND), 255))
    d = ImageDraw.Draw(base)
    # subtle dot grid
    gc = (30, 50, 56) if dark else (232, 223, 205)
    for y in range(40, H, 60):
        for x in range(30, W, 60): d.ellipse((x - 2, y - 2, x + 2, y + 2), fill=gc)
    R = W - 80
    if s['src']:
        reveal(base, text_img(s['src'], 28, 400, DGREY if dark else GREY), R - 22, 120, t, 0.05)
        reveal(base, text_img(s['card'], 40, 800, WHITE if dark else INK), R - 22, 156, t, 0.15)
        p = ease((t - 0.15) / 0.4); d.rounded_rectangle((R - 6, 186, R, 186 + 50 * p), 3, fill=MINT if dark else TEAL)
    if s['head']:
        y = 300
        for k, line in enumerate(s['head']):
            im = rich_img(line, 92, 900); reveal(base, im, R, y, t, 0.35 + k * 0.45, dy=40); y += 150
    k = s['ill']; ix, iy = 90, 600
    if k == 'hook':
        paste(base, fade(ill_hook(t), ease(t / 0.5)), ix, iy + 40)
    elif k == 'cal':
        im, n = ill_calendar(t); paste(base, fade(im, ease(t / 0.4)), ix, iy + 60)
        num = text_img(str(n), 210, 900, RED); paste(base, num, W / 2 + 10, 400)
        reveal(base, text_img('يوم', 84, 800, INK), W / 2 - 10, 500, t, 0.5)
        reveal(base, rich_img([('من الإجازات الخاصة', GREY)], 46, 700), W / 2, 1540, t, 2.6, anchor='c')
    elif k == 'clock':
        paste(base, fade(ill_clock(t), ease(t / 0.4)), ix, iy + 40)
    elif k == 'year':
        im, n = ill_year(t); paste(base, fade(im, ease(t / 0.4)), ix, iy + 120)
        num = text_img(str(max(n, 1)), 200, 900, TEAL); paste(base, num, W / 2 + 10, 400)
        reveal(base, text_img('شهر', 80, 800, INK), W / 2 - 10, 490, t, 0.4)
    elif k == 'crib':
        paste(base, fade(ill_crib(t), ease(t / 0.4)), ix, iy)
    elif k == 'letter':
        paste(base, fade(ill_letter(t), ease(t / 0.4)), ix, iy)
    elif k == 'range':
        im, xa, xb, y, p = ill_range(t); paste(base, fade(im, ease(t / 0.4)), ix, iy + 60)
        y0 = iy + 60 + y
        a = text_img('3 أشهر', 56, 800, WHITE); paste(base, fade(a, ease((t - 0.5) / 0.4)), ix + xa - a.width / 2, y0 + 80)
        b = text_img('12 شهر', 56, 800, RED); paste(base, fade(b, ease((t - 2.0) / 0.4)), ix + xb - b.width / 2, y0 + 80)
        reveal(base, text_img('إلى', 50, 700, DGREY), W / 2, y0 - 150, t, 1.2, anchor='c')
    elif k == 'office':
        paste(base, fade(ill_office(t), ease(t / 0.4)), ix, iy)
    elif k == 'end':
        paste(base, sadu(t), 0, 250)
        reveal(base, text_img('ارسلي الريل', 88, 800, INK), W / 2, 420, t, 0.2, anchor='c')
        reveal(base, rich_img([('لكل أم ', INK), ('تشتغل', RED)], 110, 900), W / 2, 540, t, 0.55, anchor='c')
        # small recap chips
        chips = [('98 يوم أمومة', TEAL), ('ساعة رضاعة لسنة', TEAL), ('رعاية طفل لين سنة', TEAL), ('لا فصل بسبب الحمل', RED)]
        for j, (c, col) in enumerate(chips):
            im = text_img(c, 46, 700, WHITE)
            pill = Image.new('RGBA', (im.width + 70, 96), (0, 0, 0, 0))
            ImageDraw.Draw(pill).rounded_rectangle((0, 0, pill.width - 1, 95), 48, fill=col)
            pill.alpha_composite(im, (35, int(48 - im.height / 2)))
            reveal(base, pill, W / 2, 820 + j * 125, t, 1.0 + j * 0.25, anchor='c')
        nx = text_img('الحلقة الجاية', 40, 700, GREY); reveal(base, nx, W / 2, 1380, t, 2.2, anchor='c')
        reveal(base, text_img('إجازة الأبوة', 72, 900, INK), W / 2, 1430, t, 2.4, anchor='c')
        reveal(base, text_img('للتوعية فقط، والمرجع النص الرسمي لقانون العمل 53/2023', 30, 400, GREY), W / 2, 1720, t, 2.8, anchor='c')
        paste(base, sadu(t + 3), 0, 1640)
    if s['cap']:
        reveal(base, rich_img(s['cap'], 54, 800), W / 2, 1560, t, 1.0, anchor='c')
    # edge fades
    a = min(1, t / 0.22, (dur - t) / 0.22)
    if a < 1:
        ov = Image.new('RGBA', (W, H), (*(DARK if dark else SAND), int(255 * (1 - max(0, a)))))
        base.alpha_composite(ov)
    return base.convert('RGB')

if __name__ == '__main__':
    durs = [float(x) for x in open(f'{ROOT}/durs.txt').read().split()]
    mode = sys.argv[1]
    if mode == 'sheet':
        ims = [scene_frame(i, durs[i] * 0.72, durs[i]).resize((270, 480)) for i in range(len(SC))]
        sh = Image.new('RGB', (270 * 5, 480 * 2), 'white')
        for i, im in enumerate(ims): sh.paste(im, ((i % 5) * 270, (i // 5) * 480))
        sh.save(f'{ROOT}/sheet.png')
    else:
        i = int(mode); n = int(round(durs[i] * FPS)); tmp = f'{ROOT}/clips/_{i:02d}.mp4'
        os.makedirs(f'{ROOT}/clips', exist_ok=True)
        p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                              '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', '-pix_fmt', 'yuv420p', tmp], stdin=subprocess.PIPE)
        for f in range(n): p.stdin.write(scene_frame(i, f / FPS, durs[i]).tobytes())
        p.stdin.close(); p.wait(); os.replace(tmp, f'{ROOT}/clips/{i:02d}.mp4'); print('done', i)
