"""חילוץ כתובת, טלפון ושם נמען מטקסט של תווית משלוח (תוצאת OCR).

הגישה: מפרקים לשורות, נותנים ניקוד לכל שורה (מילת רחוב, מספר בית, שם עיר,
כותרת "כתובת"/"Address") ומחזירים מועמדים מדורגים. השליח תמיד מאשר או מתקן
את הכתובת לפני השמירה, כך שהחילוץ לא חייב להיות מושלם.
"""
from __future__ import annotations

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
NAME_LABELS = r"(?:שם(?:\s*הנמען)?|נמען|לכבוד|name|recipient|to)"
NOISE_WORDS = r"(?:שולח|from|sender|משקל|weight|מספר הזמנה|order|tracking|ברקוד|barcode|הזמנה)"

PHONE_RE = re.compile(r"(?<!\d)(?:\+?972[-\s]?|0)(?:5\d|[2-489]|7\d)[-\s]?\d{3}[-\s]?\d{4}(?!\d)")
HOUSE_NUM_RE = re.compile(r"(?<![\d/])\d{1,4}(?:\s?[א-תa-zA-Z](?![א-תa-zA-Z]))?(?![\d/])")
ZIP_RE = re.compile(r"(?<!\d)\d{5}(?:\d{2})?(?!\d)")


@dataclass
class ParsedLabel:
    candidates: list[str] = field(default_factory=list)
    phone: str | None = None
    recipient: str | None = None
    lines: list[str] = field(default_factory=list)


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
    if HOUSE_NUM_RE.search(ZIP_RE.sub("", no_phone)):
        s += 2
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


def normalize_address(addr: str) -> str:
    """ניקוי כתובת לפני המרה לקואורדינטות."""
    addr = _strip_label(_clean_line(addr))
    addr = PHONE_RE.sub("", addr)
    addr = ZIP_RE.sub("", addr)
    addr = re.sub(r"(?:^|\s)(?:רחוב|רח'|רח׳|רח\.)\s*", " ", addr)
    addr = re.sub(r"(?:^|\s)(?:שד'|שד׳|שד\.)\s*", " שדרות ", addr)
    addr = re.sub(r"(?:^|\s)(?:דירה|ד'|קומה|כניסה|apt\.?|floor)\s*[^\s,]+", "", addr, flags=re.IGNORECASE)
    addr = re.sub(r"\s*,\s*", ", ", addr)
    addr = re.sub(r"\s+", " ", addr)
    return addr.strip(" ,-")


def parse_label(text: str, max_candidates: int = 4) -> ParsedLabel:
    raw_lines = [ln for ln in (text or "").splitlines()]
    lines = [_clean_line(ln) for ln in raw_lines]
    lines = [ln for ln in lines if ln]
    result = ParsedLabel(lines=lines)

    phone = PHONE_RE.search(text or "")
    if phone:
        result.phone = re.sub(r"[\s-]", "", phone.group(0))

    for i, line in enumerate(lines):
        m = re.match(rf"^\s*{NAME_LABELS}\s*[:：]\s*(.+)$", line, re.IGNORECASE)
        if m and not re.search(r"\d", m.group(1)):
            result.recipient = m.group(1).strip()[:120]
            break

    scored: list[tuple[float, str]] = []
    for i, line in enumerate(lines):
        prev_is_label = i > 0 and bool(re.fullmatch(rf"\s*{LABEL_WORDS}\s*[:：]?\s*", lines[i - 1], re.IGNORECASE))
        content = _strip_label(line)
        if not content:
            continue
        s = _score(line, prev_is_label)
        candidate = content
        # רחוב בשורה אחת ועיר בשורה הבאה
        if i + 1 < len(lines) and not _find_city(content):
            nxt_city = _find_city(lines[i + 1])
            if nxt_city and len(lines[i + 1]) <= len(nxt_city) + 12:
                candidate = f"{content}, {nxt_city}"
                s += 1.5
        scored.append((s, candidate))

    seen: set[str] = set()
    for s, cand in sorted(scored, key=lambda t: t[0], reverse=True):
        norm = normalize_address(cand)
        if s < 3 or not norm or norm in seen:
            continue
        seen.add(norm)
        result.candidates.append(norm)
        if len(result.candidates) >= max_candidates:
            break
    return result
