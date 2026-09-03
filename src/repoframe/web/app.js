const SVG_NS = "http://www.w3.org/2000/svg";
const token = document.querySelector('meta[name="repoframe-token"]').content;

const ui = {
  iterationMode: document.querySelector("#iteration-mode"),
  longRunMode: document.querySelector("#long-run-mode"),
  connection: document.querySelector("#connection"),
  connectionLabel: document.querySelector("#connection-label"),
  canvasShell: document.querySelector("#canvas-shell"),
  graphHeader: document.querySelector("#graph-header"),
  goalPicker: document.querySelector("#goal-picker"),
  goalSelect: document.querySelector("#goal-select"),
  goalSelectValue: document.querySelector("#goal-select-value"),
  goalMenu: document.querySelector("#goal-menu"),
  goalOutcome: document.querySelector("#goal-outcome"),
  graphViewControls: document.querySelector("#graph-view-controls"),
  focusView: document.querySelector("#focus-view"),
  fullView: document.querySelector("#full-view"),
  diagnostics: document.querySelector("#diagnostics"),
  diagnosticTitle: document.querySelector("#diagnostic-title"),
  issueList: document.querySelector("#issue-list"),
  empty: document.querySelector("#empty-state"),
  emptyTitle: document.querySelector("#empty-title"),
  emptyCopy: document.querySelector("#empty-copy"),
  graphScroll: document.querySelector("#graph-scroll"),
  graph: document.querySelector("#graph"),
  iterationCard: document.querySelector("#iteration-card"),
  iterationFiles: document.querySelector("#iteration-files"),
  iterationAdditions: document.querySelector("#iteration-additions"),
  iterationDeletions: document.querySelector("#iteration-deletions"),
  iterationError: document.querySelector("#iteration-error"),
  closeIteration: document.querySelector("#close-iteration"),
  commitButton: document.querySelector("#commit-button"),
  commitPushButton: document.querySelector("#commit-push-button"),
  readOnlyNote: document.querySelector("#read-only-note"),
  operationCard: document.querySelector("#operation-card"),
  operationStage: document.querySelector("#operation-stage"),
  cancelOperation: document.querySelector("#cancel-operation"),
  nodePanel: document.querySelector("#node-panel"),
  closeNodePanel: document.querySelector("#close-node-panel"),
  nodeStatus: document.querySelector("#node-status"),
  nodeTitle: document.querySelector("#node-title"),
  nodeSummary: document.querySelector("#node-summary"),
  nodeDependencySection: document.querySelector("#node-dependency-section"),
  nodeDependencies: document.querySelector("#node-dependencies"),
  nodeEvidenceSection: document.querySelector("#node-evidence-section"),
  nodeEvidence: document.querySelector("#node-evidence"),
  interventionResultSection: document.querySelector("#intervention-result-section"),
  interventionResult: document.querySelector("#intervention-result"),
  interventionSection: document.querySelector("#intervention-section"),
  openIntervention: document.querySelector("#open-intervention"),
  interventionForm: document.querySelector("#intervention-form"),
  interventionText: document.querySelector("#intervention-text"),
  cancelIntervention: document.querySelector("#cancel-intervention"),
  interventionDisabled: document.querySelector("#intervention-disabled"),
  commitPanel: document.querySelector("#commit-panel"),
  closeCommitPanel: document.querySelector("#close-commit-panel"),
  commitTitle: document.querySelector("#commit-title"),
  commitSummary: document.querySelector("#commit-summary"),
  commitFileCount: document.querySelector("#commit-file-count"),
  commitAdditions: document.querySelector("#commit-additions"),
  commitDeletions: document.querySelector("#commit-deletions"),
  commitFiles: document.querySelector("#commit-files"),
  commitForm: document.querySelector("#commit-form"),
  commitSubject: document.querySelector("#commit-subject"),
  commitBody: document.querySelector("#commit-body"),
  confirmCommit: document.querySelector("#confirm-commit"),
  notice: document.querySelector("#notice"),
};

const app = {
  runtime: null,
  goals: [],
  currentGoalId: null,
  currentState: null,
  selected: null,
  graphMode: "focus",
  goalsEtag: null,
  goalEtag: null,
  iterationEtag: null,
  activeOperationId: null,
  commitProposal: null,
  pan: null,
  graphScale: 1,
  graphSize: null,
  lastActiveNode: null,
  noticeTimer: null,
  bootstrapped: false,
};

const nodeTextContext = document.createElement("canvas").getContext("2d");

function svgElement(name, attributes = {}) {
  const element = document.createElementNS(SVG_NS, name);
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value)));
  return element;
}

function truncate(value, length) {
  const text = String(value || "");
  return text.length > length ? `${text.slice(0, length - 1)}…` : text;
}

