"use strict";

const elements = {
  appTitle: document.querySelector("#app-title"),
  cameraSource: document.querySelector("#camera-source"),
  captureDialog: document.querySelector("#capture-dialog"),
  captureImage: document.querySelector("#capture-image"),
  captureTime: document.querySelector("#capture-time"),
  dialogClose: document.querySelector("#dialog-close"),
  eventGrid: document.querySelector("#event-grid"),
  eventsEmpty: document.querySelector("#events-empty"),
  eventsMeta: document.querySelector("#events-meta"),
  exposureDetail: document.querySelector("#exposure-detail"),
  exposureValue: document.querySelector("#exposure-value"),
  feedDetail: document.querySelector("#feed-detail"),
  feedValue: document.querySelector("#feed-value"),
  footerHost: document.querySelector("#footer-host"),
  footerVersion: document.querySelector("#footer-version"),
  frameDetail: document.querySelector("#frame-detail"),
  frameStatus: document.querySelector("#frame-status"),
  frameValue: document.querySelector("#frame-value"),
  fullscreenButton: document.querySelector("#fullscreen-button"),
  healthLabel: document.querySelector("#health-label"),
  healthState: document.querySelector("#health-state"),
  localClock: document.querySelector("#local-clock"),
  pauseButton: document.querySelector("#pause-button"),
  powerDetail: document.querySelector("#power-detail"),
  powerValue: document.querySelector("#power-value"),
  reconnectButton: document.querySelector("#reconnect-button"),
  snapshotButton: document.querySelector("#snapshot-button"),
  storageDetail: document.querySelector("#storage-detail"),
  storageValue: document.querySelector("#storage-value"),
  stream: document.querySelector("#camera-stream"),
  streamNotice: document.querySelector("#stream-notice"),
  streamShell: document.querySelector("#stream-shell"),
  systemDetail: document.querySelector("#system-detail"),
  systemValue: document.querySelector("#system-value"),
  warningBanner: document.querySelector("#warning-banner"),
  warningCopy: document.querySelector("#warning-copy"),
};

const viewState = {
  paused: false,
  streamLoaded: false,
};

const dateTime = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "medium",
});

const relativeTime = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });

function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) return "--";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value >= 10 || unit === 0 ? value.toFixed(0) : value.toFixed(1)} ${units[unit]}`;
}

function formatDuration(seconds) {
  if (!Number.isFinite(seconds)) return "Uptime unavailable";
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  if (days > 0) return `${days}d ${hours}h uptime`;
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${minutes}m uptime`;
}

function formatRelative(isoDate) {
  const seconds = Math.round((new Date(isoDate).getTime() - Date.now()) / 1000);
  if (Math.abs(seconds) < 60) return relativeTime.format(seconds, "second");
  const minutes = Math.round(seconds / 60);
  if (Math.abs(minutes) < 60) return relativeTime.format(minutes, "minute");
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 24) return relativeTime.format(hours, "hour");
  return relativeTime.format(Math.round(hours / 24), "day");
}

function exposureLabel(meanLuma) {
  if (!Number.isFinite(meanLuma)) return ["--", "Brightness unavailable"];
  if (meanLuma < 45) return ["Low light", `Luma ${meanLuma}`];
  if (meanLuma > 220) return ["Very bright", `Luma ${meanLuma}`];
  return ["Balanced", `Luma ${meanLuma}`];
}

function setHealthState(state) {
  const labels = {
    degraded: "Needs attention",
    loading: "Connecting",
    offline: "Offline",
    online: "Live",
  };
  elements.healthState.dataset.state = state;
  elements.healthLabel.textContent = labels[state] || "Unknown";
}

function showStreamNotice(message) {
  elements.streamNotice.textContent = message;
  elements.streamNotice.hidden = false;
}

function hideStreamNotice() {
  elements.streamNotice.hidden = true;
}

function startStream() {
  viewState.paused = false;
  viewState.streamLoaded = false;
  elements.pauseButton.textContent = "Pause";
  showStreamNotice("Connecting to camera");
  elements.stream.src = `/stream?advance_headers=1&dual_final_frames=1&t=${Date.now()}`;
}

function pauseStream() {
  viewState.paused = true;
  elements.pauseButton.textContent = "Resume";
  elements.stream.src = `/snapshot?t=${Date.now()}`;
  showStreamNotice("Live view paused");
}

function togglePause() {
  if (viewState.paused) {
    startStream();
  } else {
    pauseStream();
  }
}

function saveSnapshot() {
  const link = document.createElement("a");
  link.href = `/snapshot?download=1&t=${Date.now()}`;
  document.body.append(link);
  link.click();
  link.remove();
}

async function toggleFullscreen() {
  if (document.fullscreenElement) {
    await document.exitFullscreen();
  } else {
    await elements.streamShell.requestFullscreen();
  }
}

