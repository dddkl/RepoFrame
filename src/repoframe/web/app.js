"use strict";

const NS = "http://www.w3.org/2000/svg";
const ui = {
  iterationNav: document.querySelector("#iteration-nav"),
  longRunNav: document.querySelector("#long-run-nav"),
  iterationView: document.querySelector("#iteration-view"),
  longRunView: document.querySelector("#long-run-view"),
  connection: document.querySelector("#connection"),
  connectionLabel: document.querySelector("#connection-label"),
  repositoryName: document.querySelector("#repository-name"),
  branchName: document.querySelector("#branch-name"),
  iterationError: document.querySelector("#iteration-error"),
  changeSummary: document.querySelector("#change-summary"),
  workingStatus: document.querySelector("#working-status"),
  changedFiles: document.querySelector("#changed-files"),
  additions: document.querySelector("#additions"),
  deletions: document.querySelector("#deletions"),
  workingFiles: document.querySelector("#working-files"),
  cleanMessage: document.querySelector("#clean-message"),
  latestCommit: document.querySelector("#latest-commit"),
  recentCommits: document.querySelector("#recent-commits"),
  diagnostics: document.querySelector("#diagnostics"),
  diagnosticTitle: document.querySelector("#diagnostic-title"),
  issueList: document.querySelector("#issue-list"),
  goalSelect: document.querySelector("#goal-select"),
  goalOutcome: document.querySelector("#goal-outcome"),
  graphScroll: document.querySelector("#graph-scroll"),
  graph: document.querySelector("#graph"),
  empty: document.querySelector("#empty-state"),
  emptyTitle: document.querySelector("#empty-title"),
  emptyCopy: document.querySelector("#empty-copy"),
  panel: document.querySelector("#node-panel"),
  closePanel: document.querySelector("#close-panel"),
  nodeStatus: document.querySelector("#node-status"),
  nodeTitle: document.querySelector("#node-title"),
  nodeSummary: document.querySelector("#node-summary"),
  nodeDependencies: document.querySelector("#node-dependencies"),
  nodeEvidence: document.querySelector("#node-evidence"),
};

let mode = "iteration";
let iterationEtag = null;
let goalsEtag = null;
let goalEtag = null;
let goals = [];
let currentGoalId = null;
let currentState = null;
let selectedNodeId = null;
let pan = null;

function setConnection(state, label) {
  ui.connection.dataset.state = state;
  ui.connectionLabel.textContent = label;
}