function fitNodeTitle(value, maxWidth) {
  const text = String(value || "");
  if (!nodeTextContext) return truncate(text, 24);
  nodeTextContext.font = '700 14px Aptos, "Segoe UI", sans-serif';
  if (nodeTextContext.measureText(text).width <= maxWidth) return text;
  const characters = [...text];
  let low = 0;
  let high = characters.length;
  while (low < high) {
    const middle = Math.ceil((low + high) / 2);
    const candidate = `${characters.slice(0, middle).join("")}…`;
    if (nodeTextContext.measureText(candidate).width <= maxWidth) low = middle;
    else high = middle - 1;
  }
  return `${characters.slice(0, Math.max(1, low)).join("")}…`;
}

function setConnection(online) {
  ui.connection.dataset.state = online ? "online" : "offline";
  ui.connectionLabel.textContent = online ? "Live" : "Offline";
}

function showNotice(message, duration = 5000) {
  window.clearTimeout(app.noticeTimer);
  ui.notice.textContent = message;
  ui.notice.hidden = false;
  app.noticeTimer = window.setTimeout(() => {
    ui.notice.hidden = true;
  }, duration);
}

async function jsonRequest(url, options = {}) {
  const response = await fetch(url, { cache: "no-store", ...options });
  if (response.status === 304) return { response, payload: null };
  let payload = {};
  try {
    payload = await response.json();
  } catch {
    payload = {};
  }
  if (!response.ok) {
    const error = new Error(payload.message || payload.error || `HTTP ${response.status}`);
    error.payload = payload;
    error.status = response.status;
    throw error;
  }
  return { response, payload };
}

async function postJson(url, body) {
  return jsonRequest(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-RepoFrame-Token": token,
    },
    body: JSON.stringify(body),
  });
}

function routeGoalId() {
  const match = window.location.pathname.match(/^\/long-run\/([a-z0-9][a-z0-9_-]*)$/);
  return match ? match[1] : null;
}

function currentGoalMeta() {
  return app.goals.find((goal) => goal.id === app.currentGoalId) || null;
}

function isBusy() {
  return Boolean(
    app.activeOperationId ||
    (app.runtime && app.runtime.agent && app.runtime.agent.status === "running")
  );
}

function renderRuntime() {
  if (!app.runtime) return;
  const mode = app.runtime.mode;
  const busy = isBusy();
  ui.iterationMode.setAttribute("aria-pressed", String(mode === "iteration"));
  ui.longRunMode.setAttribute("aria-pressed", String(mode === "long-run"));
  ui.iterationMode.disabled = !app.runtime.interactive || busy;
  ui.longRunMode.disabled = !app.runtime.interactive || busy;
  ui.iterationCard.hidden = mode !== "iteration";
  ui.canvasShell.classList.toggle("is-frozen", mode === "iteration");
  ui.readOnlyNote.hidden = app.runtime.interactive;
  ui.closeIteration.disabled = !app.runtime.capabilities.mode_switch;
  ui.commitButton.disabled = !app.runtime.capabilities.commit || busy;
  ui.commitPushButton.disabled = !app.runtime.capabilities.push || busy;

  const operation = app.runtime.operation;
  if (operation && ["queued", "running"].includes(operation.status)) {
    ui.operationCard.hidden = false;
    ui.operationStage.textContent = operation.stage;
    ui.cancelOperation.disabled = !app.runtime.interactive;
    if (!app.activeOperationId) {
      app.activeOperationId = operation.id;
      monitorOperation(operation.id);
    }
  } else if (!app.activeOperationId) {
    ui.operationCard.hidden = true;
  }

  if (mode === "long-run" && app.bootstrapped) {
    ui.iterationError.hidden = true;
  }
  refreshNodePanelAvailability();
}

async function pollRuntime() {
  try {
    const previousMode = app.runtime && app.runtime.mode;
    const { payload } = await jsonRequest("/api/v1/runtime");
    app.runtime = payload;
    renderRuntime();
    setConnection(true);
    if (previousMode && previousMode !== payload.mode) {
      if (payload.mode === "long-run") {
        app.goalEtag = null;
        await pollGoals();
      } else {
        await pollIteration();
      }
    }
  } catch {
    setConnection(false);
  }
}

async function switchMode(mode) {
  if (!app.runtime || !app.runtime.interactive || isBusy()) return;
  try {
    const { payload } = await postJson("/api/v1/mode", { mode });
    app.runtime.mode = payload.mode;
    renderRuntime();
    if (mode === "iteration") await pollIteration();
    else {
      app.goalEtag = null;
      await pollGoals();
    }
  } catch (error) {
    showNotice(error.message);
  }
}

function renderDiagnostics(issues, title = "State needs attention") {
  ui.diagnosticTitle.textContent = title;
  ui.issueList.replaceChildren();
  (issues || []).forEach((issue) => {
    const item = document.createElement("li");
    item.textContent = `${issue.code} ${issue.path}: ${issue.message}`;
    ui.issueList.append(item);
  });
  ui.diagnostics.hidden = !(issues && issues.length);
}

