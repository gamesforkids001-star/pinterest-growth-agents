"""Pillow pin images, 1000x1500 (2:3), big text for small screens. 4 layouts x 5 palettes."""
import hashlib, os
from PIL import Image, ImageDraw, ImageFont
W, H = 1000, 1500
FONTS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]
MONO = ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"] + FONTS
LAYOUTS = ["bold", "steps", "checklist", "cheatsheet"]

def font(size, mono=False):
    for p in (MONO if mono else FONTS):
        if os.path.exists(p): return ImageFont.truetype(p, size)
    return ImageFont.load_default(size=size)

def wrap(d, text, f, width):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= width: cur = t
        else:
            if cur: lines.append(cur)
            cur = w
    return lines + ([cur] if cur else [])

def fit(d, text, start, minimum, width, max_lines, mono=False):
    for s in range(start, minimum - 1, -4):
        f = font(s, mono); ls = wrap(d, text, f, width)
        if len(ls) <= max_lines and all(d.textlength(l, font=f) <= width for l in ls): return f, ls
    f = font(minimum, mono); return f, wrap(d, text, f, width)[:max_lines]

def _lum(hexc):
    r, g, b = (int(hexc[i:i + 2], 16) for i in (1, 3, 5)); return 0.299 * r + 0.587 * g + 0.114 * b

def icon(d, cat, x, y, s, col):
    if cat == "pdf": d.rounded_rectangle([x, y, x + s * .75, y + s], 12, outline=col, width=8); d.line([x + s * .15, y + s * .4, x + s * .6, y + s * .4], fill=col, width=8); d.line([x + s * .15, y + s * .65, x + s * .6, y + s * .65], fill=col, width=8)
    elif cat == "image": d.rounded_rectangle([x, y, x + s, y + s * .8], 12, outline=col, width=8); d.polygon([(x + s * .1, y + s * .7), (x + s * .4, y + s * .35), (x + s * .65, y + s * .7)], fill=col); d.ellipse([x + s * .7, y + s * .15, x + s * .85, y + s * .3], fill=col)
    elif cat == "calc":
        d.rounded_rectangle([x, y, x + s * .8, y + s], 12, outline=col, width=8)
        for i in range(3):
            for j in range(3): d.rectangle([x + s * (.12 + .22 * i), y + s * (.3 + .22 * j), x + s * (.24 + .22 * i), y + s * (.42 + .22 * j)], fill=col)
    elif cat == "dev": d.text((x, y), "{ }", font=font(int(s)), fill=col)
    else: d.text((x, y), "Aa", font=font(int(s * .9)), fill=col)

def render(spec, out_path, brand="Easy File Online Tools", colors=None):
    """spec: layout, title, benefit, bullets[], tool_name, category, seed"""
    colors = colors or ["#0F172A", "#1D4ED8", "#B45309", "#047857", "#BE123C"]
    h = int(hashlib.sha256(str(spec.get("seed", spec["title"])).encode()).hexdigest(), 16)
    bg = colors[h % len(colors)]; dark = _lum(bg) < 150
    fg, sub = ("#FFFFFF", "#E2E8F0") if dark else ("#0F172A", "#334155")
    card = "#FFFFFF" if dark else "#0F172A"; cfg = "#0F172A" if dark else "#FFFFFF"
    layout = spec.get("layout") if spec.get("layout") in LAYOUTS else LAYOUTS[h % 4]
    im = Image.new("RGB", (W, H), bg); d = ImageDraw.Draw(im); m = 70; tw = W - 2 * m
    icon(d, spec.get("category", "text"), m, 70, 110, fg)
    d.text((m + 160, 95), spec["tool_name"], font=font(40), fill=sub)
    bullets = [b for b in spec.get("bullets", []) if b][:5]
    if layout == "bold" or not bullets:
        f, ls = fit(d, spec["title"], 110, 64, tw, 5); y = 330
        for l in ls: d.text((m, y), l, font=f, fill=fg); y += int(f.size * 1.25)
        d.rounded_rectangle([m, H - 470, W - m, H - 230], 24, fill=card)
        f2, l2 = fit(d, spec["benefit"], 56, 36, tw - 80, 3)
        yy = H - 440
        for l in l2: d.text((m + 40, yy), l, font=f2, fill=cfg); yy += int(f2.size * 1.3)
    else:
        f, ls = fit(d, spec["title"], 84, 54, tw, 3); y = 270
        for l in ls: d.text((m, y), l, font=f, fill=fg); y += int(f.size * 1.25)
        top = y + 50; d.rounded_rectangle([m - 20, top, W - m + 20, H - 200], 28, fill=card)
        each = (H - 200 - top - 60) // len(bullets); yy = top + 40
        mono = layout == "cheatsheet"
        for i, b in enumerate(bullets):
            mark = {"steps": f"{i + 1}", "checklist": "\u2713", "cheatsheet": ">"}.get(layout, str(i + 1))
            fb, lb = fit(d, b, 46, 30, tw - 150, 3, mono)
            d.ellipse([m + 5, yy + 2, m + 75, yy + 72], fill=bg); d.text((m + 40 - d.textlength(mark, font=font(40)) / 2, yy + 14), mark, font=font(40), fill=fg)
            ty = yy
            for l in lb: d.text((m + 110, ty), l, font=fb, fill=cfg); ty += int(fb.size * 1.25)
            yy += each
    d.text((m, H - 130), brand, font=font(38), fill=sub)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    im.save(out_path, "JPEG", quality=86, optimize=True); return out_path
