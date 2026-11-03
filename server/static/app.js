/**
 * RemoteDesk Client Application
 * Connects to the Relay Server, renders screen stream, and forwards user inputs.
 */

// State configuration
const state = {
  relayUrl: localStorage.getItem("remotedesk_relay") || "",
  deviceId: localStorage.getItem("remotedesk_device_id") || "windows-laptop",
  pin: localStorage.getItem("remotedesk_pin") || "123456",
  quality: localStorage.getItem("remotedesk_quality") || "medium",
  fps: parseInt(localStorage.getItem("remotedesk_fps") || "25", 10),
  hostOnline: false,
  screen: { width: 1920, height: 1080 },
  ws: null,
  reconnectTimer: null,
  pingTimer: null,
  lastPingTime: 0,
  ping: 0,
  frameCount: 0,
  lastFpsCalc: performance.now(),
  fpsVal: 0,
};

// DOM Elements
const canvas = document.getElementById("screenCanvas");
const ctx = canvas.getContext("2d", { alpha: false });
const statusBadge = document.getElementById("statusBadge");
const statusText = document.getElementById("statusText");
const pingVal = document.getElementById("pingVal");
const fpsVal = document.getElementById("fpsVal");
const displayDeviceId = document.getElementById("displayDeviceId");
const qualitySelect = document.getElementById("qualitySelect");
const fpsSelect = document.getElementById("fpsSelect");
const overlay = document.getElementById("offlineOverlay");
const overlayTitle = document.getElementById("overlayTitle");
const overlayMessage = document.getElementById("overlayMessage");
const overlayDeviceId = document.getElementById("overlayDeviceId");
const settingsModal = document.getElementById("settingsModal");
const inputRelayUrl = document.getElementById("inputRelayUrl");
const inputDeviceId = document.getElementById("inputDeviceId");
const inputPin = document.getElementById("inputPin");

// Initialize UI
displayDeviceId.textContent = state.deviceId;
overlayDeviceId.textContent = state.deviceId;
qualitySelect.value = state.quality;
fpsSelect.value = state.fps.toString();
inputRelayUrl.value = state.relayUrl;
inputDeviceId.value = state.deviceId;
inputPin.value = state.pin;

function getWebSocketUrl() {
  let base = state.relayUrl.trim();
  if (!base) {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    base = `${proto}//${window.location.host}`;
  } else {
    base = base.replace(/^http:/, "ws:").replace(/^https:/, "wss:");
    if (!base.startsWith("ws://") && !base.startsWith("wss://")) {
      base = "wss://" + base;
    }
  }
  return `${base}/ws/client?id=${encodeURIComponent(state.deviceId)}&pin=${encodeURIComponent(state.pin)}`;
}

function updateStatus(type, text) {
  statusBadge.className = `badge ${type}`;
  statusText.textContent = text;
}

function connectWebSocket() {
  if (state.ws) {
    try {
      state.ws.close();
    } catch (e) {}
  }

  updateStatus("connecting", "Connecting...");
  const wsUrl = getWebSocketUrl();
  console.log("[RemoteDesk] Connecting to:", wsUrl);

  try {
    state.ws = new WebSocket(wsUrl);
  } catch (err) {
    console.error("WebSocket init error:", err);
    scheduleReconnect();
    return;
  }

  state.ws.binaryType = "blob";

  state.ws.onopen = () => {
    console.log("[RemoteDesk] Connected to relay server.");
    updateStatus("connecting", "Connected to relay");
    startPing();
    sendConfig();
  };

  state.ws.onmessage = async (event) => {
    if (typeof event.data === "string") {
      try {
        const msg = JSON.parse(event.data);
        handleJsonMessage(msg);
      } catch (e) {
        console.error("JSON parse error", e);
      }
    } else if (event.data instanceof Blob) {
      // Binary screen frame received
      handleScreenFrame(event.data);
    }
  };

  state.ws.onclose = (event) => {
    console.warn("[RemoteDesk] WebSocket closed:", event.code, event.reason);
    stopPing();
    state.hostOnline = false;
    if (event.code === 4001) {
      updateStatus("offline", "Auth Failed (Bad PIN)");
      showOverlay("Authentication Failed", "The PIN / Password was incorrect. Please check your settings.");
    } else {
      updateStatus("offline", "Disconnected");
      showOverlay("Relay Disconnected", "Connecting back to relay server...");
      scheduleReconnect();
    }
  };

  state.ws.onerror = (err) => {
    console.error("[RemoteDesk] WebSocket error:", err);
  };
}

