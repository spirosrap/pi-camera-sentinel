"use strict";

const elements = {
  addButton: document.querySelector("#motion-mask-add"),
  applyButton: document.querySelector("#motion-mask-apply"),
  canvas: document.querySelector("#motion-mask-canvas"),
  clearButton: document.querySelector("#motion-mask-clear"),
  frameTime: document.querySelector("#motion-mask-frame-time"),
  message: document.querySelector("#motion-mask-message"),
  meta: document.querySelector("#motion-mask-meta"),
  preview: document.querySelector("#motion-mask-preview"),
  previewNotice: document.querySelector("#motion-mask-preview-notice"),
  previewShell: document.querySelector("#motion-mask-preview-shell"),
  refreshButton: document.querySelector("#motion-mask-refresh"),
  removeButton: document.querySelector("#motion-mask-remove"),
  resetButton: document.querySelector("#motion-mask-reset"),
};

const state = {
  busy: false,
  dirty: false,
  draft: null,
  drawing: false,
  frameBusy: false,
  pointerStart: null,
  regions: [],
  saved: null,
  selected: -1,
};

const minimumDrawnMaskSize = 0.02;
const requestTimeoutMs = 10000;
const frameTime = new Intl.DateTimeFormat(undefined, {
  hour: "numeric",
  minute: "2-digit",
  second: "2-digit",
});

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

function cloneRegions(regions = []) {
  return regions.map((region) => ({
    x: Number(region.x),
    y: Number(region.y),
    width: Number(region.width),
    height: Number(region.height),
  }));
}

function regionsEqual(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
}

function setMessage(message, status = "idle") {
  elements.message.textContent = message;
  elements.message.dataset.state = status;
}

function renderMeta() {
  const count = state.regions.length;
  const noun = count === 1 ? "area" : "areas";
  elements.meta.textContent = `${count} ignored ${noun}${state.dirty ? " / unsaved" : ""}`;
}

function updateControls() {
  const ready = state.saved !== null;
  const maximum = state.saved?.max_regions || 0;
  elements.addButton.disabled = state.busy || !ready || (!state.drawing && state.regions.length >= maximum);
  elements.addButton.textContent = state.drawing ? "Cancel" : "Add area";
  elements.addButton.setAttribute("aria-pressed", String(state.drawing));
  elements.removeButton.disabled = state.busy || state.selected < 0;
  elements.clearButton.disabled = state.busy || state.regions.length === 0;
  elements.resetButton.disabled = state.busy || !state.dirty;
  elements.refreshButton.disabled = state.frameBusy;
  elements.applyButton.disabled = state.busy || !state.dirty;
  elements.previewShell.classList.toggle("is-drawing", state.drawing);
  renderMeta();
}

function setBusy(busy) {
  state.busy = busy;
  updateControls();
}

function canvasPoint(event) {
  const bounds = elements.canvas.getBoundingClientRect();
  return {
    x: Math.min(1, Math.max(0, (event.clientX - bounds.left) / bounds.width)),
    y: Math.min(1, Math.max(0, (event.clientY - bounds.top) / bounds.height)),
  };
}

