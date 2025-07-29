import threading, logging
import keyboard  # pip install keyboard
# from Command import Command
from typing import Dict, Tuple
import time # **הוסף שורה זו כאן**

logger = logging.getLogger(__name__)


class KeyboardProcessor:
    """
    Maintains a cursor on an R×C grid and maps raw key names
    into logical actions via a user‑supplied keymap.
    """

    def __init__(self, rows: int, cols: int, keymap: Dict[str, str]):
        self.rows = rows
        self.cols = cols
        self.keymap = keymap  # type: Dict[str, str]
        self._cursor = [0, 0]  # [row, col]
        self._lock = threading.Lock()

    def process_key(self, event):
        # Only care about key‑down events
        if event.event_type != "down":
            return None

        key = event.name
        action = self.keymap.get(key)
        logger.debug("Key '%s' → action '%s'", key, action)

        if action in ("up", "down", "left", "right"):
            with self._lock:
                r, c = self._cursor
                if action == "up":
                    r = max(0, r - 1)
                elif action == "down":
                    r = min(self.rows - 1, r + 1)
                elif action == "left":
                    c = max(0, c - 1)
                elif action == "right":
                    c = min(self.cols - 1, c + 1)
                self._cursor = [r, c]
                logger.debug("Cursor moved to (%s,%s)", r, c)

        return action

    def get_cursor(self) -> Tuple[int, int]:
        with self._lock:
            return tuple(self._cursor)  # type: Tuple[int, int]




