# client.py (for board rendering only, without user input)

import asyncio
import sys
import websockets
import json
import pathlib 
import os 
import cv2 

import time 

# No imports for KeyboardProcessor or KeyboardProducer in this version


current_dir = os.path.dirname(os.path.abspath(__file__))
project_root_for_imports = os.path.join(current_dir, 'KFC_Py')
sys.path.append(project_root_for_imports)
pieces_root_path = pathlib.Path(current_dir) / "pieces" 

from client.Board import Board 
from client.GraphicsFactory import  ImgFactory,GraphicsFactory
from client.img import Img 
from server.Piece import Piece 
from typing import Dict, List, Tuple



BOARD_OFFSET_X = 308 
BOARD_OFFSET_Y = 98 
CELL_PX = 77 
BOARD_W_CELLS = 8
BOARD_H_CELLS = 8

# !!! הגדרה חדשה: מחלקת מצב כלי פשוטה עבור הלקוח !!!
class ClientPieceState:
    """
    A simplified State object for client-side Piece instances.
    It primarily holds the current position for rendering.
    """
    def __init__(self, initial_pos: Tuple[int, int], piece_type: str, piece_side: str):
        self._current_cell = initial_pos
        self.piece_type = piece_type # Keep type and side for drawing logic
        self.piece_side = piece_side

    def current_cell(self) -> Tuple[int, int]:
        """Returns the current cell coordinates (row, col) of the piece."""
        return self._current_cell
    
    def set_current_cell(self, new_pos: Tuple[int, int]):
        """Sets the current cell coordinates of the piece."""
        self._current_cell = new_pos
    
    # Placeholder for graphics - will need proper implementation for sprites
    class GraphicsPlaceholder:
        def get_img(self):
            # This is a dummy for Piece.state.graphics.get_img()
            # In a full implementation, this would return the actual sprite.
            return None # Or a dummy Img object if your draw method expects it
    
    @property
    def graphics(self):
        # Return an instance of the placeholder graphics
        return self.GraphicsPlaceholder()

# !!! סוף הגדרה חדשה !!!


async def initialize_client_graphics():
    """Initializes the board and graphics objects on the client side."""
    global client_board, client_canvas

    board_png_path = pieces_root_path / "board.png"
    if not board_png_path.exists():
        print(f"Error: board.png not found at {board_png_path}")
        return

    full_bg_path = pieces_root_path / "full.jpg"
    if not full_bg_path.exists():
        print(f"Error: full.jpg not found at {full_bg_path}")
        return

    board_img = Img().read(str(board_png_path), size=(CELL_PX*BOARD_W_CELLS, CELL_PX*BOARD_H_CELLS), keep_aspect=False)
    client_board = Board(CELL_PX, CELL_PX, BOARD_W_CELLS, BOARD_H_CELLS, board_img)

    client_canvas = Img().read(str(full_bg_path), size=None, keep_aspect=False)
    client_canvas.initial_img_data = client_canvas.img.copy() 

    # We only need this if we actually load piece sprites on client
    # graphics_factory_instance_for_pieces = GraphicsFactory(ImgFactory()) 

    cv2.namedWindow("KungFu Chess Client", cv2.WINDOW_AUTOSIZE)
    cv2.moveWindow("KungFu Chess Client", 0, 0)
    print("Client graphics initialized.")