function normalizedRegion(start, end) {
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

function drawRegions() {
  const bounds = elements.canvas.getBoundingClientRect();
  if (!bounds.width || !bounds.height) return;
  const ratio = window.devicePixelRatio || 1;
  const width = Math.round(bounds.width * ratio);
  const height = Math.round(bounds.height * ratio);
  if (elements.canvas.width !== width || elements.canvas.height !== height) {
    elements.canvas.width = width;
    elements.canvas.height = height;
  }

  const context = elements.canvas.getContext("2d");
  if (!context) return;
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  context.clearRect(0, 0, bounds.width, bounds.height);

  const regions = state.draft ? [...state.regions, state.draft] : state.regions;
  regions.forEach((region, index) => {
    const x = region.x * bounds.width;
    const y = region.y * bounds.height;
    const regionWidth = region.width * bounds.width;
    const regionHeight = region.height * bounds.height;
    const selected = index === state.selected || index >= state.regions.length;
    context.fillStyle = selected ? "rgba(182, 58, 53, 0.38)" : "rgba(182, 58, 53, 0.24)";
    context.strokeStyle = selected ? "#ffffff" : "rgba(255, 255, 255, 0.88)";
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

function regionAt(point) {
  for (let index = state.regions.length - 1; index >= 0; index -= 1) {
    const region = state.regions[index];
    if (
      point.x >= region.x
      && point.x <= region.x + region.width
      && point.y >= region.y
      && point.y <= region.y + region.height
    ) return index;
  }
  return -1;
}

function stopDrawing() {
  state.drawing = false;
  state.pointerStart = null;
  state.draft = null;
  updateControls();
  drawRegions();
}

function markDirty(message = "Unsaved ignored areas") {
  state.dirty = !regionsEqual(state.regions, state.saved?.regions || []);
  setMessage(state.dirty ? message : "Ignored areas up to date");
  updateControls();
  drawRegions();
}

function renderRegions(payload, message = "Ignored areas up to date") {
  state.saved = {
    ...payload,
    regions: cloneRegions(payload.regions),
  };
  state.regions = cloneRegions(payload.regions);
  state.selected = -1;
  state.dirty = false;
  stopDrawing();
  setBusy(false);
  setMessage(message, "success");
  drawRegions();
}

async function refreshRegions(force = false) {
  if (state.busy || state.drawing || state.pointerStart || (state.dirty && !force)) return;
  setBusy(true);
  setMessage("Reading ignored areas");
  try {
    renderRegions(await requestJSON("/api/masks"));
  } catch (error) {
    state.saved = null;
    setBusy(false);
    setMessage(error.message, "error");
  }
}

function refreshFrame() {
  state.frameBusy = true;
  elements.previewNotice.textContent = "Loading still frame";
  elements.previewNotice.hidden = false;
  elements.frameTime.textContent = "Refreshing";
  elements.frameTime.removeAttribute("datetime");
  elements.preview.src = `/snapshot?t=${Date.now()}`;
  updateControls();
}

function toggleDrawing() {
  if (state.drawing) {
    stopDrawing();
    setMessage("Drawing cancelled");
    return;
  }
  if (!state.saved || state.regions.length >= state.saved.max_regions) return;
  state.selected = -1;
  state.drawing = true;
  setMessage(`Drawing ignored area ${state.regions.length + 1}`);
  updateControls();
  drawRegions();
}

function removeSelected() {
  if (state.selected < 0) return;
  state.regions.splice(state.selected, 1);
  state.selected = -1;
  markDirty();
}

function clearRegions() {
  state.regions = [];
  state.selected = -1;
  stopDrawing();
  markDirty();
}

function resetRegions() {
  if (!state.saved) return;
  state.regions = cloneRegions(state.saved.regions);
  state.selected = -1;
  state.dirty = false;
  stopDrawing();
  setMessage("Unsaved changes discarded");
  updateControls();
  drawRegions();
}

async function applyRegions() {
  if (!state.dirty || state.busy) return;
  setBusy(true);
  setMessage("Applying ignored areas");
  try {
    const payload = await requestJSON("/api/masks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ regions: state.regions }),
    });
    renderRegions(payload, "Ignored areas applied");
  } catch (error) {
    setBusy(false);
    setMessage(error.message, "error");
  }
}

function beginPointer(event) {
  if (!state.saved || state.busy) return;
  const point = canvasPoint(event);
  if (!state.drawing) {
    state.selected = regionAt(point);
    updateControls();
    drawRegions();
    return;
  }
  event.preventDefault();
  state.pointerStart = point;
  state.draft = normalizedRegion(point, point);
  elements.canvas.setPointerCapture(event.pointerId);
  drawRegions();
}

function movePointer(event) {
  if (!state.pointerStart) return;
  event.preventDefault();
  state.draft = normalizedRegion(state.pointerStart, canvasPoint(event));
  drawRegions();
}

function finishPointer(event) {
  if (!state.pointerStart) return;
  event.preventDefault();
  const region = normalizedRegion(state.pointerStart, canvasPoint(event));
  if (elements.canvas.hasPointerCapture(event.pointerId)) {
    elements.canvas.releasePointerCapture(event.pointerId);
  }
  state.pointerStart = null;
  state.draft = null;
  state.drawing = false;
  if (region.width >= minimumDrawnMaskSize && region.height >= minimumDrawnMaskSize) {
    state.regions.push(region);
    state.selected = state.regions.length - 1;
    markDirty();
  } else {
    setMessage("Area is too small", "error");
    updateControls();
    drawRegions();
  }
}

function cancelPointer(event) {
  if (state.pointerStart && elements.canvas.hasPointerCapture(event.pointerId)) {
    elements.canvas.releasePointerCapture(event.pointerId);
  }
  stopDrawing();
  setMessage("Drawing cancelled");
}

elements.preview.addEventListener("load", () => {
  if (elements.preview.naturalWidth && elements.preview.naturalHeight) {
    elements.previewShell.style.aspectRatio = `${elements.preview.naturalWidth} / ${elements.preview.naturalHeight}`;
  }
  const capturedAt = new Date();
  elements.frameTime.dateTime = capturedAt.toISOString();
  elements.frameTime.textContent = `Refreshed ${frameTime.format(capturedAt)}`;
  elements.previewNotice.hidden = true;
  state.frameBusy = false;
  updateControls();
  drawRegions();
});

elements.preview.addEventListener("error", () => {
  elements.previewNotice.textContent = "Still frame unavailable";
  elements.previewNotice.hidden = false;
  elements.frameTime.textContent = "Unavailable";
  state.frameBusy = false;
  updateControls();
});

elements.addButton.addEventListener("click", toggleDrawing);
elements.removeButton.addEventListener("click", removeSelected);
elements.clearButton.addEventListener("click", clearRegions);
elements.resetButton.addEventListener("click", resetRegions);
elements.refreshButton.addEventListener("click", refreshFrame);
elements.applyButton.addEventListener("click", applyRegions);
elements.canvas.addEventListener("pointerdown", beginPointer);
elements.canvas.addEventListener("pointermove", movePointer);
elements.canvas.addEventListener("pointerup", finishPointer);
elements.canvas.addEventListener("pointercancel", cancelPointer);

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && state.drawing) {
    event.preventDefault();
    stopDrawing();
    setMessage("Drawing cancelled");
  } else if ((event.key === "Delete" || event.key === "Backspace") && state.selected >= 0) {
    event.preventDefault();
    removeSelected();
  }
});

window.addEventListener("beforeunload", (event) => {
  if (!state.dirty) return;
  event.preventDefault();
  event.returnValue = "";
});

document.addEventListener("visibilitychange", () => {
  if (!document.hidden) refreshRegions();
});

if ("ResizeObserver" in window) {
  new ResizeObserver(drawRegions).observe(elements.previewShell);
} else {
  window.addEventListener("resize", drawRegions);
}

refreshRegions();
refreshFrame();
