"""זיהוי טקסט מתמונת תווית (Tesseract, עברית + אנגלית). רץ על השרת, בחינם."""
from __future__ import annotations

import io

from PIL import Image, ImageFilter, ImageOps

from ..config import settings

MAX_SIDE = 2400


def _prepare(image_bytes: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(image_bytes))
    img = ImageOps.exif_transpose(img)  # סיבוב לפי כיוון הטלפון
    img = img.convert("L")  # גווני אפור
    w, h = img.size
    scale = 1.0
    if max(w, h) > MAX_SIDE:
        scale = MAX_SIDE / max(w, h)
    elif max(w, h) < 1200:
        scale = 1200 / max(w, h)
    if scale != 1.0:
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    img = ImageOps.autocontrast(img, cutoff=1)
    img = img.filter(ImageFilter.SHARPEN)
    return img


def extract_text(image_bytes: bytes) -> str:
    import pytesseract

    img = _prepare(image_bytes)
    # psm 4: עמודה אחת של טקסט בגדלים משתנים - מתאים לתוויות
    text = pytesseract.image_to_string(img, lang=settings.ocr_langs, config="--psm 4")
    if len(text.strip()) < 10:
        text = pytesseract.image_to_string(img, lang=settings.ocr_langs, config="--psm 11")
    return text.strip()
