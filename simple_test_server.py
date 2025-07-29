import asyncio
import websockets
import sys
import os
import json # וודא ש-json מיובא גם כאן


async def simple_handler(websocket, path=None): 
    """Handler for the simple test server."""
    print(f"לקוח חדש התחבר לשרת הבדיקה.")
    try:
        if path: 
            print(f"חיבור בנתיב: {path}")
        async for message in websocket:
            print(f"שרת הבדיקה קיבל: {message}")
            # !!! תיקון כאן: שלח תגובה בפורמט JSON !!!
            response_data = {"status": "success", "message": f"השרת הפשוט קיבל: {message}"}
            await websocket.send(json.dumps(response_data))
            print(f"שרת הבדיקה שלח: {response_data}")
    except websockets.exceptions.ConnectionClosedOK:
        print("חיבור לקוח לשרת הבדיקה נסגר.")
    except Exception as e:
        print(f"שגיאה בשרת הבדיקה: {e}")

async def main_test_server():
    """Main function to run the simple test server."""
    try:
        print("מנסה להפעיל את שרת הבדיקה הפשוט בפורט 8765...")
        async with websockets.serve(simple_handler, "localhost", 8765):
            print("--- שרת הבדיקה הפשוט פועל ומאזין לחיבורים בפורט 8765! ---")
            await asyncio.sleep(float('inf')) 
    except OSError as e:
        print(f"!!! שגיאה בהפעלת שרת הבדיקה (ייתכן שהפורט תפוס או בעיית רשת): {e} !!!")
    except Exception as e:
        print(f"!!! שגיאה קריטית כללית בהפעלת שרת הבדיקה: {e} !!!")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main_test_server())