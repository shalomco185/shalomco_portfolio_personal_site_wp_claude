"""זיהוי טקסט מתמונת תווית (Tesseract, עברית + אנגלית). רץ על השרת, בחינם.

שלבי העיבוד:
  1. סיבוב לפי כיוון הטלפון וגווני אפור.
  2. חיתוך אוטומטי לאזור התווית: הנייר הבהיר על רקע הקרטון.
  3. יישור: מציאת זווית ההטיה של שורות הטקסט ותיקונה.
  4. הגדלה, כך שגובה האותיות יתאים ל-OCR.
  5. כמה מעברי קריאה (מצבי פריסה ועיבוד שונים). נבחר המעבר שבו נמצאה הכתובת הטובה ביותר.
"""
from __future__ import annotations

import io
import logging

from PIL import Image, ImageFilter, ImageOps

from ..config import settings
from .address_parser import ParsedLabel, parse_label

log = logging.getLogger(__name__)

TARGET_WIDTH = 2000  # רוחב התווית אחרי הגדלה (בפיקסלים)
MAX_SIDE = 3000


def _load_gray(image_bytes: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(image_bytes))
    img = ImageOps.exif_transpose(img)
    return img.convert("L")


def _crop_to_label(gray: Image.Image) -> Image.Image:
    """מוצא את המלבן הבהיר הגדול (התווית) וחותך אליו. אם לא נמצא, מחזיר את התמונה כמו שהיא."""
    small = gray.copy()
    small.thumbnail((400, 400))
    sx, sy = gray.width / small.width, gray.height / small.height
    hist = small.histogram()
    # סף בהירות: האחוזון ה-70 (נייר לבן בהיר מהקרטון שסביבו)
    total, acc, thr = sum(hist), 0, 200
    for v, c in enumerate(hist):
        acc += c
        if acc >= total * 0.70:
            thr = max(v, 140)
            break
    mask = small.point(lambda p: 255 if p >= thr else 0).filter(ImageFilter.MinFilter(3))
    bbox = mask.getbbox()
    if not bbox:
        return gray
    x0, y0, x1, y1 = bbox
    area = (x1 - x0) * (y1 - y0) / (small.width * small.height)
    if area < 0.04 or area > 0.97:  # לא נמצאה תווית ברורה, או שהתווית כבר ממלאת את התמונה
        return gray
    pad = 0.03
    w, h = x1 - x0, y1 - y0
    box = (
        max(0, int((x0 - w * pad) * sx)),
        max(0, int((y0 - h * pad) * sy)),
        min(gray.width, int((x1 + w * pad) * sx)),
        min(gray.height, int((y1 + h * pad) * sy)),
    )
    return gray.crop(box)


def _skew_score(img: Image.Image) -> float:
    """כמה "חדות" שורות הטקסט: שונות של סכומי השורות האופקיות."""
    w, h = img.size
    data = img.tobytes()
    rows = [data[r * w:(r + 1) * w].count(0) for r in range(h)]
    mean = sum(rows) / h
    return sum((r - mean) ** 2 for r in rows)


def _deskew(gray: Image.Image) -> Image.Image:
    small = gray.copy()
    small.thumbnail((600, 600))
    bw = small.point(lambda p: 0 if p < 128 else 255).convert("1").convert("L")
    best_angle, best = 0.0, -1.0
    for angle in [a / 2 for a in range(-20, 21)]:  # -10..10 מעלות, בקפיצות של חצי מעלה
        rot = bw.rotate(angle, resample=Image.NEAREST, fillcolor=255)
        score = _skew_score(rot)
        if score > best:
            best, best_angle = score, angle
    if abs(best_angle) < 0.25:
        return gray
    return gray.rotate(best_angle, resample=Image.BICUBIC, expand=True, fillcolor=255)


def _upscale(gray: Image.Image) -> Image.Image:
    w, h = gray.size
    scale = TARGET_WIDTH / w
    scale = min(scale, MAX_SIDE / max(w, h))
    if abs(scale - 1) > 0.1:
        gray = gray.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    return gray


def _binarize(gray: Image.Image) -> Image.Image:
    """סף Otsu: הפרדה בין דיו לנייר."""
    hist = gray.histogram()
    total = sum(hist)
    sum_all = sum(i * c for i, c in enumerate(hist))
    w_b = sum_b = 0
    best_t, best_var = 128, -1.0
    for t, c in enumerate(hist):
        w_b += c
        if w_b == 0:
            continue
        w_f = total - w_b
        if w_f == 0:
            break
        sum_b += t * c
        m_b, m_f = sum_b / w_b, (sum_all - sum_b) / w_f
        var = w_b * w_f * (m_b - m_f) ** 2
        if var > best_var:
            best_var, best_t = var, t
    return gray.point(lambda p: 255 if p > best_t else 0)


def prepare_variants(image_bytes: bytes) -> list[Image.Image]:
    gray = _load_gray(image_bytes)
    label = _crop_to_label(gray)
    label = _deskew(label)
    label = _upscale(label)
    soft = ImageOps.autocontrast(label, cutoff=1)
    # שוליים לבנים: Tesseract מפספס אותיות שנוגעות בקצה התמונה (בעברית: האות הראשונה, מימין)
    pad = max(40, soft.width // 25)
    soft = ImageOps.expand(soft, border=pad, fill=255)
    return [soft, _binarize(soft.filter(ImageFilter.MedianFilter(3)))]


def _ocr(img: Image.Image, psm: int) -> str:
    import pytesseract

    return pytesseract.image_to_string(img, lang=settings.ocr_langs, config=f"--psm {psm}").strip()


def read_label(image_bytes: bytes) -> tuple[str, ParsedLabel]:
    """מריץ כמה מעברי קריאה ומחזיר את הטקסט והניתוח הטובים ביותר."""
    variants = prepare_variants(image_bytes)
    passes = [(variants[0], 6), (variants[1], 6), (variants[0], 4), (variants[1], 11)]
    best_text, best_parsed, best_q = "", parse_label(""), -1.0
    for img, psm in passes:
        try:
            text = _ocr(img, psm)
        except Exception:  # noqa: BLE001 - מעבר שנכשל לא מפיל את השאר
            log.exception("OCR pass failed")
            continue
        parsed = parse_label(text)
        q = parsed.quality
        if q > best_q:
            best_text, best_parsed, best_q = text, parsed, q
        if q >= 8:  # כתובת עם רחוב, מספר ועיר: מספיק טוב, חוסכים זמן
            break
    return best_text, best_parsed


def extract_text(image_bytes: bytes) -> str:
    """תאימות לאחור: מחזיר רק את הטקסט הטוב ביותר."""
    return read_label(image_bytes)[0]
