# KFC_Py/GameObservers.py

import logging
import os
from typing import Dict, Tuple, List
import threading 
from pathlib import Path 

import cv2
import pygame
from EventSystem import Observer
from img import Img

try:
    import pygame.mixer as mixer # **שנה שורה זו**
    mixer.init() # **הוסף שורה זו - חשוב לאתחל את המיקסר**
except ImportError:
    logging.warning("Pygame library not found or mixer failed to initialize. Install with: pip install pygame")
    mixer = None # **שנה שורה זו**


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
        self.player1_score_pos = player1_score_pos
        self.player2_score_pos = player2_score_pos
        self.scores = {'W': 0, 'B': 0}
        logger.info("ScoreDisplay initialized and subscribed.")

    def update(self, event_type: str, *args, **kwargs):
        if event_type == "piece_captured":
            captured_piece_type = kwargs.get('captured_piece_type')
            captured_by_player_side = kwargs.get('captured_by_player_side') 
            
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
        font_size = 1.0 
        thickness = 2 
        
        canvas.put_text(f"P1 (White) Score: {self.scores['W']}", 
                        self.player1_score_pos[0], self.player1_score_pos[1], 
                        font_size, color=(0, 255, 0, 255), thickness=thickness)
        
        canvas.put_text(f"P2 (Black) Score: {self.scores['B']}", 
                        self.player2_score_pos[0], self.player2_score_pos[1], 
                        font_size, color=(255, 0, 0, 255), thickness=thickness)


class MoveListDisplay(Observer):
    def __init__(self, player1_display_pos: Tuple[int, int], player2_display_pos: Tuple[int, int], max_moves_to_show: int = 10):
        self.player1_display_pos = player1_display_pos
        self.player2_display_pos = player2_display_pos
        self.max_moves_to_show = max_moves_to_show
        self.player1_moves: List[str] = []
        self.player2_moves: List[str] = []
        logger.info("MoveListDisplay initialized and subscribed.")

    def update(self, event_type: str, *args, **kwargs):
        # MoveListDisplay listens to "move" and "jump" events
        if event_type == "move" or event_type == "jump": 
            piece_id = kwargs.get('piece_id')
            from_cell = kwargs.get('from_cell')
            to_cell = kwargs.get('to_cell')
            player = kwargs.get('player')

            move_str = ""
            if event_type == "jump" and from_cell == to_cell:
                # אם זו קפיצה והחייל נשאר באותו מקום
                move_str = f"{piece_id[0]} jumped in place at {chr(ord('a') + to_cell[1])}{8 - to_cell[0]}"
            else:
                # מהלך רגיל או קפיצה למקום אחר
                move_str = f"{piece_id[0]} {chr(ord('a') + from_cell[1])}{8 - from_cell[0]}->{chr(ord('a') + to_cell[1])}{8 - to_cell[0]}"
            
            if player == 1:
                self.player1_moves.append(move_str)
                if len(self.player1_moves) > self.max_moves_to_show:
                    self.player1_moves = self.player1_moves[-self.max_moves_to_show:]
                logger.info(f"P1 Move recorded: {move_str}")
            elif player == 2:
                self.player2_moves.append(move_str)
                if len(self.player2_moves) > self.max_moves_to_show:
                    self.player2_moves = self.player2_moves[-self.max_moves_to_show:]
                logger.info(f"P2 Move recorded: {move_str}")

        elif event_type == "game_start":
            # איפוס רשימות המהלכים בתחילת משחק
            self.player1_moves = []
            self.player2_moves = []
            logger.info("Game started, move list reset.")
        elif event_type == "game_end":
            logger.info(f"Game ended. Total P1 moves: {len(self.player1_moves)}, P2 moves: {len(self.player2_moves)}")

    def draw(self, canvas: Img):
        font_size = 0.6
        thickness = 1
        line_height = 18 

        current_y_p1 = self.player1_display_pos[1]
        for i, move_str in enumerate(self.player1_moves):
            canvas.put_text(move_str, 
                            self.player1_display_pos[0], 
                            current_y_p1 + (i * line_height), 
                            font_size, color=(0, 0, 0, 255), thickness=thickness)
        
        current_y_p2 = self.player2_display_pos[1]
        for i, move_str in enumerate(self.player2_moves):
            canvas.put_text(move_str, 
                            self.player2_display_pos[0], 
                            current_y_p2 + (i * line_height), 
                            font_size, color=(0, 0, 0, 255), thickness=thickness)


