"use strict";

const NS = "http://www.w3.org/2000/svg";
const ui = {
  connection: document.querySelector("#connection"),
  connectionLabel: document.querySelector("#connection-label"),
  diagnostics: document.querySelector("#diagnostics"),
  diagnosticTitle: document.querySelector("#diagnostic-title"),
  issueList: document.querySelector("#issue-list"),
  graphScroll: document.querySelector("#graph-scroll"),
  graph: document.querySelector("#graph"),
  empty: document.querySelector("#empty-state"),
  panel: document.querySelector("#node-panel"),
  closePanel: document.querySelector("#close-panel"),
  nodeStatus: document.querySelector("#node-status"),
  nodeTitle: document.querySelector("#node-title"),
  nodeSummary: document.querySelector("#node-summary"),
  nodeDependencies: document.querySelector("#node-dependencies"),
  nodeEvidence: document.querySelector("#node-evidence"),
};

let etag = null;
let currentState = null;
let selectedNodeId = null;
let pan = null;

function setConnection(state, label) {
  ui.connection.dataset.state = state;
  ui.connectionLabel.textContent = label;
}

function fillList(element, values, emptyLabel) {
  element.replaceChildren();
  const items = values.length ? values : [emptyLabel];
  items.forEach((value) => {
    const item = document.createElement("li");
    item.textContent = value;
    element.append(item);
  });
}

function showDiagnostics(issues) {
  ui.diagnostics.hidden = false;
  ui.diagnosticTitle.textContent = currentState
    ? "Current state is invalid; showing the last valid snapshot below."
    : "RepoFrame cannot render the current snapshot.";
  ui.issueList.replaceChildren();
  issues.forEach((issue) => {
    const item = document.createElement("li");
    const code = document.createElement("code");
    code.textContent = `${issue.code} ${issue.path}`;
    item.append(code, document.createTextNode(` — ${issue.message}`));
    ui.issueList.append(item);
  });
}

function rankNodes(nodes) {
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const memo = new Map();
  function rank(node) {
    if (memo.has(node.id)) return memo.get(node.id);
    const value = node.depends_on.length
      ? Math.max(...node.depends_on.map((id) => rank(byId.get(id)))) + 1
      : 0;
    memo.set(node.id, value);
    return value;
  }
  nodes.forEach(rank);
  return memo;
}

function svgElement(name, attributes = {}) {
  const element = document.createElementNS(NS, name);
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value)));
  return element;
}

function truncated(value, length) {
  return value.length > length ? `${value.slice(0, length - 1)}…` : value;
}

function renderGraph(nodes) {
  ui.graph.replaceChildren();
  if (!nodes.length) {
    ui.empty.hidden = false;
    ui.graphScroll.hidden = true;
    return;
  }
  ui.empty.hidden = true;
  ui.graphScroll.hidden = false;

  const ranks = rankNodes(nodes);
  const columns = new Map();
  nodes.forEach((node) => {
    const rank = ranks.get(node.id);
    if (!columns.has(rank)) columns.set(rank, []);
    columns.get(rank).push(node);
  });
  const nodeWidth = 230;
  const nodeHeight = 78;
  const columnGap = 112;
  const rowGap = 34;
  const padding = 48;
  const maxRows = Math.max(...Array.from(columns.values(), (column) => column.length));
  const maxRank = Math.max(...ranks.values());
  const width = padding * 2 + (maxRank + 1) * nodeWidth + maxRank * columnGap;
  const viewportWidth = ui.graphScroll.clientWidth;
  const viewportHeight = ui.graphScroll.clientHeight;
  const graphWidth = Math.max(viewportWidth, width);
  const height = Math.max(viewportHeight, padding * 2 + maxRows * nodeHeight + (maxRows - 1) * rowGap);
  ui.graph.setAttribute("viewBox", `0 0 ${graphWidth} ${height}`);
  ui.graph.setAttribute("width", graphWidth);
  ui.graph.setAttribute("height", height);

  const positions = new Map();
  Array.from(columns.entries()).forEach(([rank, column]) => {
    const contentHeight = column.length * nodeHeight + (column.length - 1) * rowGap;
    const top = Math.max(padding, (height - contentHeight) / 2);
    column.forEach((node, index) => {
      positions.set(node.id, {
        x: padding + rank * (nodeWidth + columnGap),
        y: top + index * (nodeHeight + rowGap),
      });
    });
  });

  const defs = svgElement("defs");
  const marker = svgElement("marker", {
    id: "arrow",
    viewBox: "0 0 10 10",
    refX: 9,
    refY: 5,
    markerWidth: 6,
    markerHeight: 6,
    orient: "auto-start-reverse",
  });
  marker.append(svgElement("path", { d: "M 0 0 L 10 5 L 0 10 z", fill: "#45515d" }));
  defs.append(marker);
  ui.graph.append(defs);

  nodes.forEach((node) => {
    const target = positions.get(node.id);
    node.depends_on.forEach((dependency) => {
      const source = positions.get(dependency);
      const startX = source.x + nodeWidth;
      const startY = source.y + nodeHeight / 2;
      const endX = target.x;
      const endY = target.y + nodeHeight / 2;
      const control = Math.max(44, (endX - startX) / 2);
      ui.graph.append(svgElement("path", {
        class: "edge",
        d: `M ${startX} ${startY} C ${startX + control} ${startY}, ${endX - control} ${endY}, ${endX} ${endY}`,
        "marker-end": "url(#arrow)",
      }));
    });
  });

  nodes.forEach((node) => {
    const position = positions.get(node.id);
    const group = svgElement("g", {
      class: "node",
      transform: `translate(${position.x} ${position.y})`,
      tabindex: 0,
      role: "button",
      "aria-label": `${node.title}, ${node.status}`,
      "data-status": node.status,
    });
    group.append(svgElement("rect", { width: nodeWidth, height: nodeHeight, rx: 12 }));
    const status = svgElement("text", { x: 16, y: 24, class: "node-status" });
    status.textContent = node.status;
    const title = svgElement("text", { x: 16, y: 54, class: "node-title" });
    title.textContent = truncated(node.title, 27);
    group.append(status, title);
    const select = () => showNode(node.id);
    group.addEventListener("click", select);
    group.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        select();
      }
    });
    ui.graph.append(group);
  });
}

