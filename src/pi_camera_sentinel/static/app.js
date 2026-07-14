"use strict";

const elements = {
  appTitle: document.querySelector("#app-title"),
  appVersion: document.querySelector("#app-version"),
  autoExposureToggle: document.querySelector("#auto-exposure-toggle"),
  autoWhiteBalanceToggle: document.querySelector("#auto-white-balance-toggle"),
  cameraApplyButton: document.querySelector("#camera-apply-button"),
  cameraControlMessage: document.querySelector("#camera-control-message"),
  cameraRefreshButton: document.querySelector("#camera-refresh-button"),
  cameraSource: document.querySelector("#camera-source"),
  captureDialog: document.querySelector("#capture-dialog"),
  captureImage: document.querySelector("#capture-image"),
  captureTime: document.querySelector("#capture-time"),
  dialogClose: document.querySelector("#dialog-close"),
  eventGrid: document.querySelector("#event-grid"),
  eventPagination: document.querySelector("#event-pagination"),
  eventRangeControls: document.querySelector("#event-range-controls"),
  eventsEmpty: document.querySelector("#events-empty"),
  eventsLoadMore: document.querySelector("#events-load-more"),
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
  maskAddButton: document.querySelector("#motion-mask-add"),
  maskApplyButton: document.querySelector("#motion-mask-apply"),
  maskCanvas: document.querySelector("#motion-mask-canvas"),
  maskClearButton: document.querySelector("#motion-mask-clear"),
  maskMessage: document.querySelector("#motion-mask-message"),
  maskMeta: document.querySelector("#motion-mask-meta"),
  maskPreview: document.querySelector("#motion-mask-preview"),
  maskPreviewNotice: document.querySelector("#motion-mask-preview-notice"),
  maskPreviewShell: document.querySelector("#motion-mask-preview-shell"),
  maskRefreshButton: document.querySelector("#motion-mask-refresh"),
  maskRemoveButton: document.querySelector("#motion-mask-remove"),
  maskResetButton: document.querySelector("#motion-mask-reset"),
  pauseButton: document.querySelector("#pause-button"),
  powerDetail: document.querySelector("#power-detail"),
  powerValue: document.querySelector("#power-value"),
  profileControls: document.querySelector("#profile-controls"),
  quietHoursApply: document.querySelector("#quiet-hours-apply"),
  quietHoursDetail: document.querySelector("#quiet-hours-detail"),
  quietHoursEnd: document.querySelector("#quiet-hours-end"),
  quietHoursForm: document.querySelector("#quiet-hours-form"),
  quietHoursRow: document.querySelector("#quiet-hours-row"),
  quietHoursStart: document.querySelector("#quiet-hours-start"),
  quietHoursToggle: document.querySelector("#quiet-hours-toggle"),
  reconnectButton: document.querySelector("#reconnect-button"),
  servicesMeta: document.querySelector("#services-meta"),
  snapshotButton: document.querySelector("#snapshot-button"),
  storageDetail: document.querySelector("#storage-detail"),
  storageValue: document.querySelector("#storage-value"),
  stream: document.querySelector("#camera-stream"),
  streamNotice: document.querySelector("#stream-notice"),
  streamShell: document.querySelector("#stream-shell"),
  systemDetail: document.querySelector("#system-detail"),
  systemValue: document.querySelector("#system-value"),
  tuningForm: document.querySelector("#tuning-form"),
  warningBanner: document.querySelector("#warning-banner"),
  warningCopy: document.querySelector("#warning-copy"),
  webhookDetail: document.querySelector("#webhook-detail"),
  webhookRow: document.querySelector("#webhook-row"),
  webhookState: document.querySelector("#webhook-state"),
  webhookTestButton: document.querySelector("#webhook-test"),
};

const viewState = {
  cameraBusy: false,
  cameraState: null,
  dirtyControls: new Set(),
  eventCursor: null,
  eventSummary: null,
  eventWindow: "24h",
  events: [],
  eventsBusy: false,
  maskBusy: false,
  maskDirty: false,
  maskDraft: null,
  maskDrawing: false,
  maskPointerStart: null,
  maskRegions: [],
  maskSelected: -1,
  maskState: null,
  paused: false,
  policyBusy: false,
  policyDirty: false,
  policyState: null,
  serviceBusy: new Set(),
  serviceStates: {},
  streamLoaded: false,
  webhookBusy: false,
  webhookIntegration: null,
};

