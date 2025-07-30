# KFC_Py/EventSystem.py

from abc import ABC, abstractmethod
from typing import List, Any, Callable


class Observer(ABC):
    """
    ממשק בסיסי עבור אובייקטים המעוניינים לקבל עדכונים.
    כל "צופה" או "מנוי" חייב לממש את המתודה update.
    """
    @abstractmethod
    def update(self, event_type: str, *args, **kwargs):
        """
        נקרא כאשר מתרחש אירוע שה-Observer נרשם אליו.
        event_type: סוג האירוע (לדוגמה: "piece_captured", "game_start").
        *args, **kwargs: נתונים נוספים הקשורים לאירוע.
        """
        pass


class Publisher:
    """
    מחלקה בסיסית עבור אובייקטים המסוגלים לפרסם אירועים ולנהל מנויים.
    אובייקטים המפרסמים אירועים יירשו ממחלקה זו או ישתמשו במופע שלה.
    """
    def __init__(self):
        # מילון של אירועים, כאשר כל מפתח הוא event_type וכל ערך הוא רשימה של Observers
        self._subscribers: List[Observer] = []
        # ניתן גם לממש עם מילון של רשימות לפי סוג אירוע אם נדרש סינון מורכב יותר
        # self._subscribers_by_event: Dict[str, List[Observer]] = defaultdict(list)

    def subscribe(self, observer: Observer):
        """
        מוסיף Observer לרשימת המנויים.
        """
        if observer not in self._subscribers:
            self._subscribers.append(observer)

    def unsubscribe(self, observer: Observer):
        """
        מסיר Observer מרשימת המנויים.
        """
        if observer in self._subscribers:
            self._subscribers.remove(observer)

    def notify(self, event_type: str, *args, **kwargs):
        """
        מודיע לכל המנויים הרשומים על אירוע מסוים.
        """
        for observer in self._subscribers:
            observer.update(event_type, *args, **kwargs)