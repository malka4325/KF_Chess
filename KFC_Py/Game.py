import queue, threading, time, math, logging
from typing import List, Dict, Tuple, Optional, Set
from collections import defaultdict

import cv2

from Board import Board
from Command import Command
from img import Img
from Piece import Piece
from GraphicsFactory import GraphicsFactory



from KeyboardInput import KeyboardProcessor, KeyboardProducer

# set up a module-level logger – real apps can configure handlers/levels
logger = logging.getLogger(__name__)


class InvalidBoard(Exception): ...


class Game:
    def __init__(self, pieces: List[Piece], board: Board, pieces_root=None, graphics_factory=None, img_factory=None):
        if not self._validate(pieces):
            raise InvalidBoard("missing kings")
        self.pieces = pieces
        self.board = board
        self.pieces_root = pieces_root  # שמור את pieces_root לשימוש בקידום
        self.graphics_factory = graphics_factory
        self.img_factory = img_factory
        self.START_NS = time.monotonic_ns()
        self._time_factor = 1  # for tests
        self.user_input_queue = queue.Queue()  # thread-safe

        # lookup tables ---------------------------------------------------
        self.pos: Dict[Tuple[int, int], List[Piece]] = defaultdict(list)
        self.piece_by_id: Dict[str, Piece] = {p.id: p for p in pieces}

        self.selected_id_1: Optional[str] = None
        self.selected_id_2: Optional[str] = None
        self.last_cursor2: Optional[Tuple[int, int]] = None
        self.last_cursor1: Optional[Tuple[int, int]] = None

        # keyboard helpers ---------------------------------------------------
        self.keyboard_processor: Optional[KeyboardProcessor] = None
        self.keyboard_producer: Optional[KeyboardProducer] = None
        
        self.running = True # Keep this flag, it's for graceful exit

    def game_time_ms(self) -> int:
        return self._time_factor * (time.monotonic_ns() - self.START_NS) // 1_000_000

    def clone_board(self) -> Board:
        return self.board.clone()

    def start_user_input_thread(self):

        # player 1 key‐map
        p1_map = {
            "up": "up", "down": "down", "left": "left", "right": "right",
            "enter": "select", "+": "jump"
        }
        # player 2 key‐map (blue): w/a/s/d or ש/ד/ג/ס for movement, space for select
        p2_map = {
            # English
            "w": "up", "s": "down", "a": "left", "d": "right",
            "space": "select", "g": "jump",
            # Hebrew
            "'": "up", "ד": "down", "ש": "left", "ג": "right",
            # Sometimes users use ס for left (a)
            "ע": "jump"
        }

        # create two processors
        self.kp1 = KeyboardProcessor(self.board.H_cells,
                                     self.board.W_cells,
                                     keymap=p1_map)
        self.kp2 = KeyboardProcessor(self.board.H_cells,
                                     self.board.W_cells,
                                     keymap=p2_map)

        # Set initial cursor positions if provided
        if self.last_cursor1 is not None:
            self.kp1._cursor = list(self.last_cursor1)
        if self.last_cursor2 is not None:
            self.kp2._cursor = list(self.last_cursor2)

        # **pass the player number** as the 4th argument!
        self.kb_prod_1 = KeyboardProducer(self,
                                          self.user_input_queue,
                                          self.kp1,
                                          player=1)
        self.kb_prod_2 = KeyboardProducer(self,
                                          self.user_input_queue,
                                          self.kp2,
                                          player=2)

        self.kb_prod_1.start()
        self.kb_prod_2.start()

    def _update_cell2piece_map(self):
        self.pos.clear()
        for p in self.pieces:
            self.pos[p.current_cell()].append(p)

    def _run_game_loop(self, num_iterations=None, is_with_graphics=True):
        it_counter = 0
        # Change loop condition to also check self.running
        while not self._is_win() and self.running: 
            now = self.game_time_ms()

            for p in self.pieces:
                p.update(now)

            self._update_cell2piece_map()

            while not self.user_input_queue.empty():
                cmd: Command = self.user_input_queue.get()
                self._process_input(cmd)

            if is_with_graphics:
                self._draw()
                self._show() # _show will now handle the close event

            self._resolve_collisions()

            # for testing
            if num_iterations is not None:
                it_counter += 1
                if num_iterations <= it_counter:
                    self.running = False # Stop the loop if iterations limit is reached
                    return


    def run(self, num_iterations=None, is_with_graphics=True):
        self.start_user_input_thread()
        start_ms = self.START_NS
        for p in self.pieces:
            p.reset(start_ms)

        self.running = True # Ensure game starts as running
        self._run_game_loop(num_iterations, is_with_graphics)

        self._announce_win()
        # Ensure keyboard threads are stopped when game stops
        if self.kb_prod_1 and self.kb_prod_1.is_alive():
            self.kb_prod_1.stop()
            self.kb_prod_1.join(timeout=1) # Wait for the thread to finish
        if self.kb_prod_2 and self.kb_prod_2.is_alive():
            self.kb_prod_2.stop()
            self.kb_prod_2.join(timeout=1) # Wait for the thread to finish
        cv2.destroyAllWindows() # Destroy all OpenCV windows upon exit

    def _draw(self):
        # Revert to original _draw logic
        self.curr_board = self.clone_board()
        for p in self.pieces:
            p.draw_on_board(self.curr_board, now_ms=self.game_time_ms())

        # overlay both players' cursors, but only log on change
        if self.kp1 and self.kp2:
            for player, kp, last in (
                    (1, self.kp1, 'last_cursor1'),
                    (2, self.kp2, 'last_cursor2')
            ):
                r, c = kp.get_cursor()
                # draw rectangle
                y1 = r * self.board.cell_H_pix
                x1 = c * self.board.cell_W_pix
                y2 = y1 + self.board.cell_H_pix - 1
                x2 = x1 + self.board.cell_W_pix - 1
                color = (0, 255, 0) if player == 1 else (255, 0, 0) # Original color tuple without alpha
                self.curr_board.img.draw_rect(x1, y1, x2, y2, color)

                # only print if moved
                prev = getattr(self, last)
                if prev != (r, c):
                    logger.debug("Marker P%s moved to (%s, %s)", player, r, c)
                    setattr(self, last, (r, c))
    def _show(self):
        # Display the extended canvas instead of the simple board image
        cv2.imshow("KungFu Chess", self.board.img.img) # Give the window a name
        key = cv2.waitKey(1) # Wait 1ms for a key press or window event

        if key == 27: # ASCII for ESC key, often used to close windows
            self.running = False
        
        # Check for window close event (clicking X button)
        # This requires a named window. cv2.getWindowProperty returns -1 if window is closed.
        if cv2.getWindowProperty("KungFu Chess", cv2.WND_PROP_VISIBLE) < 1:
            self.running = False

    def _side_of(self, piece_id: str) -> str:
        return piece_id[1]

    def _process_input(self, cmd: Command):
        mover = self.piece_by_id.get(cmd.piece_id)
        if not mover:
            logger.debug("Unknown piece id %s", cmd.piece_id)
            return

        # Determine player from command (assume Command has 'player' attribute)
        player = getattr(cmd, 'player', None)
        if player is not None:
            # player 1 = ירוק = לבן (W), player 2 = כחול = שחור (B)
            side = self._side_of(cmd.piece_id)
            if (player == 1 and side != 'W') or (player == 2 and side != 'B'):
                logger.debug("Player %s tried to move piece %s of side %s", player, cmd.piece_id, side)
                return

        mover.on_command(cmd, self.pos)

    def _resolve_collisions(self):
        self._update_cell2piece_map()
        occupied = self.pos

        for cell, plist in occupied.items():
            if len(plist) < 2:
                continue

            # Prefer as winner the piece that actually moved (start_cell != cell),
            # otherwise fall back to the most recent arrival
            moving_pieces = [p for p in plist if getattr(p.state.physics, '_start_cell', cell) != cell]
            if moving_pieces:
                winner = max(moving_pieces, key=lambda p: p.state.physics.get_start_ms())
            else:
                winner = max(plist, key=lambda p: p.state.physics.get_start_ms())

            winner_side = self._side_of(winner.id)
            need_clear_path = getattr(winner.state.physics, 'do_i_need_clear_path', True)

            # For knights: skip collision checks at all intermediate cells, only check at the destination cell
            if not need_clear_path:
                # Only check collision at the destination cell
                # If this is not the destination cell for the knight, skip collision resolution
                end_cell = getattr(winner.state.physics, '_end_cell', None)
                if cell != end_cell:
                    continue
                # At the destination cell, only block if there is a friendly piece
                if any(p is not winner and self._side_of(p.id) == winner_side for p in plist):
                    start_cell = getattr(winner.state.physics, '_start_cell', None)
                    if start_cell and winner.current_cell() != start_cell:
                        now = self.game_time_ms()
                        move_type = 'move'
                        from Command import Command
                        cmd = Command(now, winner.id, move_type, [start_cell, start_cell])
                        winner.state.reset(cmd)
                    continue
            else:
                # Usual logic for pieces that need clear path
                if any(p is not winner and self._side_of(p.id) == winner_side for p in plist):
                    start_cell = getattr(winner.state.physics, '_start_cell', None)
                    if start_cell and winner.current_cell() != start_cell:
                        now = self.game_time_ms()
                        move_type = 'move'
                        from Command import Command
                        cmd = Command(now, winner.id, move_type, [start_cell, start_cell])
                        winner.state.reset(cmd)
                    continue

            # Determine if captures allowed: default allow
            if not winner.state.can_capture():
                # Allow capture even for idle pieces to satisfy game rules
                pass

            # Remove every other piece that *can be captured* and is from the opposite side
            to_remove = []
            for p in plist:
                if p is winner:
                    continue
                # Only capture if from opposite side
                # --- DEBUG LOG ---
                import logging
                logger = logging.getLogger("collision")
                logger.info(f"Checking capture: piece={p.id} state={getattr(p.state, 'name', None)} can_be_captured={p.state.can_be_captured()} winner={winner.id} winner_side={winner_side} piece_side={self._side_of(p.id)}")
                if p.state.can_be_captured() and self._side_of(p.id) != winner_side:
                    logger.info(f"CAPTURE: {p.id} (state={getattr(p.state, 'name', None)}) is being captured by {winner.id}")
                    to_remove.append(p)
            for p in to_remove:
                if p in self.pieces:
                    self.pieces.remove(p)

        # --- Pawn Promotion ---
        # Promote pawns that reached the last row
        from PieceFactory import PieceFactory
        to_promote = []
        for p in list(self.pieces):
            if p.id.startswith('PW') and p.current_cell()[0] == 0:
                to_promote.append((p, 'QW'))
            elif p.id.startswith('PB') and p.current_cell()[0] == self.board.H_cells - 1:
                to_promote.append((p, 'QB'))
        if to_promote:
            # השתמש ב-board, pieces_root, graphics_factory, img_factory מהאובייקט
            gfx_factory = self.graphics_factory or (GraphicsFactory(self.img_factory) if self.img_factory else None)
            factory = PieceFactory(self.board, self.pieces_root, graphics_factory=gfx_factory)
            for pawn, queen_type in to_promote:
                cell = pawn.current_cell()
                # Remove pawn
                self.pieces.remove(pawn)
                # Create queen at same cell
                queen = factory.create_piece(queen_type, cell)
                self.pieces.append(queen)
                # Update lookup
                self.piece_by_id[queen.id] = queen
                if pawn.id in self.piece_by_id:
                    del self.piece_by_id[pawn.id]

    def _validate(self, pieces):
        """Ensure both kings present and no two pieces share a cell."""
        has_white_king = has_black_king = False
        seen_cells: Dict[Tuple[int, int], str] = {}
        for p in pieces:
            cell = p.current_cell()
            if cell in seen_cells:
                # Allow overlap only if piece is from opposite side
                if seen_cells[cell] == p.id[1]:
                    return False
            else:
                seen_cells[cell] = p.id[1]
            if p.id.startswith("KW"):
                has_white_king = True
            elif p.id.startswith("KB"):
                has_black_king = True
        return has_white_king and has_black_king

    def _is_win(self) -> bool:
        kings = [p for p in self.pieces if p.id.startswith(('KW', 'KB'))]
        return len(kings) < 2

    def _announce_win(self):
        import cv2
        winner = 'Black' if any(p.id.startswith('KB') for p in self.pieces) else 'White'
        text = f'{winner} wins!'
        logger.info(text)

        # Try to use the current board image (after last move)
        board_img = getattr(self, 'curr_board', self.board).img
        # Get image size
        h, w = board_img.img.shape[:2]
        # Dynamic font size and thickness
        font_size = min(w, h) / 400
        thickness = 3
        # Calculate text size for centering
        text_size, _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_size, thickness)
        text_w, text_h = text_size
        x = (w - text_w) // 2
        y = (h + text_h) // 2
        # Draw the text in the center (red)
        board_img.put_text(text, x, y, font_size, color=(144, 144, 254, 1), thickness=thickness)
        board_img.show()
        time.sleep(5)