async def draw_board_state(board_state: List[Dict]):
    """
    Draws the current board state on the client's window.
    """
    global client_canvas, client_board, client_pieces

    if client_canvas is None or client_board is None:
        print("Client graphics not initialized for drawing.")
        return

    client_canvas.img = client_canvas.initial_img_data.copy()
    client_board.img.draw_on(client_canvas, BOARD_OFFSET_X, BOARD_OFFSET_Y)

    updated_pieces_map = {}
    for piece_data in board_state:
        piece_id = piece_data['piece_id']
        current_pos = tuple(piece_data['current_pos'])
        piece_type = piece_data['type']
        piece_side = piece_data['side']
        
        if piece_id in client_pieces:
            piece = client_pieces[piece_id]
            piece.state.set_current_cell(current_pos) # Update existing piece's state
        else:
            # !!! תיקון: יצירת Piece עם ClientPieceState !!!
            # יצירת מופע של ClientPieceState עבור ה-Piece
            init_state_obj = ClientPieceState(current_pos, piece_type, piece_side)
            piece = Piece(piece_id, init_state_obj) # יצירת Piece עם 2 ארגומנטים בלבד
            client_pieces[piece_id] = piece
            print(f"Client: New piece '{piece_id}' created at {current_pos}.")
        
        updated_pieces_map[piece_id] = piece 

    pieces_to_remove = [p_id for p_id in client_pieces if p_id not in updated_pieces_map]
    for p_id in pieces_to_remove:
        del client_pieces[p_id]
        print(f"Client: Piece {p_id} removed (captured).")

    for piece_id, piece in client_pieces.items():
        try:
            r, c = piece.state.current_cell() # קבל את המיקום מה-state של ה-Piece
            x_pix = c * client_board.cell_W_pix + BOARD_OFFSET_X
            y_pix = r * client_board.cell_H_pix + BOARD_OFFSET_Y
            
            # TODO: כאן תצטרך לטעון ולצייר את הספירט האמיתי של הכלי.
            # זה דורש ש-PieceFactory/GraphicsFactory ייצרו אובייקטי Graphics מלאים
            # עבור הכלים בצד הלקוח.
            # בינתיים, נמשיך לצייר ריבוע placeholder.
            color = (0, 0, 255) if 'B' in piece_id else (255, 0, 0) 
            cv2.rectangle(client_canvas.img, (x_pix, y_pix), 
                          (x_pix + client_board.cell_W_pix, y_pix + client_board.cell_H_pix), 
                          color, 2)
            cv2.putText(client_canvas.img, piece_id, (x_pix + 5, y_pix + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        except Exception as e:
            print(f"Client: Error drawing piece {piece_id}: {e}")

    cv2.imshow("KungFu Chess Client", client_canvas.img)
    cv2.waitKey(1) 


async def receive_and_process_messages(websocket, client_id):
    """Handles receiving and processing messages from the server."""
    try:
        async for response_json in websocket:
            try:
                response = json.loads(response_json)
                
                if "event_type" in response:
                    event_type = response["event_type"]
                    if event_type == "initial_board_state" or event_type == "board_update":
                        board_state = response["state"]
                        print(f"Client {client_id} received board update of type '{event_type}'. Drawing...")
                        await draw_board_state(board_state) 
                    else:
                        print(f"Client {client_id} received unknown event: {response}")
                elif "status" in response:
                    status = response["status"]
                    message_text = response.get("message", "No detailed message.") 
                    print(f"Client {client_id} received status response: {status} - {message_text}")
                else:
                    print(f"Client {client_id} received message in unknown format: {response}")

            except json.JSONDecodeError:
                print(f"Client {client_id}: Error parsing JSON response from server: {response_json}")
            except Exception as e:
                print(f"Client {client_id}: General error occurred while processing message: {e}")

    except websockets.exceptions.ConnectionClosedOK:
        print(f"Client {client_id}: Connection closed successfully.")
    except Exception as e:
        print(f"Client {client_id}: WebSocket connection error: {e}")
        cv2.destroyAllWindows()


async def connect_and_manage_client(player_id, initial_piece_id, initial_from_coords, initial_to_coords):
    """
    This function connects to the WebSocket server, initiates message reception,
    and sends an initial hardcoded command (no user input in this version).
    """
    uri = "ws://localhost:8765" 
    try:
        async with websockets.connect(uri) as websocket:
            print(f"Client {player_id} connected.")
            
            receive_task = asyncio.create_task(receive_and_process_messages(websocket, player_id))

            # Send an initial hardcoded command after a delay to test server response
            await asyncio.sleep(1) 
            initial_command_message = {
                "piece_id": initial_piece_id,
                "command_type": "MOVE_PIECE",
                "to_pos": list(initial_to_coords)
            }
            await websocket.send(json.dumps(initial_command_message))
            print(f"Client {player_id} sending initial hardcoded move: {initial_command_message}")

            await receive_task 

    except ConnectionRefusedError:
        print(f"Client {player_id}: Error: Connection refused. Ensure server is running.")
    except Exception as e:
        print(f"Client {player_id}: General error occurred: {e}")
        cv2.destroyAllWindows()


async def main_client():
    global client_board, client_canvas, client_pieces 

    await initialize_client_graphics() 

    await asyncio.gather(
        connect_and_manage_client(1, 1, (6,4), (4,4)), 
        connect_and_manage_client(2, 2, (1,2), (3,2))  
    )

    print("All client tasks finished. Keeping client window alive. Press ESC to close.")
    while True:
        key = cv2.waitKey(1) & 0xFF
        if key == 27: 
            break
    cv2.destroyAllWindows()


if __name__ == "__main__":
    asyncio.run(main_client())