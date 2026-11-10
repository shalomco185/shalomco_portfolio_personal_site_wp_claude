"""Generate realistic Hebrew shipping-label photos for OCR benchmarking."""
import json, random, sys
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
FONT_R = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
CASES = [
  # (lines, expected street, expected city)
  (["שולח: אקספרס בע\"מ", "המסגר 12, תל אביב", "נמען: דנה לוי", "כתובת: הרצל 25, רמת גן", "טלפון: 052-1234567"], "הרצל 25", "רמת גן"),
  (["משה כהן", "ויצמן 14", "כפר סבא", "054-7654321"], "ויצמן 14", "כפר סבא"),
  (["לכבוד: יעל אברהם", "רחוב הנשיא 8 דירה 3", "חיפה", "טל: 050-1112233"], "הנשיא 8", "חיפה"),
  (["מספר משלוח: 7290005778230", "משקל: 1.2 ק\"ג", "נמען: אבי ביטון", "ז'בוטינסקי 102, פתח תקווה", "0523334455"], "ז'בוטינסקי 102", "פתח תקווה"),
  (["פתח תקווה", "רוטשילד 45", "שירה מזרחי", "058-9998877"], "רוטשילד 45", "פתח תקווה"),
  (["SHIP TO:", "Rina Levi", "12 Dizengoff St", "Tel Aviv", "Israel"], "Dizengoff", "Tel Aviv"),
  (["נמען", "אורי שלום", "שדרות בן גוריון 30", "אשדוד", "053-1231231"], "בן גוריון 30", "אשדוד"),
  (["מאת: חנות הספרים", "אלנבי 99 תל אביב", "אל: נועה פרץ", "הגפן 7, ראשון לציון", "קומה 2"], "הגפן 7", "ראשון לציון"),
  (["רונית גבאי", "בית לחם 21 ירושלים", "02-6543210"], "בית לחם 21", "ירושלים"),
  (["כתובת למשלוח", "האלון 5", "רעננה", "דוד יוסף 052-8887766"], "האלון 5", "רעננה"),
  (["Order #554433", "נמען: מיכל דהן", "סוקולוב 60 הרצליה", "054-1112222"], "סוקולוב 60", "הרצליה"),
  (["שולח: מחסן מרכזי", "החרש 4, חולון", "לכבוד", "גלעד כץ", "הרימון 3, נס ציונה"], "הרימון 3", "נס ציונה"),
]
def barcode(d, x, y, w, h, rnd):
    cx = x
    while cx < x + w:
        bw = rnd.choice([2, 3, 5]); d.rectangle([cx, y, cx + bw, y + h], fill="black"); cx += bw + rnd.choice([2, 3, 4])
def make(case_i, lines, variant, out):
    rnd = random.Random(case_i * 10 + variant)
    W, H = 900, 260 + 70 * len(lines)
    lab = Image.new("RGB", (W, H), (250, 250, 246)); d = ImageDraw.Draw(lab)
    barcode(d, 60, 20, 520, 110, rnd)
    y = 160
    for k, ln in enumerate(lines):
        size = rnd.choice([30, 34, 38]) if k else 34
        f = ImageFont.truetype(FONT_B if rnd.random() < .5 else FONT_R, size)
        rtl = any("֐" <= ch <= "׿" for ch in ln)
        if rtl: d.text((W - 40, y), ln, fill=(20, 20, 20), font=f, direction="rtl", anchor="ra")
        else: d.text((40, y), ln, fill=(20, 20, 20), font=f, anchor="la")
        y += 70
    # put the label on a cardboard background, perspective + rotation
    bg = Image.new("RGB", (1500, 1600), (172, 140, 102))
    ang = rnd.uniform(-7, 7) if variant < 3 else rnd.choice([-1, 1]) * rnd.uniform(7, 11)
    lab_r = lab.rotate(ang, expand=True, fillcolor=(172, 140, 102), resample=Image.BICUBIC)
    bg.paste(lab_r, (rnd.randint(150, 350), rnd.randint(200, 450)))
    # uneven lighting
    grad = Image.linear_gradient("L").resize(bg.size).rotate(rnd.choice([0, 90, 45]), expand=False)
    shade = Image.merge("RGB", [grad.point(lambda v: 120 + v // 2)] * 3)
    bg = Image.blend(bg, Image.composite(bg, shade, grad.point(lambda v: 160)), .35)
    if variant >= 3:  # perspective tilt (phone not parallel to the box)
        w0, h0 = bg.size; k = rnd.uniform(0.04, 0.09)
        bg = bg.transform(bg.size, Image.QUAD, (w0*k, 0, 0, h0, w0, h0, w0*(1-k), 0), resample=Image.BICUBIC, fillcolor=(172,140,102))
    if variant >= 1: bg = bg.filter(ImageFilter.GaussianBlur(rnd.uniform(1.0, 1.8) if variant < 4 else rnd.uniform(2.0, 2.5)))
    if variant >= 2:
        noise = Image.effect_noise(bg.size, 22).convert("RGB"); bg = Image.blend(bg, noise, .12)
    bg = bg.resize((1200, 1280) if variant < 5 else (900, 960))  # v5: label farther away  # phone photo downscaled by the app (whole box in frame)
    bg.save(out, "JPEG", quality=70)
meta = []
for i, (lines, street, city) in enumerate(CASES):
    for v in (range(3, 6) if "--hard" in sys.argv else range(3)):
        fn = f"case{i:02d}_v{v}.jpg"; make(i, lines, v, fn); meta.append({"file": fn, "street": street, "city": city})
json.dump(meta, open("meta_hard.json" if "--hard" in sys.argv else "meta.json", "w"), ensure_ascii=False, indent=1)
print(len(meta), "images")
