"use strict";

const elements = {
  activityActive: document.querySelector("#activity-active"),
  activityAxisEnd: document.querySelector("#activity-axis-end"),
  activityAxisMiddle: document.querySelector("#activity-axis-middle"),
  activityAxisStart: document.querySelector("#activity-axis-start"),
  activityBand: document.querySelector("#activity-band"),
  activityChart: document.querySelector("#activity-chart"),
  activityClear: document.querySelector("#activity-clear"),
  activityLast: document.querySelector("#activity-last"),
  activityPeak: document.querySelector("#activity-peak"),
  activityRange: document.querySelector("#activity-range"),
  activityTotal: document.querySelector("#activity-total"),
  alertBatchDetail: document.querySelector("#alert-batch-detail"),
  alertBatchRow: document.querySelector("#alert-batch-row"),
  alertBatchState: document.querySelector("#alert-batch-state"),
  appTitle: document.querySelector("#app-title"),
  appVersion: document.querySelector("#app-version"),
  autoExposureToggle: document.querySelector("#auto-exposure-toggle"),
  autoWhiteBalanceToggle: document.querySelector("#auto-white-balance-toggle"),
  cameraApplyButton: document.querySelector("#camera-apply-button"),
  cameraControlMessage: document.querySelector("#camera-control-message"),
  cameraRefreshButton: document.querySelector("#camera-refresh-button"),
  cameraSource: document.querySelector("#camera-source"),
  captureDialog: document.querySelector("#capture-dialog"),
  captureDownload: document.querySelector("#capture-download"),
  captureImage: document.querySelector("#capture-image"),
  captureImageStatus: document.querySelector("#capture-image-status"),
  captureNext: document.querySelector("#capture-next"),
  capturePosition: document.querySelector("#capture-position"),
  capturePrevious: document.querySelector("#capture-previous"),
  captureSize: document.querySelector("#capture-size"),
  captureStage: document.querySelector("#capture-stage"),
  captureTime: document.querySelector("#capture-time"),
  dialogClose: document.querySelector("#dialog-close"),
  eventGrid: document.querySelector("#event-grid"),
  eventPagination: document.querySelector("#event-pagination"),
  eventRangeControls: document.querySelector("#event-range-controls"),
  eventsSection: document.querySelector("#events-section"),
  eventsEmpty: document.querySelector("#events-empty"),
  eventsLoadMore: document.querySelector("#events-load-more"),
  eventsMeta: document.querySelector("#events-meta"),
  retentionMeta: document.querySelector("#retention-meta"),
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
  monitoringSection: document.querySelector("#monitoring-section"),
  pauseButton: document.querySelector("#pause-button"),
  powerDetail: document.querySelector("#power-detail"),
  powerMetric: document.querySelector("#power-metric"),
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
  recoveryHistoryList: document.querySelector("#recovery-history-list"),
  recoveryHistoryMeta: document.querySelector("#recovery-history-meta"),
  recoveryRestartButton: document.querySelector("#recovery-restart"),
  servicesMeta: document.querySelector("#services-meta"),
  snapshotButton: document.querySelector("#snapshot-button"),
  storageDetail: document.querySelector("#storage-detail"),
  storageValue: document.querySelector("#storage-value"),
  streamFallback: document.querySelector("#camera-fallback"),
  stream: document.querySelector("#camera-stream"),
  streamNotice: document.querySelector("#stream-notice"),
  streamShell: document.querySelector("#stream-shell"),
  systemDetail: document.querySelector("#system-detail"),
  systemValue: document.querySelector("#system-value"),
  tuningForm: document.querySelector("#tuning-form"),
  tuningSection: document.querySelector("#tuning-section"),
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
  captureLoadingOlder: false,
  captureName: null,
  dirtyControls: new Set(),
  eventCursor: null,
  eventActivity: null,
  eventSelection: null,
  eventSummary: null,
  eventWindow: "24h",
  events: [],
  eventsBusy: false,
  monitoringInitialized: false,
  paused: false,
  policyBusy: false,
  policyDirty: false,
  policyState: null,
  recoveryBusy: false,
  recoveryState: null,
  healthAlertState: null,
  serviceBusy: new Set(),
  servicesBusy: false,
  serviceStates: {},
  statusBusy: false,
  streamFeedOnline: null,
  streamLoaded: false,
  streamStartedAt: null,
  streamReconnectAttempt: 0,
  streamReconnectTimer: null,
  webhookBusy: false,
  webhookIntegration: null,
  cameraInitialized: false,
  eventsInitialized: false,
};

let eventRefreshRequest = null;

