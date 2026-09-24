# ComposeBridge — Python Bridge

 Python Apply 
 WebSocket Kotlin .

## 

```bash
cd bridge
pip install -r requirements.txt
```

## 

```bash
python server.py
```

 : `ws://0.0.0.0:8711`

## 

From device Python:
```json
{
 "type": "edit_request",
 "payload": {
 "file": "HomeScreenForTest.kt",
 "utf16Offset": 987,
 "utf16Length": 461,
 "composable": "Card",
 "property": "padding",
 "currentValue": "16.dp",
 "newValue": "24.dp",
 "requestId": "uuid"
 }
}
```

 Python :
```json
{
 "type": "edit_response",
 "payload": {
 "requestId": "uuid",
 "status": "success",
 "oldValue": "16.dp",
 "newValue": "24.dp"
 }
}
```

## 

✅ Phase 1: WebSocket server ( )

⏳ Phase 2: Tree-sitter integration

⏳ Phase 3: Offset → AST

⏳ Phase 4: Property Finder

⏳ Phase 5: Surgical Edit