const state = {
  symbol: "sh000852",
  klines: [],
  pens: [],
  analysis: { segments: [], centers: [], signals: [] },
  selectedPenId: null,
  hitPens: [],
  zoomLevel: 1,
  scrollOffset: 0,
};
const MIN_VISIBLE = 30;
const MAX_VISIBLE = 800;

const chart = document.getElementById("chart");
const ctx = chart.getContext("2d");
const statusText = document.getElementById("statusText");
const penList = document.getElementById("penList");
const selectedPen = document.getElementById("selectedPen");
const summary = document.getElementById("summary");

function setStatus(text) {
  statusText.textContent = text;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "请求失败");
  }
  return data;
}

async function refresh() {
  const data = await api(`/api/state?symbol=${state.symbol}&limit=800`);
  state.klines = data.klines;
  state.pens = data.pens;
  state.analysis = data.analysis;
  draw();
  renderSidePanel();
  setStatus(`K线 ${state.klines.length} 根，笔 ${state.pens.length} 条`);
}

function layout() {
  const rect = chart.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  chart.width = Math.floor(rect.width * ratio);
  chart.height = Math.floor(rect.height * ratio);
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  return { width: rect.width, height: rect.height, padLeft: 54, padRight: 18, padTop: 20, padBottom: 42 };
}

function visibleKlines() {
  const total = state.klines.length;
  if (!total) return [];
  const visible = Math.max(MIN_VISIBLE, Math.round(total / state.zoomLevel));
  const clamped = Math.min(visible, MAX_VISIBLE);
  const maxOffset = Math.max(0, total - clamped);
  const offset = Math.min(state.scrollOffset, maxOffset);
  return state.klines.slice(offset, offset + clamped);
}

function priceRange() {
  if (!state.klines.length) return { min: 0, max: 1 };
  const vis = visibleKlines();
  const lows = vis.map((item) => item.low);
  const highs = vis.map((item) => item.high);
  const min = Math.min(...lows);
  const max = Math.max(...highs);
  const padding = (max - min) * 0.08 || 1;
  return { min: min - padding, max: max + padding };
}

function draw() {
  const box = layout();
  const vis = visibleKlines();
  ctx.clearRect(0, 0, box.width, box.height);
  state.hitPens = [];
  drawGrid(box);
  if (!vis.length) {
    ctx.fillStyle = "#64717d";
    ctx.fillText("请先点击“拉取K线”", box.padLeft, box.padTop + 24);
    return;
  }
  drawKlines(box, vis);
  drawCenters(box, vis);
  drawPens(box, vis);
  drawSignals(box, vis);
}

function xScale(box, index) {
  const plotWidth = box.width - box.padLeft - box.padRight;
  return box.padLeft + (index + 0.5) * (plotWidth / visibleKlines().length);
}

function yScale(box, price) {
  const range = priceRange();
  const plotHeight = box.height - box.padTop - box.padBottom;
  return box.padTop + ((range.max - price) / (range.max - range.min)) * plotHeight;
}

function indexByDt(dt) {
  return visibleKlines().findIndex((item) => item.dt === dt);
}

function drawGrid(box) {
  ctx.strokeStyle = "#e7ecf2";
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i += 1) {
    const y = box.padTop + ((box.height - box.padTop - box.padBottom) / 4) * i;
    ctx.beginPath();
    ctx.moveTo(box.padLeft, y);
    ctx.lineTo(box.width - box.padRight, y);
    ctx.stroke();
  }
  ctx.fillStyle = "#7b8793";
  ctx.font = "12px sans-serif";
  const range = priceRange();
  for (let i = 0; i <= 4; i += 1) {
    const value = range.max - ((range.max - range.min) / 4) * i;
    const y = box.padTop + ((box.height - box.padTop - box.padBottom) / 4) * i;
    ctx.fillText(value.toFixed(2), 8, y + 4);
  }
}

function drawKlines(box, vis) {
  const candleWidth = Math.max(3, (box.width - box.padLeft - box.padRight) / vis.length * 0.58);
  vis.forEach((item, index) => {
    const x = xScale(box, index);
    const openY = yScale(box, item.open);
    const closeY = yScale(box, item.close);
    const highY = yScale(box, item.high);
    const lowY = yScale(box, item.low);
    const up = item.close >= item.open;
    ctx.strokeStyle = up ? "#d94b4b" : "#1f9a6b";
    ctx.fillStyle = up ? "#d94b4b" : "#1f9a6b";
    ctx.beginPath();
    ctx.moveTo(x, highY);
    ctx.lineTo(x, lowY);
    ctx.stroke();
    ctx.fillRect(x - candleWidth / 2, Math.min(openY, closeY), candleWidth, Math.max(1, Math.abs(closeY - openY)));
  });
}