function scheduleReconnect() {
  if (state.reconnectTimer) return;
  state.reconnectTimer = setTimeout(() => {
    state.reconnectTimer = null;
    connectWebSocket();
  }, 2500);
}

function startPing() {
  stopPing();
  state.pingTimer = setInterval(() => {
    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
      state.lastPingTime = performance.now();
      state.ws.send(JSON.stringify({ type: "ping" }));
    }
  }, 3000);
}

function stopPing() {
  if (state.pingTimer) {
    clearInterval(state.pingTimer);
    state.pingTimer = null;
  }
}

function sendConfig() {
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) return;
  state.ws.send(JSON.stringify({
    type: "config",
    quality: state.quality,
    fps: state.fps
  }));
}

function showOverlay(title, message) {
  overlayTitle.textContent = title;
  overlayMessage.textContent = message;
  overlay.classList.remove("hidden");
}

function hideOverlay() {
  overlay.classList.add("hidden");
}

function handleJsonMessage(msg) {
  if (msg.type === "host_status") {
    state.hostOnline = msg.online;
    if (msg.screen) {
      state.screen = msg.screen;
      canvas.width = msg.screen.width;
      canvas.height = msg.screen.height;
    }

    if (msg.online) {
      updateStatus("online", "Online");
      hideOverlay();
    } else {
      updateStatus("connecting", "Laptop Offline");
      showOverlay("Waiting for Windows Laptop...", "The laptop is currently offline or the agent is not running yet.");
    }
  } else if (msg.type === "pong") {
    state.ping = Math.round(performance.now() - state.lastPingTime);
    pingVal.textContent = state.ping;
  } else if (msg.type === "screen_info") {
    if (msg.screen) {
      state.screen = msg.screen;
      canvas.width = msg.screen.width;
      canvas.height = msg.screen.height;
    }
  }
}

async function handleScreenFrame(blob) {
  try {
    const imgBitmap = await createImageBitmap(blob);
    ctx.drawImage(imgBitmap, 0, 0, canvas.width, canvas.height);
    imgBitmap.close();

    // FPS counter calculation
    state.frameCount++;
    const now = performance.now();
    if (now - state.lastFpsCalc >= 1000) {
      state.fpsVal = state.frameCount;
      fpsVal.textContent = state.fpsVal;
      state.frameCount = 0;
      state.lastFpsCalc = now;
    }
  } catch (err) {
    console.error("Frame render error:", err);
  }
}

// =================== Input Forwarding ===================

function getNormalizedCoords(e) {
  const rect = canvas.getBoundingClientRect();
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;

  // Normalized coordinate 0.0 to 1.0
  const normX = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
  const normY = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));

  return {
    normX: parseFloat(normX.toFixed(4)),
    normY: parseFloat(normY.toFixed(4)),
  };
}

let lastMouseMoveTime = 0;
canvas.addEventListener("mousemove", (e) => {
  if (!state.hostOnline || !state.ws || state.ws.readyState !== WebSocket.OPEN) return;
  const now = performance.now();
  if (now - lastMouseMoveTime < 25) return; // Cap mouse moves to 40Hz to avoid network flooding
  lastMouseMoveTime = now;

  const { normX, normY } = getNormalizedCoords(e);
  state.ws.send(JSON.stringify({
    type: "mouse_move",
    x: normX,
    y: normY
  }));
});

canvas.addEventListener("mousedown", (e) => {
  if (!state.hostOnline || !state.ws || state.ws.readyState !== WebSocket.OPEN) return;
  canvas.focus();
  const { normX, normY } = getNormalizedCoords(e);
  const buttonMap = ["left", "middle", "right"];
  const button = buttonMap[e.button] || "left";

  state.ws.send(JSON.stringify({
    type: "mouse_down",
    button: button,
    x: normX,
    y: normY
  }));
});