function route() {
  const match = window.location.pathname.match(/^\/long-run\/([a-z0-9][a-z0-9_-]*)$/);
  mode = window.location.pathname.startsWith("/long-run") ? "long-run" : "iteration";
  currentGoalId = match ? match[1] : null;
  ui.iterationView.hidden = mode !== "iteration";
  ui.longRunView.hidden = mode !== "long-run";
  if (mode === "iteration") ui.iterationNav.setAttribute("aria-current", "page");
  else ui.iterationNav.removeAttribute("aria-current");
  if (mode === "long-run") ui.longRunNav.setAttribute("aria-current", "page");
  else ui.longRunNav.removeAttribute("aria-current");
  if (window.location.pathname === "/") history.replaceState({}, "", "/iteration");
  closeNode();
  refresh();
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

function formatDate(value) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function commitContent(commit, compact = false) {
  if (!commit) {
    const empty = document.createElement("p");
    empty.className = "quiet-empty";
    empty.textContent = "No commits yet.";
    return empty;
  }
  if (compact) {
    const row = document.createElement("li");
    row.className = "commit-row";
    const hash = document.createElement("code");
    hash.className = "commit-hash";
    hash.textContent = commit.short_hash;
    const subject = document.createElement("span");
    subject.className = "subject";
    subject.textContent = commit.subject;
    const time = document.createElement("time");
    time.dateTime = commit.authored_at;
    time.textContent = formatDate(commit.authored_at);
    row.append(hash, subject, time);
    return row;
  }
  const fragment = document.createDocumentFragment();
  const subject = document.createElement("p");
  subject.className = "commit-subject";
  subject.textContent = commit.subject;
  const meta = document.createElement("div");
  meta.className = "commit-meta";
  const hash = document.createElement("code");
  hash.className = "commit-hash";
  hash.textContent = commit.short_hash;
  const author = document.createElement("span");
  author.textContent = commit.author;
  const time = document.createElement("time");
  time.dateTime = commit.authored_at;
  time.textContent = formatDate(commit.authored_at);
  meta.append(hash, author, time);
  fragment.append(subject, meta);
  return fragment;
}

function renderIteration(data) {
  const changes = data.working_changes;
  ui.iterationError.hidden = true;
  ui.repositoryName.textContent = data.repository;
  ui.branchName.textContent = data.branch;
  ui.changedFiles.textContent = String(changes.changed_files);
  ui.additions.textContent = String(changes.additions);
  ui.deletions.textContent = String(changes.deletions);
  ui.changeSummary.textContent = data.clean ? "No local changes" : `${changes.changed_files} changed file${changes.changed_files === 1 ? "" : "s"}`;
  ui.workingStatus.textContent = data.clean ? "Clean" : "In progress";
  ui.cleanMessage.hidden = !data.clean;
  ui.workingFiles.replaceChildren();
  changes.files.forEach((file) => {
    const row = document.createElement("li");
    row.className = "file-row";
    const path = document.createElement("span");
    path.className = "file-path";
    path.textContent = file.path;
    path.title = file.path;
    const state = document.createElement("span");
    state.className = "file-state";
    state.dataset.status = file.status;
    const area = file.staged && file.unstaged ? " · staged + unstaged" : file.staged ? " · staged" : "";
    state.textContent = `${file.status}${area}`;
    row.append(path, state);
    ui.workingFiles.append(row);
  });
  ui.latestCommit.replaceChildren(commitContent(data.latest_commit));
  ui.recentCommits.replaceChildren(...data.recent_commits.map((commit) => commitContent(commit, true)));
  if (!data.recent_commits.length) ui.recentCommits.append(commitContent(null));
}

function showDiagnostics(issues, title = "RepoFrame cannot render the current snapshot.") {
  ui.diagnostics.hidden = false;
  ui.diagnosticTitle.textContent = title;
  ui.issueList.replaceChildren();
  issues.forEach((issue) => {
    const item = document.createElement("li");
    const code = document.createElement("code");
    code.textContent = `${issue.code} ${issue.path || ""}`.trim();
    item.append(code, document.createTextNode(` — ${issue.message}`));
    ui.issueList.append(item);
  });
}

function rankNodes(nodes) {
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const memo = new Map();
  function rank(node) {
    if (memo.has(node.id)) return memo.get(node.id);
    const value = node.depends_on.length ? Math.max(...node.depends_on.map((id) => rank(byId.get(id)))) + 1 : 0;
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
    ui.emptyTitle.textContent = "Waiting for an execution path";
    ui.emptyCopy.textContent = "The Goal is active. Meaningful stages will appear as the Agent progresses.";
    ui.empty.hidden = false;
    ui.graphScroll.hidden = true;
    return;
  }
  ui.empty.hidden = true;
  ui.graphScroll.hidden = false;
  const ranks = rankNodes(nodes);
  const columns = new Map();
  nodes.forEach((node) => {
    const nodeRank = ranks.get(node.id);
    if (!columns.has(nodeRank)) columns.set(nodeRank, []);
    columns.get(nodeRank).push(node);
  });
  const nodeWidth = 230;
  const nodeHeight = 78;
  const columnGap = 112;
  const rowGap = 34;
  const padding = 48;
  const maxRows = Math.max(...Array.from(columns.values(), (column) => column.length));
  const maxRank = Math.max(...ranks.values());
  const contentWidth = padding * 2 + (maxRank + 1) * nodeWidth + maxRank * columnGap;
  const width = Math.max(ui.graphScroll.clientWidth, contentWidth);
  const height = Math.max(ui.graphScroll.clientHeight, padding * 2 + maxRows * nodeHeight + (maxRows - 1) * rowGap);
  ui.graph.setAttribute("viewBox", `0 0 ${width} ${height}`);
  ui.graph.setAttribute("width", width);
  ui.graph.setAttribute("height", height);
  const positions = new Map();
  Array.from(columns.entries()).forEach(([nodeRank, column]) => {
    const contentHeight = column.length * nodeHeight + (column.length - 1) * rowGap;
    const top = Math.max(padding, (height - contentHeight) / 2);
    column.forEach((node, index) => positions.set(node.id, { x: padding + nodeRank * (nodeWidth + columnGap), y: top + index * (nodeHeight + rowGap) }));
  });
  const defs = svgElement("defs");
  const marker = svgElement("marker", { id: "arrow", viewBox: "0 0 10 10", refX: 9, refY: 5, markerWidth: 6, markerHeight: 6, orient: "auto-start-reverse" });
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
      ui.graph.append(svgElement("path", { class: "edge", d: `M ${startX} ${startY} C ${startX + control} ${startY}, ${endX - control} ${endY}, ${endX} ${endY}`, "marker-end": "url(#arrow)" }));
    });
  });
  nodes.forEach((node) => {
    const position = positions.get(node.id);
    const group = svgElement("g", { class: "node", transform: `translate(${position.x} ${position.y})`, tabindex: 0, role: "button", "aria-label": `${node.title}, ${node.status}`, "data-status": node.status });
    group.append(svgElement("rect", { width: nodeWidth, height: nodeHeight, rx: 12 }));
    const status = svgElement("text", { x: 16, y: 24, class: "node-status" });
    status.textContent = node.status;
    const title = svgElement("text", { x: 16, y: 54, class: "node-title" });
    title.textContent = truncated(node.title, 27);
    group.append(status, title);
    const select = () => showNode(node.id);
    group.addEventListener("click", select);
    group.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); select(); }
    });
    ui.graph.append(group);
  });
}

