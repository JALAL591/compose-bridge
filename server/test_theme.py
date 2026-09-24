import asyncio
import json
import websockets


async def test():
 async with websockets.connect("ws://127.0.0.1:8711") as ws:
 # 1) 
 await ws.send(json.dumps({"type": "theme_tokens"}))
 resp = json.loads(await ws.recv())
 print(f"Total tokens: {len(resp['tokens'])}")
 print()

 # 2) 
 for key in list(resp["tokens"].keys())[:8]:
 info = resp["tokens"][key]
 print(f" {key:40} → {info['hex']}")
 print()

 # 3) 
 print("Categories:")
 for cat, tokens in resp["categories"].items():
 print(f" {cat}: {len(tokens)} tokens")
 print()

 # 4) token 
 test_colors = ["0xFFEAB308", "0xFF010D2A", "0xFF3B82F6"]

 for color in test_colors:
 await ws.send(json.dumps({
 "type": "identify_token",
 "hex": color,
 }))
 resp = json.loads(await ws.recv())
 token = resp["token"] or "(not found)"
 print(f" {color} → {token}")


if __name__ == "__main__":
 asyncio.run(test())