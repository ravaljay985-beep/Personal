#!/usr/bin/env python3
"""
RemoteDesk Windows Host Agent
------------------------------
Runs silently on the remote Windows machine.
1. Connects to the relay server via WebSocket.
2. Captures desktop frames at target FPS with JPEG compression.
3. Receives remote mouse & keyboard commands and injects them natively into Windows.
4. Automatically reconnects if Wi-Fi drops or the machine wakes from sleep.
"""

import asyncio
import io
import json
import os
import sys
import time

# Check and import required dependencies
try:
    import mss
    HAS_MSS = True
except ImportError:
    HAS_MSS = False

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import pyautogui
    pyautogui.PAUSE = 0  # CRITICAL: Disable 0.1s default delay for buttery-smooth mouse movement
    pyautogui.FAILSAFE = False  # Disable failsafe corner abort for remote sessions
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

try:
    import websockets
    from websockets.asyncio.client import connect
except ImportError:
    print("[ERROR] 'websockets' library is required. Run: pip install websockets")
    sys.exit(1)


# Configuration (Can be passed via CLI args or environment variables)
RELAY_URL = os.environ.get("REMOTEDESK_RELAY", "ws://localhost:8000")
DEVICE_ID = os.environ.get("REMOTEDESK_ID", "windows-laptop")
PIN = os.environ.get("REMOTEDESK_PIN", "123456")

# Dynamic Stream Settings
stream_config = {
    "quality": 55,       # JPEG quality (1-100)
    "target_fps": 25,     # Target frames per second
    "scale": 0.85,       # Downscale factor (1.0 = native, 0.75 = 75% resolution)
    "has_client": False  # Only stream frames when a client is connected
}

# Key mapping from browser JavaScript key names to PyAutoGUI key names
KEY_MAP = {
    "Enter": "enter",
    "Backspace": "backspace",
    "Tab": "tab",
    "Escape": "esc",
    "Control": "ctrl",
    "Shift": "shift",
    "Alt": "alt",
    "Meta": "win",
    "ArrowUp": "up",
    "ArrowDown": "down",
    "ArrowLeft": "left",
    "ArrowRight": "right",
    "Delete": "delete",
    "Home": "home",
    "End": "end",
    "PageUp": "pageup",
    "PageDown": "pagedown",
    "CapsLock": "capslock",
}


def get_screen_resolution():
    """Returns actual primary display width and height."""
    if HAS_PYAUTOGUI:
        return pyautogui.size()
    elif HAS_MSS:
        with mss.mss() as sct:
            mon = sct.monitors[1]
            return mon["width"], mon["height"]
    return 1920, 1080


def capture_screen_jpeg(sct, screen_width, screen_height):
    """Fast screen capture + JPEG compression."""
    quality = stream_config["quality"]
    scale = stream_config["scale"]

    if HAS_MSS:
        monitor = sct.monitors[1]  # Primary monitor
        sct_img = sct.grab(monitor)
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
    else:
        from PIL import ImageGrab
        img = ImageGrab.grab()

    # Scale resolution if requested to save bandwidth
    if scale < 0.99:
        new_w = int(img.width * scale)
        new_h = int(img.height * scale)
        img = img.resize((new_w, new_h), Image.Resampling.BILINEAR)

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=quality, optimize=False)
    return buffer.getvalue()


def handle_input_event(data: dict, screen_width: int, screen_height: int):
    """Executes mouse and keyboard events on Windows."""
    if not HAS_PYAUTOGUI:
        return

    evt_type = data.get("type")

    try:
        if evt_type == "mouse_move":
            norm_x = data.get("x", 0)
            norm_y = data.get("y", 0)
            target_x = int(norm_x * screen_width)
            target_y = int(norm_y * screen_height)
            pyautogui.moveTo(target_x, target_y)

        elif evt_type == "mouse_down":
            norm_x = data.get("x", 0)
            norm_y = data.get("y", 0)
            target_x = int(norm_x * screen_width)
            target_y = int(norm_y * screen_height)
            button = data.get("button", "left")
            pyautogui.mouseDown(target_x, target_y, button=button)

        elif evt_type == "mouse_up":
            norm_x = data.get("x", 0)
            norm_y = data.get("y", 0)
            target_x = int(norm_x * screen_width)
            target_y = int(norm_y * screen_height)
            button = data.get("button", "left")
            pyautogui.mouseUp(target_x, target_y, button=button)

        elif evt_type == "mouse_wheel":
            # Windows wheel clicks (positive is up, negative is down)
            dy = data.get("dy", 0)
            clicks = -int(dy / 25)
            if clicks != 0:
                pyautogui.scroll(clicks)

        elif evt_type == "key_down":
            key_name = data.get("key", "")
            mapped = KEY_MAP.get(key_name, key_name.lower())
            pyautogui.keyDown(mapped)

        elif evt_type == "key_up":
            key_name = data.get("key", "")
            mapped = KEY_MAP.get(key_name, key_name.lower())
            pyautogui.keyUp(mapped)

        elif evt_type == "shortcut":
            shortcut = data.get("shortcut")
            if shortcut == "win":
                pyautogui.press("win")
            elif shortcut == "alt_tab":
                pyautogui.hotkey("alt", "tab")
            elif shortcut == "esc":
                pyautogui.press("esc")

        elif evt_type == "config":
            # Adapt streaming parameters dynamically from client
            q_mode = data.get("quality")
            if q_mode == "low":
                stream_config["quality"] = 40
                stream_config["scale"] = 0.65
            elif q_mode == "medium":
                stream_config["quality"] = 60
                stream_config["scale"] = 0.85
            elif q_mode == "high":
                stream_config["quality"] = 80
                stream_config["scale"] = 1.0

            fps = data.get("fps")
            if fps and isinstance(fps, int) and 5 <= fps <= 60:
                stream_config["target_fps"] = fps
            print(f"[CONFIG] Updated: Quality={stream_config['quality']}, Scale={stream_config['scale']}, FPS={stream_config['target_fps']}")

    except Exception as e:
        print(f"[INPUT ERROR] Failed handling {evt_type}: {e}")