function setGoalMenuOpen(open, focusEdge = null) {
  const canOpen = open && !ui.goalSelect.disabled;
  ui.goalMenu.hidden = !canOpen;
  ui.goalSelect.setAttribute("aria-expanded", String(canOpen));
  if (!canOpen) return;
  const options = [...ui.goalMenu.querySelectorAll('[role="option"]')];
  const selected = options.find((option) => option.getAttribute("aria-selected") === "true");
  const target = focusEdge === "last" ? options.at(-1) : selected || options[0];
  if (target) target.focus();
}

async function selectGoal(goalId) {
  if (!app.goals.some((goal) => goal.id === goalId)) return;
  setGoalMenuOpen(false);
  ui.goalSelect.focus();
  if (goalId === app.currentGoalId) return;
  app.currentGoalId = goalId;
  app.currentState = null;
  app.goalEtag = null;
  app.graphScale = 1;
  app.graphSize = null;
  app.lastActiveNode = null;
  closeNodePanel();
  history.pushState({}, "", `/long-run/${goalId}`);
  await pollGoals();
}

function moveGoalOption(event) {
  const options = [...ui.goalMenu.querySelectorAll('[role="option"]')];
  const index = options.indexOf(event.currentTarget);
  let target = null;
  if (event.key === "ArrowDown") target = options[(index + 1) % options.length];
  if (event.key === "ArrowUp") target = options[(index - 1 + options.length) % options.length];
  if (event.key === "Home") target = options[0];
  if (event.key === "End") target = options.at(-1);
  if (target) {
    event.preventDefault();
    target.focus();
  } else if (event.key === "Escape") {
    event.preventDefault();
    setGoalMenuOpen(false);
    ui.goalSelect.focus();
  }
}

function renderGoals(payload) {
  app.goals = payload.goals || [];
  renderDiagnostics(payload.issues || [], "Some execution paths could not be loaded");
  const requested = routeGoalId();
  if (requested && app.goals.some((goal) => goal.id === requested)) app.currentGoalId = requested;
  if (!app.goals.some((goal) => goal.id === app.currentGoalId)) {
    const current = app.goals.find((goal) => goal.current) || app.goals[0];
    app.currentGoalId = current ? current.id : null;
    app.goalEtag = null;
  }

  ui.goalMenu.replaceChildren();
  app.goals.forEach((goal) => {
    const option = document.createElement("button");
    option.type = "button";
    option.className = "goal-option";
    option.setAttribute("role", "option");
    option.setAttribute("aria-selected", String(goal.id === app.currentGoalId));
    option.dataset.goalId = goal.id;
    const title = document.createElement("span");
    title.className = "goal-option-title";
    title.textContent = goal.title;
    const meta = document.createElement("span");
    meta.className = "goal-option-meta";
    meta.textContent = goal.current ? "Current" : "History";
    option.append(title, meta);
    option.addEventListener("click", () => selectGoal(goal.id));
    option.addEventListener("keydown", moveGoalOption);
    ui.goalMenu.append(option);
  });
  ui.goalSelect.disabled = app.goals.length === 0;
  setGoalMenuOpen(false);

  if (!app.currentGoalId) {
    app.currentState = null;
    app.graphSize = null;
    ui.goalSelectValue.textContent = "No execution paths";
    ui.goalOutcome.textContent = "";
    ui.graph.replaceChildren();
    ui.empty.hidden = false;
    ui.emptyTitle.textContent = "No Long Run goal";
    ui.emptyCopy.textContent = 'Create one with repoframe init --goal "...".';
    ui.graphViewControls.hidden = true;
    closeNodePanel();
    return;
  }
  ui.empty.hidden = true;
  const selectedGoal = currentGoalMeta();
  ui.goalSelectValue.textContent = selectedGoal ? selectedGoal.title : "No execution paths";
  if (window.location.pathname !== `/long-run/${app.currentGoalId}`) {
    history.replaceState({}, "", `/long-run/${app.currentGoalId}`);
  }
}

async function pollGoals() {
  try {
    const goalHeaders = app.goalsEtag ? { "If-None-Match": app.goalsEtag } : {};
    const listing = await jsonRequest("/api/v1/goals", { headers: goalHeaders });
    if (listing.payload) {
      app.goalsEtag = listing.response.headers.get("ETag");
      renderGoals(listing.payload);
    }
    if (!app.currentGoalId) {
      setConnection(true);
      return;
    }
    const stateHeaders = app.goalEtag ? { "If-None-Match": app.goalEtag } : {};
    const result = await jsonRequest(
      `/api/v1/goals/${encodeURIComponent(app.currentGoalId)}`,
      { headers: stateHeaders }
    );
    if (result.payload) {
      app.goalEtag = result.response.headers.get("ETag");
      renderState(result.payload);
    }
    setConnection(true);
  } catch (error) {
    if (error.status === 404) {
      app.goalsEtag = null;
      app.goalEtag = null;
    }
    setConnection(false);
  }
}

