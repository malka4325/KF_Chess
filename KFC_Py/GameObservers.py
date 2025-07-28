
import logging
from typing import Dict, Tuple, List

import cv2
from EventSystem import Observer
from img import Img

logger = logging.getLogger(__name__)

class ScoreDisplay(Observer):
    PIECE_VALUES = {
        'P': 1,  # Pawn
        'N': 3,  # Knight
        'B': 3,  # Bishop
        'R': 5,  # Rook
        'Q': 9,  # Queen
        'K': 0   # King (usually 0, capturing king ends game)
    }

    def __init__(self, game_instance, player1_score_pos: Tuple[int, int], player2_score_pos: Tuple[int, int]):
        self.game = game_instance
        self.player1_score_pos = player1_score_pos # (x, y) pixel for player 1 score
        self.player2_score_pos = player2_score_pos # (x, y) pixel for player 2 score
        self.scores = {'W': 0, 'B': 0} # White (P1) vs Black (P2)
        logger.info("ScoreDisplay initialized and subscribed.")

    def update(self, event_type: str, *args, **kwargs):
        """
        מעדכן את הניקוד בהתאם לאירוע.
        """
        if event_type == "piece_captured":
            captured_piece_type = kwargs.get('captured_piece_type')
            # שנה את השורה הבאה:
            captured_by_player_side = kwargs.get('captured_by_player_side') # **תיקון: הסרנו את ה-'_by' הכפול**
            
            value = self.PIECE_VALUES.get(captured_piece_type, 0)
            
            if captured_by_player_side == 'W':
                self.scores['W'] += value
                logger.info(f"Player 1 (White) captured {captured_piece_type}. Current Score: {self.scores['W']}")
            elif captured_by_player_side == 'B':
                self.scores['B'] += value
                logger.info(f"Player 2 (Black) captured {captured_piece_type}. Current Score: {self.scores['B']}")
            
        elif event_type == "game_start":
            self.scores = {'W': 0, 'B': 0}
            logger.info("Game started, scores reset.")
        elif event_type == "game_end":
            logger.info(f"Game ended. Final Score: White: {self.scores['W']}, Black: {self.scores['B']}")


    def draw(self, canvas: Img):
        """
        מצייר את הניקוד הנוכחי על הקנבס.
        """
        font_size = 1.0 
        thickness = 2 
        
        canvas.put_text(f"P1 Score: {self.scores['W']}", 
                        self.player1_score_pos[0], self.player1_score_pos[1], 
                        font_size, color=(0, 255, 0, 255), thickness=thickness) # ירוק
        
        canvas.put_text(f"P2 Score: {self.scores['B']}", 
                        self.player2_score_pos[0], self.player2_score_pos[1], 
                        font_size, color=(255, 0, 0, 255), thickness=thickness) # אדום


class MoveListDisplay(Observer):
    """
    Observer המציג רשימת מהלכים על המסך, מחולק לשני שחקנים.
    """
    def __init__(self, player1_display_pos: Tuple[int, int], player2_display_pos: Tuple[int, int], max_moves_to_show: int =30):
        self.player1_display_pos = player1_display_pos # (x, y) פיקסל של פינת התצוגה לשחקן 1
        self.player2_display_pos = player2_display_pos # (x, y) פיקסל של פינת התצוגה לשחקן 2
        self.max_moves_to_show = max_moves_to_show
        self.player1_moves: List[str] = [] # רשימת המהלכים לשחקן 1
        self.player2_moves: List[str] = [] # רשימת המהלכים לשחקן 2
        logger.info("MoveListDisplay initialized and subscribed.")

    def update(self, event_type: str, *args, **kwargs):
        """
        מעדכן את רשימת המהלכים בהתאם לאירוע.
        """
        if event_type == "piece_moved":
            piece_id = kwargs.get('piece_id')
            from_cell = kwargs.get('from_cell')
            to_cell = kwargs.get('to_cell')
            player = kwargs.get('player')

            move_str = f"{piece_id[0]} {chr(ord('a') + from_cell[1])}{8 - from_cell[0]}->{chr(ord('a') + to_cell[1])}{8 - to_cell[0]}"
            
            if player == 1: # שחקן 1 (לבן)
                self.player1_moves.append(move_str)
                if len(self.player1_moves) > self.max_moves_to_show:
                    self.player1_moves = self.player1_moves[-self.max_moves_to_show:]
                logger.info(f"P1 Move recorded: {move_str}")
                print(f"*** DEBUG: MoveListDisplay processed P1 move: {move_str} ***")

            elif player == 2: # שחקן 2 (שחור)
                self.player2_moves.append(move_str)
                if len(self.player2_moves) > self.max_moves_to_show:
                    self.player2_moves = self.player2_moves[-self.max_moves_to_show:]
                logger.info(f"P2 Move recorded: {move_str}")
                print(f"*** DEBUG: MoveListDisplay processed P2 move: {move_str} ***")

        elif event_type == "game_start":
            self.player1_moves = []
            self.player2_moves = []
            logger.info("Game started, move list reset.")
            print(f"*** DEBUG: MoveListDisplay reset for game start. ***")
        elif event_type == "game_end":
            logger.info(f"Game ended. Total P1 moves: {len(self.player1_moves)}, P2 moves: {len(self.player2_moves)}")
            print(f"*** DEBUG: MoveListDisplay received game_end. ***")

    def draw(self, canvas: Img):
        """
        מצייר את רשימות המהלכים של שני השחקנים על הקנבס.
        """
        font_size = 0.7
        thickness = 1
        line_height = 30 # רווח בין שורות

        # ציור מהלכי שחקן 1
        current_y_p1 = self.player1_display_pos[1]
        for i, move_str in enumerate(self.player1_moves):
            canvas.put_text(move_str, 
                            self.player1_display_pos[0], 
                            current_y_p1 + (i * line_height), 
                            font_size, color=(0, 0, 0, 255), thickness=thickness) # לבן
        
        # ציור מהלכי שחקן 2
        current_y_p2 = self.player2_display_pos[1]
        for i, move_str in enumerate(self.player2_moves):
            canvas.put_text(move_str, 
                            self.player2_display_pos[0], 
                            current_y_p2 + (i * line_height), 
                            font_size, color=(0, 0, 0, 255), thickness=thickness) # לבן