# server.py

import os 
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy" 
print("SDL_VIDEODRIVER and SDL_AUDIODRIVER environment variables set to 'dummy'.")


import asyncio
import websockets
import sys
import json
import pathlib 
from collections import deque 
from typing import List, Dict, Tuple 
from GameEvent import GameEvent

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, 'KFC_Py')
sys.path.append(project_root)

# Mocking the 'keyboard' module
class MockKeyboard:
    def hook(self, *args, **kwargs): pass
    def unhook_all(self): pass
    def wait(self, *args, **kwargs): pass
sys.modules['keyboard'] = MockKeyboard()
print("Module 'keyboard' successfully mocked.")


from server.Game import Game
from client.Board import Board
from server.PieceFactory import PieceFactory 
# from client.GraphicsFactory import GraphicsFactory 
# from client.EventSystem import Publisher, Observer 
from Command import Command 
from ServerGameObserver import ServerGameObserver

from mock_img import mock_graphics_image_loader 
from server.GameFactory import create_game 

class MockImgFactory:
    def __init__(self):
        pass

    def __call__(self, path, size=None, keep_aspect=False, interpolation=None):
        return mock_graphics_image_loader(path, size, keep_aspect)

    def read(self, path, size=None, keep_aspect=False):
        return mock_graphics_image_loader(path, size, keep_aspect)


game_instance: Game = None
# Global set of connected clients, used for broadcasting
connected_clients: set = set() 




async def game_handler(websocket, path=None): 
    global game_instance
    connected_clients.add(websocket) 
    print(f"New client connected. Total connected clients: {len(connected_clients)}")

    try:
        global server_observer 
        initial_board_state = server_observer._get_current_board_state_for_serialization()
        await websocket.send(json.dumps({"event_type": "initial_board_state", "state": initial_board_state}))
        print(f"Initial board state sent to client {websocket.remote_address}")


        async for message in websocket:
            print(f"Message received from client: {message}")
            
            try:
                command_data = json.loads(message)
                piece_id = command_data['piece_id']
                command_type_str = command_data['command_type'] 
                to_pos_list = command_data['to_pos'] 
                
                command_type_for_command_obj = command_type_str.lower().replace("_piece", "")
                
                current_game_time = game_instance.game_time_ms() 
                
                params_for_command_obj = [None, tuple(to_pos_list)] 
                
                command = Command(
                    timestamp=current_game_time,
                    piece_id=piece_id,
                    type=command_type_for_command_obj,
                    params=params_for_command_obj,
                    player=None 
                )
                print(f"Message parsed as command: {command}")

                if game_instance:
                    await asyncio.to_thread(game_instance.user_input_queue.put, command) 
                    print("Command sent for processing by game instance.")
                    
                    response_message = f"Server: Move '{command.piece_id}' to '{command.params[1]}' received for processing. Waiting for board update..."
                    await websocket.send(json.dumps({"status": "received", "message": response_message}))
                    print(f"Response sent to client: {response_message}")

            except json.JSONDecodeError:
                error_message = f"Server: Error: Invalid JSON message format: {message}"
                print(error_message)
                await websocket.send(json.dumps({"status": "error", "message": error_message}))
            except AttributeError as e:
                error_message = f"Server: Error parsing command type or data structure: {e}. Message: {message}"
                print(error_message)
                await websocket.send(json.dumps({"status": "error", "message": error_message}))
            except KeyError as e:
                error_message = f"Server: Error: Missing required field in JSON: {e}. Message: {message}"
                print(error_message)
                await websocket.send(json.dumps({"status": "error", "message": error_message}))

    except websockets.exceptions.ConnectionClosedOK:
        print("Client connection closed successfully.")
    except Exception as e:
        print(f"Error handling connection: {e}")
    finally:
        connected_clients.discard(websocket) 
        print(f"Client disconnected. Total connected clients: {len(connected_clients)}")


async def main():
    global game_instance
    global server_observer 

    try:
        import cv2 
        cv2.namedWindow = lambda *args, **kwargs: None
        cv2.moveWindow = lambda *args, **kwargs: None
        cv2.imshow = lambda *args, **kwargs: None
        cv2.waitKey = lambda *args, **kwargs: 1 
        cv2.getWindowProperty = lambda *args, **kwargs: 1 
        cv2.destroyAllWindows = lambda *args, **kwargs: None
        print("OpenCV (cv2) functions successfully mocked for server.")
    except ImportError:
        print("cv2 module not found, skipping OpenCV mocking.")
    except Exception as e:
        print(f"Error mocking OpenCV: {e}")

    try:
        import pygame
        pygame.mixer.init = lambda *args, **kwargs: None
        pygame.mixer.quit = lambda *args, **kwargs: None
        pygame.mixer.music.load = lambda *args, **kwargs: None
        pygame.mixer.music.play = lambda *args, **kwargs: None
        pygame.mixer.music.stop = lambda *args, **kwargs: None
        print("pygame.mixer successfully mocked for server.")
    except ImportError:
        print("pygame module not found, skipping pygame.mixer mock.")
    except Exception as e:
        print(f"Error mocking pygame.mixer: {e}")


    # 1. Path definitions
    base_project_dir = pathlib.Path(current_dir)
    pieces_root_path = base_project_dir / "pieces"
    board_csv_path = pieces_root_path / "board.csv" 
    
    # 2. Initialize helper objects
    mock_img_factory_instance = MockImgFactory()
    
    # 3. Initialize game instance using create_game function
    try:
        game_instance = create_game( 
            pieces_root=pieces_root_path,
            img_factory=mock_img_factory_instance 
        )
        print("Game instance successfully initialized using create_game (from GameFactory.py).")

        if game_instance._is_win():
            print("!!! WARNING: Game is in an immediate win state after initialization. Game loop will terminate immediately. !!!")

        game_instance.start_user_input_thread = lambda: None 
        
        # Initialize the ServerGameObserver here!
        main_loop = asyncio.get_running_loop() 
        server_observer = ServerGameObserver(game_instance, connected_clients, main_loop)
        
        print("Attempting to create and run Game loop Task in a separate thread...")
        game_task = asyncio.create_task(asyncio.to_thread(game_instance.run, is_with_graphics=False)) 
        print("Game loop Task launched asynchronously on server (in separate thread and without graphics/keyboard input).")

        def game_task_done_callback(fut):
            try:
                fut.result() 
            except asyncio.CancelledError:
                print("Game task cancelled.")
            except Exception as e:
                print(f"!!! Critical error in Game loop Task: {type(e).__name__}: {e} !!!")
                import traceback
                traceback.print_exc() 

        game_task.add_done_callback(game_task_done_callback)

    except FileNotFoundError as e:
        print(f"Error: Required file not found. Ensure 'pieces_root' and 'board.csv' paths are correct. {e}")
        print("Ensure folder structure is as follows:")
        print("  your_project_folder/")
        print("  ├── server.py")
        print("  ├── KFC_Py/")
        print("  │   ├── Game.py")
        print("  │   └── ...")
        print("  └── pieces/")
        print("      ├── board.csv")
        print("      └── ...")
        return 
    except Exception as e:
        print(f"Error initializing game instance: {e}")
        print("Ensure all imports are correct and GameFactory/Game constructors are valid.")
        return 

    # 4. Start WebSocket server
    print("Attempting to start WebSocket server...")
    try:
        async with websockets.serve(game_handler, "localhost", 8765):
            print("WebSocket server activated and listening on port 8765...")
            await asyncio.sleep(float('inf')) 
    except Exception as e:
        print(f"!!! Critical error starting WebSocket server: {type(e).__name__}: {e} !!!")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())