async function pollIteration() {
  try {
    const headers = app.iterationEtag ? { "If-None-Match": app.iterationEtag } : {};
    const result = await jsonRequest("/api/v1/iteration", { headers });
    if (result.payload) {
      app.iterationEtag = result.response.headers.get("ETag");
      const changes = result.payload.working_changes;
      ui.iterationFiles.textContent = changes.changed_files;
      ui.iterationAdditions.textContent = changes.additions;
      ui.iterationDeletions.textContent = changes.deletions;
    }
    ui.iterationError.hidden = true;
    setConnection(true);
  } catch (error) {
    ui.iterationError.textContent = error.message;
    ui.iterationError.hidden = false;
    setConnection(false);
  }
}

function graphSubset(nodes, interventions) {
  if (nodes.length <= 40 || app.graphMode === "full") {
    return { nodes: [...nodes], hidden: 0 };
  }
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const dependents = new Map(nodes.map((node) => [node.id, []]));
  nodes.forEach((node) => node.depends_on.forEach((dependency) => {
    if (dependents.has(dependency)) dependents.get(dependency).push(node.id);
  }));
  const visible = new Set(
    nodes
      .filter((node) => !["done", "skipped"].includes(node.status))
      .map((node) => node.id)
  );
  interventions
    .filter((item) => item.status !== "incorporated")
    .forEach((item) => visible.add(item.target_node_id));

  let frontier = [...visible];
  for (let hop = 0; hop < 2; hop += 1) {
    const next = [];
    frontier.forEach((id) => {
      const node = byId.get(id);
      if (node) {
        node.depends_on.forEach((dependency) => {
          if (!visible.has(dependency)) next.push(dependency);
          visible.add(dependency);
        });
      }
      (dependents.get(id) || []).forEach((dependent) => {
        if (!visible.has(dependent)) next.push(dependent);
        visible.add(dependent);
      });
    });
    frontier = next;
  }
  if (!visible.size) nodes.slice(-12).forEach((node) => visible.add(node.id));
  return { nodes: nodes.filter((node) => visible.has(node.id)), hidden: nodes.length - visible.size };
}

function executionLayout(allNodes, visibleNodes) {
  const allById = new Map(allNodes.map((node) => [node.id, node]));
  const depth = new Map(allNodes.map((node) => [node.id, 0]));
  const indegree = new Map(allNodes.map((node) => [node.id, node.depends_on.length]));
  const children = new Map(allNodes.map((node) => [node.id, []]));
  allNodes.forEach((node) => node.depends_on.forEach((dependency) => {
    if (children.has(dependency)) children.get(dependency).push(node.id);
  }));
  const queue = allNodes.filter((node) => indegree.get(node.id) === 0).map((node) => node.id);
  for (let index = 0; index < queue.length; index += 1) {
    const id = queue[index];
    (children.get(id) || []).forEach((child) => {
      depth.set(child, Math.max(depth.get(child), depth.get(id) + 1));
      indegree.set(child, indegree.get(child) - 1);
      if (indegree.get(child) === 0) queue.push(child);
    });
  }
  const ranks = new Map();
  visibleNodes.forEach((node) => {
    const rank = depth.get(node.id) || 0;
    if (!ranks.has(rank)) ranks.set(rank, []);
    ranks.get(rank).push(node);
  });
  const sortedRanks = [...ranks.keys()].sort((a, b) => a - b);
  const order = new Map();
  sortedRanks.forEach((rank) => ranks.get(rank).forEach((node, index) => order.set(node.id, index)));
  for (let pass = 0; pass < 2; pass += 1) {
    sortedRanks.forEach((rank) => {
      ranks.get(rank).sort((left, right) => {
        const score = (node) => {
          const source = allById.get(node.id);
          const parents = (source ? source.depends_on : []).filter((id) => order.has(id));
          return parents.length
            ? parents.reduce((sum, id) => sum + order.get(id), 0) / parents.length
            : order.get(node.id);
        };
        return score(left) - score(right);
      });
      ranks.get(rank).forEach((node, index) => order.set(node.id, index));
    });
  }

  const nodeWidth = 230;
  const nodeHeight = 80;
  const gapX = 72;
  const gapY = 96;
  const maxRankSize = Math.max(1, ...[...ranks.values()].map((rank) => rank.length));
  const baseWidth = Math.max(ui.graphScroll.clientWidth, 320 + maxRankSize * (nodeWidth + gapX));
  const positions = new Map();
  sortedRanks.forEach((rank) => {
    const entries = ranks.get(rank);
    const rowWidth = entries.length * nodeWidth + Math.max(0, entries.length - 1) * gapX;
    const startX = Math.max(80, (baseWidth - rowWidth) / 2);
    entries.forEach((node, index) => {
      positions.set(node.id, {
        x: startX + index * (nodeWidth + gapX),
        y: 92 + rank * (nodeHeight + gapY),
      });
    });
  });
  const maxDepth = Math.max(0, ...sortedRanks);
  return {
    positions,
    nodeWidth,
    nodeHeight,
    width: baseWidth,
    height: Math.max(ui.graphScroll.clientHeight, 210 + (maxDepth + 1) * (nodeHeight + gapY)),
  };
}