class KeyboardProducer(threading.Thread):
    """
    Runs in its own daemon thread; hooks into the `keyboard` lib,
    polls events, translates them via the KeyboardProcessor,
    and turns `select`/`jump` into Command objects on the Game queue (or sends via WebSocket).
    Each producer is tied to a player number (1 or 2).
    """

    # !!! שינוי בחתימת הקונסטרוקטור: הוספת websocket_connection !!!
    def __init__(self, game, queue, processor: KeyboardProcessor, player: int, websocket_connection):
        self.daemon = True  
        super().__init__(daemon=True)
        self.game = game # במקרה של הלקוח, זה יהיה מופע ה-Game המקומי (חלקי)
        self.queue = queue # תור קלט פנימי (לא בשימוש ישיר לשליחה לשרת)
        self.processor = processor # שינוי שם ל-processor כדי למנוע התנגשות עם self.proc ב-run
        self.player = player
        self._stop_event = threading.Event()
        self.last_key_press_time_ns = time.monotonic_ns()
        self.websocket_connection = websocket_connection # !!! הוספה חדשה: חיבור ה-WebSocket !!!
        self.selected_id = None
        self.selected_cell = None


    def run(self):
        keyboard.hook(self._on_event)
        # ה-client's main loop (asyncio.run) הוא זה שרץ לנצח, לא ה-run של Producer
        # נשאר בלולאה כל עוד חיבור ה-websocket פתוח (client.py יטפל בזה)
        # או כל עוד ה-Game עדיין רץ (game.running)
        while self.game.running: # נניח של-client's game_instance יש running flag
             time.sleep(0.01) # שינה קצרה כדי לא לצרוך CPU
        
        keyboard.unhook_all() 
        logger.info(f"KeyboardProducer for Player {self.player} stopped.")

    # !!! שינוי ב-_on_event: שליחה דרך WebSocket !!!
    def _on_event(self, event):
        if not self.game.running: # וודא שהמשחק עדיין פעיל (למשל, השרת לא כבה)
            return

        action = self.processor.process_key(event) # שימוש ב-self.processor
        if action not in ("select", "jump"):
            return

        cell = self.processor.get_cursor()
        
        # בניית הפקודה ושליחתה דרך ה-WebSocket
        if action == "select":
            if self.selected_id is None:
                piece = self._find_piece_at(cell) # נצטרך לממש _find_piece_at עבור הלקוח
                if not piece:
                    print(f"[WARN] Player{self.player}: No piece at {cell}")
                    return
                self.selected_id = piece.id
                self.selected_cell = cell
                print(f"[KEY] Player{self.player} selected {piece.id} at {cell}")
                return
            elif cell == self.selected_cell:  # selected same place = deselect
                self.selected_id = None
                self.selected_cell = None
                print(f"[KEY] Player{self.player} deselected.")
                return
            else: # move selected piece
                # במקום לדחוף לתור מקומי, נשלח לשרת דרך WebSocket
                command_to_send = {
                    "piece_id": self.selected_id,
                    "command_type": "MOVE_PIECE", # או כל סוג פקודה שתרצו לשלוח
                    "to_pos": list(cell)
                }
                # קריאה ל-asyncio.run_coroutine_threadsafe לשליחה אסינכרונית מה-thread
                # זה מסובך כי זה מ-thread ללולאת אירועים.
                # דרך פשוטה יותר: שה-main_client יתפוס את הפקודה ויישלח אותה.
                # או שה-KeyboardProducer יהיה Task אסינכרוני בעצמו.
                
                # כרגע, נשתמש בפתרון פשוט: פשוט נדפיס מה היתה הפקודה
                # ונצטרך לשנות את ה-run() ב-client.py כדי שיקבל קלט מהמקלדת.
                print(f"[KEY] Player{self.player} attempted to send MOVE command: {command_to_send}")
                # TODO: כאן הלוגיקה לשליחת הפקודה דרך ה-WebSocket_connection!
                # זה דורש מעט ארכיטקטורה נוספת בלקוח.
                
                # פתרון זמני: נשתמש ב-queue כדי לשלוח ל-main_client.
                # ה-main_client יצטרך לקבל תור קלט מה-Producer ולשלוח דרכו.
                self.queue.put(command_to_send) # נדחוף לתור, ו-main_client ייקח משם
                logger.info(f"Player{self.player} queued {command_to_send}")

                self.selected_id = None
                self.selected_cell = None
        elif action == "jump":
            if self.selected_id is not None and self.selected_cell is not None:
                command_to_send = {
                    "piece_id": self.selected_id,
                    "command_type": "JUMP_PIECE",
                    "to_pos": list(cell)
                }
                print(f"[KEY] Player{self.player} attempted to send JUMP command: {command_to_send}")
                self.queue.put(command_to_send)
                logger.info(f"Player{self.player} queued {command_to_send}")
                self.selected_id = None
                self.selected_cell = None
            else: # Single click jump
                piece = self._find_piece_at(cell) # נצטרך לממש _find_piece_at עבור הלקוח
                if not piece:
                    print(f"[WARN] Player{self.player}: No piece at {cell}")
                    return
                self.selected_id = piece.id
                self.selected_cell = cell
                command_to_send = {
                    "piece_id": self.selected_id,
                    "command_type": "JUMP_PIECE",
                    "to_pos": list(cell)
                }
                print(f"[KEY] Player{self.player} attempted to send JUMP command (single click): {command_to_send}")
                self.queue.put(command_to_send)
                logger.info(f"Player{self.player} queued {command_to_send}")
                self.selected_id = None
                self.selected_cell = None

    # !!! שינוי ב-_find_piece_at: גישה ל-client_pieces הגלובלי !!!
    def _find_piece_at(self, cell):
        # כדי לאפשר ל-KeyboardProducer למצוא כלים, הוא יצטרך גישה למצב הלוח של הלקוח.
        # נניח ש-client_pieces הוא מילון גלובלי שמנוהל על ידי client.py
        # ושהוא מכיל את כל הכלים הנוכחיים על הלוח.
        global client_pieces # גישה למילון הכלים הגלובלי של הלקוח
        for piece_id, piece in client_pieces.items():
            if piece.current_cell() == cell: # נניח שלחפץ Piece יש current_cell()
                return piece
        return None

    def stop(self):
        # מנגנון העצירה של KeyboardProducer - קריאה ל-unhook_all
        keyboard.unhook_all()
        # print(f"DEBUG: KeyboardProducer for Player {self.player} unhooked.") # הדפסת אבחון