async def receive_loop(ws, screen_w, screen_h):
    """Listens for input events and control messages from the server."""
    async for message in ws:
        if isinstance(message, str):
            try:
                data = json.loads(message)
                msg_type = data.get("type")
                if msg_type == "ping":
                    await ws.send(json.dumps({"type": "pong"}))
                else:
                    handle_input_event(data, screen_w, screen_h)
            except Exception as e:
                print(f"[RECV ERROR] {e}")


async def stream_screen_loop(ws, screen_w, screen_h):
    """Continuously captures and transmits desktop frames."""
    sct = mss.mss() if HAS_MSS else None

    try:
        while True:
            t_start = time.perf_counter()

            # Capture frame
            jpeg_bytes = capture_screen_jpeg(sct, screen_w, screen_h)
            await ws.send(jpeg_bytes)

            # Frame rate pacing
            target_dt = 1.0 / stream_config["target_fps"]
            elapsed = time.perf_counter() - t_start
            sleep_time = max(0.005, target_dt - elapsed)
            await asyncio.sleep(sleep_time)
    finally:
        if sct:
            sct.close()


async def run_agent():
    """Main agent loop with automatic reconnect on failure or reboot."""
    screen_w, screen_h = get_screen_resolution()
    print("=" * 60)
    print("  💻 RemoteDesk Windows Host Agent")
    print(f"  • Screen Resolution: {screen_w}x{screen_h}")
    print(f"  • Relay Server:      {RELAY_URL}")
    print(f"  • Device ID:         {DEVICE_ID}")
    print("=" * 60)

    # Convert http(s) to ws(s) if provided
    base_url = RELAY_URL.replace("http://", "ws://").replace("https://", "wss://")
    ws_url = f"{base_url}/ws/host?id={DEVICE_ID}&pin={PIN}"

    retry_delay = 2

    while True:
        try:
            print(f"[CONNECTING] Dialing relay server: {base_url}...")
            async with connect(
                ws_url,
                ping_interval=15,
                ping_timeout=30,
                max_size=10 * 1024 * 1024
            ) as ws:
                print(f"[CONNECTED] RemoteDesk agent is ONLINE and ready for unattended access.")
                retry_delay = 2  # Reset backoff on successful connect

                # Send initial display resolution metadata
                await ws.send(json.dumps({
                    "type": "screen_info",
                    "screen": {"width": screen_w, "height": screen_h}
                }))

                # Run capture loop and input receiver concurrently
                stream_task = asyncio.create_task(stream_screen_loop(ws, screen_w, screen_h))
                recv_task = asyncio.create_task(receive_loop(ws, screen_w, screen_h))

                done, pending = await asyncio.wait(
                    [stream_task, recv_task],
                    return_when=asyncio.FIRST_EXCEPTION
                )

                for task in pending:
                    task.cancel()

        except websockets.exceptions.ConnectionClosed as e:
            print(f"[DISCONNECTED] Connection closed ({e}). Reconnecting in {retry_delay}s...")
        except Exception as e:
            print(f"[ERROR] Connection failure: {e}. Reconnecting in {retry_delay}s...")

        await asyncio.sleep(retry_delay)
        retry_delay = min(retry_delay * 1.5, 30)  # Exponential backoff capped at 30 seconds


if __name__ == "__main__":
    # Parse CLI flags: python agent.py --relay ws://... --id ... --pin ...
    args = sys.argv[1:]
    for i in range(len(args)):
        if args[i] == "--relay" and i + 1 < len(args):
            RELAY_URL = args[i + 1]
        elif args[i] == "--id" and i + 1 < len(args):
            DEVICE_ID = args[i + 1]
        elif args[i] == "--pin" and i + 1 < len(args):
            PIN = args[i + 1]

    try:
        asyncio.run(run_agent())
    except KeyboardInterrupt:
        print("\nAgent stopped by user.")