function createMarker(defs, id, color) {
  const marker = svgElement("marker", {
    id,
    viewBox: "0 0 10 10",
    refX: 8,
    refY: 5,
    markerWidth: 6,
    markerHeight: 6,
    orient: "auto-start-reverse",
  });
  marker.append(svgElement("path", { d: "M 0 0 L 10 5 L 0 10 z", fill: color }));
  defs.append(marker);
}

function edgePath(from, to, nodeWidth, nodeHeight) {
  const x1 = from.x + nodeWidth / 2;
  const y1 = from.y + nodeHeight;
  const x2 = to.x + nodeWidth / 2;
  const y2 = to.y;
  const middle = y1 + (y2 - y1) / 2;
  return `M ${x1} ${y1} C ${x1} ${middle}, ${x2} ${middle}, ${x2} ${y2}`;
}

function interventionTitle(intervention) {
  return intervention.text.split(/\r?\n/, 1)[0];
}

function appendGraphNode(container, item, position, layout, kind = "execution") {
  const group = svgElement("g", {
    class: "graph-node",
    transform: `translate(${position.x} ${position.y})`,
    tabindex: 0,
    role: "button",
    "aria-label": `${item.title}, ${item.status}`,
    "data-status": item.status,
    "data-kind": kind,
  });
  if (item.status === "active") {
    group.append(svgElement("rect", {
      class: "active-ring",
      x: -7,
      y: -7,
      width: layout.nodeWidth + 14,
      height: layout.nodeHeight + 14,
      rx: 17,
    }));
  }
  group.append(svgElement("rect", {
    class: "node-body",
    width: layout.nodeWidth,
    height: layout.nodeHeight,
    rx: 13,
  }));
  const status = svgElement("text", { x: 16, y: 24, class: "node-status" });
  status.textContent = item.status.replace("_", " ");
  const title = svgElement("text", { x: 16, y: 55, class: "node-title" });
  title.textContent = fitNodeTitle(item.title, layout.nodeWidth - 32);
  group.append(status, title);
  const select = () => {
    if (item.id === "__collapsed") {
      app.graphMode = "full";
      updateViewControls();
      renderGraph(app.currentState);
      return;
    }
    showNode(kind, item.id);
  };
  group.addEventListener("click", select);
  group.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      select();
    }
  });
  container.append(group);
}

function renderGraph(state) {
  const nodes = state.nodes || [];
  const interventions = state.interventions || [];
  const subset = graphSubset(nodes, interventions);
  const visibleNodes = [...subset.nodes];
  if (subset.hidden > 0) {
    visibleNodes.unshift({
      id: "__collapsed",
      title: `${subset.hidden} hidden nodes`,
      status: "collapsed",
      depends_on: [],
    });
  }
  const layout = executionLayout(nodes, visibleNodes);
  const positions = layout.positions;
  const visibleIds = new Set(visibleNodes.map((node) => node.id));
  const interventionPositions = new Map();
  const targetCounts = new Map();
  let maxX = Math.max(0, ...[...positions.values()].map((position) => position.x));
  const laneX = maxX + layout.nodeWidth + 120;
  interventions.forEach((item) => {
    if (!visibleIds.has(item.target_node_id)) return;
    const target = positions.get(item.target_node_id);
    const offset = targetCounts.get(item.target_node_id) || 0;
    targetCounts.set(item.target_node_id, offset + 1);
    interventionPositions.set(item.id, { x: laneX, y: target.y + offset * (layout.nodeHeight + 20) });
  });
  if (interventionPositions.size) layout.width = Math.max(layout.width, laneX + layout.nodeWidth + 100);
  layout.height = Math.max(
    layout.height,
    ...[...interventionPositions.values()].map((position) => position.y + layout.nodeHeight + 100)
  );

  ui.graph.replaceChildren();
  ui.graph.setAttribute("viewBox", `0 0 ${layout.width} ${layout.height}`);
  app.graphSize = { width: layout.width, height: layout.height };
  applyGraphScale();
  const defs = svgElement("defs");
  createMarker(defs, "arrow", "#4a554b");
  createMarker(defs, "intervention-arrow", "#899784");
  ui.graph.append(defs);

  const edges = svgElement("g", { "aria-hidden": "true" });
  visibleNodes.forEach((node) => {
    if (node.id === "__collapsed") return;
    node.depends_on.forEach((dependency) => {
      if (!positions.has(dependency)) return;
      edges.append(svgElement("path", {
        class: "edge",
        d: edgePath(positions.get(dependency), positions.get(node.id), layout.nodeWidth, layout.nodeHeight),
        "marker-end": "url(#arrow)",
      }));
    });
  });
  interventions.forEach((item) => {
    const source = interventionPositions.get(item.id);
    const target = positions.get(item.target_node_id);
    if (!source || !target) return;
    edges.append(svgElement("path", {
      class: "intervention-edge",
      d: edgePath(target, source, layout.nodeWidth, layout.nodeHeight),
      "marker-end": "url(#intervention-arrow)",
    }));
    (item.result && item.result.node_ids || []).forEach((nodeId) => {
      const result = positions.get(nodeId);
      if (!result) return;
      edges.append(svgElement("path", {
        class: "intervention-edge result-edge",
        d: edgePath(source, result, layout.nodeWidth, layout.nodeHeight),
        "marker-end": "url(#intervention-arrow)",
      }));
    });
  });
  ui.graph.append(edges);

  const nodeLayer = svgElement("g");
  visibleNodes.forEach((node) => appendGraphNode(nodeLayer, node, positions.get(node.id), layout));
  interventions.forEach((item) => {
    const position = interventionPositions.get(item.id);
    if (!position) return;
    appendGraphNode(
      nodeLayer,
      { id: item.id, title: interventionTitle(item), status: item.status },
      position,
      layout,
      "intervention"
    );
  });
  ui.graph.append(nodeLayer);

  const active = nodes.find((node) => node.status === "active");
  if (active && positions.has(active.id) && app.lastActiveNode !== active.id) {
    const position = positions.get(active.id);
    const left = (position.x + layout.nodeWidth / 2) * app.graphScale - ui.graphScroll.clientWidth / 2;
    const top = (position.y + layout.nodeHeight / 2) * app.graphScale - ui.graphScroll.clientHeight / 2;
    ui.graphScroll.scrollTo({
      left: Math.max(0, left),
      top: Math.max(0, top),
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
    });
    app.lastActiveNode = active.id;
  }
  updateViewControls();
}

