# RemoteDesk 🚀
### Unattended Remote Desktop for Windows with Mac Web / Chrome Extension Client

A lightweight, self-hosted remote desktop software built in Python and JavaScript. It provides **permanent unattended remote access** to your Windows laptop from your Mac whenever the Windows laptop is powered on and connected to the internet.

---

## 🏗️ How It Works

```
[Windows Laptop (Host)]               [Relay / Web Server]                [Mac (Client)]
  • Auto-starts silently on boot        • Hosted on cloud or local          • Chrome Extension or Browser
  • Ultra-fast screen capture (mss)     • Authenticates secret PIN          • Interactive canvas display
  • Natively injects inputs             • Relays video & input commands     • Mouse & keyboard forwarding
```

---

## 📁 Project Structure

```
remotedesk/
├── server/
│   ├── server.py              # Relay server + static Web Client server
│   ├── static/                # Web UI (index.html, style.css, app.js)
│   └── requirements.txt       # Server dependencies (websockets)
├── agent/
│   ├── agent.py               # Windows Host Agent (screen capture + input injection)
│   ├── install_autostart.bat  # 1-Click unattended auto-start installer for Windows
│   ├── stop_agent.bat         # Helper to stop background agent
│   ├── build_exe.bat          # 1-Click PyInstaller compiler to generate standalone .exe
│   └── requirements.txt       # Windows dependencies (mss, Pillow, pyautogui, websockets)
└── chrome_extension/
    ├── manifest.json          # Manifest V3 configuration
    ├── popup.html / popup.js  # Quick-connect browser popup
    ├── viewer.html / js / css # Dedicated remote desktop tab
    └── icons/                 # Extension icons
```

---

## ⚡ Quick Start Guide

### Step 1: Start the Relay Server
You can run this on any server accessible over the internet (e.g. free Render, Railway, a $3 VPS, or using a free Cloudflare Tunnel).

```bash
cd remotedesk/server
python3 server.py
```
* Default port: `8000`
* Default PIN: `123456` (Change via `export REMOTEDESK_PIN="your_secret_pin"`)

---

### Step 2: One-Time Setup on Windows Laptop
Copy the `remotedesk/agent` folder to your Windows laptop.

1. Open `agent.py` and set your server's public address in `RELAY_URL` (or pass it via CLI):
   ```python
   RELAY_URL = "ws://your-server-domain:8000"
   PIN = "your_secret_pin"
   ```
2. **Right-click `install_autostart.bat` and run it.**
   * It installs the required libraries (`mss`, `pyautogui`, `pillow`, `websockets`).
   * It registers the agent to launch invisibly in the background on system startup using `pythonw.exe`.
   * **That's it!** From now on, whenever the laptop is turned on and connected to Wi-Fi, it will automatically connect to your relay server. Your brother does not need to accept any prompt or click anything.

---

### Step 3: Access from Your Mac

You have two easy ways to access the Windows laptop:

#### Method A: Directly via Web Browser
Open your browser (Chrome or Safari) on your Mac and visit:
```
http://your-server-ip:8000
```
Enter your PIN and click **Connect**.

#### Method B: As a Chrome Extension
1. Open Google Chrome on your Mac.
2. Go to `chrome://extensions/`.
3. Enable **Developer mode** in the top-right corner.
4. Click **Load unpacked** and select the `remotedesk/chrome_extension` folder.
5. Click the RemoteDesk extension icon in your Chrome toolbar, enter your Server URL and PIN, and click **Launch Remote Control**!

---

## ⚙️ Features & Controls

* **Unattended Access**: Starts on Windows boot silently without popping up any command prompt window.
* **Smart Throttling**: When no Mac client is connected, the agent suspends screen capture to consume **0% CPU**.
* **Adaptive Quality**: Toggle between *Low* (Speed), *Medium* (Balanced), and *High* (Clarity) dynamically from the top bar.
* **Native Keyboard & Mouse**: Supports right-clicks, mouse wheel scrolling, drag-and-drop, and special shortcuts (`⊞ Windows Key`, `Alt+Tab`, `Escape`).
* **Auto-Reconnect**: If Wi-Fi briefly drops or the laptop goes to sleep and wakes up, it re-establishes the connection immediately.

