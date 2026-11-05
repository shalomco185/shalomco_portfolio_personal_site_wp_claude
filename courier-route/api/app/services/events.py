"""אירועי מערכת: נקודות חיבור להרחבות עתידיות.

הקוד הראשי מפעיל emit("route_planned", ...) וכדומה. מי שירצה להוסיף בעתיד הודעות
ללקוח, חישוב מחדש של המסלול אחרי עיכוב או סטטיסטיקות, נרשם עם @on("...").

אירועים קיימים:
  route_planned(route)                - נשמר מסלול חדש (כולל זמן הגעה משוער לכל עצירה)
  stop_status_changed(stop, old, new) - הסטטוס של עצירה השתנה (נמסר / לא בבית); ה-API קיים, לא בממשק
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Callable

log = logging.getLogger(__name__)

_handlers: dict[str, list[Callable[..., Any]]] = defaultdict(list)


def on(event: str):
    def decorator(fn: Callable[..., Any]):
        _handlers[event].append(fn)
        return fn

    return decorator


def emit(event: str, **kwargs: Any) -> None:
    for handler in _handlers.get(event, []):
        try:
            handler(**kwargs)
        except Exception:  # אירוע שנכשל לא מפיל את הפעולה הראשית
            log.exception("event handler failed: %s", event)


# --- דוגמה (כבויה) לחיבור הודעה ללקוח כשמסלול מתוכנן ---
# from .notifications import Message, get_notifier
#
# @on("route_planned")
# def notify_customers(route):
#     notifier = get_notifier()
#     for item in route.items:
#         if item.stop.phone:
#             minutes = round(item.eta_offset_s / 60)
#             notifier.send(Message(item.stop.phone, f"המשלוח שלך יגיע בעוד כ-{minutes} דקות",
#                                   item.stop_id, "route_planned"))