function drawPens(box, vis) {
  state.pens.forEach((pen) => {
    const startIndex = indexByDt(pen.start_dt);
    const endIndex = indexByDt(pen.end_dt);
    if (startIndex < 0 || endIndex < 0) return;
    const x1 = xScale(box, startIndex);
    const y1 = yScale(box, pen.start_price);
    const x2 = xScale(box, endIndex);
    const y2 = yScale(box, pen.end_price);
    const selected = pen.id === state.selectedPenId;
    ctx.strokeStyle = pen.status === "confirmed" ? "#276ef1" : "#de8c2f";
    ctx.lineWidth = selected ? 4 : 2;
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
    ctx.fillStyle = ctx.strokeStyle;
    ctx.beginPath();
    ctx.arc(x1, y1, selected ? 5 : 4, 0, Math.PI * 2);
    ctx.arc(x2, y2, selected ? 5 : 4, 0, Math.PI * 2);
    ctx.fill();
    state.hitPens.push({ id: pen.id, x1, y1, x2, y2 });
  });
}

function drawCenters(box, vis) {
  state.analysis.centers.forEach((center) => {
    const startIndex = indexByDt(center.start_dt);
    const endIndex = indexByDt(center.end_dt);
    if (startIndex < 0 || endIndex < 0) return;
    const x = xScale(box, startIndex);
    const w = xScale(box, endIndex) - x;
    const y = yScale(box, center.high);
    const h = yScale(box, center.low) - y;
    ctx.fillStyle = "rgba(39, 110, 241, 0.12)";
    ctx.strokeStyle = "rgba(39, 110, 241, 0.5)";
    ctx.fillRect(x, y, Math.max(w, 2), Math.max(h, 2));
    ctx.strokeRect(x, y, Math.max(w, 2), Math.max(h, 2));
  });
}

function drawSignals(box, vis) {
  state.analysis.signals.forEach((signal) => {
    const index = indexByDt(signal.dt);
    if (index < 0) return;
    const x = xScale(box, index);
    const y = yScale(box, signal.price);
    ctx.fillStyle = signal.kind === "buy_watch" ? "#d94b4b" : "#1f9a6b";
    ctx.beginPath();
    ctx.arc(x, y, 6, 0, Math.PI * 2);
    ctx.fill();
  });
}

function renderSidePanel() {
  renderSelectedPen();
  renderSummary();
  penList.innerHTML = state.pens.length
    ? state.pens.map((pen) => `
      <div class="pen-card ${pen.id === state.selectedPenId ? "active" : ""}" data-id="${pen.id}">
        <span class="tag ${pen.status}">${pen.status === "confirmed" ? "已确认" : "候选"}</span>
        <div>${pen.direction === "up" ? "向上" : "向下"}：${pen.start_dt} → ${pen.end_dt}</div>
        <div>${pen.start_price.toFixed(2)} → ${pen.end_price.toFixed(2)}</div>
      </div>
    `).join("")
    : `<div class="empty">暂无笔。先生成候选笔，或手工新增。</div>`;
  document.querySelectorAll(".pen-card").forEach((node) => {
    node.addEventListener("click", () => selectPen(Number(node.dataset.id)));
  });
}

function renderSelectedPen() {
  const pen = state.pens.find((item) => item.id === state.selectedPenId);
  if (!pen) {
    selectedPen.className = "selected-empty";
    selectedPen.innerHTML = "点击图上的笔进行确认、删除或调整。";
    return;
  }
  selectedPen.className = "";
  selectedPen.innerHTML = `
    <div class="edit-grid">
      <input id="editStartDt" value="${pen.start_dt}">
      <input id="editStartPrice" type="number" step="0.01" value="${pen.start_price}">
      <input id="editEndDt" value="${pen.end_dt}">
      <input id="editEndPrice" type="number" step="0.01" value="${pen.end_price}">
    </div>
    <div class="button-row">
      <button id="savePenBtn">保存调整</button>
      ${pen.status === "candidate" ? `<button id="confirmPenBtn" class="secondary">确认</button>` : ""}
      <button id="deletePenBtn" class="danger">删除</button>
    </div>
  `;
  document.getElementById("savePenBtn").addEventListener("click", saveSelectedPen);
  document.getElementById("deletePenBtn").addEventListener("click", deleteSelectedPen);
  const confirmBtn = document.getElementById("confirmPenBtn");
  if (confirmBtn) confirmBtn.addEventListener("click", confirmSelectedPen);
}

function renderSummary() {
  const center = state.analysis.centers[state.analysis.centers.length - 1];
  const signal = state.analysis.signals[state.analysis.signals.length - 1];
  summary.innerHTML = `
    <div class="summary-card">已确认笔：${state.pens.filter((item) => item.status === "confirmed").length} 条</div>
    <div class="summary-card">线段：${state.analysis.segments.length} 条</div>
    <div class="summary-card">最近中枢：${center ? `${center.low.toFixed(2)} - ${center.high.toFixed(2)}` : "暂无"}</div>
    <div class="summary-card">最新信号：${signal ? signal.message : "暂无"}</div>
  `;
}

function selectPen(id) {
  state.selectedPenId = id;
  draw();
  renderSidePanel();
}

function distanceToSegment(px, py, x1, y1, x2, y2) {
  const dx = x2 - x1;
  const dy = y2 - y1;
  if (dx === 0 && dy === 0) return Math.hypot(px - x1, py - y1);
  const t = Math.max(0, Math.min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)));
  return Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy));
}

