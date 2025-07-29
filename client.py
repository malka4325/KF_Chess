import asyncio
import sys
import time
import websockets
import json
import pathlib # נצטרך את זה לטיפול בנתיבים
import os # נצטרך את זה לטיפול בנתיבים
# ייבוא עבור רינדור גרפי וניהול לוח מקומי
import cv2 # נצטרך את OpenCV לרינדור

from typing import Dict, List, Tuple

# וודא שנתיב KFC_Py מתווסף ל-sys.path גם בלקוח אם הוא לא נמצא באותה תיקייה
current_dir = os.path.dirname(os.path.abspath(__file__))
# נניח שתיקיית KFC_Py נמצאת רמה אחת מעל client.py, או באותה רמה
# אם client.py נמצא ב-your_project_folder/client.py ו-KFC_Py ב-your_project_folder/KFC_Py
project_root_for_imports = os.path.join(current_dir, 'KFC_Py')
sys.path.append(project_root_for_imports)
# ואולי גם תיקיית pieces אם היא לא בתוך KFC_Py
pieces_root_path = pathlib.Path(current_dir) / "pieces" # נתיב לתיקיית pieces
from Board import Board # וודא ש-KFC_Py נמצא ב-sys.path אם client.py מופעל מחוץ לתיקייה
from GraphicsFactory import ImgFactory,GraphicsFactory
from img import  Img # ImgFactory האמיתי מגיע מ-Img.py
from Piece import Piece # נצטרך את מחלקת Piece
from KeyboardInput import KeyboardProcessor, KeyboardProducer
from Game import Game # נצטרך מופע Game חלקי בלקוח עבור KeyboardProducer.game.running
# הגדרות גלובליות בצד הלקוח (לצורך הרינדור)
client_board: Board = None
client_canvas: Img = None
client_pieces: Dict[str, Piece] = {} # מילון של אובייקטי Piece בצד הלקוח

# הגדרות רינדור (צריך להתאים לגודל הלוח והתמונה שלך)
BOARD_OFFSET_X = 308 
BOARD_OFFSET_Y = 98 
CELL_PX = 77 # גודל תא בפיקסלים, מ-GameFactory
BOARD_W_CELLS = 8
BOARD_H_CELLS = 8


