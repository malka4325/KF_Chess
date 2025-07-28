
import threading, logging
import time
from time import time
import keyboard  # pip install keyboard
from Command import Command
from typing import Dict, Tuple

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
    and turns `select`/`jump` into Command objects on the Game queue.
    Each producer is tied to a player number (1 or 2).
    """

    def __init__(self, game, queue, processor: KeyboardProcessor, player: int):
        super().__init__(daemon=True)
        self.game = game
        self.queue = queue
        self.proc = processor
        self.player = player
        self.selected_id = None
        self.selected_cell = None
        self._stop_event = threading.Event() # Event to signal thread to stop

    def run(self):
        keyboard.hook(self._on_event)
        # Change to loop while game is running
        while not self._stop_event.is_set():
            # A small sleep to prevent busy-waiting if there are no events
            time.sleep(0.01) # Sleep to yield CPU and allow stop_event to be checked
            
            # The keyboard.wait() needs to be handled carefully in a thread.
            # Directly using keyboard.wait() will block indefinitely.
            # Instead, rely on the global hook and check the stop event.
            # The actual key processing happens in _on_event via the hook.
            # We just need to keep this thread alive and responsive to stop signals.
            
            # If a more immediate stop is needed, you might need to find a non-blocking
            # way to wait for keyboard events or break the keyboard.wait()
            # For now, relying on the 'daemon' property and stop_event.
            
            # Since keyboard.wait() blocks, we cannot just loop while not _stop_event.is_set()
            # if keyboard.wait() is inside. The solution is to remove keyboard.wait()
            # and let the hook handle events, while the main thread manages life cycle.
            # The daemon thread will exit when the main program exits.
            pass # Keep looping and relying on main thread to manage `running` flag in Game

        keyboard.unhook_all() # Unhook when thread is told to stop
        logger.info(f"KeyboardProducer for Player {self.player} stopped.")

    def _find_piece_at(self, cell):
        for p in self.game.pieces:
            if p.current_cell() == cell:
                return p
        return None

    def _on_event(self, event):
        if not self.game.running:
            return

        action = self.proc.process_key(event)
        # only interpret select/jump
        if action not in ("select", "jump"):
            return

        cell = self.proc.get_cursor()
        # read/write the correct selected_id_X on the Game
        if action == "select":
            if self.selected_id is None:
                # first press = pick up the piece under the cursor
                piece = self._find_piece_at(cell)
                if not piece:
                    print(f"[WARN] No piece at {cell}")
                    return
                self.selected_id = piece.id
                self.selected_cell = cell
                print(f"[KEY] Player{self.player} selected {piece.id} at {cell}")
                return
            elif cell == self.selected_cell:  # selected same place
                self.selected_id = None
                return
            else:
                cmd = Command(
                    self.game.game_time_ms(),
                    self.selected_id,
                    "move",
                    [self.selected_cell, cell],
                    player=self.player
                )
                self.queue.put(cmd)
                logger.info(f"Player{self.player} queued {cmd}")
                self.selected_id = None
                self.selected_cell = None
        elif action == "jump":
            # If a piece is selected, perform a jump from selected_cell to current cell
            if self.selected_id is not None and self.selected_cell is not None:
                cmd = Command(
                    self.game.game_time_ms(),
                    self.selected_id,
                    "jump",
                    [self.selected_cell, cell],
                    player=self.player
                )
                self.queue.put(cmd)
                logger.info(f"Player{self.player} queued {cmd}")
                self.selected_id = None
                self.selected_cell = None
            else:
                # If no piece is selected, select the piece under the cursor and IMMEDIATELY perform jump to the same cell
                piece = self._find_piece_at(cell)
                if not piece:
                    print(f"[WARN] No piece at {cell}")
                    return
                self.selected_id = piece.id
                self.selected_cell = cell
                # Immediately perform jump to the same cell (single click jump)
                cmd = Command(
                    self.game.game_time_ms(),
                    self.selected_id,
                    "jump",
                    [self.selected_cell, cell],
                    player=self.player
                )
                self.queue.put(cmd)
                logger.info(f"Player{self.player} queued {cmd}")
                self.selected_id = None
                self.selected_cell = None
    def stop(self):
        self._stop_event.set() # Signal the thread to stop
        # In KeyboardProducer's run method, keyboard.wait() is used, which blocks the thread.
        # Calling unhook_all() from another thread will cause keyboard.wait() to unblock.
        # Thus, simply setting the event and then calling unhook_all directly should work.
        keyboard.unhook_all() # This will unblock keyboard.wait() if it's running
