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
    return [m.group(0) for m in re.finditer(r'[0-9/%.+×÷=]+|[^0-9/%.+×÷=]+', s)]

@lru_cache(maxsize=2048)
def text_img(s, size, w, color):
    """Mixed Arabic + Latin digits, laid out right to left."""
    parts = []
    for r in runs(s):
        lat = bool(re.match(r'[0-9/%.+×÷=]', r))
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


def latin_img(s, size, w, color):
    """Left-to-right math line in the Latin font."""
    f = font('latin', w, size); bb = f.getbbox(s); pad = int(size * 0.12)
    im = Image.new('RGBA', (bb[2] - bb[0] + 6, bb[3] - bb[1] + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((3 - bb[0], pad - bb[1]), s, font=f, fill=color); return im

def fit(im, maxw):
    if im.width <= maxw: return im
    return im.resize((maxw, int(im.height * maxw / im.width)), Image.LANCZOS)

def pill(txt_im, col, padx=36, h=None):
    h = h or txt_im.height - 20
    p = Image.new('RGBA', (txt_im.width + 2 * padx, h), (0, 0, 0, 0))
    ImageDraw.Draw(p).rounded_rectangle((0, 0, p.width - 1, h - 1), h // 2, fill=col)
    p.alpha_composite(txt_im, (padx, int(h / 2 - txt_im.height / 2))); return p

# ---------- illustrations (900 x 900, pasted at (90, 600)) ----------
IW, IH = 900, 900
def ill_clockplus(t):
    cv = Canvas(IW, IH); cx, cy, R = 420, 470, 270
    cv.ell((cx - R - 16, cy - R - 16, cx + R + 16, cy + R + 16), fill=INK)
    cv.ell((cx - R, cy - R, cx + R, cy + R), fill=WHITE)
    for i in range(12):
        a = math.radians(i * 30 - 90); r1 = R - 24; r2 = R - (60 if i % 3 == 0 else 44)
        cv.line([(cx + r1 * math.cos(a), cy + r1 * math.sin(a)), (cx + r2 * math.cos(a), cy + r2 * math.sin(a))], INK, 9 if i % 3 == 0 else 5)
    sp = ease(t / 2.5) * 4.0 + max(0, t - 2.5) * 0.4   # fast then slow
    ah = math.radians(-90 + 150 + 30 * sp); am = math.radians(-90 + 360 * sp)
    q = ease((t - 0.3) / 2.2)
    if q > 0: cv.pie((cx - R + 30, cy - R + 30, cx + R - 30, cy + R - 30), -90 + 150, -90 + 150 + 30 * sp, (*RED, 70))
    cv.line([(cx, cy), (cx + 135 * math.cos(ah), cy + 135 * math.sin(ah))], INK, 16)
    cv.line([(cx, cy), (cx + 210 * math.cos(am), cy + 210 * math.sin(am))], RED, 9)
    cv.ell((cx - 18, cy - 18, cx + 18, cy + 18), fill=INK)
    if t > 0.9:
        s = back((t - 0.9) / 0.5); bx, by = 720, 190
        cv.ell((bx - 85 * s, by - 85 * s, bx + 85 * s, by + 85 * s), fill=RED)
        cv.rr((bx - 45 * s, by - 11 * s, bx + 45 * s, by + 11 * s), 6 * s, fill=WHITE)
        cv.rr((bx - 11 * s, by - 45 * s, bx + 11 * s, by + 45 * s), 6 * s, fill=WHITE)
    return cv.out()

def ill_hours(t, phase):
    """phase 1: fill 8 regular hours; phase 2: add 4 overtime hours + limit."""
    cv = Canvas(IW, IH); cw, ch, gx, gy = 118, 150, 22, 40
    x0 = (IW - (6 * cw + 5 * gx)) / 2; y0 = 220
    n8 = 8 if phase == 2 else int(8 * ease((t - 0.4) / 2.0) + 0.001)
    n4 = int(4 * ease((t - 0.6) / 1.6) + 0.001) if phase == 2 else 0
    cells = []
    for i in range(12):
        r, c = divmod(i, 6); x = x0 + (5 - c) * (cw + gx); y = y0 + r * (ch + gy); cells.append((x, y))
        if i < n8: cv.rr((x, y, x + cw, y + ch), 26, fill=TEAL)
        elif 8 <= i < 8 + n4: cv.rr((x, y, x + cw, y + ch), 26, fill=RED)
        else: cv.rr((x, y, x + cw, y + ch), 26, outline=LINE, width=4)
    if phase == 2 and t > 2.3:
        p = ease((t - 2.3) / 0.5); x = x0 - 30; y = y0 + ch + gy
        cv.line([(x0 - 26, y), (x0 - 26, y + ch * p)], RED, 10)
        cv.rr((x0 - 46, y - 6, x0 - 6, y + 6), 6, fill=RED); cv.rr((x0 - 46, y + ch - 6, x0 - 6, y + ch + 6), 6, fill=RED)
    im = cv.out()
    for i, (x, y) in enumerate(cells):
        on = i < n8 or (8 <= i < 8 + n4)
        lab = latin_img(str(i + 1), 64, 800, WHITE if on else LINE)
        paste(im, lab, x + cw / 2 - lab.width / 2, y + ch / 2 - lab.height / 2)
    if phase == 2 and t > 2.5:
        tag = pill(text_img('حد أقصى 12 ساعة', 46, 800, WHITE), RED, h=86)
        paste(im, fade(tag, ease((t - 2.5) / 0.4)), IW / 2 - tag.width / 2, y0 + 2 * ch + gy + 90)
    return im

def ill_payslip(t):
    cv = Canvas(IW, IH); x0, x1 = 120, 780
    cv.rr((x0, 120, x1, 760), 30, fill=WHITE)
    cv.rr((x0, 120, x1, 230), 30, fill=TEAL); cv.d.rectangle((x0 * S, 200 * S, x1 * S, 230 * S), fill=TEAL)
    rows = [(300, True), (440, False), (580, False)]
    p = ease((t - 0.6) / 0.5)
    cv.rr((x0 + 30, 300 - 20, x1 - 30, 300 + 90), 20, fill=(*TEAL, int(40 * p)))
    for k, (y, on) in enumerate(rows[1:]):
        q = ease((t - 1.2 - k * 0.35) / 0.4)
        if q > 0: cv.line([(x0 + 50, y + 40), (x0 + 50 + (x1 - x0 - 100) * q, y + 40)], RED, 8)
    im = cv.out()
    paste(im, text_img('قسيمة الراتب', 48, 800, WHITE), x1 - 40 - text_img('قسيمة الراتب', 48, 800, WHITE).width, 128)
    labels = [('الأجر الأساسي', '225', INK, TEAL), ('بدل سكن', '60', GREY, GREY), ('بدل نقل', '30', GREY, GREY)]
    for (lab, val, c1, c2), (y, _) in zip(labels, rows):
        a = text_img(lab, 52, 800, c1); paste(im, a, x1 - 60 - a.width, y - 10)
        b = latin_img(val, 64, 800, c2); paste(im, b, x0 + 60, y - 6)
    return im

def ill_equation(t, lhs, res, label, col, icon=None, dark=False):
    im = Image.new('RGBA', (IW, IH), (0, 0, 0, 0)); fg = WHITE if dark else INK
    if icon:
        cv = Canvas(IW, IH); bob = math.sin(t * 2.5) * 8
        if icon == 'sun':
            cx, cy = 450, 110 + bob; r = max(1, 60 * back(t / 0.5))
            for k in range(12):
                a = math.radians(k * 30 + t * 30)
                cv.line([(cx + (r + 18) * math.cos(a), cy + (r + 18) * math.sin(a)), (cx + (r + 44) * math.cos(a), cy + (r + 44) * math.sin(a))], (240, 182, 60), 9)
            cv.ell((cx - r, cy - r, cx + r, cy + r), fill=(240, 182, 60))
        elif icon == 'moon':
            cx, cy = 450, 110 + bob; r = max(1, 64 * back(t / 0.5))
            cv.ell((cx - r, cy - r, cx + r, cy + r), fill=(240, 206, 120)); cv.ell((cx - r + 34, cy - r - 18, cx + r + 34, cy + r - 18), fill=DARK)
            for sx, sy in ((300, 80), (620, 140), (580, 50)):
                rr = 8 + 3 * math.sin(t * 4 + sx); cv.ell((sx - rr, sy - rr, sx + rr, sy + rr), fill=(240, 206, 120))
        im.alpha_composite(cv.out())
    a = fit(latin_img(lhs, 120, 800, fg), 860)
    reveal(im, a, IW / 2, 270, t, 0.4, anchor='c')
    eq = latin_img('=', 110, 800, GREY if not dark else DGREY); reveal(im, eq, IW / 2, 430, t, 1.0, anchor='c')
    if t > 1.3:
        p = ease((t - 1.3) / 0.9)
        dec = len(res.split('.')[1]) if '.' in res else 0
        shown = f'{float(res) * p:.{dec}f}' if p < 1 else res
        r = latin_img(shown, 170, 900, WHITE); rr = latin_img(res, 170, 900, WHITE)
        box = Image.new('RGBA', (rr.width + 110, rr.height + 70), (0, 0, 0, 0))
        ImageDraw.Draw(box).rounded_rectangle((0, 0, box.width - 1, box.height - 1), 50, fill=col)
        box.alpha_composite(r, (box.width - 55 - r.width, 35))
        s = 0.8 + 0.2 * back((t - 1.3) / 0.5)
        bx = box.resize((int(box.width * s), int(box.height * s)), Image.LANCZOS)
        paste(im, fade(bx, ease((t - 1.3) / 0.3)), IW / 2 - bx.width / 2, 560 + (box.height - bx.height) / 2)
    reveal(im, text_img(label, 54, 800, fg), IW / 2, 790, t, 1.8, anchor='c')
    return im

def ill_holiday(t):
    cv = Canvas(IW, IH); x0, y0, cw, gap = 150, 260, 76, 12
    cv.rr((x0 - 30, y0 - 110, x0 + 7 * (cw + gap) + 18, y0 + 5 * (cw + gap) + 20), 28, fill=WHITE)
    cv.rr((x0 - 30, y0 - 110, x0 + 7 * (cw + gap) + 18, y0 - 40), 28, fill=TEAL)
    for xx in (x0 + 110, x0 + 510): cv.rr((xx - 8, y0 - 140, xx + 8, y0 - 86), 8, fill=INK)
    for i in range(35):
        r, c = divmod(i, 7); c = 6 - c; x = x0 + c * (cw + gap); y = y0 + r * (cw + gap)
        weekend = c in (0, 1)
        cv.rr((x, y, x + cw, y + cw), 14, fill=(232, 222, 202) if weekend else (244, 240, 230))
    tx, ty = x0 + 0 * (cw + gap), y0 + 2 * (cw + gap)
    p = ease((t - 0.8) / 0.5)
    if p > 0:
        cv.rr((tx, ty, tx + cw, ty + cw), 14, fill=RED)
        r = 70 * back((t - 0.8) / 0.5); cx, cy = tx + cw / 2, ty + cw / 2
        cv.ell((cx - r, cy - r, cx + r, cy + r), outline=RED, width=8)
    im = cv.out()
    if t > 1.6:
        c1 = pill(rich_img([('+7.500', WHITE), (' ريال', WHITE)], 50, 800), TEAL, h=96)
        paste(im, fade(c1, ease((t - 1.6) / 0.4)), IW / 2 + 20, 780 + 20 * (1 - ease((t - 1.6) / 0.4)))
        c2 = pill(text_img('أو يوم بديل', 50, 800, WHITE), INK, h=96)
        paste(im, fade(c2, ease((t - 2.2) / 0.4)), IW / 2 - 20 - c2.width, 780 + 20 * (1 - ease((t - 2.2) / 0.4)))
    return im

# ---------- scenes ----------
LAW = 'قانون العمل العماني 53/2023'
EX = 'مثال توضيحي'
SC = [
    dict(bg='l', src=LAW, card='المرسوم السلطاني 53/2023', head=[[('اشتغلت ساعات زيادة؟', INK)], [('كيف ', INK), ('تنحسب', RED), ('؟', INK)]], cap=None),
    dict(bg='l', src=LAW, card='المادة 70', head=[[('دوامك ', INK), ('8 ساعات', TEAL), (' باليوم', INK)]], cap=[('و40 ساعة في الأسبوع', GREY)]),
    dict(bg='l', src=LAW, card='المادة 71', head=[[('اللي بعدها ', INK), ('إضافي', RED)]], cap=[('الأصلي والإضافي مع بعض', GREY)]),
    dict(bg='l', src=LAW, card='المادة 1', head=[[('الحساب على ', INK), ('الأساسي', TEAL)]], cap=[('البدلات ', INK), ('ما تدخل', RED)]),
    dict(bg='l', src=EX, card='الخطوة 1', head=[[('مثال', RED)], [('راتب أساسي 225 ريال', INK)]], cap=None),
    dict(bg='l', src=EX, card='الخطوة 2', head=[[('أجر ', INK), ('الساعة', TEAL)]], cap=None),
    dict(bg='l', src=LAW, card='المادة 71', head=[[('نهاري ', INK), ('+25%', RED)]], cap=[('على الأقل', GREY)]),
    dict(bg='d', src=LAW, card='المادتان 1 و71', head=[[('ليلي ', WHITE), ('+50%', RED)]], cap=[('من 9 مساء إلى 5 الفجر', DGREY)]),
    dict(bg='l', src=LAW, card='المادة 71', head=[[('اشتغلت يوم راحتك', INK)], [('أو ', INK), ('عطلة رسمية', RED), ('؟', INK)]], cap=None),
    dict(bg='l', src=None, card=None, head=None, cap=None),
]

def scene_frame(i, t, dur):
    s = SC[i]; dark = s['bg'] == 'd'
    base = Image.new('RGBA', (W, H), (*(DARK if dark else SAND), 255)); d = ImageDraw.Draw(base)
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
            reveal(base, fit(rich_img(line, 92, 900), W - 160), R, y, t, 0.35 + k * 0.45, dy=40); y += 150
    ix, iy = 90, 600; fa = ease(t / 0.4)
    if i == 0: paste(base, fade(ill_clockplus(t), fa), ix, iy)
    elif i == 1: paste(base, fade(ill_hours(t, 1), fa), ix, iy)
    elif i == 2: paste(base, ill_hours(t, 2), ix, iy)
    elif i == 3: paste(base, fade(ill_payslip(t), fa), ix, iy)
    elif i == 4: paste(base, ill_equation(t, '225 ÷ 30', '7.500', 'ريال أجر اليوم', TEAL), ix, iy)
    elif i == 5: paste(base, ill_equation(t, '7.500 ÷ 8', '0.9375', 'ريال لكل ساعة', TEAL), ix, iy)
    elif i == 6: paste(base, ill_equation(t, '0.9375 × 4 × 1.25', '4.688', 'ريال عن 4 ساعات نهارية', RED, 'sun'), ix, iy - 40)
    elif i == 7: paste(base, ill_equation(t, '0.9375 × 4 × 1.50', '5.625', 'ريال عن 4 ساعات ليلية', RED, 'moon', True), ix, iy - 40)
    elif i == 8: paste(base, fade(ill_holiday(t), fa), ix, iy)
    elif i == 9:
        paste(base, sadu(t), 0, 250)
        reveal(base, text_img('ارسل الريل', 88, 800, INK), W / 2, 400, t, 0.2, anchor='c')
        reveal(base, rich_img([('لكل واحد ', INK), ('يشتغل', RED)], 110, 900), W / 2, 520, t, 0.55, anchor='c')
        chips = [('8 ساعات باليوم', TEAL), ('نهاري +25%', TEAL), ('ليلي +50%', INK), ('العطلة أجر يوم أو يوم بديل', RED)]
        for j, (c, col) in enumerate(chips):
            reveal(base, pill(text_img(c, 46, 700, WHITE), col, padx=36, h=96), W / 2, 800 + j * 125, t, 1.0 + j * 0.25, anchor='c')
        reveal(base, text_img('النسب حد أدنى، وعقدك ممكن يعطيك أكثر', 44, 700, TEAL), W / 2, 1340, t, 2.2, anchor='c')
        reveal(base, text_img('للتوعية فقط، والمرجع النص الرسمي لقانون العمل 53/2023', 30, 400, GREY), W / 2, 1720, t, 2.8, anchor='c')
        paste(base, sadu(t + 3), 0, 1640)
    if s['cap']:
        reveal(base, fit(rich_img(s['cap'], 54, 800), W - 160), W / 2, 1560, t, 1.0, anchor='c')
    a = min(1, t / 0.22, (dur - t) / 0.22)
    if a < 1: base.alpha_composite(Image.new('RGBA', (W, H), (*(DARK if dark else SAND), int(255 * (1 - max(0, a))))))
    return base.convert('RGB')
if __name__ == '__main__':
    durs = [float(x) for x in open(f'{ROOT}/durs.txt').read().split()]
    mode = sys.argv[1]
    if mode == 'sheet':
        ims = [scene_frame(i, durs[i] * 0.72, durs[i]).resize((270, 480)) for i in range(len(SC))]
        sh = Image.new("RGB", (270 * 5, 480 * 2), 'white')
        for i, im in enumerate(ims): sh.paste(im, ((i % 5) * 270, (i // 5) * 480))
        sh.save(f'{ROOT}/sheet.png')
    else:
        i = int(mode); n = int(round(durs[i] * FPS)); tmp = f'{ROOT}/clips/_{i:02d}.mp4'
        os.makedirs(f'{ROOT}/clips', exist_ok=True)
        p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                              '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', '-pix_fmt', 'yuv420p', tmp], stdin=subprocess.PIPE)
        for f in range(n): p.stdin.write(scene_frame(i, f / FPS, durs[i]).tobytes())
        p.stdin.close(); p.wait(); os.replace(tmp, f'{ROOT}/clips/{i:02d}.mp4'); print('done', i)