function applyGraphScale() {
  if (!app.graphSize) return;
  ui.graph.setAttribute("width", Math.round(app.graphSize.width * app.graphScale));
  ui.graph.setAttribute("height", Math.round(app.graphSize.height * app.graphScale));
}

function updateViewControls() {
  const large = app.currentState && app.currentState.nodes.length > 40;
  ui.graphViewControls.hidden = !large;
  ui.focusView.setAttribute("aria-pressed", String(app.graphMode === "focus"));
  ui.fullView.setAttribute("aria-pressed", String(app.graphMode === "full"));
}

function renderState(state) {
  app.currentState = state;
  ui.empty.hidden = false;
  if (!state.nodes.length && !(state.interventions || []).length) {
    ui.graph.replaceChildren();
    app.graphSize = null;
    ui.empty.hidden = false;
    ui.emptyTitle.textContent = "Waiting for an execution path";
    ui.emptyCopy.textContent = "The Agent can add meaningful stages as the Goal becomes clear.";
  } else {
    ui.empty.hidden = true;
    renderGraph(state);
  }
  ui.goalOutcome.textContent = state.goal.outcome;
  if (app.selected) showNode(app.selected.kind, app.selected.id, false);
}

function fillList(element, values, emptyText) {
  element.replaceChildren();
  if (!values || !values.length) {
    const item = document.createElement("li");
    item.textContent = emptyText;
    element.append(item);
    return;
  }
  values.forEach((value) => {
    const item = document.createElement("li");
    item.textContent = value;
    element.append(item);
  });
}

function refreshNodePanelAvailability() {
  if (!app.selected || app.selected.kind !== "execution") return;
  const meta = currentGoalMeta();
  const canIntervene = Boolean(
    meta &&
    meta.current &&
    app.runtime &&
    app.runtime.mode === "long-run" &&
    app.runtime.capabilities.intervention &&
    !isBusy()
  );
  ui.openIntervention.hidden = !canIntervene;
  ui.interventionDisabled.hidden = canIntervene;
  if (!canIntervene) {
    if (meta && !meta.current) ui.interventionDisabled.textContent = "Historical execution paths are read-only.";
    else if (app.runtime && !app.runtime.interactive) {
      ui.interventionDisabled.textContent = "Start repoframe interact to add an intervention.";
    } else if (isBusy()) ui.interventionDisabled.textContent = "Wait for the current Agent operation to finish.";
    else ui.interventionDisabled.textContent = "Interventions are available in Long Run.";
  }
}

function showNode(kind, id, focus = true) {
  if (!app.currentState) return;
  app.selected = { kind, id };
  ui.interventionForm.hidden = true;
  ui.interventionText.value = "";
  if (kind === "execution") {
    const node = app.currentState.nodes.find((candidate) => candidate.id === id);
    if (!node) return closeNodePanel();
    ui.nodeStatus.textContent = node.status;
    ui.nodeTitle.textContent = node.title;
    ui.nodeSummary.textContent = node.summary || "No summary recorded yet.";
    ui.nodeDependencySection.hidden = false;
    ui.nodeEvidenceSection.hidden = false;
    fillList(ui.nodeDependencies, node.depends_on, "No dependencies");
    fillList(ui.nodeEvidence, node.evidence || [], "No evidence recorded");
    ui.interventionResultSection.hidden = true;
    ui.interventionSection.hidden = false;
    refreshNodePanelAvailability();
  } else {
    const item = (app.currentState.interventions || []).find((candidate) => candidate.id === id);
    if (!item) return closeNodePanel();
    ui.nodeStatus.textContent = item.status.replace("_", " ");
    ui.nodeTitle.textContent = interventionTitle(item);
    ui.nodeSummary.textContent = item.text;
    ui.nodeDependencySection.hidden = true;
    ui.nodeEvidenceSection.hidden = true;
    ui.interventionSection.hidden = true;
    ui.interventionResultSection.hidden = !item.result;
    ui.interventionResult.textContent = item.result ? item.result.summary : "";
  }
  ui.nodePanel.classList.add("is-open");
  ui.nodePanel.setAttribute("aria-hidden", "false");
  if (focus) window.setTimeout(() => ui.closeNodePanel.focus(), 20);
}

