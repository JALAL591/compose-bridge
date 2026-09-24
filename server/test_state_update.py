import asyncio
import json
import websockets


async def send_update(property_name, value):
 uri = "ws://127.0.0.1:8711"
 async with websockets.connect(uri) as ws:
 message = {
 "type": "state_update",
 "property": property_name,
 "value": str(value)
 }
 await ws.send(json.dumps(message))
 print(f"📤 Sent: {property_name} = {value}")

 response = await ws.recv()
 print(f"📥 Response: {response}")


async def main():
 print("=== BridgeState WebSocket Test ===")
 print()

 # Test 1: padding
 print("🔵 Test 1: cardPadding 16 → 80")
 await send_update("cardPadding", "80")
 await asyncio.sleep(3)

 # Test 2: color
 print()
 print("🔴 Test 2: cardBackgroundColor → red")
 await send_update("cardBackgroundColor", "#E53935")
 await asyncio.sleep(3)

 # Test 3: title
 print()
 print("📝 Test 3: titleText → 'Hello Bridge!'")
 await send_update("titleText", "Hello Bridge!")
 await asyncio.sleep(3)

 # Test 4: reset
 print()
 print("♻️ Test 4: reset all")
 async with websockets.connect("ws://127.0.0.1:8711") as ws:
 await ws.send(json.dumps({"type": "reset_state"}))
 print(f"📥 Response: {await ws.recv()}")

 print()
 print("✅ Tests complete!")


if __name__ == "__main__":
 asyncio.run(main())