chart.addEventListener("click", (event) => {
  const rect = chart.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;
  const hit = state.hitPens.find((item) => distanceToSegment(x, y, item.x1, item.y1, item.x2, item.y2) < 10);
  if (hit) selectPen(hit.id);
});

async function saveSelectedPen() {
  const pen = state.pens.find((item) => item.id === state.selectedPenId);
  if (!pen) return;
  const payload = {
    start_dt: document.getElementById("editStartDt").value,
    start_price: Number(document.getElementById("editStartPrice").value),
    end_dt: document.getElementById("editEndDt").value,
    end_price: Number(document.getElementById("editEndPrice").value),
  };
  payload.direction = payload.end_price >= payload.start_price ? "up" : "down";
  try {
    const updated = await api(`/api/pens/${pen.id}`, { method: "PATCH", body: JSON.stringify(payload) });
    const idx = state.pens.findIndex((item) => item.id === pen.id);
    if (idx !== -1) state.pens[idx] = updated;
    draw();
    setStatus("已保存");
  } catch (err) {
    setStatus("保存失败: " + err.message);
  }
}

async function confirmSelectedPen() {
  const pen = state.pens.find((item) => item.id === state.selectedPenId);
  if (!pen) return;
  await api(`/api/pens/${pen.id}`, { method: "PATCH", body: JSON.stringify({ status: "confirmed" }) });
  await refresh();
}

async function deleteSelectedPen() {
  const pen = state.pens.find((item) => item.id === state.selectedPenId);
  if (!pen) return;
  await api(`/api/pens/${pen.id}`, { method: "PATCH", body: JSON.stringify({ status: "deleted" }) });
  state.selectedPenId = null;
  await refresh();
}

document.getElementById("fetchBtn").addEventListener("click", async () => {
  try {
    setStatus("正在拉取新浪K线...");
    await api("/api/fetch", { method: "POST", body: JSON.stringify({ symbol: state.symbol, scale: 30, datalen: 800 }) });
    await refresh();
  } catch (error) {
    setStatus(error.message);
  }
});

document.getElementById("candidateBtn").addEventListener("click", async () => {
  try {
    await api(`/api/candidates/generate?symbol=${state.symbol}&limit=800`, { method: "POST" });
    await refresh();
  } catch (error) {
    setStatus(error.message);
  }
});

document.getElementById("confirmAllBtn").addEventListener("click", async () => {
  await api(`/api/pens/confirm-all?symbol=${state.symbol}`, { method: "POST" });
  await refresh();
});

document.getElementById("undoBtn").addEventListener("click", async () => {
  const result = await api("/api/undo", { method: "POST" });
  setStatus(result.message);
  await refresh();
});

document.getElementById("manualBtn").addEventListener("click", async () => {
  const payload = {
    symbol: state.symbol,
    start_dt: document.getElementById("startDt").value,
    start_price: Number(document.getElementById("startPrice").value),
    end_dt: document.getElementById("endDt").value,
    end_price: Number(document.getElementById("endPrice").value),
  };
  await api("/api/pens/manual", { method: "POST", body: JSON.stringify(payload) });
  await refresh();
});

window.addEventListener("resize", draw);
refresh().catch((error) => setStatus(error.message));


// Wheel zoom + drag pan
let isDragging = false;
let dragStartX = 0;
let dragStartOffset = 0;

chart.addEventListener(""wheel"", (event) => {
  event.preventDefault();
  const total = state.klines.length;
  if (!total) return;
  const delta = event.deltaY > 0 ? -0.2 : 0.2;
  state.zoomLevel = Math.max(0.2, Math.min(10, state.zoomLevel + delta));
  const vis = Math.min(Math.max(MIN_VISIBLE, Math.round(total / state.zoomLevel)), MAX_VISIBLE);
  const maxOffset = Math.max(0, total - vis);
  state.scrollOffset = Math.min(state.scrollOffset, maxOffset);
  draw();
}, { passive: false });

chart.addEventListener(""mousedown"", (event) => {
  if (event.button !== 0) return;
  isDragging = true;
  dragStartX = event.clientX;
  dragStartOffset = state.scrollOffset;
  chart.style.cursor = ""grabbing"";
});

chart.addEventListener(""mousemove"", (event) => {
  if (!isDragging) return;
  const total = state.klines.length;
  const vis = Math.min(Math.max(MIN_VISIBLE, Math.round(total / state.zoomLevel)), MAX_VISIBLE);
  const maxOffset = Math.max(0, total - vis);
  const box = layout();
  const plotWidth = box.width - box.padLeft - box.padRight;
  const dx = event.clientX - dragStartX;
  const candlesMoved = Math.round(-dx / (plotWidth / vis));
  state.scrollOffset = Math.max(0, Math.min(maxOffset, dragStartOffset + candlesMoved));
  draw();
});

chart.addEventListener(""mouseup"", () => {
  isDragging = false;
  chart.style.cursor = ""default"";
});

chart.addEventListener(""mouseleave"", () => {
  isDragging = false;
  chart.style.cursor = ""default"";
});