const serviceElements = {
  motion: {
    detail: document.querySelector("#motion-service-detail"),
    row: document.querySelector("#motion-service-row"),
    state: document.querySelector("#motion-service-state"),
    toggle: document.querySelector("#motion-service-toggle"),
  },
  watchdog: {
    detail: document.querySelector("#watchdog-service-detail"),
    row: document.querySelector("#watchdog-service-row"),
    state: document.querySelector("#watchdog-service-state"),
    toggle: document.querySelector("#watchdog-service-toggle"),
  },
};

const rangeInputs = [...document.querySelectorAll('.range-control input[type="range"]')];
const controlInputs = [...document.querySelectorAll("[data-control]")];
const profileButtons = [...elements.profileControls.querySelectorAll("[data-profile]")];
const eventRangeButtons = [...elements.eventRangeControls.querySelectorAll("[data-event-window]")];

const dateTime = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "medium",
});

const relativeTime = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
const minimumDrawnMaskSize = 0.02;

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
  elements.healthState.title = labels[state] || "Unknown";
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
  const { camera, feed, integrations, system, warnings } = status;
  document.title = status.title;
  elements.appTitle.textContent = status.title;
  elements.appVersion.textContent = `v${status.version}`;
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

  if (!viewState.webhookBusy) {
    renderWebhookIntegration(integrations?.home_assistant || { configured: false });
  }

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

function renderWebhookIntegration(integration, message = null) {
  viewState.webhookIntegration = integration;
  const configured = Boolean(integration.configured);
  elements.webhookRow.dataset.state = configured ? "active" : "inactive";
  elements.webhookState.textContent = configured ? "Configured" : "Off";
  elements.webhookDetail.textContent = message || (configured ? "Motion event webhook enabled" : "Not configured");
  elements.webhookTestButton.disabled = viewState.webhookBusy || !configured;
  elements.webhookTestButton.textContent = viewState.webhookBusy ? "Sending" : "Send test";
}