function closeNodePanel() {
  app.selected = null;
  ui.nodePanel.classList.remove("is-open");
  ui.nodePanel.setAttribute("aria-hidden", "true");
  ui.interventionForm.hidden = true;
}

function openCommitPanel(proposal) {
  app.commitProposal = proposal;
  const changes = proposal.working_changes;
  ui.commitTitle.textContent = proposal.intent === "commit_push" ? "Review commit and push" : "Review commit";
  ui.confirmCommit.textContent = proposal.intent === "commit_push" ? "Commit & Push" : "Commit";
  ui.commitSummary.textContent = proposal.summary;
  ui.commitSubject.value = proposal.subject;
  ui.commitBody.value = proposal.body || "";
  ui.commitFileCount.textContent = changes.changed_files;
  ui.commitAdditions.textContent = changes.additions;
  ui.commitDeletions.textContent = changes.deletions;
  ui.commitFiles.replaceChildren();
  changes.files.forEach((file) => {
    const item = document.createElement("li");
    const path = document.createElement("code");
    path.textContent = file.path;
    const status = document.createElement("span");
    status.textContent = file.status;
    item.append(path, status);
    ui.commitFiles.append(item);
  });
  ui.commitPanel.classList.add("is-open");
  ui.commitPanel.setAttribute("aria-hidden", "false");
  window.setTimeout(() => ui.commitSubject.focus(), 20);
}

function closeCommitPanel() {
  app.commitProposal = null;
  ui.commitPanel.classList.remove("is-open");
  ui.commitPanel.setAttribute("aria-hidden", "true");
}

async function startOperation(type, payload) {
  try {
    const result = await postJson("/api/v1/operations", { type, payload });
    app.activeOperationId = result.payload.id;
    ui.operationCard.hidden = false;
    ui.operationStage.textContent = result.payload.stage;
    renderRuntime();
    monitorOperation(result.payload.id);
  } catch (error) {
    showNotice(error.message);
  }
}

async function monitorOperation(id) {
  if (app.activeOperationId !== id) return;
  try {
    const { payload } = await jsonRequest(`/api/v1/operations/${encodeURIComponent(id)}`);
    ui.operationStage.textContent = payload.stage;
    if (["queued", "running"].includes(payload.status)) {
      window.setTimeout(() => monitorOperation(id), 500);
      return;
    }
    app.activeOperationId = null;
    ui.operationCard.hidden = true;
    await pollRuntime();
    if (payload.status === "completed") {
      if (payload.type === "git.prepare_commit") {
        openCommitPanel(payload.result);
      } else if (payload.type === "intervention.create") {
        showNotice(
          payload.result.disposition === "incorporated"
            ? "Execution path updated."
            : "The intervention needs more user input."
        );
        app.goalsEtag = null;
        app.goalEtag = null;
        await pollGoals();
      } else {
        const push = payload.result.push;
        if (push && push.pushed === false) {
          showNotice(`Commit created. Push failed: ${push.message}`, 8000);
        } else {
          showNotice(push ? "Committed and pushed." : "Commit created.");
        }
        closeCommitPanel();
        app.iterationEtag = null;
        await pollIteration();
      }
    } else {
      showNotice(payload.error ? payload.error.message : "Operation did not complete.", 8000);
      if (payload.type === "intervention.create") {
        app.goalEtag = null;
        await pollGoals();
      }
    }
  } catch (error) {
    app.activeOperationId = null;
    ui.operationCard.hidden = true;
    showNotice(error.message);
    await pollRuntime();
  }
}

async function bootstrap() {
  await pollRuntime();
  await pollGoals();
  if (app.runtime && app.runtime.mode === "iteration") await pollIteration();
  app.bootstrapped = true;
  window.setInterval(async () => {
    await pollRuntime();
    if (!app.runtime) return;
    if (app.runtime.mode === "long-run") await pollGoals();
    else await pollIteration();
  }, 1000);
}

