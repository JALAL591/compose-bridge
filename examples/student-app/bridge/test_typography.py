import asyncio
import json
import websockets


async def send_update(prop, val):
 async with websockets.connect("ws://127.0.0.1:8711") as ws:
 await ws.send(json.dumps({
 "type": "state_update",
 "property": prop,
 "value": str(val),
 }))
 resp = await ws.recv()
 print(f"📤 {prop} = {val}")
 print(f"📥 {resp}")
 print()


async def main():
 print("=== Typography Test ===")
 print()

 print("🔵 Test 1: headlineLarge.fontSize = 48")
 await send_update("AppTypography.headlineLarge.fontSize", "48")
 await asyncio.sleep(2)

 print("🟢 Test 2: headlineLarge.fontSize = 18")
 await send_update("AppTypography.headlineLarge.fontSize", "18")
 await asyncio.sleep(2)

 print("🟡 Test 3: bodyLarge.fontSize = 24")
 await send_update("AppTypography.bodyLarge.fontSize", "24")


if __name__ == "__main__":
 asyncio.run(main())