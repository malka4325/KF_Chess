from enum import Enum

class GameEvent(Enum):
    MOVE = "move"
    JUMP = "jump"
    PIECE_CAPTURED = "piece_captured"
    PAWN_PROMOTED = "pawn_promoted"
    GAME_START = "game_start"
    GAME_END = "game_end"