function showNode(nodeId) {
  if (!currentState) return;
  const node = currentState.nodes.find((candidate) => candidate.id === nodeId);
  if (!node) { closeNode(); return; }
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
  ui.goalOutcome.textContent = state.goal.outcome;
  renderGraph(state.nodes);
  if (selectedNodeId) showNode(selectedNodeId);
}

function renderGoals(payload) {
  goals = payload.goals;
  ui.diagnostics.hidden = !payload.issues.length;
  if (payload.issues.length) showDiagnostics(payload.issues, "Some Long Run snapshots could not be loaded.");
  ui.goalSelect.replaceChildren();
  goals.forEach((goal) => {
    const option = document.createElement("option");
    option.value = goal.id;
    option.textContent = `${goal.title} · ${goal.status}`;
    ui.goalSelect.append(option);
  });
  if (!goals.length) {
    currentGoalId = null;
    currentState = null;
    ui.goalOutcome.textContent = "";
    ui.graphScroll.hidden = true;
    ui.emptyTitle.textContent = "No Long Run goal";
    ui.emptyCopy.replaceChildren(
      document.createTextNode("Create one with "),
      Object.assign(document.createElement("code"), { textContent: 'repoframe init --goal "…"' }),
      document.createTextNode("."),
    );
    ui.empty.hidden = false;
    return;
  }
  if (!goals.some((goal) => goal.id === currentGoalId)) {
    currentGoalId = (goals.find((goal) => goal.current) || goals[0]).id;
    history.replaceState({}, "", `/long-run/${currentGoalId}`);
    goalEtag = null;
  }
  ui.goalSelect.value = currentGoalId;
}

async function pollIteration() {
  try {
    const headers = iterationEtag ? { "If-None-Match": iterationEtag } : {};
    const response = await fetch("/api/v1/iteration", { headers, cache: "no-store" });
    if (response.status === 304) { setConnection("online", "Live"); return; }
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.message || `HTTP ${response.status}`);
    iterationEtag = response.headers.get("ETag");
    renderIteration(payload);
    setConnection("online", "Live");
  } catch (error) {
    ui.iterationError.textContent = error.message;
    ui.iterationError.hidden = false;
    setConnection("offline", "Offline");
  }
}

async function pollGoals() {
  try {
    const headers = goalsEtag ? { "If-None-Match": goalsEtag } : {};
    const response = await fetch("/api/v1/goals", { headers, cache: "no-store" });
    if (response.status !== 304) {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      goalsEtag = response.headers.get("ETag");
      renderGoals(await response.json());
    }
    if (!currentGoalId) { setConnection("online", "Live"); return; }
    const goalHeaders = goalEtag ? { "If-None-Match": goalEtag } : {};
    const goalResponse = await fetch(`/api/v1/goals/${encodeURIComponent(currentGoalId)}`, { headers: goalHeaders, cache: "no-store" });
    if (goalResponse.status === 304) { setConnection("online", "Live"); return; }
    if (goalResponse.status === 404) { goalsEtag = null; goalEtag = null; return; }
    if (!goalResponse.ok) throw new Error(`HTTP ${goalResponse.status}`);
    goalEtag = goalResponse.headers.get("ETag");
    renderState(await goalResponse.json());
    setConnection("online", "Live");
  } catch (error) {
    setConnection("offline", "Offline");
  }
}

function refresh() {
  if (mode === "iteration") pollIteration();
  else pollGoals();
}

ui.goalSelect.addEventListener("change", () => {
  currentGoalId = ui.goalSelect.value;
  currentState = null;
  selectedNodeId = null;
  goalEtag = null;
  history.pushState({}, "", `/long-run/${currentGoalId}`);
  pollGoals();
});
ui.closePanel.addEventListener("click", closeNode);
ui.graphScroll.addEventListener("pointerdown", (event) => {
  if (event.button !== 0 || event.target.closest(".node")) return;
  pan = { pointerId: event.pointerId, x: event.clientX, y: event.clientY, scrollLeft: ui.graphScroll.scrollLeft, scrollTop: ui.graphScroll.scrollTop };
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
  if (ui.graphScroll.hasPointerCapture(event.pointerId)) ui.graphScroll.releasePointerCapture(event.pointerId);
  pan = null;
  ui.graphScroll.classList.remove("is-panning");
}
ui.graphScroll.addEventListener("pointerup", stopPanning);
ui.graphScroll.addEventListener("pointercancel", stopPanning);
window.addEventListener("resize", () => { if (mode === "long-run" && currentState) renderGraph(currentState.nodes); });
window.addEventListener("popstate", route);
document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeNode(); });

route();
setInterval(refresh, 1000);
