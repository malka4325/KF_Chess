# KFC_Py/Game.py

import queue, threading, time, math, logging
from typing import List, Dict, Tuple, Optional, Set
from collections import defaultdict

import cv2
from Board import Board
from Command import Command
from Piece import Piece
from img import Img
from KeyboardInput import KeyboardProcessor, KeyboardProducer 
from GraphicsFactory import GraphicsFactory 
from pygame import mixer

from EventSystem import Publisher, Observer 
from GameObservers import ScoreDisplay 
from GameObservers import MoveListDisplay
from GameObservers import SoundPlayer 


logger = logging.getLogger(__name__)


class InvalidBoard(Exception): ...


class Game(Publisher):
    def __init__(self, pieces: List[Piece], board: Board, pieces_root=None, graphics_factory=None, img_factory=None):
        super().__init__()
        if not self._validate(pieces):
            raise InvalidBoard("missing kings")
        self.pieces = pieces
        self.board = board 
        self.pieces_root = pieces_root
        self.graphics_factory = graphics_factory
        self.img_factory = img_factory
        self.START_NS = time.monotonic_ns()
        self._time_factor = 1
        self.user_input_queue = queue.Queue()

        self.pos: Dict[Tuple[int, int], List[Piece]] = defaultdict(list)
        self.piece_by_id: Dict[str, Piece] = {p.id: p for p in pieces}

        self.selected_id_1: Optional[str] = None
        self.selected_id_2: Optional[str] = None
        self.last_cursor2: Optional[Tuple[int, int]] = None
        self.last_cursor1: Optional[Tuple[int, int]] = None

        self.keyboard_processor: Optional[KeyboardProcessor] = None
        self.keyboard_producer: Optional[KeyboardProducer] = None
        
        self.running = True

        full_bg_path = self.pieces_root / "full.jpg"
        if not full_bg_path.exists():
            raise FileNotFoundError(f"Missing background image: {full_bg_path}")
        
        self.main_canvas = Img().read(full_bg_path, size=None, keep_aspect=False)
        self.initial_main_canvas_img_data = self.main_canvas.img.copy()

        self.canvas_width = self.main_canvas.img.shape[1]
        self.canvas_height = self.main_canvas.img.shape[0]

        self.board_offset_x = 308 
        self.board_offset_y = 98 
        
        # יצירת מופע של ScoreDisplay ורישומו ל-Publisher (כלומר, Game)
        p1_score_display_pos = (50, 50) 
        p2_score_display_pos = (self.canvas_width - 350, 50) 
        self.score_display = ScoreDisplay(self, p1_score_display_pos, p2_score_display_pos)
        self.subscribe(self.score_display)

        # יצירת מופע של MoveListDisplay ורישומו ל-Publisher
        p1_movelist_display_pos = (50, 130) 
        p2_movelist_display_pos = (self.canvas_width - 300, 130) 
        self.move_list_display = MoveListDisplay(p1_movelist_display_pos, p2_movelist_display_pos)
        self.subscribe(self.move_list_display)

        sounds_folder_path = self.pieces_root / "sounds" 
        self.sound_player = SoundPlayer(sounds_folder_path)
        self.subscribe(self.sound_player)


    def game_time_ms(self) -> int:
        return self._time_factor * (time.monotonic_ns() - self.START_NS) // 1_000_000

    def clone_board(self) -> Board:
        return self.board.clone()

    def start_user_input_thread(self):
        p1_map = {
            "up": "up", "down": "down", "left": "left", "right": "right",
            "enter": "select", "+": "jump"
        }
        p2_map = {
            "w": "up", "s": "down", "a": "left", "d": "right",
            "space": "select", "g": "jump",
            "'": "up", "ד": "down", "ש": "left", "ג": "right",
            "ע": "jump"
        }

        self.kp1 = KeyboardProcessor(self.board.H_cells,
                                     self.board.W_cells,
                                     keymap=p1_map)
        self.kp2 = KeyboardProcessor(self.board.H_cells,
                                     self.board.W_cells,
                                     keymap=p2_map)

        if self.last_cursor1 is not None:
            self.kp1._cursor = list(self.last_cursor1)
        if self.last_cursor2 is not None:
            self.kp2._cursor = list(self.last_cursor2)

        self.kb_prod_1 = KeyboardProducer(self, self.user_input_queue, self.kp1, player=1)
        self.kb_prod_2 = KeyboardProducer(self, self.user_input_queue, self.kp2, player=2)

        self.kb_prod_1.start()
        self.kb_prod_2.start()


    def _update_cell2piece_map(self):
        self.pos.clear()
        for p in self.pieces:
            self.pos[p.current_cell()].append(p)

    def _run_game_loop(self, num_iterations=None, is_with_graphics=True):
        it_counter = 0
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
                self._show()

            self._resolve_collisions()

            if num_iterations is not None:
                it_counter += 1
                if num_iterations <= it_counter:
                    self.running = False
                    return

    
    def run(self, num_iterations=None, is_with_graphics=True):
        self.start_user_input_thread()
        start_ms = self.START_NS
        for p in self.pieces:
            p.reset(start_ms)

        self.running = True
        self.notify("game_start", timestamp=self.game_time_ms()) 

        self._run_game_loop(num_iterations, is_with_graphics)

        self._announce_win()
        self.notify("game_end", timestamp=self.game_time_ms()) 

        if self.kb_prod_1 and self.kb_prod_1.is_alive():
            self.kb_prod_1.stop()
            self.kb_prod_1.join(timeout=1)
        if self.kb_prod_2 and self.kb_prod_2.is_alive():
            self.kb_prod_2.stop()
            self.kb_prod_2.join(timeout=1)
        
        cv2.destroyAllWindows()
        mixer.quit() # **הוסף שורה זו - סגור את המיקסר של Pygame בסיום המשחק**

    def _draw(self):
        self.main_canvas.img = self.initial_main_canvas_img_data.copy()

        self.board.img.draw_on(self.main_canvas, self.board_offset_x, self.board_offset_y)

        for p in self.pieces:
            x_pix, y_pix = p.state.physics.get_pos_pix() 
            sprite = p.state.graphics.get_img()
            
            sprite.draw_on(self.main_canvas, self.board_offset_x + x_pix, self.board_offset_y + y_pix)

        if self.kp1 and self.kp2:
            for player, kp, last in (
                    (1, self.kp1, 'last_cursor1'),
                    (2, self.kp2, 'last_cursor2')
            ):
                r, c = kp.get_cursor()
                y1 = r * self.board.cell_H_pix + self.board_offset_y
                x1 = c * self.board.cell_W_pix + self.board_offset_x
                y2 = y1 + self.board.cell_H_pix - 1
                x2 = x1 + self.board.cell_W_pix - 1
                color = (0, 255, 0, 255) if player == 1 else (255, 0, 0, 255) 
                self.main_canvas.draw_rect(x1, y1, x2, y2, color)

                prev = getattr(self, last)
                if prev != (r, c):
                    logger.debug("Marker P%s moved to (%s, %s)", player, r, c)
                    setattr(self, last, (r, c))

        self.score_display.draw(self.main_canvas)
        self.move_list_display.draw(self.main_canvas)


    def _show(self):
        cv2.imshow("KungFu Chess", self.main_canvas.img)
        key = cv2.waitKey(1)

        if key == 27:
            self.running = False
        if cv2.getWindowProperty("KungFu Chess", cv2.WND_PROP_VISIBLE) < 1:
            self.running = False


    def _side_of(self, piece_id: str) -> str:
        return piece_id[1]

    def _process_input(self, cmd: Command):
        mover = self.piece_by_id.get(cmd.piece_id)
        if not mover:
            logger.debug("Unknown piece id %s", cmd.piece_id)
            return

        player = getattr(cmd, 'player', None)
        side = self._side_of(cmd.piece_id)
        if (player == 1 and side != 'W') or (player == 2 and side != 'B'):
            logger.debug("Player %s tried to move piece %s of side %s", player, cmd.piece_id, side)
            return

        original_cell = mover.current_cell() 

        move_successful_in_state_machine = mover.on_command(cmd, self.pos)

        # פרסם אירוע אם המהלך חוקי
        if move_successful_in_state_machine and cmd.type in ["move", "jump"]:
            # השתמש ב-cmd.type כסוג האירוע כדי לנגן צליל ספציפי (move/jump)
            self.notify(cmd.type, 
                        piece_id=cmd.piece_id, 
                        from_cell=original_cell, 
                        to_cell=cmd.params[1] if len(cmd.params) > 1 else None, 
                        player=player, 
                        timestamp=self.game_time_ms())
            logger.info(f"Published {cmd.type}: {cmd.piece_id} from {original_cell} to {cmd.params[1] if len(cmd.params) > 1 else 'N/A'}")
            print(f"*** DEBUG: Game successfully published '{cmd.type}' event for {cmd.piece_id}! ***")
        else:
            logger.debug(f"Move for {cmd.piece_id} (cmd type: {cmd.type}) was not successful by state machine or not a move/jump type.")
            print(f"DEBUG: Game did NOT publish '{cmd.type}' event for {cmd.piece_id} (state machine rejected or not a move/jump).")

    def _resolve_collisions(self):
        self._update_cell2piece_map()
        occupied = self.pos

        for cell, plist in occupied.items():
            if len(plist) < 2:
                continue

            moving_pieces = [p for p in plist if getattr(p.state.physics, '_start_cell', cell) != cell]
            if moving_pieces:
                winner = max(moving_pieces, key=lambda p: p.state.physics.get_start_ms())
            else:
                winner = max(plist, key=lambda p: p.state.physics.get_start_ms())

            winner_side = self._side_of(winner.id)
            need_clear_path = getattr(winner.state.physics, 'do_i_need_clear_path', True)

            if not need_clear_path:
                end_cell = getattr(winner.state.physics, '_end_cell', None)
                if cell != end_cell:
                    continue
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
                if any(p is not winner and self._side_of(p.id) == winner_side for p in plist):
                    start_cell = getattr(winner.state.physics, '_start_cell', None)
                    if start_cell and winner.current_cell() != start_cell:
                        now = self.game_time_ms()
                        move_type = 'move'
                        from Command import Command
                        cmd = Command(now, winner.id, move_type, [start_cell, start_cell])
                        winner.state.reset(cmd)
                    continue

            if not winner.state.can_capture():
                pass

            to_remove = []
            for p in plist:
                if p is winner:
                    continue
                if p.state.can_be_captured() and self._side_of(p.id) != winner_side:
                    to_remove.append(p)
            for p in to_remove:
                if p in self.pieces:
                    self.pieces.remove(p)
                    captured_piece_type = p.id[0] 
                    captured_by_player_side = winner_side 
                    self.notify("piece_captured", 
                                captured_piece_type=captured_piece_type, 
                                captured_by_player_side=captured_by_player_side, 
                                timestamp=self.game_time_ms())
                    logger.info(f"CAPTURED: {p.id} by {winner.id}. Notifying observers.")


        # --- Pawn Promotion ---
        from PieceFactory import PieceFactory # ייבוא כאן כדי למנוע תלות מעגלית
        to_promote = []
        for p in list(self.pieces):
            if p.id.startswith('PW') and p.current_cell()[0] == 0:
                to_promote.append((p, 'QW'))
            elif p.id.startswith('PB') and p.current_cell()[0] == self.board.H_cells - 1:
                to_promote.append((p, 'QB'))
        if to_promote:
            gfx_factory = self.graphics_factory or (GraphicsFactory(self.img_factory) if self.img_factory else None)
            factory = PieceFactory(self.board, self.pieces_root, graphics_factory=gfx_factory)
            for pawn, queen_type in to_promote:
                cell = pawn.current_cell()
                self.pieces.remove(pawn)
                queen = factory.create_piece(queen_type, cell)
                self.pieces.append(queen)
                self.piece_by_id[queen.id] = queen
                if pawn.id in self.piece_by_id:
                    del self.piece_by_id[pawn.id]
                promoted_piece_id = queen.id
                promoted_by_player_side = queen_type[1]
                self.notify("pawn_promoted", 
                            promoted_piece_id=promoted_piece_id, 
                            promoted_by_player_side=promoted_by_player_side,
                            timestamp=self.game_time_ms())
                logger.info(f"PAWN PROMOTED: {pawn.id} to {queen.id}. Notifying observers.")


    def _validate(self, pieces):
        """Ensure both kings present and no two pieces share a cell."""
        has_white_king = has_black_king = False
        seen_cells: Dict[Tuple[int, int], str] = {}
        for p in pieces:
            cell = p.current_cell()
            if cell in seen_cells:
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
        winner = 'Black' if any(p.id.startswith('KB') for p in self.pieces) else 'White'
        text = f'{winner} wins!'
        logger.info(text)

        board_img = getattr(self, 'main_canvas', None)
        if board_img is None:
            board_img = self.board.img 

        h, w = board_img.img.shape[:2]
        font_size = min(w, h) / 400
        thickness = 3
        text_size, _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_size, thickness)
        text_w, text_h = text_size
        x = (w - text_w) // 2
        y = (h + text_h) // 2
        board_img.put_text(text, x, y, font_size, color=(144, 144, 254, 255), thickness=thickness)
        board_img.show()
        time.sleep(5)