#!/usr/bin/env python3
"""
RemoteDesk Relay & Web Server
------------------------------
Handles:
1. Static web app serving (Mac browser / Web client).
2. Secure WebSocket relay connecting the remote Windows Host and Mac Client.
3. Unattended access authentication with Device ID & Secret PIN.
"""

import asyncio
import json
import mimetypes
import os
import sys
import time
from typing import Dict, Optional, Set
import websockets
from websockets.asyncio.server import ServerConnection, serve
from websockets.http11 import Response

# Default Configuration (can be overridden via environment variables)
HOST = os.environ.get("REMOTEDESK_HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", os.environ.get("REMOTEDESK_PORT", "8000")))
DEFAULT_PIN = os.environ.get("REMOTEDESK_PIN", "123456")  # Change this to your secret PIN!

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


class DeviceSession:
    def __init__(self, device_id: str):
        self.device_id = device_id
        self.host_ws: Optional[ServerConnection] = None
        self.clients: Set[ServerConnection] = set()
        self.screen_info: dict = {"width": 1920, "height": 1080}
        self.last_active: float = time.time()


# Active registered devices: device_id -> DeviceSession
DEVICES: Dict[str, DeviceSession] = {}


def get_or_create_device(device_id: str) -> DeviceSession:
    if device_id not in DEVICES:
        DEVICES[device_id] = DeviceSession(device_id)
    return DEVICES[device_id]


def serve_static_file(connection: ServerConnection, path: str) -> Optional[Response]:
    """Serves static files (HTML, JS, CSS, icons) for the Web Client."""
    clean_path = path.split("?")[0].lstrip("/")
    if not clean_path or clean_path == "":
        clean_path = "index.html"

    file_path = os.path.normpath(os.path.join(STATIC_DIR, clean_path))
    # Security: prevent path traversal outside static folder
    if not file_path.startswith(STATIC_DIR):
        return connection.respond(403, "Forbidden", [("Content-Type", "text/plain")], b"Access Denied")

    if not os.path.isfile(file_path):
        return connection.respond(404, "Not Found", [("Content-Type", "text/plain")], b"404 Not Found")

    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = "application/octet-stream"
    if mime_type.startswith("text/") or mime_type in ["application/javascript", "application/json"]:
        mime_type += "; charset=utf-8"

    try:
        with open(file_path, "rb") as f:
            content = f.read()
        return connection.respond(
            200,
            "OK",
            [
                ("Content-Type", mime_type),
                ("Content-Length", str(len(content))),
                ("Cache-Control", "no-cache"),
            ],
            content,
        )
    except Exception as e:
        return connection.respond(500, "Internal Server Error", [("Content-Type", "text/plain")], str(e).encode())


def http_handler(connection: ServerConnection, request) -> Optional[Response]:
    """Intercepts HTTP requests before WebSocket upgrade."""
    path = request.path.split("?")[0]
    # If it's a websocket path, allow upgrade
    if path in ["/ws", "/ws/host", "/ws/client"]:
        return None
    # Otherwise serve static files
    return serve_static_file(connection, request.path)