const serviceElements = {
  motion: {
    detail: document.querySelector("#motion-service-detail"),
    row: document.querySelector("#motion-service-row"),
    state: document.querySelector("#motion-service-state"),
    toggle: document.querySelector("#motion-service-toggle"),
  },
  recovery: {
    detail: document.querySelector("#recovery-service-detail"),
    row: document.querySelector("#recovery-service-row"),
    state: document.querySelector("#recovery-service-state"),
    toggle: document.querySelector("#recovery-service-toggle"),
  },
  health: {
    detail: document.querySelector("#health-service-detail"),
    row: document.querySelector("#health-service-row"),
    state: document.querySelector("#health-service-state"),
    toggle: document.querySelector("#health-service-toggle"),
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
const activityTime = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" });
const activityDay = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" });
const activityWeekday = new Intl.DateTimeFormat(undefined, { weekday: "short" });
const clockTime = new Intl.DateTimeFormat(undefined, { timeStyle: "medium" });
const streamReconnectBaseMs = 750;
const streamReconnectMaxMs = 8000;
const streamConnectTimeoutMs = 10000;
const requestTimeoutMs = 10000;
const deferredSectionMargin = "600px 0px";

function scheduleIdle(callback, timeout = 1000) {
  if ("requestIdleCallback" in window) {
    window.requestIdleCallback(callback, { timeout });
  } else {
    window.setTimeout(callback, 0);
  }
}

function runWhenNear(element, callback) {
  let started = false;
  const run = () => {
    if (started) return;
    started = true;
    callback();
  };
  if (!("IntersectionObserver" in window)) {
    scheduleIdle(run);
    return;
  }
  const observer = new IntersectionObserver((entries) => {
    if (!entries.some((entry) => entry.isIntersecting)) return;
    observer.disconnect();
    run();
  }, { rootMargin: deferredSectionMargin });
  observer.observe(element);
}

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

function clearStreamReconnect() {
  if (viewState.streamReconnectTimer !== null) {
    window.clearTimeout(viewState.streamReconnectTimer);
    viewState.streamReconnectTimer = null;
  }
}

function streamReconnectDelay(attempt) {
  return Math.min(streamReconnectBaseMs * (2 ** Math.min(attempt, 5)), streamReconnectMaxMs);
}

function refreshStreamFallback() {
  const image = new Image();
  image.addEventListener("load", () => {
    elements.streamFallback.src = image.src;
  }, { once: true });
  image.src = `/snapshot?t=${Date.now()}`;
}

function markStreamReady(stream) {
  if (stream !== elements.stream || viewState.paused || document.hidden) return;
  clearStreamReconnect();
  viewState.streamReconnectAttempt = 0;
  viewState.streamLoaded = true;
  viewState.streamStartedAt = null;
  elements.streamShell.dataset.state = "live";
  hideStreamNotice();
  if (!elements.streamFallback.src) refreshStreamFallback();
}

function replaceStreamElement() {
  const previous = elements.stream;
  const replacement = previous.cloneNode(false);
  replacement.removeAttribute("src");
  previous.replaceWith(replacement);
  elements.stream = replacement;
  replacement.addEventListener("load", () => {
    markStreamReady(replacement);
  });
  replacement.addEventListener("error", () => {
    if (replacement !== elements.stream) return;
    viewState.streamLoaded = false;
    if (!viewState.paused) scheduleStreamReconnect("Camera stream interrupted");
  });
  return replacement;
}

function startStream({ resetBackoff = true, message = "Connecting to camera" } = {}) {
  clearStreamReconnect();
  if (resetBackoff) viewState.streamReconnectAttempt = 0;
  viewState.paused = false;
  viewState.streamLoaded = false;
  viewState.streamStartedAt = Date.now();
  elements.pauseButton.textContent = "Pause";
  elements.streamShell.dataset.state = "connecting";
  showStreamNotice(message);
  refreshStreamFallback();
  replaceStreamElement().src = `/stream?advance_headers=1&dual_final_frames=1&t=${Date.now()}`;
}

function scheduleStreamReconnect(message, { immediate = false } = {}) {
  if (viewState.paused) return;
  if (immediate) {
    clearStreamReconnect();
    viewState.streamReconnectAttempt = 0;
  } else if (viewState.streamReconnectTimer !== null) {
    return;
  }
  if (!navigator.onLine) {
    elements.streamShell.dataset.state = "offline";
    showStreamNotice("Network offline / waiting to reconnect");
    return;
  }

  refreshStreamFallback();

  const delay = immediate ? 0 : streamReconnectDelay(viewState.streamReconnectAttempt);
  if (!immediate) viewState.streamReconnectAttempt += 1;
  elements.streamShell.dataset.state = "retrying";
  showStreamNotice(
    delay === 0
      ? `${message} / reconnecting`
      : `${message} / retrying in ${Math.ceil(delay / 1000)}s`,
  );
  viewState.streamReconnectTimer = window.setTimeout(() => {
    viewState.streamReconnectTimer = null;
    startStream({ resetBackoff: false, message: "Reconnecting to camera" });
  }, delay);
}

function pauseStream() {
  clearStreamReconnect();
  viewState.streamReconnectAttempt = 0;
  viewState.paused = true;
  viewState.streamLoaded = false;
  viewState.streamStartedAt = null;
  elements.pauseButton.textContent = "Resume";
  elements.streamShell.dataset.state = "paused";
  refreshStreamFallback();
  replaceStreamElement();
  showStreamNotice("Live view paused");
}

function inspectStreamHealth() {
  if (viewState.paused || document.hidden || viewState.streamReconnectTimer !== null) return;
  if (elements.stream.naturalWidth > 0 && elements.stream.naturalHeight > 0) {
    if (!viewState.streamLoaded) markStreamReady(elements.stream);
    return;
  }
  if (
    viewState.streamStartedAt !== null
    && Date.now() - viewState.streamStartedAt >= streamConnectTimeoutMs
  ) {
    viewState.streamLoaded = false;
    scheduleStreamReconnect("Live view interrupted");
  }
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
  const { automation, camera, feed, integrations, system, warnings } = status;
  document.title = status.title;
  elements.appTitle.textContent = status.title;
  elements.appVersion.textContent = `v${status.version}`;
  elements.footerVersion.textContent = `${status.title} v${status.version}`;
  elements.footerHost.textContent = system.hostname;
  elements.cameraSource.textContent = camera.device;
  setHealthState(status.state);

  const feedOnline = Boolean(feed.ok && feed.online && !feed.stale);
  const previousFeedOnline = viewState.streamFeedOnline;
  viewState.streamFeedOnline = feedOnline;
  elements.feedValue.textContent = feedOnline ? "Online" : feed.stale ? "Stale" : "Unavailable";
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

  renderPowerStatus(system.power, system.undervoltage_seen);

  elements.storageValue.textContent = `${formatBytes(system.disk_free_bytes)} free`;
  elements.storageDetail.textContent = `${system.disk_free_percent}% available`;

  elements.systemValue.textContent = system.temperature_c == null ? system.hostname : `${system.temperature_c} C`;
  elements.systemDetail.textContent = formatDuration(system.uptime_seconds);

  renderAlertBatching(automation?.alert_batching || { enabled: false });
  renderFeedRecovery(automation?.feed_recovery || null);
  renderHealthAlerts(automation?.health_alerts || null);

  if (!viewState.webhookBusy) {
    renderWebhookIntegration(integrations?.home_assistant || { configured: false });
  }

  if (feed.frame_timestamp) {
    const captured = new Date(feed.frame_timestamp * 1000);
    const age = feed.frame_age_seconds == null ? "" : ` / ${feed.frame_age_seconds.toFixed(1)}s old`;
    elements.frameStatus.textContent = `${dateTime.format(captured)}${age}`;
  } else {
    elements.frameStatus.textContent = feed.error
      ? "Latest frame retained / waiting for camera"
      : "Waiting for the first camera frame";
  }

  if (warnings.length) {
    elements.warningCopy.textContent = warnings.join(" / ");
    elements.warningBanner.hidden = false;
  } else {
    elements.warningBanner.hidden = true;
  }

  if (!feedOnline && !viewState.paused) {
    viewState.streamLoaded = false;
    scheduleStreamReconnect(feed.stale ? "Camera frame is stale" : "Camera feed unavailable");
  } else if (previousFeedOnline === false && !viewState.paused) {
    scheduleStreamReconnect("Camera recovered", { immediate: true });
  } else if (viewState.streamLoaded && !viewState.paused) {
    hideStreamNotice();
  }
}

function renderPowerStatus(power, legacyUndervoltage) {
  const state = power?.state || "unknown";
  const currentIssues = Array.isArray(power?.current_issues) ? power.current_issues : [];
  const occurredIssues = Array.isArray(power?.occurred_issues) ? power.occurred_issues : [];
  elements.powerMetric.dataset.state = state;

  if (state === "active") {
    elements.powerValue.textContent = power.under_voltage_now ? "Undervoltage now" : "Throttling now";
    elements.powerDetail.textContent = currentIssues.join(" / ") || "Pi hardware limit active";
  } else if (state === "recovered") {
    elements.powerValue.textContent = "Recovered";
    elements.powerDetail.textContent = "Recent undervoltage / stable now";
  } else if (state === "recent") {
    elements.powerValue.textContent = "Recent warning";
    elements.powerDetail.textContent = "Current hardware flags unavailable";
  } else if (state === "historical") {
    elements.powerValue.textContent = "Past issue";
    elements.powerDetail.textContent = `${occurredIssues.join(" / ")} since boot`;
  } else if (state === "stable") {
    elements.powerValue.textContent = "Stable";
    elements.powerDetail.textContent = "No active throttling flags";
  } else if (legacyUndervoltage === true) {
    elements.powerValue.textContent = "Recent warning";
    elements.powerDetail.textContent = "Check supply and USB load";
  } else {
    elements.powerValue.textContent = "Unknown";
    elements.powerDetail.textContent = "Power telemetry unavailable";
  }
}

function renderAlertBatching(batching) {
  const enabled = Boolean(batching.enabled);
  elements.alertBatchRow.dataset.state = enabled ? "active" : "inactive";
  elements.alertBatchState.textContent = enabled ? "On" : "Off";
  if (enabled) {
    const windowSeconds = Number(batching.window_seconds);
    const windowLabel = Number.isInteger(windowSeconds) ? windowSeconds : windowSeconds.toFixed(1);
    elements.alertBatchDetail.textContent = `${windowLabel}s window / up to ${batching.max_photos} photos`;
  } else {
    elements.alertBatchDetail.textContent = "Immediate single alerts";
  }
}

function recoveryDetail(recovery) {
  if (!recovery?.state) return "Waiting for recovery status";
  const state = recovery.state;
  const restarts = Number(state.restart_count) || 0;
  const restartLabel = restarts === 1 ? "1 recovery" : `${restarts} recoveries`;
  const alertsLabel = recovery.telegram_alerts ? " / Telegram alerts" : "";
  if (state.status === "healthy") return `Healthy / ${restartLabel}${alertsLabel}`;
  if (state.status === "failing") {
    return `${state.consecutive_failures}/${recovery.failure_threshold} failed checks / ${state.last_reason}`;
  }
  if (state.status === "restarted") {
    const when = state.last_restart_at ? formatRelative(state.last_restart_at) : "recently";
    return `Stream restarted ${when} / ${restartLabel}`;
  }
  if (state.status === "cooldown") return `Restart cooldown / ${state.last_reason}`;
  if (state.status === "failed") return `Restart failed / ${state.last_reason}`;
  if (state.status === "unavailable") return state.last_reason || "Recovery state unavailable";
  return `Waiting for first check / ${recovery.failure_threshold} failures required`;
}

function renderFeedRecovery(recovery) {
  viewState.recoveryState = recovery;
  renderRecoveryHistory(recovery?.state?.events || []);
  if (viewState.serviceStates.recovery) {
    renderService("recovery", viewState.serviceStates.recovery);
  }
}

function healthAlertDetail(healthAlerts) {
  if (!healthAlerts?.state?.initialized) return "Waiting for first health sample";
  const trackers = Array.isArray(healthAlerts.state.trackers) ? healthAlerts.state.trackers : [];
  const active = trackers.filter((tracker) => tracker.active);
  const activeLabel = active.length
    ? `${active.length} active ${active.length === 1 ? "condition" : "conditions"}`
    : "All clear";
  const pending = Array.isArray(healthAlerts.state.pending_alerts)
    ? healthAlerts.state.pending_alerts.length
    : 0;
  const delivery = healthAlerts.telegram_alerts ? "Telegram alerts" : "local monitoring";
  return pending ? `${activeLabel} / ${pending} pending / ${delivery}` : `${activeLabel} / ${delivery}`;
}

function renderHealthAlerts(healthAlerts) {
  viewState.healthAlertState = healthAlerts;
  if (viewState.serviceStates.health) {
    renderService("health", viewState.serviceStates.health);
  }
}

function recoveryEventLabel(event) {
  if (event.type === "feed_unhealthy") return "Feed became unhealthy";
  if (event.type === "feed_recovered") return "Feed recovered";
  if (event.type === "stream_restarted") {
    return event.trigger === "manual" ? "Manual feed restart" : "Automatic feed restart";
  }
  if (event.type === "restart_failed") {
    return event.trigger === "manual" ? "Manual restart failed" : "Automatic restart failed";
  }
  return "Recovery update";
}

function renderRecoveryHistory(events) {
  const recent = Array.isArray(events) ? events.slice(-5).reverse() : [];
  elements.recoveryHistoryList.replaceChildren();
  elements.recoveryHistoryMeta.textContent = recent.length
    ? `${recent.length} recent ${recent.length === 1 ? "incident" : "incidents"}`
    : "No incidents recorded";

  recent.forEach((event) => {
    const item = document.createElement("li");
    const copy = document.createElement("div");
    const label = document.createElement("strong");
    const reason = document.createElement("span");
    const time = document.createElement("time");
    label.textContent = recoveryEventLabel(event);
    reason.textContent = event.reason || "No detail recorded";
    time.dateTime = event.occurred_at || "";
    time.textContent = event.occurred_at ? formatRelative(event.occurred_at) : "time unavailable";
    copy.append(label, reason);
    item.append(copy, time);
    elements.recoveryHistoryList.append(item);
  });
}

async function restartFeed() {
  if (viewState.recoveryBusy) return;
  viewState.recoveryBusy = true;
  const currentService = viewState.serviceStates.recovery;
  if (currentService) renderService("recovery", currentService);
  elements.servicesMeta.textContent = "Restarting feed";
  try {
    const state = await requestJSON("/api/recovery/restart", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    renderFeedRecovery({ ...(viewState.recoveryState || {}), state });
    elements.servicesMeta.textContent = "Feed restart requested";
    setTimeout(startStream, 1200);
  } catch (error) {
    elements.servicesMeta.textContent = error.message;
  } finally {
    viewState.recoveryBusy = false;
    if (viewState.serviceStates.recovery) {
      renderService("recovery", viewState.serviceStates.recovery);
    }
  }
  await refreshStatus();
  await refreshServices();
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
  if (viewState.statusBusy || document.hidden) return;
  viewState.statusBusy = true;
  try {
    renderStatus(await requestJSON("/api/status"));
  } catch (error) {
    setHealthState("offline");
    elements.frameStatus.textContent = error.message;
    viewState.streamFeedOnline = false;
    if (!viewState.streamLoaded) {
      scheduleStreamReconnect("Dashboard cannot reach the camera service");
    }
  } finally {
    viewState.statusBusy = false;
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
  if (serviceId === "recovery" && state.available && state.active) {
    target.detail.textContent = recoveryDetail(viewState.recoveryState);
  } else if (serviceId === "health" && state.available && state.active) {
    target.detail.textContent = healthAlertDetail(viewState.healthAlertState);
  } else {
    target.detail.textContent = state.available
      ? `${state.name} / ${state.sub_state}`
      : state.error || "System state unavailable";
  }
  target.toggle.checked = Boolean(state.active);
  target.toggle.disabled = viewState.serviceBusy.has(serviceId) || !state.available;
  target.toggle.setAttribute("aria-busy", String(viewState.serviceBusy.has(serviceId)));
  if (serviceId === "recovery") {
    elements.recoveryRestartButton.disabled = viewState.recoveryBusy || !state.available;
    elements.recoveryRestartButton.textContent = viewState.recoveryBusy ? "Restarting" : "Restart feed";
    elements.recoveryRestartButton.setAttribute("aria-busy", String(viewState.recoveryBusy));
  }
}

function renderServices(services) {
  Object.entries(services).forEach(([serviceId, state]) => renderService(serviceId, state));
  const total = Object.keys(serviceElements).length;
  const available = Object.values(services).filter((state) => state.available).length;
  const active = Object.values(services).filter((state) => state.active).length;
  elements.servicesMeta.textContent = available === total ? `${active} of ${total} active` : "Service issue";
}

async function refreshServices() {
  if (viewState.servicesBusy || document.hidden) return;
  viewState.servicesBusy = true;
  try {
    const payload = await requestJSON("/api/services");
    if (viewState.serviceBusy.size === 0) renderServices(payload.services || {});
  } catch (error) {
    if (viewState.serviceBusy.size > 0) return;
    elements.servicesMeta.textContent = error.message;
    Object.keys(serviceElements).forEach((serviceId) => {
      renderService(serviceId, {
        active: false,
        available: false,
        error: "Service status unavailable",
        state: "unavailable",
      });
    });
  } finally {
    viewState.servicesBusy = false;
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
    renderServices(viewState.serviceStates);
  }
  window.setTimeout(refreshServices, 750);
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
  try {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), requestTimeoutMs);
    try {
      const response = await fetch(url, {
        cache: "no-store",
        ...options,
        signal: controller.signal,
      });
      let payload = {};
      try {
        payload = await response.json();
      } catch (_error) {
        payload = {};
      }
      if (!response.ok) throw new Error(payload.error || `Request failed: ${response.status}`);
      return payload;
    } finally {
      window.clearTimeout(timeout);
    }
  } catch (error) {
    if (error.name === "AbortError") throw new Error("Request timed out");
    throw error;
  }
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

function captureIndex() {
  return viewState.events.findIndex((event) => event.name === viewState.captureName);
}

function captureTotal() {
  let total = viewState.events.length;
  if (viewState.eventSelection) {
    total = Number(viewState.eventSelection.count);
  } else if (viewState.eventSummary) {
    total = viewState.eventWindow === "all"
      ? Number(viewState.eventSummary.retained_count)
      : Number(viewState.eventSummary.window_count);
  }
  return Number.isFinite(total) && total > 0 ? total : viewState.events.length;
}

function preloadAdjacentCaptures(index) {
  [index - 1, index + 1].forEach((candidate) => {
    const event = viewState.events[candidate];
    if (!event) return;
    const image = new Image();
    image.decoding = "async";
    image.fetchPriority = "low";
    image.src = event.url;
  });
}

function renderCaptureViewer() {
  if (!viewState.captureName) return;
  const index = captureIndex();
  if (index < 0) {
    if (elements.captureDialog.open) elements.captureDialog.close();
    return;
  }

  const event = viewState.events[index];
  if (elements.captureImage.dataset.captureName !== event.name) {
    elements.captureStage.dataset.state = "loading";
    elements.captureImageStatus.textContent = "Loading capture";
    elements.captureImageStatus.hidden = false;
    elements.captureImage.dataset.captureName = event.name;
    elements.captureImage.src = event.url;
  }
  elements.captureImage.alt = `Motion capture from ${dateTime.format(new Date(event.captured_at))}`;
  elements.captureDownload.href = event.url;
  elements.captureDownload.download = event.name;
  elements.captureTime.dateTime = event.captured_at;
  elements.captureTime.textContent = dateTime.format(new Date(event.captured_at));
  elements.captureSize.textContent = formatBytes(event.size_bytes);
  elements.capturePosition.textContent = viewState.captureLoadingOlder
    ? "Loading older captures"
    : `${index + 1} of ${captureTotal()}`;
  elements.capturePrevious.disabled = viewState.captureLoadingOlder || index === 0;
  elements.captureNext.disabled = viewState.captureLoadingOlder
    || (index === viewState.events.length - 1 && viewState.eventCursor == null);
}

function openCapture(event) {
  viewState.captureName = event.name;
  if (!elements.captureDialog.open) elements.captureDialog.showModal();
  renderCaptureViewer();
}

async function moveCapture(direction) {
  if (!elements.captureDialog.open || viewState.captureLoadingOlder) return;
  const index = captureIndex();
  const target = index + direction;
  if (target >= 0 && target < viewState.events.length) {
    viewState.captureName = viewState.events[target].name;
    renderCaptureViewer();
    return;
  }
  if (direction < 0 || viewState.eventCursor == null) return;

  const currentName = viewState.captureName;
  viewState.captureLoadingOlder = true;
  renderCaptureViewer();
  const loaded = await refreshEvents({ append: true });
  viewState.captureLoadingOlder = false;
  const currentIndex = viewState.events.findIndex((event) => event.name === currentName);
  if (loaded && currentIndex >= 0 && currentIndex + 1 < viewState.events.length) {
    viewState.captureName = viewState.events[currentIndex + 1].name;
  }
  renderCaptureViewer();
}

function resetCaptureViewer() {
  viewState.captureLoadingOlder = false;
  viewState.captureName = null;
  elements.captureImage.removeAttribute("src");
  delete elements.captureImage.dataset.captureName;
  elements.captureStage.dataset.state = "idle";
  elements.captureImageStatus.hidden = true;
}

function createEventItem(event, index = 0) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "event-item";
  button.dataset.state = "loading";
  button.title = `Open capture from ${dateTime.format(new Date(event.captured_at))}`;

  const image = document.createElement("img");
  image.src = event.thumbnail_url || event.url;
  image.alt = `Motion capture from ${dateTime.format(new Date(event.captured_at))}`;
  image.loading = index < 4 ? "eager" : "lazy";
  image.decoding = "async";
  image.fetchPriority = index < 4 ? "high" : "low";
  image.width = 320;
  image.height = 180;
  image.addEventListener("load", () => {
    button.dataset.state = "ready";
  });
  image.addEventListener("error", () => {
    button.dataset.state = "error";
  });

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
  elements.eventGrid.setAttribute("aria-busy", String(busy));
  elements.eventsSection.dataset.state = busy ? "loading" : "ready";
  eventRangeButtons.forEach((button) => {
    button.disabled = busy;
  });
  elements.eventsLoadMore.disabled = busy;
  elements.eventsLoadMore.textContent = busy ? "Loading captures" : "Load older captures";
  elements.activityClear.disabled = busy;
  elements.activityChart.querySelectorAll(".activity-bar").forEach((bar) => {
    bar.disabled = busy || bar.dataset.count === "0";
  });
}

function renderEventSummary() {
  const summary = viewState.eventSummary;
  if (!summary) return;
  const shown = viewState.events.length;
  const storage = formatBytes(summary.retained_size_bytes);
  const selection = viewState.eventSelection;
  if (selection) {
    const period = activityPeriodLabel(selection);
    const range = viewState.eventWindow === "all"
      ? `${summary.retained_count} retained`
      : `${summary.window_count} in ${viewState.eventWindow === "24h" ? "24 hours" : "7 days"}`;
    elements.eventsMeta.textContent = `${shown} shown / ${selection.count} in ${period} / ${range} / ${storage}`;
  } else if (viewState.eventWindow === "all") {
    elements.eventsMeta.textContent = `${shown} shown / ${summary.retained_count} retained / ${storage}`;
  } else {
    const label = viewState.eventWindow === "24h" ? "24 hours" : "7 days";
    elements.eventsMeta.textContent = `${shown} shown / ${summary.window_count} in ${label} / ${summary.retained_count} retained / ${storage}`;
  }

  const retention = summary.retention;
  if (!retention) {
    elements.retentionMeta.textContent = "Archive policy unavailable";
    return;
  }
  const limits = [];
  if (retention.policy.max_files > 0) limits.push(`${retention.policy.max_files} files`);
  if (retention.policy.max_age_days > 0) limits.push(`${retention.policy.max_age_days} days`);
  if (retention.policy.max_bytes > 0) limits.push(formatBytes(retention.policy.max_bytes));
  const policy = limits.length > 0 ? limits.join(" / ") : "no automatic cleanup";
  const current = `${retention.archive.file_count} files / ${formatBytes(retention.archive.size_bytes)}`;
  const pending = retention.cleanup.pending
    ? ` / ${retention.cleanup.file_count} pending cleanup`
    : " / within limits";
  elements.retentionMeta.textContent = `Archive: ${current} / policy ${policy}${pending}`;
}

function activityTick(isoDate) {
  if (!isoDate) return "--";
  const date = new Date(isoDate);
  if (viewState.eventWindow === "24h") return activityTime.format(date);
  if (viewState.eventWindow === "7d") return activityWeekday.format(date);
  return activityDay.format(date);
}

function activityPeriodLabel(period) {
  const start = new Date(period.started_at);
  const end = new Date(period.ended_at);
  if (!Number.isFinite(start.getTime()) || !Number.isFinite(end.getTime())) return "selected period";
  if (viewState.eventWindow === "24h") {
    return `${activityTime.format(start)} - ${activityTime.format(end)}`;
  }
  if (viewState.eventWindow === "7d") {
    return `${activityWeekday.format(start)} ${activityTime.format(start)} - ${activityWeekday.format(end)} ${activityTime.format(end)}`;
  }
  return `${activityDay.format(start)} - ${activityDay.format(end)}`;
}

function selectionMatchesBucket(bucket) {
  const selection = viewState.eventSelection;
  if (!selection) return false;
  const selectionStart = new Date(selection.started_at).getTime();
  const selectionEnd = new Date(selection.ended_at).getTime();
  const bucketStart = new Date(bucket.started_at).getTime();
  const bucketEnd = new Date(bucket.ended_at).getTime();
  if (![selectionStart, selectionEnd, bucketStart, bucketEnd].every(Number.isFinite)) return false;
  const midpoint = selectionStart + ((selectionEnd - selectionStart) / 2);
  return bucketStart <= midpoint && midpoint < bucketEnd;
}

function beginActivityFilter(message) {
  if (elements.captureDialog.open) elements.captureDialog.close();
  viewState.eventCursor = null;
  elements.eventsEmpty.hidden = true;
  elements.eventPagination.hidden = true;
  elements.eventsMeta.textContent = message;
  renderEventActivity();
  refreshEvents();
}

function selectActivityPeriod(bucket) {
  if (viewState.eventsBusy || Number(bucket.count || 0) <= 0) return;
  if (selectionMatchesBucket(bucket)) {
    clearActivityPeriod();
    return;
  }
  viewState.eventSelection = {
    started_at: bucket.started_at,
    ended_at: bucket.ended_at,
    count: Number(bucket.count || 0),
    size_bytes: Number(bucket.size_bytes || 0),
  };
  beginActivityFilter(`Loading ${activityPeriodLabel(viewState.eventSelection)}`);
}

function clearActivityPeriod() {
  if (viewState.eventsBusy || !viewState.eventSelection) return;
  viewState.eventSelection = null;
  beginActivityFilter("Loading full range");
}

function renderEventActivity() {
  const activity = viewState.eventActivity;
  elements.activityClear.hidden = !viewState.eventSelection;
  if (!activity || !Array.isArray(activity.buckets)) {
    elements.activityBand.dataset.state = "unavailable";
    elements.activityRange.textContent = "Activity unavailable";
    elements.activityTotal.textContent = "--";
    elements.activityActive.textContent = "--";
    elements.activityPeak.textContent = "--";
    elements.activityLast.textContent = "--";
    elements.activityChart.replaceChildren();
    elements.activityChart.setAttribute("aria-label", "Motion activity unavailable");
    elements.activityAxisStart.textContent = "--";
    elements.activityAxisMiddle.textContent = "--";
    elements.activityAxisEnd.textContent = "Now";
    return;
  }

  const buckets = activity.buckets;
  const total = buckets.reduce((sum, bucket) => sum + Number(bucket.count || 0), 0);
  const peak = Number(activity.peak_count || 0);
  const rangeLabels = {
    "24h": "Rolling 24 hours",
    "7d": "Rolling 7 days",
    all: "All retained captures",
  };
  elements.activityBand.dataset.state = total > 0 ? "active" : "empty";
  elements.activityRange.textContent = rangeLabels[viewState.eventWindow] || "Selected range";
  elements.activityTotal.textContent = String(total);
  elements.activityActive.textContent = `${activity.active_bucket_count} / ${buckets.length}`;
  elements.activityPeak.textContent = peak && activity.peak_started_at
    ? `${peak} at ${activityTick(activity.peak_started_at)}`
    : "No activity";
  elements.activityLast.textContent = activity.last_captured_at
    ? formatRelative(activity.last_captured_at)
    : "None in range";

  const bars = buckets.map((bucket) => {
    const count = Number(bucket.count || 0);
    const level = peak > 0 && count > 0 ? Math.max(1, Math.ceil((count / peak) * 10)) : 0;
    const selected = selectionMatchesBucket(bucket);
    const period = activityPeriodLabel(bucket);
    const bar = document.createElement("button");
    bar.type = "button";
    bar.className = "activity-bar";
    bar.dataset.count = String(count);
    bar.dataset.level = String(level);
    bar.dataset.peak = String(peak > 0 && count === peak);
    bar.dataset.selected = String(selected);
    bar.disabled = viewState.eventsBusy || count === 0;
    bar.title = `${count} ${count === 1 ? "capture" : "captures"} / ${period}`;
    bar.setAttribute("aria-label", `${count} ${count === 1 ? "capture" : "captures"}, ${period}`);
    bar.setAttribute("aria-pressed", String(selected));
    bar.addEventListener("click", () => selectActivityPeriod(bucket));
    return bar;
  });
  elements.activityChart.replaceChildren(...bars);
  elements.activityChart.setAttribute(
    "aria-label",
    `${total} motion ${total === 1 ? "capture" : "captures"} across ${buckets.length} periods; peak ${peak}`,
  );
  const middle = buckets[Math.floor(buckets.length / 2)] || null;
  elements.activityAxisStart.textContent = activityTick(activity.starts_at);
  elements.activityAxisMiddle.textContent = activityTick(middle?.started_at);
  elements.activityAxisEnd.textContent = viewState.eventWindow === "24h"
    ? activityTime.format(new Date(activity.ends_at))
    : "Now";
}

function renderEvents({ append = false, pageEvents = [], preserveItems = false } = {}) {
  if (append) {
    const offset = elements.eventGrid.children.length;
    elements.eventGrid.append(
      ...pageEvents.map((event, index) => createEventItem(event, offset + index)),
    );
  } else if (!preserveItems) {
    elements.eventGrid.replaceChildren(...viewState.events.map(createEventItem));
  }
  elements.eventsEmpty.hidden = viewState.events.length > 0;
  elements.eventsEmpty.textContent = viewState.eventSelection
    ? "No motion captures in this period."
    : "No motion captures in this range.";
  elements.eventPagination.hidden = viewState.eventCursor == null;
  renderEventActivity();
  renderEventSummary();
  if (elements.captureDialog.open) renderCaptureViewer();
}

async function performEventRefresh({ append = false } = {}) {
  setEventsBusy(true);
  try {
    const query = new URLSearchParams({ window: viewState.eventWindow, limit: "12" });
    if (append && viewState.eventCursor != null) query.set("before", String(viewState.eventCursor));
    if (viewState.eventSelection) {
      query.set("period_start", String(new Date(viewState.eventSelection.started_at).getTime() / 1000));
      query.set("period_end", String(new Date(viewState.eventSelection.ended_at).getTime() / 1000));
    }
    const payload = await requestJSON(`/api/events?${query}`);
    const pageEvents = payload.events;
    const preserveItems = !append
      && viewState.events.length === pageEvents.length
      && viewState.events.every((event, index) => event.name === pageEvents[index].name);
    viewState.events = append ? [...viewState.events, ...pageEvents] : pageEvents;
    viewState.eventCursor = payload.next_before;
    viewState.eventSummary = payload.summary;
    viewState.eventActivity = payload.activity;
    viewState.eventSelection = payload.selection;
    renderEvents({ append, pageEvents, preserveItems });
    return true;
  } catch (error) {
    if (!append) {
      viewState.events = [];
      viewState.eventCursor = null;
      viewState.eventSummary = null;
      viewState.eventActivity = null;
      elements.eventGrid.replaceChildren();
      elements.eventsEmpty.hidden = false;
      elements.eventsEmpty.textContent = error.message;
    }
    elements.eventPagination.hidden = append ? viewState.eventCursor == null : true;
    elements.eventsMeta.textContent = "Archive unavailable";
    elements.retentionMeta.textContent = "Archive policy unavailable";
    renderEventActivity();
    return false;
  } finally {
    setEventsBusy(false);
  }
}

async function refreshEvents({ append = false } = {}) {
  if (eventRefreshRequest) {
    if (!append || !(await eventRefreshRequest)) return false;
  }

  const request = performEventRefresh({ append });
  eventRefreshRequest = request;
  try {
    return await request;
  } finally {
    if (eventRefreshRequest === request) eventRefreshRequest = null;
  }
}

function selectEventWindow(windowName) {
  if (viewState.eventsBusy || windowName === viewState.eventWindow) return;
  if (elements.captureDialog.open) elements.captureDialog.close();
  viewState.eventWindow = windowName;
  viewState.eventCursor = null;
  viewState.eventSelection = null;
  eventRangeButtons.forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.eventWindow === windowName));
  });
  elements.eventsEmpty.hidden = true;
  elements.eventPagination.hidden = true;
  elements.eventsMeta.textContent = "Loading selected range";
  refreshEvents();
}