async def initialize_client_graphics():
    """Initializes the board and graphics objects on the client side."""
    global client_board, client_canvas

    # טען את תמונת הלוח המקורית (board.png)
    # נתיב ל-board.png
    board_png_path = pieces_root_path / "board.png"
    if not board_png_path.exists():
        print(f"Error: board.png not found at {board_png_path}")
        return

    img_factory_instance = ImgFactory() # השתמש ב-ImgFactory האמיתי
    graphics_factory_instance = GraphicsFactory(img_factory_instance)

    board_img = img_factory_instance(str(board_png_path), (CELL_PX*BOARD_W_CELLS, CELL_PX*BOARD_H_CELLS), keep_aspect=False)
    client_board = Board(CELL_PX, CELL_PX, BOARD_W_CELLS, BOARD_H_CELLS, board_img)

    # טען את תמונת הרקע המלאה (full.jpg) עבור ה-canvas הראשי
    full_bg_path = pieces_root_path / "full.jpg"
    if not full_bg_path.exists():
        print(f"Error: full.jpg not found at {full_bg_path}")
        return

    client_canvas = img_factory_instance.read(str(full_bg_path), size=None, keep_aspect=False)
    # שמור עותק של תמונת הרקע המקורית לציור מחדש בכל פריימ
    client_canvas.initial_img_data = client_canvas.img.copy() 

    # צור חלון תצוגה
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

    # 1. צייר מחדש את הרקע והלוח הריק
    client_canvas.img = client_canvas.initial_img_data.copy()
    client_board.img.draw_on(client_canvas, BOARD_OFFSET_X, BOARD_OFFSET_Y)

    # 2. עדכן ויזואלית את הכלים
    # יצירת מילון זמני לכלים חדשים/מעודכנים
    updated_pieces_map = {}
    for piece_data in board_state:
        piece_id = piece_data['piece_id']
        current_pos = tuple(piece_data['current_pos'])
        piece_type = piece_data['type']
        piece_side = piece_data['side']
        
        # אם הכלי כבר קיים אצלנו, נעדכן את מיקומו
        if piece_id in client_pieces:
            piece = client_pieces[piece_id]
            piece.set_current_cell(current_pos) # נניח שקיימת מתודה כזו ב-Piece
            # print(f"Client: Updating existing piece {piece_id} to {current_pos}")
        else:
            # אם הכלי חדש (לדוגמה, לאחר קידום רגלי), ניצור אותו
            # זה דורש יצירת PieceFactory גם בצד הלקוח, או פשוט Piece עם ספירט דמה
            # לצורך הדגמה, נדפיס אזהרה. יצירת Pieces בצד הלקוח מורכבת יותר.
            print(f"Client: New piece {piece_id} at {current_pos} ({piece_type}{piece_side}) - NOT YET RENDERED FULLY.")
            # TODO: אם הכלי חדש, יהיה צורך ליצור אובייקט Piece מלא כאן
            # באמצעות PieceFactory מקומי בצד הלקוח.
            # זה יצריך גם לוודא שכל המידע הדרוש ל-PieceFactory זמין.
            # בינתיים, נשמור רק את ה-ID והמיקום.
            piece = Piece(piece_id, current_pos, None, None) # Mock Piece, יצריך תיקון
            client_pieces[piece_id] = piece
        
        updated_pieces_map[piece_id] = piece # שמור התייחסות לכלי מעודכן

    # הסר כלים שנעלמו מהלוח (נלכדו)
    pieces_to_remove = [p_id for p_id in client_pieces if p_id not in updated_pieces_map]
    for p_id in pieces_to_remove:
        del client_pieces[p_id]
        print(f"Client: Piece {p_id} removed (captured).")

    # 3. צייר את כל הכלים הפעילים
    for piece_id, piece in client_pieces.items():
        # וודא שלחפץ Piece יש את תכונת current_pos או מתודה לקבלת מיקום
        # וודא שיש לו sprite שניתן לצייר
        try:
            r, c = piece.current_cell() # קבל את המיקום הנוכחי
            x_pix = c * client_board.cell_W_pix + BOARD_OFFSET_X
            y_pix = r * client_board.cell_H_pix + BOARD_OFFSET_Y
            
            # TODO: כאן תצטרך לטעון את הספירט של הכלי (piece.state.graphics.get_img())
            # ולצייר אותו על ה-canvas. זה דורש אתחול נכון של Graphics ו-State ב-Piece המקומי.
            # בינתיים, נצייר רק ריבוע placeholder.
            # print(f"Client: Drawing piece {piece_id} at {x_pix}, {y_pix}")
            color = (0, 0, 255) if 'B' in piece_id else (255, 0, 0) # כחול לשחור, אדום ללבן
            cv2.rectangle(client_canvas.img, (x_pix, y_pix), 
                          (x_pix + client_board.cell_W_pix, y_pix + client_board.cell_H_pix), 
                          color, 2)
            cv2.putText(client_canvas.img, piece_id, (x_pix + 5, y_pix + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        except Exception as e:
            print(f"Client: Error drawing piece {piece_id}: {e}")

    # 4. הצג את החלון
    cv2.imshow("KungFu Chess Client", client_canvas.img)
    cv2.waitKey(1) # נדרש לעדכון חלון OpenCV


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
                        await draw_board_state(board_state) # קריאה לפונקציית הרינדור החדשה
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

async def connect_and_send(piece_id, from_coords, to_coords, client_id):
    """
    This function connects to the WebSocket server, initiates message reception, and sends a command.
    """
    uri = "ws://localhost:8765" 
    try:
        async with websockets.connect(uri) as websocket:
            print(f"Client {client_id} connected.")
            
            receive_task = asyncio.create_task(receive_and_process_messages(websocket, client_id))

            # Send commands after a short delay to allow initial board state to be received
            await asyncio.sleep(1) 

            command_message = {
                "piece_id": piece_id,
                "command_type": "MOVE_PIECE",
                "to_pos": list(to_coords)
            }
            await websocket.send(json.dumps(command_message))
            print(f"Client {client_id} sending: {command_message}")

            await receive_task 

    except ConnectionRefusedError:
        print(f"Client {client_id}: Error: Connection refused. Ensure server is running.")
    except Exception as e:
        print(f"Client {client_id}: General error occurred: {e}")


async def main_client():
    global client_board, client_canvas, client_pieces # לוודא שמשתנים גלובליים נגישים

    # אתחול גרפיקה
    await initialize_client_graphics()

    # יצירת תור פקודות מקומי שיקבל פקודות מה-KeyboardProducer
    local_command_queue = asyncio.Queue()

    # יצירת מופע Game "חלקי" עבור הלקוח
    # זהו מופע מינימלי שרק מטרתו להחזיק את הדגל game.running
    # ואולי את game.pieces עבור KeyboardProducer
    class MockClientGame:
        def __init__(self, pieces_dict):
            self.running = True # דגל שמציין שהמשחק עדיין פעיל (עד שהשרת יגיד אחרת)
            self.pieces = pieces_dict # המילון של הכלים ש-draw_board_state מעדכן
            self.game_time_ms = lambda: time.monotonic_ns() // 1_000_000 # פונקציית זמן פשוטה
        
        def subscribe(self, observer): # Observer יצטרך להירשם
            pass # לא צריך Observer בלקוח עבור שליחה, רק עבור קבלה.
        
        def notify(self, event_type, **kwargs):
            pass # לא מפרסם אירועים לשרת
            
    # נאתחל את מופע ה-MockClientGame כאשר נדע את מצב הלוח הראשוני מהשרת
    # בינתיים, ניצור אותו עם מילון הכלים הגלובלי הריק.
    client_game_instance = MockClientGame(client_pieces) # העבר את client_pieces למשחק הדמה

    # אתחול מעבדי מקלדת עבור שני שחקנים
    p1_keymap = {
        "up": "up", "down": "down", "left": "left", "right": "right",
        "enter": "select", "+": "jump"
    }
    p2_keymap = {
        "w": "up", "s": "down", "a": "left", "d": "right",
        "space": "select", "g": "jump",
        "'": "up", "ד": "down", "ש": "left", "ג": "right",
        "ע": "jump"
    }

    kp1 = KeyboardProcessor(BOARD_H_CELLS, BOARD_W_CELLS, keymap=p1_keymap)
    kp2 = KeyboardProcessor(BOARD_H_CELLS, BOARD_W_CELLS, keymap=p2_keymap)

    # יצירת ה-KeyboardProducers (לא מתחילים אותם כאן עדיין)
    # נצטרך להעביר ל-KeyboardProducer את חיבור ה-websocket,
    # אבל החיבור נוצר בתוך connect_and_send.
    # לכן, נצטרך להתאים את מבנה main_client או את connect_and_send
    # כך שה-KeyboardProducers יופעלו עבור כל לקוח בנפרד.

    # נשנה את connect_and_send כך שיטפל גם ב-KeyboardProducer שלו
    async def connect_and_manage_client(piece_id, from_coords, to_coords, client_id):
        uri = "ws://localhost:8765" 
        try:
            async with websockets.connect(uri) as websocket:
                print(f"Client {client_id} connected.")
                
                # Task לקבלת הודעות
                receive_task = asyncio.create_task(receive_and_process_messages(websocket, client_id))

                # יצירת KeyboardProducer ספציפי ללקוח הזה
                # הוא צריך גישה ל-client_game_instance (עבור .running ו-.pieces) ולחיבור ה-WebSocket
                kb_producer = KeyboardProducer(
                    client_game_instance, # מופע ה-Game המקומי
                    local_command_queue,  # התור שאליו ה-Producer ידחוף פקודות
                    kp1 if client_id == 1 else kp2, # בחירת ה-processor הנכון
                    client_id,
                    websocket # העברת חיבור ה-WebSocket ישירות
                )
                kb_producer.start() # הפעלת התהליכון של ה-KeyboardProducer

                # שליחת פקודות התחלתיות (כמו קודם)
                await asyncio.sleep(1) 

                command_message = {
                    "piece_id": piece_id,
                    "command_type": "MOVE_PIECE",
                    "to_pos": list(to_coords)
                }
                # במקום לשלוח כאן קבועה, הקלט יגיע מ-KeyboardProducer
                # ה-KeyboardProducer דוחף לתור local_command_queue
                # אנו נצטרך לולאה שתצרוך מ-local_command_queue ותשלח לשרת.
                
                # --- NEW LOGIC: Loop to send commands from local queue ---
                async def send_commands_from_queue():
                    while client_game_instance.running: # כל עוד המשחק רץ
                        try:
                            # קבל פקודה מהתור (מחכה אם התור ריק)
                            cmd_data_from_kb = await local_command_queue.get() 
                            
                            # שלח את הפקודה לשרת
                            await websocket.send(json.dumps(cmd_data_from_kb))
                            print(f"Client {client_id} sending command from KB: {cmd_data_from_kb}")
                            
                        except asyncio.CancelledError:
                            print(f"Client {client_id} send_commands_from_queue task cancelled.")
                            break
                        except Exception as e:
                            print(f"Client {client_id} error sending command from queue: {e}")
                            break # יציאה במקרה של שגיאה
                
                send_queue_task = asyncio.create_task(send_commands_from_queue())
                # --- END NEW LOGIC ---

                # המתן עד שמשימת הקבלה או השליחה יסתיימו
                await asyncio.gather(receive_task, send_queue_task) 

        except ConnectionRefusedError:
            print(f"Client {client_id}: Error: Connection refused. Ensure server is running.")
        except Exception as e:
            print(f"Client {client_id}: General error occurred: {e}")
        finally:
            client_game_instance.running = False # וודא שהדגל מכובה כשהלקוח מתנתק
            if kb_producer.is_alive():
                kb_producer.stop()
                kb_producer.join(timeout=1) # ניסיון לסיים את התהליכון


    # הרצת שני הלקוחות במקביל עם הפונקציה המותאמת
    await asyncio.gather(
        connect_and_manage_client(1, (6,4), (4,4), 1), 
        connect_and_manage_client(2, (1,2), (3,2), 2)  
    )

    print("All client tasks finished. Keeping client window alive. Press ESC to close.")
    while True:
        key = cv2.waitKey(1) & 0xFF
        if key == 27: # ESC key
            break
    cv2.destroyAllWindows()


if __name__ == "__main__":
    # Ensure sys.path is correctly configured for client side as well
    # (The lines at the top of client.py should already handle this)
    asyncio.run(main_client())