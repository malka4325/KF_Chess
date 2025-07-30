# PieceFactory.py
from __future__ import annotations
import csv, json, pathlib
from plistlib import InvalidFileException
from typing import Dict, Tuple

from client.Board import Board
from Command import Command
from client.GraphicsFactory import GraphicsFactory
from server.Moves import Moves
from server.PhysicsFactory import PhysicsFactory
from server.Piece import Piece
from server.State import State


class PieceFactory:
    def __init__(self,
                 board: Board,
                 pieces_root,
                 graphics_factory=None,
                 physics_factory=None):

        self.board = board
        self.graphics_factory = graphics_factory or GraphicsFactory()
        self.physics_factory = physics_factory or PhysicsFactory(board)
        self._pieces_root = pieces_root

    # ──────────────────────────────────────────────────────────────
    @staticmethod
    def _load_master_csv(pieces_root: pathlib.Path) -> Dict[str, Dict[str, str]]:
        _global_trans: Dict[str, Dict[str, str]] = {}
        csv_path = pieces_root / "transitions.csv"
        if not csv_path.exists():
            return _global_trans

        with csv_path.open(newline="", encoding="utf-8") as f:
            rdr = csv.DictReader(f)
            for row in rdr:
                frm, ev, nxt = row["from_state"], row["event"], row["to_state"]
                _global_trans.setdefault(frm, {})[ev] = nxt

        return _global_trans

    # ──────────────────────────────────────────────────────────────
    def _build_state_machine(self, piece_dir: pathlib.Path) -> State:
        board_size = (self.board.W_cells, self.board.H_cells)
        cell_px = (self.board.cell_W_pix, self.board.cell_H_pix)
        _global_trans = self._load_master_csv(piece_dir / "states")

        states: Dict[str, State] = {}

        # There is no longer a piece-wide fall-back. Each state must provide its own
        # `moves.txt`; if it does not, the state will have *no* legal moves.
        # ── load every <piece>/states/<state>/ ───────────────────
        for state_dir in (piece_dir / "states").iterdir():
            if not state_dir.is_dir():
                continue
            name = state_dir.name

            cfg_path = state_dir / "config.json"
            cfg = json.loads(cfg_path.read_text()) if cfg_path.exists() else {}

            moves_path = state_dir / "moves.txt"
            moves = Moves(moves_path, board_size) if moves_path.exists() else None
            graphics = self.graphics_factory.load(state_dir / "sprites",
                                                  cfg.get("graphics", {}), cell_px)


            physics_cfg = cfg.get("physics", {})
            physics = self.physics_factory.create((0, 0), name, physics_cfg)
            # Always force do_i_need_clear_path=False for knight (NB/NW) in move state
            if (piece_dir.name in ["NB", "NW"]) and name == "move":
                physics.do_i_need_clear_path = False
            elif ("need_clear_path" in cfg and cfg["need_clear_path"] is False) or ("need_clear_path" in physics_cfg and physics_cfg["need_clear_path"] is False):
                physics.do_i_need_clear_path = False
            elif "need_clear_path" in cfg:
                physics.do_i_need_clear_path = cfg["need_clear_path"]
            elif "need_clear_path" in physics_cfg:
                physics.do_i_need_clear_path = physics_cfg["need_clear_path"]
            else:
                physics.do_i_need_clear_path = True

            st = State(moves, graphics, physics)
            st.name = name
            states[name] = st

        # apply master CSV overrides
        for frm, ev_map in _global_trans.items():
            src = states.get(frm)
            if not src:
                continue
            for ev, nxt in ev_map.items():
                dst = states.get(nxt)
                if not dst:
                    continue
                src.set_transition(ev, dst)

        # --- Custom jump logic: idle->jump, jump->short_rest, short_rest->idle ---
        idle = states.get("idle")
        jump = states.get("jump")
        short_rest = states.get("short_rest")
        if idle and jump:
            idle.set_transition("jump", jump)
        if jump and short_rest:
            jump.set_transition("done", short_rest)
            # Make the piece invulnerable during jump
            if hasattr(jump.physics, "can_be_captured"):
                jump.physics.can_be_captured = lambda: False
        if short_rest and idle:
            short_rest.set_transition("done", idle)

        # always start at idle
        return states.get("idle")

    # ──────────────────────────────────────────────────────────────
    def create_piece(self, p_type: str, cell: Tuple[int, int]) -> Piece:
        p_dir = self._pieces_root / p_type
        state = self._build_state_machine(p_dir)

        piece = Piece(f"{p_type}_{cell}", state)
        piece.state.reset(Command(0, piece.id, "idle", [cell]))

        return piece