class SoundPlayer(Observer):
    """
    Observer המנגן צלילים בתגובה לאירועים, כעת עם Pygame.mixer.
    """
    def __init__(self, sounds_root_path: Path):
        self.sounds_root = sounds_root_path
        self.sounds: Dict[str, 'pygame.mixer.Sound'] = { # נגדיר שהמילון יכיל אובייקטי mixer.Sound
            "move": None,          
            "jump": None,          
            "piece_captured": None, 
            "pawn_promoted": None,  
            "game_end": None,      
            "game_start": None,    
        }
        self._load_sounds()
        logger.info("SoundPlayer initialized and subscribed.")

    def _load_sounds(self):
        """טוען את קבצי הצליל מהדיסק באמצעות Pygame.mixer.Sound."""
        if mixer is None:
            logger.warning("Pygame mixer not available. Sounds will not play.")
            return

        # נתיבים לקבצי הצליל - וודא ששמות הקבצים תואמים בדיוק
        # Pygame.mixer תומך גם ב-MP3 וגם ב-WAV
        self.sounds["move"] = str(self.sounds_root / "foot_step_1.mp3") # נחזיר ל-MP3 או נשאיר WAV אם הומר
        self.sounds["jump"] = str(self.sounds_root / "jump.wav")
        self.sounds["piece_captured"] = str(self.sounds_root / "gun.wav")
        self.sounds["pawn_promoted"] = str(self.sounds_root / "TADA.WAV")
        self.sounds["game_end"] = str(self.sounds_root / "applause.mp3") # נחזיר ל-MP3 או נשאיר WAV אם הומר
        self.sounds["game_start"] = str(self.sounds_root / "gamestart.mp3") # נחזיר ל-MP3 או נשאיר WAV אם הומר

        for event_type, path_str in list(self.sounds.items()): # path_str כי זה עדיין מחרוזת נתיב
            if path_str: 
                try:
                    # טען את הצליל כאובייקט mixer.Sound
                    sound_obj = mixer.Sound(path_str) # **שנה שורה זו**
                    self.sounds[event_type] = sound_obj
                    logger.info(f"Loaded sound for '{event_type}': {path_str}")
                except Exception as e:
                    logger.warning(f"Failed to load sound for '{event_type}' from '{path_str}': {e}. Sound will not play.")
                    self.sounds[event_type] = None 

    def _play_sound_async(self, sound_obj:'pygame.mixer.Sound'): # מקבל אובייקט Sound ולא נתיב
        """מנגן צליל באמצעות Pygame.mixer.Sound.play() ב-thread נפרד."""
        if mixer and sound_obj: # ודא שגם mixer קיים וגם אובייקט הצליל קיים
            try:
                # Pygame.mixer.Sound.play() כבר לא חוסם את ה-thread, אז אין צורך ב-threading נוסף.
                # אבל כדי להיות עקבי עם העיצוב הקודם של ASYNC, נשאיר את זה ב-thread
                # רק נדאג שהפונקציה playsound לא תחסום
                threading.Thread(target=sound_obj.play).start() # **שנה שורה זו**
                logger.debug(f"Playing sound object: {sound_obj}")
            except Exception as e:
                logger.error(f"Error playing sound object {sound_obj}: {e}")
        else:
            logger.debug(f"Attempted to play sound, but mixer or sound object is not available.")

    def update(self, event_type: str, *args, **kwargs):
        """
        מנגן צליל מתאים בהתאם לסוג האירוע.
        """
        # SoundPlayer שומר כעת אובייקטי mixer.Sound במילון, לא נתיבים
        sound_obj = self.sounds.get(event_type) 
        if sound_obj: # ודא שאובייקט הצליל קיים (כלומר, נטען בהצלחה)
            self._play_sound_async(sound_obj)


class TextOverlayDisplay(Observer):
    """
    Observer המציג כיתובים מעניינים בתחילת ובסיום המשחק.
    """
    def __init__(self, game_instance, display_pos: Tuple[int, int], welcome_text: str, goodbye_text: str, duration_ms: int = 3000):
        self.game = game_instance
        self.display_pos = display_pos
        self.welcome_text = welcome_text
        self.goodbye_text = goodbye_text
        self.duration_ms = duration_ms # משך הצגת הטקסט במילישניות

        self.current_text = ""
        self.is_visible = False
        self.display_start_time = 0 # זמן תחילת הצגת הטקסט

        logger.info("TextOverlayDisplay initialized and subscribed.")

    def update(self, event_type: str, *args, **kwargs):
        timestamp = kwargs.get('timestamp', self.game.game_time_ms()) # השתמש בזמן האירוע או בזמן המשחק

        if event_type == "game_start":
            self.current_text = self.welcome_text
            self.is_visible = True
            self.display_start_time = timestamp
            logger.info(f"Displaying welcome text: '{self.welcome_text}'")
        elif event_type == "game_end":
            self.current_text = self.goodbye_text
            self.is_visible = True
            self.display_start_time = timestamp
            logger.info(f"Displaying goodbye text: '{self.goodbye_text}'")

    def draw(self, canvas: Img):
        # **הדפסת Debug חדשה בתחילת מתודת draw**
        
        if not self.is_visible:
            return

        # חשב כמה זמן עבר מאז שהטקסט התחיל להופיע
        elapsed_time = self.game.game_time_ms() - self.display_start_time

        if elapsed_time > self.duration_ms:
            self.is_visible = False # הטקסט נעלם לאחר משך הזמן שהוגדר
            self.current_text = ""
            return

        # אם הטקסט עדיין אמור להיות מוצג, צייר אותו
        font_size = 2.0 # גודל גופן גדול יותר לכיתובים מרכזיים
        thickness = 4
        text_color = (0, 0, 255, 255) 
        
        # מרכז את הטקסט
        text_size, _ = cv2.getTextSize(self.current_text, cv2.FONT_HERSHEY_SIMPLEX, font_size, thickness)
        text_w, text_h = text_size
        
        canvas_center_x = self.game.canvas_width // 2
        canvas_center_y = self.game.canvas_height // 2

        x = canvas_center_x - (text_w // 2)
        y = canvas_center_y + (text_h // 2) 

        # **הדפסת Debug חדשה עם מיקום וגודל הטקסט**
        print(f"DEBUG TextOverlay: Drawing text '{self.current_text}' at canvas_pos=({x}, {y}), text_size=({text_w}, {text_h}), font_size={font_size}")
        canvas.put_text(self.current_text, x, y, font_size, color=text_color, thickness=thickness)



