document.addEventListener("DOMContentLoaded", () => {
  const relayUrlInput = document.getElementById("relayUrl");
  const deviceIdInput = document.getElementById("deviceId");
  const pinInput = document.getElementById("pin");
  const btnConnect = document.getElementById("btnConnect");

  // Load saved settings from Chrome Storage
  chrome.storage.local.get(["remotedesk_relay", "remotedesk_device_id", "remotedesk_pin"], (res) => {
    if (res.remotedesk_relay) relayUrlInput.value = res.remotedesk_relay;
    if (res.remotedesk_device_id) deviceIdInput.value = res.remotedesk_device_id;
    if (res.remotedesk_pin) pinInput.value = res.remotedesk_pin;
  });

  btnConnect.addEventListener("click", () => {
    const relay = relayUrlInput.value.trim();
    const deviceId = deviceIdInput.value.trim() || "windows-laptop";
    const pin = pinInput.value.trim() || "123456";

    chrome.storage.local.set({
      remotedesk_relay: relay,
      remotedesk_device_id: deviceId,
      remotedesk_pin: pin
    }, () => {
      // Open the viewer tab
      const viewerUrl = chrome.runtime.getURL("viewer.html");
      chrome.tabs.create({ url: viewerUrl });
      window.close();
    });
  });
});

