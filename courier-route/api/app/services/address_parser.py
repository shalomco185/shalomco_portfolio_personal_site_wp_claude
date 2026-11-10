"""חילוץ כתובת, טלפון ושם נמען מטקסט של תווית משלוח (תוצאת OCR).

הגישה: מפרקים לשורות, נותנים ניקוד לכל שורה (מילת רחוב, מספר בית, שם עיר,
כותרת "כתובת"/"Address") ומחזירים מועמדים מדורגים. השליח תמיד מאשר או מתקן
את הכתובת לפני השמירה, כך שהחילוץ לא חייב להיות מושלם.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

# ערים ויישובים נפוצים (אפשר להרחיב). משמש לזיהוי שורת עיר.
CITIES = [
    "ירושלים", "תל אביב", "תל-אביב", "תל אביב-יפו", "יפו", "חיפה", "ראשון לציון", "פתח תקווה",
    "פתח תקוה", "אשדוד", "נתניה", "באר שבע", "בני ברק", "חולון", "רמת גן", "אשקלון", "רחובות",
    "בת ים", "בית שמש", "כפר סבא", "הרצליה", "חדרה", "מודיעין", "מודיעין-מכבים-רעות", "נצרת",
    "לוד", "רמלה", "רעננה", "ראש העין", "הוד השרון", "גבעתיים", "קריית גת", "קרית גת",
    "נהריה", "עפולה", "קריית אתא", "קרית אתא", "יבנה", "אילת", "אום אל-פחם", "אלעד",
    "קריית ביאליק", "קרית ביאליק", "קריית מוצקין", "קרית מוצקין", "קריית ים", "קרית ים",
    "נס ציונה", "כרמיאל", "טבריה", "צפת", "דימונה", "נתיבות", "שדרות", "אופקים", "ערד",
    "קריית שמונה", "קרית שמונה", "מעלות-תרשיחא", "טירת כרמל", "נשר", "יקנעם", "יקנעם עילית",
    "אור יהודה", "יהוד", "יהוד-מונוסון", "גני תקווה", "קריית אונו", "קרית אונו", "גבעת שמואל",
    "רמת השרון", "כפר יונה", "אבן יהודה", "זכרון יעקב", "פרדס חנה-כרכור", "פרדס חנה",
    "אור עקיבא", "קיסריה", "בית שאן", "מגדל העמק", "נוף הגליל", "שוהם", "באר יעקב",
    "גדרה", "גן יבנה", "קריית מלאכי", "קרית מלאכי", "מבשרת ציון", "מעלה אדומים", "ביתר עילית",
    "מודיעין עילית", "אריאל", "טייבה", "טירה", "כפר קאסם", "סח'נין", "שפרעם", "רהט", "עכו",
    "Tel Aviv", "Jerusalem", "Haifa", "Rishon LeZion", "Petah Tikva", "Ashdod", "Netanya",
    "Beer Sheva", "Be'er Sheva", "Bnei Brak", "Holon", "Ramat Gan", "Herzliya", "Raanana",
    "Kfar Saba", "Rehovot", "Bat Yam", "Modiin", "Eilat",
]

STREET_WORDS = r"(?:רחוב|רח'|רח׳|רח\.|שדרות|שד'|שד׳|שד\.|דרך|סמטת|סמ'|כיכר|ככר|מעלה|משעול|שכונת|שכ'|" \
    r"street|st\.|st|road|rd\.|ave|avenue|blvd)"
LABEL_WORDS = r"(?:כתובת(?:\s*למשלוח)?|כתובת מסירה|מען|address|ship\s*to|deliver\s*to|shipping address)"
NAME_LABELS = r"(?:שם(?:\s*הנמען)?|נמען|לכבוד|אל|name|recipient|to)"
NOISE_WORDS = r"(?:שולח|from|sender|משקל|weight|מספר הזמנה|מספר משלוח|order|tracking|ברקוד|barcode|הזמנה|ק\"ג)"
# תחילת אזור השולח / הנמען בתווית (כדי לא לבחור את כתובת השולח)
SENDER_START = re.compile(r"^\s*(?:שולח|מאת|from|sender)\b", re.IGNORECASE)
RECIPIENT_START = re.compile(
    r"^\s*(?:נמען|לכבוד|אל\s*:|ship\s*to|deliver\s*to|to\s*:|כתובת\s*למשלוח|כתובת\s*מסירה)", re.IGNORECASE
)
# רחוב + מספר בית: "הרצל 25", "שדרות בן גוריון 30א", "12 Dizengoff St"
STREET_NUM_RE = re.compile(
    r"(?:[א-ת][א-ת'\"׳״\-]*(?:\s+[א-ת][א-ת'\"׳״\-]*){0,3}\s+\d{1,4}[א-ת]?(?![\d\-/]))"
    r"|(?:(?<![\d\-])\d{1,4}[A-Za-z]?\s+[A-Za-z][A-Za-z']+(?:\s+[A-Za-z]+){0,3})"
)

PHONE_RE = re.compile(r"(?<!\d)(?:\+?972[-\s]?|0)(?:5\d|[2-489]|7\d)[-\s]?\d{3}[-\s]?\d{4}(?!\d)")
HOUSE_NUM_RE = re.compile(r"(?<![\d/])\d{1,4}(?:\s?[א-תa-zA-Z](?![א-תa-zA-Z]))?(?![\d/])")
ZIP_RE = re.compile(r"(?<!\d)\d{5}(?:\d{2})?(?!\d)")


@dataclass
class ParsedLabel:
    candidates: list[str] = field(default_factory=list)
    phone: str | None = None
    recipient: str | None = None
    details: str | None = None  # קומה, דירה, כניסה...
    lines: list[str] = field(default_factory=list)
    quality: float = 0.0  # עד כמה בטוחים בכתובת הראשונה (לבחירה בין מעברי OCR)


def _clean_line(line: str) -> str:
    line = line.replace("|", " ").replace("_", " ")
    line = re.sub(r"[“”\"«»]", "", line)
    line = re.sub(r"\s+", " ", line)
    return line.strip(" -–—:;.,")


# שמות ערים שהם גם מילת רחוב ("שדרות רוטשילד"): נחשבים עיר רק בסוף השורה
AMBIGUOUS_CITIES = {"שדרות"}


def _find_city(text: str) -> str | None:
    low = text.lower()
    best = None
    for city in CITIES:
        if city.lower() not in low:
            continue
        if city in AMBIGUOUS_CITIES and not re.search(rf"{city}\s*$", text.strip()):
            continue
        if best is None or len(city) > len(best):
            best = city
    return best


_CITY_BY_KEY = {re.sub(r"[\s\-]", "", c.lower()): c for c in CITIES}


def _fuzzy_city(line: str) -> str | None:
    """מזהה שורה שהיא שם עיר, גם עם טעות OCR קטנה ("כפר סבה")."""
    text = _strip_label(line).strip(" ,.")
    if not text or len(text) > 24 or re.search(r"\d", text):
        return None
    exact = _find_city(text)
    if exact and len(text) <= len(exact) + 3:
        return exact
    key = re.sub(r"[\s\-]", "", text.lower())
    match = difflib.get_close_matches(key, list(_CITY_BY_KEY), n=1, cutoff=0.8)
    return _CITY_BY_KEY[match[0]] if match else None


def _strip_label(line: str) -> str:
    return re.sub(rf"^\s*{LABEL_WORDS}\s*[:：\-]?\s*", "", line, flags=re.IGNORECASE).strip()


def _score(line: str, prev_is_label: bool) -> float:
    if not line or len(line) < 3:
        return -10
    s = 0.0
    no_phone = PHONE_RE.sub("", line)
    if re.search(LABEL_WORDS, line, re.IGNORECASE):
        s += 3
    if re.search(rf"(?:^|\s){STREET_WORDS}(?:\s|$)", line, re.IGNORECASE):
        s += 3
    if STREET_NUM_RE.search(ZIP_RE.sub("", no_phone)):
        s += 3  # תבנית של רחוב ומספר בית
    elif HOUSE_NUM_RE.search(ZIP_RE.sub("", no_phone)):
        s += 1
    if _find_city(line):
        s += 2
    if re.search(r"[א-ת]{2,}", line) or re.search(r"[A-Za-z]{3,}", line):
        s += 0.5
    if prev_is_label:
        s += 2
    if re.search(NOISE_WORDS, line, re.IGNORECASE):
        s -= 4
    if PHONE_RE.search(line) and len(no_phone.strip()) < 4:
        s -= 5
    if len(re.findall(r"\d", no_phone)) > 8:  # מספר מעקב / ברקוד
        s -= 4
    return s


DETAILS_RE = re.compile(
    r"(?:(?<=\s)|^)(דירה|ד'|ד׳|קומה|ק'|ק׳|כניסה|בניין|בנין|מגדל|apt\.?|apartment|floor|entrance)\s*:?\s*([^\s,]+)",
    re.IGNORECASE,
)


def extract_details(text: str) -> str | None:
    """מחלץ פרטי כתובת (קומה, דירה, כניסה) מטקסט התווית."""
    found: list[str] = []
    for line in (text or "").splitlines():
        if re.search(NOISE_WORDS, line, re.IGNORECASE):
            continue
        for word, value in DETAILS_RE.findall(_clean_line(line)):
            if len(value) > 6:
                continue
            item = f"{word} {value}"
            if item not in found:
                found.append(item)
    return ", ".join(found) or None


def normalize_address(addr: str) -> str:
    """ניקוי כתובת לפני המרה לקואורדינטות."""
    addr = _strip_label(_clean_line(addr))
    addr = PHONE_RE.sub("", addr)
    addr = ZIP_RE.sub("", addr)
    addr = re.sub(r"(?:^|\s)(?:רחוב|רח'|רח׳|רח\.)\s*", " ", addr)
    addr = re.sub(r"(?:^|\s)(?:שד'|שד׳|שד\.)\s*", " שדרות ", addr)
    addr = re.sub(r"(?:^|\s)(?:דירה|ד'|קומה|כניסה|apt\.?|floor)\s*[^\s,]+", "", addr, flags=re.IGNORECASE)
    addr = re.sub(r"(\d[א-ת]?)\.\s+(?=[א-תA-Za-z])", r"\1, ", addr)  # "הרימון 3. נס ציונה" -> "הרימון 3, נס ציונה"
    addr = re.sub(r"\s*,\s*", ", ", addr)
    addr = re.sub(r"\s+", " ", addr)
    return addr.strip(" ,-")


def parse_label(text: str, max_candidates: int = 4) -> ParsedLabel:
    raw_lines = [ln for ln in (text or "").splitlines()]
    lines = [_clean_line(ln) for ln in raw_lines]
    lines = [ln for ln in lines if ln]
    result = ParsedLabel(lines=lines)

    result.details = extract_details(text)

    phone = PHONE_RE.search(text or "")
    if phone:
        result.phone = re.sub(r"[\s-]", "", phone.group(0))

    for i, line in enumerate(lines):
        m = re.match(rf"^\s*{NAME_LABELS}\s*[:：]\s*(.+)$", line, re.IGNORECASE)
        if m and not re.search(r"\d", m.group(1)):
            result.recipient = m.group(1).strip()[:120]
            break

    # אזורי שולח / נמען
    in_sender = [False] * len(lines)
    state = False
    for i, line in enumerate(lines):
        if RECIPIENT_START.search(line):
            state = False
        elif SENDER_START.search(line):
            state = True
        in_sender[i] = state

    scored: list[tuple[float, str]] = []
    for i, line in enumerate(lines):
        prev_is_label = i > 0 and bool(re.fullmatch(rf"\s*{LABEL_WORDS}\s*[:：]?\s*", lines[i - 1], re.IGNORECASE))
        content = _strip_label(line)
        if not content:
            continue
        s = _score(line, prev_is_label)
        if in_sender[i]:
            s -= 4
        candidate = content
        if not _find_city(content) and STREET_NUM_RE.search(content):
            # רחוב בשורה אחת והעיר בשורה הבאה או הקודמת
            nxt = _fuzzy_city(lines[i + 1]) if i + 1 < len(lines) else None
            prv = _fuzzy_city(lines[i - 1]) if i > 0 and not in_sender[i - 1] else None
            city = nxt or prv
            if city:
                candidate = f"{content}, {city}"
                s += 2
        scored.append((s, candidate))

    seen: set[str] = set()
    ranked = sorted(scored, key=lambda t: t[0], reverse=True)
    for threshold in (3, 2):  # קודם מועמדים ודאיים; אם אין, גם פחות ודאיים
        for s, cand in ranked:
            norm = normalize_address(cand)
            if s < threshold or not norm or norm in seen:
                continue
            seen.add(norm)
            result.candidates.append(norm)
            if not result.quality:
                result.quality = s + (1 if result.phone else 0)
            if len(result.candidates) >= max_candidates:
                break
        if result.candidates:
            break
    return result