function updateClock() {
  const now = new Date();
  elements.localClock.dateTime = now.toISOString();
  elements.localClock.textContent = clockTime.format(now);
}

function initializeMonitoring() {
  if (viewState.monitoringInitialized) return;
  viewState.monitoringInitialized = true;
  refreshServices();
  refreshPolicy();
}

function initializeCameraTuning() {
  if (viewState.cameraInitialized) return;
  viewState.cameraInitialized = true;
  refreshCameraState();
}

function initializeEvents() {
  if (viewState.eventsInitialized) return;
  viewState.eventsInitialized = true;
  refreshEvents();
}

elements.pauseButton.addEventListener("click", togglePause);
elements.reconnectButton.addEventListener("click", () => startStream());
elements.snapshotButton.addEventListener("click", saveSnapshot);
elements.fullscreenButton.addEventListener("click", toggleFullscreen);
elements.cameraRefreshButton.addEventListener("click", () => refreshCameraState("Controls refreshed", true));
elements.quietHoursForm.addEventListener("submit", applyPolicy);
[elements.quietHoursToggle, elements.quietHoursStart, elements.quietHoursEnd].forEach((input) => {
  input.addEventListener("change", markPolicyDirty);
});
elements.webhookTestButton.addEventListener("click", sendWebhookTest);
elements.recoveryRestartButton.addEventListener("click", restartFeed);
eventRangeButtons.forEach((button) => {
  button.addEventListener("click", () => selectEventWindow(button.dataset.eventWindow));
});
elements.activityClear.addEventListener("click", clearActivityPeriod);
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
elements.capturePrevious.addEventListener("click", () => moveCapture(-1));
elements.captureNext.addEventListener("click", () => moveCapture(1));
elements.dialogClose.addEventListener("click", () => elements.captureDialog.close());
elements.captureImage.addEventListener("load", () => {
  elements.captureStage.dataset.state = "ready";
  elements.captureImageStatus.hidden = true;
  const loadedName = elements.captureImage.dataset.captureName;
  scheduleIdle(() => {
    if (
      elements.captureDialog.open
      && elements.captureImage.dataset.captureName === loadedName
    ) {
      preloadAdjacentCaptures(captureIndex());
    }
  }, 500);
});
elements.captureImage.addEventListener("error", () => {
  elements.captureStage.dataset.state = "error";
  elements.captureImageStatus.textContent = "Capture unavailable";
  elements.captureImageStatus.hidden = false;
});
elements.captureDialog.addEventListener("close", resetCaptureViewer);
elements.captureDialog.addEventListener("click", (event) => {
  if (event.target === elements.captureDialog) elements.captureDialog.close();
});
document.addEventListener("keydown", (event) => {
  if (
    !elements.captureDialog.open
    || event.defaultPrevented
    || event.altKey
    || event.ctrlKey
    || event.metaKey
  ) return;
  if (event.key === "ArrowLeft") {
    event.preventDefault();
    moveCapture(-1);
  } else if (event.key === "ArrowRight") {
    event.preventDefault();
    moveCapture(1);
  }
});
document.addEventListener("fullscreenchange", () => {
  elements.fullscreenButton.textContent = document.fullscreenElement ? "Exit fullscreen" : "Fullscreen";
});
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    clearStreamReconnect();
    viewState.streamLoaded = false;
    viewState.streamStartedAt = null;
    refreshStreamFallback();
    replaceStreamElement();
    return;
  }
  if (!viewState.paused) {
    startStream({ message: "Refreshing live view" });
  }
  refreshStatus();
  updateClock();
  scheduleIdle(() => {
    if (viewState.monitoringInitialized) {
      refreshServices();
      refreshPolicy();
    }
    if (viewState.eventsInitialized && viewState.events.length <= 12) refreshEvents();
    if (viewState.cameraInitialized) refreshCameraState();
  }, 500);
});
window.addEventListener("offline", () => {
  clearStreamReconnect();
  viewState.streamFeedOnline = false;
  viewState.streamLoaded = false;
  elements.streamShell.dataset.state = "offline";
  showStreamNotice("Network offline / waiting to reconnect");
});
window.addEventListener("online", () => {
  if (!viewState.paused) scheduleStreamReconnect("Network restored", { immediate: true });
  refreshStatus();
  scheduleIdle(() => {
    if (viewState.monitoringInitialized) refreshServices();
    if (viewState.eventsInitialized && viewState.events.length <= 12) refreshEvents();
  }, 500);
});
startStream();
refreshStatus();
runWhenNear(elements.monitoringSection, initializeMonitoring);
runWhenNear(elements.tuningSection, initializeCameraTuning);
runWhenNear(elements.eventsSection, initializeEvents);
updateClock();
setInterval(inspectStreamHealth, 1000);
setInterval(() => {
  if (!document.hidden) refreshStatus();
}, 10000);
setInterval(() => {
  if (!document.hidden && viewState.monitoringInitialized) refreshServices();
}, 10000);
setInterval(() => {
  if (!document.hidden && viewState.monitoringInitialized) refreshPolicy();
}, 30000);
setInterval(() => {
  if (!document.hidden && viewState.eventsInitialized && viewState.events.length <= 12) refreshEvents();
}, 30000);
setInterval(() => {
  if (!document.hidden && viewState.cameraInitialized) refreshCameraState();
}, 60000);
setInterval(() => {
  if (!document.hidden) updateClock();
}, 1000);