async def host_handler(websocket: ServerConnection, device_id: str, pin: str):
    """Handles connection from the remote Windows Host Agent."""
    if pin != DEFAULT_PIN:
        print(f"[AUTH FAILED] Host attempted connection with invalid PIN for device '{device_id}'")
        await websocket.close(4001, "Invalid PIN")
        return

    session = get_or_create_device(device_id)
    if session.host_ws and session.host_ws != websocket:
        try:
            await session.host_ws.close(4002, "New host connected")
        except Exception:
            pass

    session.host_ws = websocket
    session.last_active = time.time()
    print(f"[HOST CONNECTED] Windows Host '{device_id}' connected successfully.")

    # Notify any already connected Mac clients that host is online
    for client in list(session.clients):
        try:
            await client.send(json.dumps({
                "type": "host_status",
                "online": True,
                "screen": session.screen_info
            }))
        except Exception:
            pass

    try:
        async for message in websocket:
            session.last_active = time.time()
            if isinstance(message, bytes):
                # Binary message: Screen frame (JPEG) -> broadcast to all viewing Mac clients
                for client in list(session.clients):
                    try:
                        await client.send(message)
                    except Exception:
                        session.clients.discard(client)
            else:
                # Text/JSON message: Metadata, screen resolution updates, ping/pong
                try:
                    data = json.loads(message)
                    msg_type = data.get("type")
                    if msg_type == "screen_info":
                        session.screen_info = data.get("screen", session.screen_info)
                        # Forward screen info to clients
                        for client in list(session.clients):
                            await client.send(message)
                    elif msg_type == "pong":
                        pass
                except json.JSONDecodeError:
                    pass
    except websockets.ConnectionClosed:
        pass
    finally:
        if session.host_ws == websocket:
            session.host_ws = None
        print(f"[HOST DISCONNECTED] Windows Host '{device_id}' disconnected.")
        # Notify clients that host went offline
        for client in list(session.clients):
            try:
                await client.send(json.dumps({
                    "type": "host_status",
                    "online": False,
                    "message": "Remote host disconnected"
                }))
            except Exception:
                pass


async def client_handler(websocket: ServerConnection, device_id: str, pin: str):
    """Handles connection from the Mac Client / Web Browser / Extension."""
    if pin != DEFAULT_PIN:
        print(f"[AUTH FAILED] Client attempted connection with invalid PIN for device '{device_id}'")
        await websocket.close(4001, "Invalid PIN")
        return

    session = get_or_create_device(device_id)
    session.clients.add(websocket)
    print(f"[CLIENT CONNECTED] Mac Client connected for device '{device_id}'. Active viewers: {len(session.clients)}")

    # Send current host status
    is_online = session.host_ws is not None
    await websocket.send(json.dumps({
        "type": "host_status",
        "online": is_online,
        "screen": session.screen_info,
        "message": "Connected to relay. Windows laptop is ONLINE." if is_online else "Waiting for Windows laptop to come online..."
    }))

    try:
        async for message in websocket:
            if not isinstance(message, str):
                continue
            # Forward input events (mouse, keyboard, quality commands) from client to Windows host
            if session.host_ws is not None:
                try:
                    await session.host_ws.send(message)
                except Exception:
                    pass
    except websockets.ConnectionClosed:
        pass
    finally:
        session.clients.discard(websocket)
        print(f"[CLIENT DISCONNECTED] Mac Client disconnected. Remaining viewers: {len(session.clients)}")


async def ws_router(websocket: ServerConnection):
    """Routes incoming WebSocket connections to either host or client handler."""
    path = websocket.request.path
    url_path = path.split("?")[0]
    
    # Parse query parameters
    query_str = path.split("?")[1] if "?" in path else ""
    params = dict(q.split("=", 1) for q in query_str.split("&") if "=" in q)
    
    device_id = params.get("id", "default-laptop")
    pin = params.get("pin", "")

    if url_path == "/ws/host":
        await host_handler(websocket, device_id, pin)
    elif url_path == "/ws/client":
        await client_handler(websocket, device_id, pin)
    else:
        await websocket.close(4004, "Invalid route")


async def main():
    print("=" * 60)
    print("  🚀 RemoteDesk Relay & Web Server")
    print(f"  • Listening on: http://{HOST}:{PORT}")
    print(f"  • Secret PIN:   {DEFAULT_PIN} (set REMOTEDESK_PIN env var to change)")
    print(f"  • Web Client:   http://localhost:{PORT}")
    print("=" * 60)

    async with serve(
        ws_router,
        HOST,
        PORT,
        process_request=http_handler,
        ping_interval=15,
        ping_timeout=30,
        max_size=10 * 1024 * 1024,  # 10 MB max frame size
    ):
        await asyncio.get_running_loop().create_future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped.")