async function sendWebhookTest() {
  if (viewState.webhookBusy || !viewState.webhookIntegration?.configured) return;
  viewState.webhookBusy = true;
  renderWebhookIntegration(viewState.webhookIntegration, "Sending test event");
  try {
    const result = await requestJSON("/api/webhook/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    viewState.webhookBusy = false;
    renderWebhookIntegration(
      { configured: true },
      `Test delivered / HTTP ${result.status_code}`,
    );
  } catch (error) {
    viewState.webhookBusy = false;
    renderWebhookIntegration(viewState.webhookIntegration, error.message);
    elements.webhookRow.dataset.state = "failed";
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

function renderService(serviceId, state) {
  const target = serviceElements[serviceId];
  if (!target) return;
  const labels = {
    active: "Active",
    failed: "Failed",
    paused: "Paused",
    unavailable: "Unavailable",
  };
  viewState.serviceStates[serviceId] = state;
  target.row.dataset.state = state.state;
  target.state.textContent = labels[state.state] || "Unknown";
  target.detail.textContent = state.available
    ? `${state.name} / ${state.sub_state}`
    : state.error || "System state unavailable";
  target.toggle.checked = Boolean(state.active);
  target.toggle.disabled = viewState.serviceBusy.has(serviceId) || !state.available;
  target.toggle.setAttribute("aria-busy", String(viewState.serviceBusy.has(serviceId)));
}

function renderServices(services) {
  Object.entries(services).forEach(([serviceId, state]) => renderService(serviceId, state));
  const available = Object.values(services).filter((state) => state.available).length;
  const active = Object.values(services).filter((state) => state.active).length;
  elements.servicesMeta.textContent = available === 2 ? `${active} of 2 active` : "Service issue";
}

async function refreshServices() {
  try {
    const payload = await requestJSON("/api/services");
    renderServices(payload.services || {});
  } catch (error) {
    elements.servicesMeta.textContent = error.message;
    Object.keys(serviceElements).forEach((serviceId) => {
      renderService(serviceId, {
        active: false,
        available: false,
        error: "Service status unavailable",
        state: "unavailable",
      });
    });
  }
}

async function updateService(serviceId, active) {
  viewState.serviceBusy.add(serviceId);
  const current = viewState.serviceStates[serviceId];
  if (current) renderService(serviceId, current);
  elements.servicesMeta.textContent = active ? "Starting service" : "Pausing service";
  try {
    const state = await requestJSON(`/api/services/${serviceId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ active }),
    });
    viewState.serviceStates[serviceId] = state;
  } catch (error) {
    elements.servicesMeta.textContent = error.message;
  } finally {
    viewState.serviceBusy.delete(serviceId);
    if (viewState.serviceStates[serviceId]) renderService(serviceId, viewState.serviceStates[serviceId]);
  }
  await refreshServices();
}

function setPolicyBusy(busy) {
  viewState.policyBusy = busy;
  elements.quietHoursToggle.disabled = busy || viewState.policyState == null;
  elements.quietHoursStart.disabled = busy || viewState.policyState == null;
  elements.quietHoursEnd.disabled = busy || viewState.policyState == null;
  elements.quietHoursApply.disabled = busy || !viewState.policyDirty;
}

function policyScheduleLabel(policy) {
  if (policy.quiet_hours_start === policy.quiet_hours_end) return "all day";
  return `${policy.quiet_hours_start} - ${policy.quiet_hours_end}`;
}

function renderPolicy(policy, message = null) {
  viewState.policyState = policy;
  viewState.policyDirty = false;
  elements.quietHoursToggle.checked = policy.quiet_hours_enabled;
  elements.quietHoursStart.value = policy.quiet_hours_start;
  elements.quietHoursEnd.value = policy.quiet_hours_end;
  const schedule = policyScheduleLabel(policy);
  if (message) {
    elements.quietHoursDetail.textContent = message;
  } else if (!policy.quiet_hours_enabled) {
    elements.quietHoursDetail.textContent = `Off / schedule ${schedule} / ${policy.timezone}`;
  } else if (policy.quiet_now) {
    elements.quietHoursDetail.textContent = `Quiet now / ${schedule} / ${policy.timezone}`;
  } else {
    elements.quietHoursDetail.textContent = `Scheduled ${schedule} / ${policy.timezone}`;
  }
  elements.quietHoursRow.dataset.state = policy.quiet_hours_enabled
    ? (policy.quiet_now ? "paused" : "active")
    : "inactive";
  setPolicyBusy(false);
}

function markPolicyDirty() {
  const policy = viewState.policyState;
  if (!policy) return;
  viewState.policyDirty = (
    elements.quietHoursToggle.checked !== policy.quiet_hours_enabled
    || elements.quietHoursStart.value !== policy.quiet_hours_start
    || elements.quietHoursEnd.value !== policy.quiet_hours_end
  );
  if (viewState.policyDirty) elements.quietHoursDetail.textContent = "Unsaved schedule changes";
  else renderPolicy(policy);
  setPolicyBusy(false);
}

async function refreshPolicy(force = false) {
  if (viewState.policyBusy || (viewState.policyDirty && !force)) return;
  setPolicyBusy(true);
  try {
    renderPolicy(await requestJSON("/api/policy"));
  } catch (error) {
    viewState.policyState = null;
    viewState.policyDirty = false;
    elements.quietHoursRow.dataset.state = "unavailable";
    elements.quietHoursDetail.textContent = error.message;
    setPolicyBusy(false);
  }
}

async function applyPolicy(event) {
  event.preventDefault();
  if (!viewState.policyDirty || viewState.policyBusy) return;
  setPolicyBusy(true);
  elements.quietHoursDetail.textContent = "Applying alert schedule";
  try {
    const policy = await requestJSON("/api/policy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        quiet_hours_enabled: elements.quietHoursToggle.checked,
        quiet_hours_start: elements.quietHoursStart.value,
        quiet_hours_end: elements.quietHoursEnd.value,
      }),
    });
    renderPolicy(policy, "Alert schedule applied");
  } catch (error) {
    elements.quietHoursDetail.textContent = error.message;
    setPolicyBusy(false);
  }
}

function cloneMaskRegions(regions = []) {
  return regions.map((region) => ({
    x: Number(region.x),
    y: Number(region.y),
    width: Number(region.width),
    height: Number(region.height),
  }));
}

function masksEqual(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
}

function setMaskMessage(message, state = "idle") {
  elements.maskMessage.textContent = message;
  elements.maskMessage.dataset.state = state;
}

function renderMaskMeta() {
  const count = viewState.maskRegions.length;
  const noun = count === 1 ? "area" : "areas";
  elements.maskMeta.textContent = `${count} ignored ${noun}${viewState.maskDirty ? " / unsaved" : ""}`;
}

function updateMaskControls() {
  const ready = viewState.maskState !== null;
  const maximum = viewState.maskState?.max_regions || 0;
  elements.maskAddButton.disabled = viewState.maskBusy || !ready || (!viewState.maskDrawing && viewState.maskRegions.length >= maximum);
  elements.maskAddButton.textContent = viewState.maskDrawing ? "Cancel" : "Add area";
  elements.maskAddButton.setAttribute("aria-pressed", String(viewState.maskDrawing));
  elements.maskRemoveButton.disabled = viewState.maskBusy || viewState.maskSelected < 0;
  elements.maskClearButton.disabled = viewState.maskBusy || viewState.maskRegions.length === 0;
  elements.maskResetButton.disabled = viewState.maskBusy || !viewState.maskDirty;
  elements.maskRefreshButton.disabled = viewState.maskBusy;
  elements.maskApplyButton.disabled = viewState.maskBusy || !viewState.maskDirty;
  elements.maskPreviewShell.classList.toggle("is-drawing", viewState.maskDrawing);
  renderMaskMeta();
}

function setMaskBusy(busy) {
  viewState.maskBusy = busy;
  updateMaskControls();
}

function canvasMaskPoint(event) {
  const bounds = elements.maskCanvas.getBoundingClientRect();
  return {
    x: Math.min(1, Math.max(0, (event.clientX - bounds.left) / bounds.width)),
    y: Math.min(1, Math.max(0, (event.clientY - bounds.top) / bounds.height)),
  };
}

function normalizedMaskRegion(start, end) {
  const x = Number(Math.min(start.x, end.x).toFixed(4));
  const y = Number(Math.min(start.y, end.y).toFixed(4));
  const width = Number(Math.abs(end.x - start.x).toFixed(4));
  const height = Number(Math.abs(end.y - start.y).toFixed(4));
  return {
    x,
    y,
    width: Math.min(1 - x, width),
    height: Math.min(1 - y, height),
  };
}

function drawMotionMasks() {
  const bounds = elements.maskCanvas.getBoundingClientRect();
  if (!bounds.width || !bounds.height) return;
  const ratio = window.devicePixelRatio || 1;
  const width = Math.round(bounds.width * ratio);
  const height = Math.round(bounds.height * ratio);
  if (elements.maskCanvas.width !== width || elements.maskCanvas.height !== height) {
    elements.maskCanvas.width = width;
    elements.maskCanvas.height = height;
  }
  const context = elements.maskCanvas.getContext("2d");
  if (!context) return;
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  context.clearRect(0, 0, bounds.width, bounds.height);

  const regions = viewState.maskDraft
    ? [...viewState.maskRegions, viewState.maskDraft]
    : viewState.maskRegions;
  regions.forEach((region, index) => {
    const x = region.x * bounds.width;
    const y = region.y * bounds.height;
    const regionWidth = region.width * bounds.width;
    const regionHeight = region.height * bounds.height;
    const selected = index === viewState.maskSelected || index >= viewState.maskRegions.length;
    context.fillStyle = selected ? "rgba(182, 58, 53, 0.34)" : "rgba(182, 58, 53, 0.22)";
    context.strokeStyle = selected ? "#fbe8e6" : "rgba(255, 255, 255, 0.86)";
    context.lineWidth = selected ? 3 : 2;
    context.setLineDash(selected ? [] : [7, 5]);
    context.fillRect(x, y, regionWidth, regionHeight);
    context.strokeRect(x, y, regionWidth, regionHeight);

    if (regionWidth >= 30 && regionHeight >= 26) {
      context.setLineDash([]);
      context.fillStyle = selected ? "#b63a35" : "#171a18";
      context.fillRect(x + 6, y + 6, 24, 20);
      context.fillStyle = "#ffffff";
      context.font = "700 12px Inter, sans-serif";
      context.textAlign = "center";
      context.textBaseline = "middle";
      context.fillText(String(index + 1), x + 18, y + 16);
    }
  });
  context.setLineDash([]);
}

function maskRegionAt(point) {
  for (let index = viewState.maskRegions.length - 1; index >= 0; index -= 1) {
    const region = viewState.maskRegions[index];
    if (
      point.x >= region.x
      && point.x <= region.x + region.width
      && point.y >= region.y
      && point.y <= region.y + region.height
    ) return index;
  }
  return -1;
}

function stopMaskDrawing() {
  viewState.maskDrawing = false;
  viewState.maskPointerStart = null;
  viewState.maskDraft = null;
  updateMaskControls();
  drawMotionMasks();
}

function markMasksDirty(message = "Unsaved motion masks") {
  viewState.maskDirty = !masksEqual(viewState.maskRegions, viewState.maskState?.regions || []);
  setMaskMessage(viewState.maskDirty ? message : "Motion masks up to date");
  updateMaskControls();
  drawMotionMasks();
}

function renderMotionMasks(state, message = "Motion masks up to date") {
  viewState.maskState = {
    ...state,
    regions: cloneMaskRegions(state.regions),
  };
  viewState.maskRegions = cloneMaskRegions(state.regions);
  viewState.maskSelected = -1;
  viewState.maskDirty = false;
  stopMaskDrawing();
  setMaskBusy(false);
  setMaskMessage(message, "success");
  drawMotionMasks();
}

async function refreshMotionMasks(force = false) {
  if (
    viewState.maskBusy
    || viewState.maskDrawing
    || viewState.maskPointerStart
    || (viewState.maskDirty && !force)
  ) return;
  setMaskBusy(true);
  setMaskMessage("Reading motion masks");
  try {
    renderMotionMasks(await requestJSON("/api/masks"));
  } catch (error) {
    viewState.maskState = null;
    setMaskBusy(false);
    setMaskMessage(error.message, "error");
  }
}

function refreshMotionMaskFrame() {
  elements.maskPreviewNotice.textContent = "Loading frame";
  elements.maskPreviewNotice.hidden = false;
  elements.maskPreview.src = `/snapshot?t=${Date.now()}`;
}

function toggleMaskDrawing() {
  if (viewState.maskDrawing) {
    stopMaskDrawing();
    setMaskMessage("Drawing cancelled");
    return;
  }
  if (!viewState.maskState || viewState.maskRegions.length >= viewState.maskState.max_regions) return;
  viewState.maskSelected = -1;
  viewState.maskDrawing = true;
  setMaskMessage(`Drawing area ${viewState.maskRegions.length + 1}`);
  updateMaskControls();
  drawMotionMasks();
}

function removeSelectedMask() {
  if (viewState.maskSelected < 0) return;
  viewState.maskRegions.splice(viewState.maskSelected, 1);
  viewState.maskSelected = -1;
  markMasksDirty();
}

function clearMotionMasks() {
  viewState.maskRegions = [];
  viewState.maskSelected = -1;
  stopMaskDrawing();
  markMasksDirty();
}

function resetMotionMasks() {
  if (!viewState.maskState) return;
  viewState.maskRegions = cloneMaskRegions(viewState.maskState.regions);
  viewState.maskSelected = -1;
  viewState.maskDirty = false;
  stopMaskDrawing();
  setMaskMessage("Unsaved changes discarded");
  updateMaskControls();
  drawMotionMasks();
}

async function applyMotionMasks() {
  if (!viewState.maskDirty || viewState.maskBusy) return;
  setMaskBusy(true);
  setMaskMessage("Applying motion masks");
  try {
    const state = await requestJSON("/api/masks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ regions: viewState.maskRegions }),
    });
    renderMotionMasks(state, "Motion masks applied");
  } catch (error) {
    setMaskBusy(false);
    setMaskMessage(error.message, "error");
  }
}

function beginMaskPointer(event) {
  if (!viewState.maskState || viewState.maskBusy) return;
  const point = canvasMaskPoint(event);
  if (!viewState.maskDrawing) {
    viewState.maskSelected = maskRegionAt(point);
    updateMaskControls();
    drawMotionMasks();
    return;
  }
  event.preventDefault();
  viewState.maskPointerStart = point;
  viewState.maskDraft = normalizedMaskRegion(point, point);
  elements.maskCanvas.setPointerCapture(event.pointerId);
  drawMotionMasks();
}

function moveMaskPointer(event) {
  if (!viewState.maskPointerStart) return;
  event.preventDefault();
  viewState.maskDraft = normalizedMaskRegion(viewState.maskPointerStart, canvasMaskPoint(event));
  drawMotionMasks();
}

function finishMaskPointer(event) {
  if (!viewState.maskPointerStart) return;
  event.preventDefault();
  const region = normalizedMaskRegion(viewState.maskPointerStart, canvasMaskPoint(event));
  if (elements.maskCanvas.hasPointerCapture(event.pointerId)) {
    elements.maskCanvas.releasePointerCapture(event.pointerId);
  }
  viewState.maskPointerStart = null;
  viewState.maskDraft = null;
  viewState.maskDrawing = false;
  if (region.width >= minimumDrawnMaskSize && region.height >= minimumDrawnMaskSize) {
    viewState.maskRegions.push(region);
    viewState.maskSelected = viewState.maskRegions.length - 1;
    markMasksDirty();
  } else {
    setMaskMessage("Area is too small", "error");
    updateMaskControls();
    drawMotionMasks();
  }
}

function cancelMaskPointer(event) {
  if (viewState.maskPointerStart && elements.maskCanvas.hasPointerCapture(event.pointerId)) {
    elements.maskCanvas.releasePointerCapture(event.pointerId);
  }
  stopMaskDrawing();
  setMaskMessage("Drawing cancelled");
}

function setCameraMessage(message, state = "idle") {
  elements.cameraControlMessage.textContent = message;
  elements.cameraControlMessage.dataset.state = state;
}

function setCameraBusy(busy) {
  viewState.cameraBusy = busy;
  elements.cameraRefreshButton.disabled = busy;
  profileButtons.forEach((button) => {
    button.disabled = busy;
  });
  updateDependentControls();
}

function updateApplyButton() {
  elements.cameraApplyButton.disabled = viewState.cameraBusy || viewState.dirtyControls.size === 0;
}

function updateRangeOutput(input) {
  const output = document.querySelector(`[data-output="${input.dataset.control}"]`);
  if (output) output.value = input.value;
}

function updateDependentControls() {
  const autoExposure = elements.autoExposureToggle.checked;
  const autoWhiteBalance = elements.autoWhiteBalanceToggle.checked;

  controlInputs.forEach((input) => {
    const name = input.dataset.control;
    const control = viewState.cameraState?.controls?.[name];
    let disabled = viewState.cameraBusy || !control;
    if (name === "exposure_time_absolute") disabled ||= autoExposure;
    else if (name === "white_balance_temperature") disabled ||= autoWhiteBalance;
    else if (input.type !== "checkbox") disabled ||= control?.inactive;
    input.disabled = disabled;
  });
  if (autoExposure) viewState.dirtyControls.delete("exposure_time_absolute");
  if (autoWhiteBalance) viewState.dirtyControls.delete("white_balance_temperature");
  updateApplyButton();
}

function markControlDirty(input) {
  const name = input.dataset.control;
  const value = input.type === "checkbox" ? (input.checked ? input.dataset.onValue : input.dataset.offValue) : input.value;
  if (String(value) === input.dataset.originalValue) {
    viewState.dirtyControls.delete(name);
  } else {
    viewState.dirtyControls.add(name);
  }
  profileButtons.forEach((button) => {
    const active = viewState.dirtyControls.size === 0 && button.dataset.profile === viewState.cameraState?.active_profile;
    button.setAttribute("aria-pressed", String(active));
  });
  updateDependentControls();
  setCameraMessage(viewState.dirtyControls.size ? `${viewState.dirtyControls.size} unsaved change${viewState.dirtyControls.size === 1 ? "" : "s"}` : "Controls up to date");
}

function renderCameraState(state, message = "Controls up to date") {
  viewState.cameraState = state;
  viewState.dirtyControls.clear();
  const controls = state.controls || {};

  profileButtons.forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.profile === state.active_profile));
  });

  controlInputs.forEach((input) => {
    const control = controls[input.dataset.control];
    if (!control) {
      input.disabled = true;
      return;
    }
    if (input.type === "checkbox") {
      input.dataset.onValue = input.dataset.control === "auto_exposure" ? "3" : "1";
      input.dataset.offValue = input.dataset.control === "auto_exposure" ? "1" : "0";
      input.checked = String(control.value) === input.dataset.onValue;
      input.dataset.originalValue = input.checked ? input.dataset.onValue : input.dataset.offValue;
      input.disabled = false;
      return;
    }
    input.min = control.ui_minimum;
    input.max = control.ui_maximum;
    input.step = control.step;
    input.value = Math.min(Math.max(control.value, control.ui_minimum), control.ui_maximum);
    input.dataset.originalValue = input.value;
    input.disabled = control.inactive;
    updateRangeOutput(input);
  });

  setCameraBusy(false);
  updateDependentControls();
  setCameraMessage(message, "success");
}

async function requestJSON(url, options = {}) {
  const response = await fetch(url, { cache: "no-store", ...options });
  let payload = {};
  try {
    payload = await response.json();
  } catch (_error) {
    payload = {};
  }
  if (!response.ok) throw new Error(payload.error || `Request failed: ${response.status}`);
  return payload;
}

async function refreshCameraState(message = "Controls up to date", force = false) {
  if (viewState.cameraBusy || (!force && viewState.dirtyControls.size)) return;
  setCameraBusy(true);
  setCameraMessage("Reading camera controls");
  try {
    renderCameraState(await requestJSON("/api/camera"), message);
  } catch (error) {
    viewState.cameraState = null;
    controlInputs.forEach((input) => {
      input.disabled = true;
    });
    setCameraBusy(false);
    setCameraMessage(error.message, "error");
  }
}

async function applyProfile(profile, label) {
  setCameraBusy(true);
  setCameraMessage(`Applying ${label}`);
  try {
    const state = await requestJSON("/api/camera/profile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile }),
    });
    renderCameraState(state, `${label} profile applied`);
    await refreshStatus();
  } catch (error) {
    setCameraBusy(false);
    setCameraMessage(error.message, "error");
  }
}

async function applyManualControls(event) {
  event.preventDefault();
  const controls = {};
  controlInputs.forEach((input) => {
    const name = input.dataset.control;
    if (!viewState.dirtyControls.has(name)) return;
    if (name === "exposure_time_absolute" && elements.autoExposureToggle.checked) return;
    if (name === "white_balance_temperature" && elements.autoWhiteBalanceToggle.checked) return;
    const value = input.type === "checkbox" ? (input.checked ? input.dataset.onValue : input.dataset.offValue) : input.value;
    controls[name] = Number(value);
  });
  if (!Object.keys(controls).length) return;

  setCameraBusy(true);
  setCameraMessage("Applying camera controls");
  try {
    const state = await requestJSON("/api/camera/controls", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ controls }),
    });
    renderCameraState(state, "Manual controls applied");
    await refreshStatus();
  } catch (error) {
    setCameraBusy(false);
    updateDependentControls();
    setCameraMessage(error.message, "error");
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

function setEventsBusy(busy) {
  viewState.eventsBusy = busy;
  eventRangeButtons.forEach((button) => {
    button.disabled = busy;
  });
  elements.eventsLoadMore.disabled = busy;
  elements.eventsLoadMore.textContent = busy ? "Loading captures" : "Load older captures";
}

function renderEventSummary() {
  const summary = viewState.eventSummary;
  if (!summary) return;
  const shown = viewState.events.length;
  const storage = formatBytes(summary.retained_size_bytes);
  if (viewState.eventWindow === "all") {
    elements.eventsMeta.textContent = `${shown} shown / ${summary.retained_count} retained / ${storage}`;
  } else {
    const label = viewState.eventWindow === "24h" ? "24 hours" : "7 days";
    elements.eventsMeta.textContent = `${shown} shown / ${summary.window_count} in ${label} / ${summary.retained_count} retained / ${storage}`;
  }
}

function renderEvents() {
  elements.eventGrid.replaceChildren(...viewState.events.map(createEventItem));
  elements.eventsEmpty.hidden = viewState.events.length > 0;
  elements.eventsEmpty.textContent = "No motion captures in this range.";
  elements.eventPagination.hidden = viewState.eventCursor == null;
  renderEventSummary();
}

async function refreshEvents({ append = false } = {}) {
  if (viewState.eventsBusy) return;
  setEventsBusy(true);
  try {
    const query = new URLSearchParams({ window: viewState.eventWindow, limit: "12" });
    if (append && viewState.eventCursor != null) query.set("before", String(viewState.eventCursor));
    const payload = await requestJSON(`/api/events?${query}`);
    viewState.events = append ? [...viewState.events, ...payload.events] : payload.events;
    viewState.eventCursor = payload.next_before;
    viewState.eventSummary = payload.summary;
    renderEvents();
  } catch (error) {
    if (!append) {
      viewState.events = [];
      viewState.eventCursor = null;
      viewState.eventSummary = null;
      elements.eventGrid.replaceChildren();
      elements.eventsEmpty.hidden = false;
      elements.eventsEmpty.textContent = error.message;
    }
    elements.eventPagination.hidden = append ? viewState.eventCursor == null : true;
    elements.eventsMeta.textContent = "Archive unavailable";
  } finally {
    setEventsBusy(false);
  }
}

function selectEventWindow(windowName) {
  if (viewState.eventsBusy || windowName === viewState.eventWindow) return;
  viewState.eventWindow = windowName;
  viewState.eventCursor = null;
  viewState.events = [];
  eventRangeButtons.forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.eventWindow === windowName));
  });
  refreshEvents();
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

elements.maskPreview.addEventListener("load", () => {
  if (elements.maskPreview.naturalWidth && elements.maskPreview.naturalHeight) {
    elements.maskPreviewShell.style.aspectRatio = `${elements.maskPreview.naturalWidth} / ${elements.maskPreview.naturalHeight}`;
  }
  elements.maskPreviewNotice.hidden = true;
  drawMotionMasks();
});

elements.maskPreview.addEventListener("error", () => {
  elements.maskPreviewNotice.textContent = "Frame unavailable";
  elements.maskPreviewNotice.hidden = false;
});

elements.pauseButton.addEventListener("click", togglePause);
elements.reconnectButton.addEventListener("click", startStream);
elements.snapshotButton.addEventListener("click", saveSnapshot);
elements.fullscreenButton.addEventListener("click", toggleFullscreen);
elements.cameraRefreshButton.addEventListener("click", () => refreshCameraState("Controls refreshed", true));
elements.quietHoursForm.addEventListener("submit", applyPolicy);
[elements.quietHoursToggle, elements.quietHoursStart, elements.quietHoursEnd].forEach((input) => {
  input.addEventListener("change", markPolicyDirty);
});
elements.maskAddButton.addEventListener("click", toggleMaskDrawing);
elements.maskRemoveButton.addEventListener("click", removeSelectedMask);
elements.maskClearButton.addEventListener("click", clearMotionMasks);
elements.maskResetButton.addEventListener("click", resetMotionMasks);
elements.maskRefreshButton.addEventListener("click", refreshMotionMaskFrame);
elements.maskApplyButton.addEventListener("click", applyMotionMasks);
elements.maskCanvas.addEventListener("pointerdown", beginMaskPointer);
elements.maskCanvas.addEventListener("pointermove", moveMaskPointer);
elements.maskCanvas.addEventListener("pointerup", finishMaskPointer);
elements.maskCanvas.addEventListener("pointercancel", cancelMaskPointer);
elements.webhookTestButton.addEventListener("click", sendWebhookTest);
eventRangeButtons.forEach((button) => {
  button.addEventListener("click", () => selectEventWindow(button.dataset.eventWindow));
});
elements.eventsLoadMore.addEventListener("click", () => refreshEvents({ append: true }));
Object.entries(serviceElements).forEach(([serviceId, target]) => {
  target.toggle.addEventListener("change", () => updateService(serviceId, target.toggle.checked));
});
elements.tuningForm.addEventListener("submit", applyManualControls);
profileButtons.forEach((button) => {
  button.addEventListener("click", () => applyProfile(button.dataset.profile, button.textContent));
});
rangeInputs.forEach((input) => {
  input.addEventListener("input", () => {
    updateRangeOutput(input);
    markControlDirty(input);
  });
});
[elements.autoExposureToggle, elements.autoWhiteBalanceToggle].forEach((input) => {
  input.addEventListener("change", () => markControlDirty(input));
});
elements.dialogClose.addEventListener("click", () => elements.captureDialog.close());
elements.captureDialog.addEventListener("click", (event) => {
  if (event.target === elements.captureDialog) elements.captureDialog.close();
});
document.addEventListener("fullscreenchange", () => {
  elements.fullscreenButton.textContent = document.fullscreenElement ? "Exit fullscreen" : "Fullscreen";
});
if ("ResizeObserver" in window) {
  new ResizeObserver(drawMotionMasks).observe(elements.maskPreviewShell);
} else {
  window.addEventListener("resize", drawMotionMasks);
}

startStream();
refreshStatus();
refreshServices();
refreshPolicy();
refreshMotionMasks();
refreshMotionMaskFrame();
refreshEvents();
refreshCameraState();
updateClock();
setInterval(refreshStatus, 10000);
setInterval(refreshServices, 10000);
setInterval(refreshPolicy, 30000);
setInterval(refreshMotionMasks, 30000);
setInterval(() => {
  if (viewState.events.length <= 12) refreshEvents();
}, 30000);
setInterval(refreshCameraState, 60000);
setInterval(updateClock, 1000);
