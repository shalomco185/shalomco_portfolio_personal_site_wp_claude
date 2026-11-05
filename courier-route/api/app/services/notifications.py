"""הודעות ללקוחות: תשתית בלבד. בגרסה הבסיסית לא נשלחת אף הודעה.

כדי להוסיף SMS או WhatsApp: כותבים מחלקה שמממשת Notifier.send (למשל מול ספק
SMS ישראלי), רושמים אותה ב-NOTIFIERS ומגדירים NOTIFIER=<שם> בקובץ .env.
האירועים שמפעילים הודעות מוגדרים ב-events.py.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from ..config import settings

log = logging.getLogger(__name__)


@dataclass
class Message:
    phone: str
    text: str
    stop_id: int | None = None
    kind: str = "generic"  # route_planned / on_the_way / delivered / failed


class Notifier(Protocol):
    name: str

    def send(self, message: Message) -> None: ...


class NoopNotifier:
    name = "none"

    def send(self, message: Message) -> None:  # לא שולח כלום
        return None


class LogNotifier:
    """שימושי לבדיקה: כותב ליומן השרת מה היה נשלח."""

    name = "log"

    def send(self, message: Message) -> None:
        log.info("NOTIFY %s -> %s: %s", message.kind, message.phone, message.text)


NOTIFIERS: dict[str, type] = {"none": NoopNotifier, "log": LogNotifier}


def get_notifier() -> Notifier:
    return NOTIFIERS.get(settings.notifier, NoopNotifier)()
