from app.services.address_parser import normalize_address, parse_label


def test_hebrew_label_with_label_word():
    text = """שולח: חנות אונליין בע"מ
מספר הזמנה: 123456789012
לכבוד: דנה לוי
כתובת: רחוב הרצל 25, רמת גן
טלפון: 052-1234567
"""
    p = parse_label(text)
    assert p.candidates[0] == "הרצל 25, רמת גן"
    assert p.phone == "0521234567"
    assert p.recipient == "דנה לוי"


def test_street_and_city_on_separate_lines():
    text = "נמען: יוסי כהן\nשדרות רוטשילד 10\nתל אביב\n054 765 4321"
    p = parse_label(text)
    assert p.candidates[0] == "שדרות רוטשילד 10, תל אביב"
    assert p.phone == "0547654321"


def test_english_label():
    text = "SHIP TO:\nMoshe Levi\n12 Dizengoff St\nTel Aviv 6433212\nIsrael"
    p = parse_label(text)
    assert any("Dizengoff" in c for c in p.candidates)


def test_normalize_removes_apartment_and_zip():
    assert normalize_address("רח' ויצמן 5 דירה 3, כפר סבא 4442101") == "ויצמן 5, כפר סבא"


def test_tracking_number_not_address():
    p = parse_label("RR123456789IL\n1234567890123")
    assert p.candidates == []


def test_details_extracted():
    p = parse_label("כתובת: הרצל 25 דירה 4, רמת גן\nקומה 2 כניסה ב")
    assert p.candidates[0] == "הרצל 25, רמת גן"
    assert p.details == "דירה 4, קומה 2, כניסה ב"


def test_city_on_line_above_street():
    p = parse_label("פתח תקווה\nרוטשילד 45\nשירה מזרחי\n058-9998877")
    assert p.candidates[0] == "רוטשילד 45, פתח תקווה"


def test_sender_address_is_not_chosen():
    text = "שולח: מחסן מרכזי\nהחרש 4, חולון\nלכבוד\nגלעד כץ\nהרימון 3, נס ציונה"
    assert parse_label(text).candidates[0] == "הרימון 3, נס ציונה"


def test_street_without_street_word_and_fuzzy_city():
    p = parse_label("משה כהן\nויצמן 14\nכפר סבה\n054-7654321")  # OCR error in the city name
    assert p.candidates[0] == "ויצמן 14, כפר סבא"
    assert p.quality >= 6