function showNode(nodeId) {
  if (!currentState) return;
  const node = currentState.nodes.find((candidate) => candidate.id === nodeId);
  if (!node) {
    closeNode();
    return;
  }
  selectedNodeId = nodeId;
  ui.nodeStatus.textContent = node.status;
  ui.nodeTitle.textContent = node.title;
  ui.nodeSummary.textContent = node.summary || "No summary recorded yet.";
  fillList(ui.nodeDependencies, node.depends_on, "No dependencies");
  fillList(ui.nodeEvidence, node.evidence || [], "No evidence recorded");
  ui.panel.classList.add("is-open");
  ui.panel.setAttribute("aria-hidden", "false");
  requestAnimationFrame(() => ui.closePanel.focus());
}

function closeNode() {
  selectedNodeId = null;
  ui.panel.classList.remove("is-open");
  ui.panel.setAttribute("aria-hidden", "true");
}

function renderState(state) {
  currentState = state;
  ui.diagnostics.hidden = true;
  renderGraph(state.nodes);
  if (selectedNodeId) showNode(selectedNodeId);
}

async function poll() {
  try {
    const headers = etag ? { "If-None-Match": etag } : {};
    const response = await fetch("/api/v1/state", { headers, cache: "no-store" });
    if (response.status === 304) {
      setConnection("online", "Live");
      return;
    }
    if (response.status === 422) {
      const payload = await response.json();
      showDiagnostics(payload.issues);
      setConnection("offline", "Invalid state");
      etag = null;
      return;
    }
    if (response.status === 404) {
      showDiagnostics([{ code: "file.not_found", path: "$", message: ".repoframe/state.json was not found." }]);
      setConnection("offline", "State missing");
      etag = null;
      return;
    }
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    etag = response.headers.get("ETag");
    renderState(await response.json());
    setConnection("online", "Live");
  } catch (error) {
    setConnection("offline", "Offline");
  }
}

ui.closePanel.addEventListener("click", closeNode);
ui.graphScroll.addEventListener("pointerdown", (event) => {
  if (event.button !== 0 || event.target.closest(".node")) return;
  pan = {
    pointerId: event.pointerId,
    x: event.clientX,
    y: event.clientY,
    scrollLeft: ui.graphScroll.scrollLeft,
    scrollTop: ui.graphScroll.scrollTop,
  };
  ui.graphScroll.classList.add("is-panning");
  ui.graphScroll.setPointerCapture(event.pointerId);
  event.preventDefault();
});

ui.graphScroll.addEventListener("pointermove", (event) => {
  if (!pan || pan.pointerId !== event.pointerId) return;
  ui.graphScroll.scrollLeft = pan.scrollLeft - (event.clientX - pan.x);
  ui.graphScroll.scrollTop = pan.scrollTop - (event.clientY - pan.y);
});

function stopPanning(event) {
  if (!pan || pan.pointerId !== event.pointerId) return;
  if (ui.graphScroll.hasPointerCapture(event.pointerId)) {
    ui.graphScroll.releasePointerCapture(event.pointerId);
  }
  pan = null;
  ui.graphScroll.classList.remove("is-panning");
}

ui.graphScroll.addEventListener("pointerup", stopPanning);
ui.graphScroll.addEventListener("pointercancel", stopPanning);
window.addEventListener("resize", () => {
  if (currentState) renderGraph(currentState.nodes);
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeNode();
});

poll();
setInterval(poll, 1000);
