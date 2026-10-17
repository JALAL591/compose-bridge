import json
import asyncio
import websockets
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


async def test():
    async with websockets.connect('ws://127.0.0.1:8711') as ws:
        await ws.send(json.dumps({'type': 'auth', 'token': 'test-token-local-dev'}))
        await ws.recv()

        await ws.send(json.dumps({'type': 'agent_start'}))
        await ws.recv()

        print('')
        print('=' * 60)
        print('AGENT STARTED -- 20 seconds window')
        print('=' * 60)
        print('')
        print('On your phone:')
        print('  1. Open Design Mode (wrench icon)')
        print('  2. Tap HeroCard')
        print('  3. Move Slider 3 times')
        print('')
        print('Watch Queue counter go 1 -> 2 -> 3')
        print('')

        await asyncio.sleep(20)

        await ws.send(json.dumps({'type': 'agent_end'}))
        await ws.recv()

        print('')
        print('=' * 60)
        print('AGENT ENDED')
        print('=' * 60)
        print('')
        print('On your phone NOW:')
        print('  1. Move Slider ONE MORE TIME (direct edit)')
        print('  2. Queue should drop to 0')
        print('  3. Tap Sync button')
        print('')


if __name__ == '__main__':
    asyncio.run(test())
