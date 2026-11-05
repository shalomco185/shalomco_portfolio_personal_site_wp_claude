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
