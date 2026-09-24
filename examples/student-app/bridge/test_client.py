# test_client.py
import asyncio
import json
import websockets


async def test():
 uri = "ws://127.0.0.1:8711"
 print(f"🔌 Connecting to {uri}...")
 print()

 async with websockets.connect(uri) as ws:
 # 1) Handshake
 print("📤 Sending: hello")
 await ws.send(json.dumps({"type": "hello"}))
 response = await ws.recv()
 print(f"📥 Received: {response}")
 print()

 # 2) Edit request
 print("📤 Sending: edit_request")
 await ws.send(json.dumps({
 "type": "edit_request",
 "payload": {
 "file": "HomeScreenForTest.kt",
 "utf16Offset": 987,
 "utf16Length": 461,
 "composable": "Card",
 "property": "padding",
 "currentValue": "16.dp",
 "newValue": "24.dp",
 "requestId": "test-001"
 }
 }))
 response = await ws.recv()
 print(f"📥 Received: {response}")
 print()
 print("✅ Test completed successfully!")


if __name__ == "__main__":
 asyncio.run(test())