function renderStatus(status) {
  const { camera, feed, system, warnings } = status;
  document.title = status.title;
  elements.appTitle.textContent = status.title;
  elements.footerVersion.textContent = `${status.title} v${status.version}`;
  elements.footerHost.textContent = system.hostname;
  elements.cameraSource.textContent = camera.device;
  setHealthState(status.state);

  elements.feedValue.textContent = feed.ok && feed.online ? "Online" : "Unavailable";
  elements.feedDetail.textContent = feed.latency_ms == null ? "No response" : `${feed.latency_ms} ms snapshot`;

  if (feed.width && feed.height) {
    elements.frameValue.textContent = `${feed.width} x ${feed.height}`;
    const drops = feed.dropped_frames == null ? "drops unavailable" : `${feed.dropped_frames} dropped`;
    elements.frameDetail.textContent = drops;
  } else {
    elements.frameValue.textContent = "--";
    elements.frameDetail.textContent = "No current frame";
  }

  const exposure = exposureLabel(feed.mean_luma);
  elements.exposureValue.textContent = exposure[0];
  elements.exposureDetail.textContent = exposure[1];

  if (system.undervoltage_seen === true) {
    elements.powerValue.textContent = "Undervoltage";
    elements.powerDetail.textContent = "Check supply and USB load";
  } else if (system.undervoltage_seen === false) {
    elements.powerValue.textContent = "Stable";
    elements.powerDetail.textContent = "No recent warning";
  } else {
    elements.powerValue.textContent = "Unknown";
    elements.powerDetail.textContent = "Kernel status unavailable";
  }

  elements.storageValue.textContent = `${formatBytes(system.disk_free_bytes)} free`;
  elements.storageDetail.textContent = `${system.disk_free_percent}% available`;

  elements.systemValue.textContent = system.temperature_c == null ? system.hostname : `${system.temperature_c} C`;
  elements.systemDetail.textContent = formatDuration(system.uptime_seconds);

  if (feed.frame_timestamp) {
    const captured = new Date(feed.frame_timestamp * 1000);
    const age = feed.frame_age_seconds == null ? "" : ` / ${feed.frame_age_seconds.toFixed(1)}s old`;
    elements.frameStatus.textContent = `${dateTime.format(captured)}${age}`;
  } else {
    elements.frameStatus.textContent = feed.error || "Frame timestamp unavailable";
  }

  if (warnings.length) {
    elements.warningCopy.textContent = warnings.join(" / ");
    elements.warningBanner.hidden = false;
  } else {
    elements.warningBanner.hidden = true;
  }

  if (status.state === "offline") {
    showStreamNotice("Camera feed unavailable");
  } else if (viewState.streamLoaded && !viewState.paused) {
    hideStreamNotice();
  }
}

async function refreshStatus() {
  try {
    const response = await fetch("/api/status", { cache: "no-store" });
    if (!response.ok) throw new Error(`Status request failed: ${response.status}`);
    renderStatus(await response.json());
  } catch (error) {
    setHealthState("offline");
    elements.frameStatus.textContent = error.message;
    showStreamNotice("Dashboard cannot reach the camera service");
  }
}

function openCapture(event) {
  elements.captureImage.src = event.url;
  elements.captureTime.dateTime = event.captured_at;
  elements.captureTime.textContent = dateTime.format(new Date(event.captured_at));
  elements.captureDialog.showModal();
}

function createEventItem(event) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "event-item";
  button.title = `Open capture from ${dateTime.format(new Date(event.captured_at))}`;

  const image = document.createElement("img");
  image.src = event.url;
  image.alt = `Motion capture from ${dateTime.format(new Date(event.captured_at))}`;
  image.loading = "lazy";

  const caption = document.createElement("span");
  const label = document.createElement("strong");
  label.textContent = formatRelative(event.captured_at);
  const size = document.createElement("small");
  size.textContent = formatBytes(event.size_bytes);
  caption.append(label, size);
  button.append(image, caption);
  button.addEventListener("click", () => openCapture(event));
  return button;
}

async function refreshEvents() {
  try {
    const response = await fetch("/api/events", { cache: "no-store" });
    if (!response.ok) throw new Error(`Events request failed: ${response.status}`);
    const { events } = await response.json();
    elements.eventGrid.replaceChildren(...events.map(createEventItem));
    elements.eventsEmpty.hidden = events.length > 0;
    elements.eventsMeta.textContent = events.length ? `${events.length} most recent frames` : "No saved events";
  } catch (error) {
    elements.eventGrid.replaceChildren();
    elements.eventsEmpty.hidden = false;
    elements.eventsEmpty.textContent = error.message;
    elements.eventsMeta.textContent = "Archive unavailable";
  }
}

function updateClock() {
  const now = new Date();
  elements.localClock.dateTime = now.toISOString();
  elements.localClock.textContent = new Intl.DateTimeFormat(undefined, { timeStyle: "medium" }).format(now);
}

elements.stream.addEventListener("load", () => {
  viewState.streamLoaded = true;
  if (!viewState.paused) hideStreamNotice();
});

elements.stream.addEventListener("error", () => {
  viewState.streamLoaded = false;
  showStreamNotice("Camera stream interrupted");
});

elements.pauseButton.addEventListener("click", togglePause);
elements.reconnectButton.addEventListener("click", startStream);
elements.snapshotButton.addEventListener("click", saveSnapshot);
elements.fullscreenButton.addEventListener("click", toggleFullscreen);
elements.dialogClose.addEventListener("click", () => elements.captureDialog.close());
elements.captureDialog.addEventListener("click", (event) => {
  if (event.target === elements.captureDialog) elements.captureDialog.close();
});
document.addEventListener("fullscreenchange", () => {
  elements.fullscreenButton.textContent = document.fullscreenElement ? "Exit fullscreen" : "Fullscreen";
});

startStream();
refreshStatus();
refreshEvents();
updateClock();
setInterval(refreshStatus, 10000);
setInterval(refreshEvents, 30000);
setInterval(updateClock, 1000);