canvas.addEventListener("mouseup", (e) => {
  if (!state.hostOnline || !state.ws || state.ws.readyState !== WebSocket.OPEN) return;
  const { normX, normY } = getNormalizedCoords(e);
  const buttonMap = ["left", "middle", "right"];
  const button = buttonMap[e.button] || "left";

  state.ws.send(JSON.stringify({
    type: "mouse_up",
    button: button,
    x: normX,
    y: normY
  }));
});

canvas.addEventListener("contextmenu", (e) => {
  e.preventDefault(); // Prevent browser right-click context menu
});

canvas.addEventListener("wheel", (e) => {
  if (!state.hostOnline || !state.ws || state.ws.readyState !== WebSocket.OPEN) return;
  e.preventDefault();
  state.ws.send(JSON.stringify({
    type: "mouse_wheel",
    dx: e.deltaX,
    dy: e.deltaY
  }));
}, { passive: false });

// Keyboard events
window.addEventListener("keydown", (e) => {
  // Ignore if user is typing in a modal input
  if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;
  if (!state.hostOnline || !state.ws || state.ws.readyState !== WebSocket.OPEN) return;

  // Prevent default browser shortcuts when controlling remote machine
  if (["Tab", "Alt", "F1", "F3", "F5"].includes(e.key) || (e.ctrlKey && ["c", "v", "x", "a", "w", "t"].includes(e.key.toLowerCase()))) {
    e.preventDefault();
  }

  state.ws.send(JSON.stringify({
    type: "key_down",
    key: e.key,
    code: e.code,
    ctrl: e.ctrlKey,
    alt: e.altKey,
    shift: e.shiftKey,
    meta: e.metaKey
  }));
});

window.addEventListener("keyup", (e) => {
  if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;
  if (!state.hostOnline || !state.ws || state.ws.readyState !== WebSocket.OPEN) return;

  state.ws.send(JSON.stringify({
    type: "key_up",
    key: e.key,
    code: e.code
  }));
});

// Quick Keys
function sendShortcut(shortcutType) {
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) return;
  state.ws.send(JSON.stringify({
    type: "shortcut",
    shortcut: shortcutType
  }));
}

let cursorHidden = false;
const btnToggleCursor = document.getElementById("btnToggleCursor");
if (btnToggleCursor) {
  btnToggleCursor.addEventListener("click", () => {
    cursorHidden = !cursorHidden;
    canvas.style.cursor = cursorHidden ? "none" : "crosshair";
    btnToggleCursor.textContent = cursorHidden ? "👁️ Show Arrow" : "👁️ Hide Arrow";
  });
}

document.getElementById("btnWinKey").addEventListener("click", () => sendShortcut("win"));
document.getElementById("btnAltTab").addEventListener("click", () => sendShortcut("alt_tab"));
document.getElementById("btnEsc").addEventListener("click", () => sendShortcut("esc"));

// Fullscreen
document.getElementById("btnFullscreen").addEventListener("click", () => {
  const elem = document.getElementById("viewerContainer");
  if (!document.fullscreenElement) {
    elem.requestFullscreen().catch(err => alert("Fullscreen error: " + err.message));
  } else {
    document.exitFullscreen();
  }
});

// Settings & Controls
qualitySelect.addEventListener("change", (e) => {
  state.quality = e.target.value;
  localStorage.setItem("remotedesk_quality", state.quality);
  sendConfig();
});

fpsSelect.addEventListener("change", (e) => {
  state.fps = parseInt(e.target.value, 10);
  localStorage.setItem("remotedesk_fps", state.fps.toString());
  sendConfig();
});

document.getElementById("btnSettings").addEventListener("click", () => {
  settingsModal.classList.add("show");
});

document.getElementById("btnCloseSettings").addEventListener("click", () => {
  settingsModal.classList.remove("show");
});

document.getElementById("btnSaveSettings").addEventListener("click", () => {
  state.relayUrl = inputRelayUrl.value.trim();
  state.deviceId = inputDeviceId.value.trim() || "windows-laptop";
  state.pin = inputPin.value.trim() || "123456";

  localStorage.setItem("remotedesk_relay", state.relayUrl);
  localStorage.setItem("remotedesk_device_id", state.deviceId);
  localStorage.setItem("remotedesk_pin", state.pin);

  displayDeviceId.textContent = state.deviceId;
  overlayDeviceId.textContent = state.deviceId;

  settingsModal.classList.remove("show");
  connectWebSocket();
});

// Start connection on load
connectWebSocket();

