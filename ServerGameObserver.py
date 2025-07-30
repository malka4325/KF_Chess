import asyncio
import json
import os
import sys
from typing import List, Dict
from client.EventSystem import Observer
from server.Game import Game

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, 'KFC_Py')
sys.path.append(project_root)

class ServerGameObserver(Observer):
    def __init__(self, game_instance: Game, clients_set: set, loop: asyncio.AbstractEventLoop):
        self.game = game_instance
        self.clients = clients_set 
        self.loop = loop 
        self.game.subscribe(self) 
        print("ServerGameObserver initialized and subscribed to game events.")

    def update(self, event_type: str, **kwargs):
        print(f"ServerGameObserver received event: {event_type} with details: {kwargs}")
        
        if event_type in ["move", "jump", "piece_captured", "pawn_promoted", "game_start", "game_end"]:
            board_state = self._get_current_board_state_for_serialization()
            self.loop.call_soon_threadsafe(self._schedule_broadcast_task, board_state)

    def _get_current_board_state_for_serialization(self) -> List[Dict]:
        serialized_pieces = []
        for piece in self.game.pieces:
            row, col = piece.current_cell()
            serialized_pieces.append({
                "piece_id": piece.id,
                "current_pos": [row, col], 
                "type": piece.id[0], 
                "side": piece.id[1] 
            })
        return serialized_pieces

    async def _broadcast_state_to_clients(self, board_state: List[Dict]):
        if not self.clients:
            print("No clients connected to send board update.")
            return

        message = json.dumps({"event_type": "board_update", "state": board_state})
        
        send_tasks = []
        for websocket in list(self.clients):
            try:
                send_tasks.append(websocket.send(message))
            except Exception as e:
                print(f"Error preparing send to client {websocket.remote_address}: {e}")
                self.clients.discard(websocket)
        
        if send_tasks:
            await asyncio.gather(*send_tasks, return_exceptions=True)
            print(f"Board state sent to {len(send_tasks)} clients.")
        else:
            print("No active send tasks.")

    def _schedule_broadcast_task(self, board_state: List[Dict]):
        self.loop.create_task(self._broadcast_state_to_clients(board_state))