ui.iterationMode.addEventListener("click", () => switchMode("iteration"));
ui.longRunMode.addEventListener("click", () => switchMode("long-run"));
ui.closeIteration.addEventListener("click", () => switchMode("long-run"));
ui.commitButton.addEventListener("click", () => startOperation("git.prepare_commit", { intent: "commit" }));
ui.commitPushButton.addEventListener("click", () => startOperation("git.prepare_commit", { intent: "commit_push" }));
ui.cancelOperation.addEventListener("click", async () => {
  if (!app.activeOperationId) return;
  try {
    await postJson(`/api/v1/operations/${encodeURIComponent(app.activeOperationId)}/cancel`, {});
  } catch (error) {
    showNotice(error.message);
  }
});

ui.goalSelect.addEventListener("click", () => {
  setGoalMenuOpen(ui.goalMenu.hidden);
});
ui.goalSelect.addEventListener("keydown", (event) => {
  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault();
    setGoalMenuOpen(true, event.key === "ArrowUp" ? "last" : null);
  } else if (event.key === "Escape") {
    setGoalMenuOpen(false);
  }
});
document.addEventListener("pointerdown", (event) => {
  if (!ui.goalPicker.contains(event.target)) setGoalMenuOpen(false);
});
ui.focusView.addEventListener("click", () => {
  app.graphMode = "focus";
  updateViewControls();
  if (app.currentState) renderGraph(app.currentState);
});
ui.fullView.addEventListener("click", () => {
  app.graphMode = "full";
  updateViewControls();
  if (app.currentState) renderGraph(app.currentState);
});

ui.closeNodePanel.addEventListener("click", closeNodePanel);
ui.openIntervention.addEventListener("click", () => {
  ui.openIntervention.hidden = true;
  ui.interventionForm.hidden = false;
  ui.interventionText.focus();
});
ui.cancelIntervention.addEventListener("click", () => {
  ui.interventionForm.hidden = true;
  ui.interventionText.value = "";
  refreshNodePanelAvailability();
});
ui.interventionForm.addEventListener("submit", (event) => {
  event.preventDefault();
  if (!app.selected || app.selected.kind !== "execution" || !app.currentGoalId) return;
  const text = ui.interventionText.value.trim();
  if (!text) return;
  ui.interventionForm.hidden = true;
  startOperation("intervention.create", {
    goal_id: app.currentGoalId,
    target_node_id: app.selected.id,
    text,
  });
});

ui.closeCommitPanel.addEventListener("click", closeCommitPanel);
ui.commitForm.addEventListener("submit", (event) => {
  event.preventDefault();
  if (!app.commitProposal) return;
  const type = app.commitProposal.intent === "commit_push" ? "git.commit_push" : "git.commit";
  const payload = {
    proposal_id: app.commitProposal.proposal_id,
    subject: ui.commitSubject.value,
    body: ui.commitBody.value,
  };
  startOperation(type, payload);
});

ui.graphScroll.addEventListener("wheel", (event) => {
  if (!app.graphSize || !app.currentState || !app.runtime || app.runtime.mode !== "long-run") return;
  event.preventDefault();
  const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? ui.graphScroll.clientHeight : 1;
  const nextScale = Math.min(
    1.8,
    Math.max(0.45, Math.round(app.graphScale * Math.exp(-event.deltaY * unit * 0.0012) * 100) / 100)
  );
  if (nextScale === app.graphScale) return;
  const bounds = ui.graphScroll.getBoundingClientRect();
  const localX = event.clientX - bounds.left;
  const localY = event.clientY - bounds.top;
  const anchorX = (ui.graphScroll.scrollLeft + localX) / app.graphScale;
  const anchorY = (ui.graphScroll.scrollTop + localY) / app.graphScale;
  app.graphScale = nextScale;
  applyGraphScale();
  ui.graphScroll.scrollLeft = Math.max(0, anchorX * nextScale - localX);
  ui.graphScroll.scrollTop = Math.max(0, anchorY * nextScale - localY);
}, { passive: false });

ui.graphScroll.addEventListener("pointerdown", (event) => {
  if (event.button !== 0 || event.target.closest(".graph-node")) return;
  app.pan = {
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
  if (!app.pan || app.pan.pointerId !== event.pointerId) return;
  ui.graphScroll.scrollLeft = app.pan.scrollLeft - (event.clientX - app.pan.x);
  ui.graphScroll.scrollTop = app.pan.scrollTop - (event.clientY - app.pan.y);
});
function stopPan(event) {
  if (!app.pan || app.pan.pointerId !== event.pointerId) return;
  app.pan = null;
  ui.graphScroll.classList.remove("is-panning");
}
ui.graphScroll.addEventListener("pointerup", stopPan);
ui.graphScroll.addEventListener("pointercancel", stopPan);

window.addEventListener("popstate", async () => {
  const goalId = routeGoalId();
  if (goalId && goalId !== app.currentGoalId) {
    app.currentGoalId = goalId;
    app.goalEtag = null;
    app.graphScale = 1;
    app.graphSize = null;
    app.lastActiveNode = null;
    await pollGoals();
  }
});
window.addEventListener("resize", () => {
  if (app.currentState && app.runtime && app.runtime.mode === "long-run") renderGraph(app.currentState);
});

bootstrap();
