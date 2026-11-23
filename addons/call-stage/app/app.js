const tabs = document.querySelector("#tabs");
const panel = document.querySelector("#panel");
const panelBody = document.querySelector("#panel-body");
const lanes = document.querySelector("#lanes");
const guides = document.querySelector("#guides");
const sequence = document.querySelector("#sequence");
const empty = document.querySelector("#empty");
const live = document.querySelector("#live");
const liveLabel = document.querySelector("#live-label");
const modal = document.querySelector("#modal");
const modalTitle = document.querySelector("#modal-title");
const modalBody = document.querySelector("#modal-body");
const network = document.querySelector("#network");
const networkRows = document.querySelector("#network-rows");
const networkDetail = document.querySelector("#network-detail");
const networkToggle = document.querySelector("#network-toggle");
const networkScale = document.querySelector("#network-scale");
const historyBoard = document.querySelector("#history");
const historyList = document.querySelector("#history-list");
const historyToggle = document.querySelector("#history-toggle");

const ICONS = {
  client: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="4" y="5" width="16" height="12" rx="2"/><path d="M8 21h8M12 17v4"/></svg>',
  api: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path d="M8 8L4 12l4 4M16 8l4 4-4 4M13 6l-2 12"/></svg>',
};

const MARK = '<svg viewBox="0 0 491 469" aria-hidden="true"><path d="M234.539 0C105.007 0.00197474 0.00124218 104.99 0 234.499C-1.16182e-05 364.01 105.005 469 234.54 469L341.58 469V354.155H491L378.608 222.981H228.447L340.729 354.029L234.54 354.029C168.514 354.029 114.993 300.515 114.991 234.501C114.991 168.488 168.515 114.973 234.54 114.971C267.35 114.972 297.054 128.17 318.669 149.576L328.148 158.963L408.435 76.5927L399.049 67.3571C356.729 25.7155 298.623 0.00099608 234.539 0Z" fill="url(#gravitee-mark)"/><defs><linearGradient id="gravitee-mark" x1="443.632" y1="25.448" x2="53.0113" y2="469.07" gradientUnits="userSpaceOnUse"><stop stop-color="#FF7200"/><stop offset="1" stop-color="#F01114"/></linearGradient></defs></svg>';

const LANES = {
  client: { css: "client", name: "Client", sub: "Sent the request" },
  gravitee: { css: "gateway", name: "Gravitee", sub: "API gateway" },
  api: { css: "api", name: "API", sub: "" },
};

function pathOf(url) {
  try { return new URL(url).pathname; } catch (error) { return url; }
}

function wait(ms) {
  return new Promise((done) => setTimeout(done, ms));
}

function setLive(text, state) {
  live.className = "live" + (state ? " " + state : "");
  liveLabel.textContent = text;
}

function colorOf(kind) {
  if (kind === "gravitee") return "#f01114";
  if (kind === "api") return "#059669";
  return "#64748b";
}

function renderLanes(participants, requestPath) {
  const columns = "repeat(" + participants.length + ", minmax(0, 1fr))";
  lanes.style.gridTemplateColumns = columns;
  guides.style.gridTemplateColumns = columns;
  lanes.replaceChildren();
  guides.replaceChildren();
  participants.forEach((kind) => {
    const meta = LANES[kind];
    const lane = document.createElement("div");
    lane.className = "lane " + meta.css;
    const icon = document.createElement("div");
    icon.className = "lane-icon";
    icon.innerHTML = kind === "gravitee" ? MARK : ICONS[kind];
    const title = document.createElement("span");
    title.className = "lane-name";
    title.textContent = meta.name;
    const sub = document.createElement("span");
    sub.className = "lane-sub";
    sub.textContent = kind === "api" ? requestPath : meta.sub;
    lane.append(icon, title, sub);
    lanes.append(lane);
    const line = document.createElement("i");
    line.className = meta.css;
    guides.append(line);
  });
}

let linksObserver = null;

function clearDiagram() {
  if (linksObserver) linksObserver.disconnect();
  linksObserver = null;
  lanes.replaceChildren();
  guides.replaceChildren();
  sequence.replaceChildren();
  empty.hidden = false;
}

function shortBody(body) {
  const text = (body || "").trim();
  if (!text) return "Empty response";
  try {
    const data = JSON.parse(text);
    if (typeof data.count === "number") return data.count + (data.count === 1 ? " service" : " services");
    if (data.message) return String(data.message);
    if (data.error) return String(data.error);
  } catch (error) { /* plain text */ }
  return text.length > 64 ? text.slice(0, 64) + "…" : text;
}

function pretty(body) {
  const text = body || "";
  try { return JSON.stringify(JSON.parse(text), null, 2); } catch (error) { return text; }
}

function headerLines(headers) {
  const names = Object.keys(headers || {});
  if (!names.length) return "(none)";
  return names.map((name) => name + ": " + headers[name]).join("\n");
}

function openModal(title, blocks) {
  modalTitle.textContent = title;
  modalBody.replaceChildren();
  blocks.forEach((block) => {
    const heading = document.createElement("h3");
    heading.textContent = block.label;
    const body = document.createElement("pre");
    body.textContent = block.text;
    modalBody.append(heading, body);
  });
  modal.hidden = false;
}

function closeModal() {
  modal.hidden = true;
}

modal.addEventListener("click", (event) => { if (event.target === modal) closeModal(); });
document.querySelector("#modal-close").addEventListener("click", closeModal);
document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeModal(); });

function graviteeLines(log) {
  const lines = [];
  if (!log) return lines;
  if (log.message) lines.push(log.message);
  if (log.plan) lines.push("Plan: " + log.plan);
  if (log.application) lines.push("Application: " + log.application);
  if (log.gatewayMs !== undefined && log.gatewayMs !== null) lines.push("Gateway: " + log.gatewayMs + " ms");
  const seen = [log.method, log.uri].filter(Boolean).join(" ");
  if (seen) lines.push(seen);
  return lines;
}

function graviteeNote(payload) {
  const accepted = payload.trace && payload.trace.apiAnswered;
  const fallback = accepted ? "Accepted" : "Rejected";
  const log = payload.gravitee;
  if (!log) return fallback;
  const parts = [log.plan, log.application].filter(Boolean);
  return parts.join(" · ") || fallback;
}

function detailBlocks(payload, note, includeLog) {
  const blocks = [];
  if (note) blocks.push({ label: "What happened", text: note });
  const logged = includeLog ? graviteeLines(payload.gravitee) : [];
  if (logged.length) blocks.push({ label: "Gravitee log", text: logged.join("\n") });
  blocks.push({
    label: "Request",
    text: payload.request.method + " " + payload.request.url + "\n\n" + headerLines(payload.request.headers),
  });
  blocks.push({
    label: "Response",
    text: payload.status + " · " + payload.elapsed + " ms\n\n" + headerLines(payload.responseHeaders) + "\n\n" + pretty(payload.body),
  });
  return blocks;
}

function card(css, phase, title, detail, onClick) {
  const box = document.createElement("button");
  box.type = "button";
  box.className = "card " + css + " arriving";
  const tag = document.createElement("em");
  tag.textContent = phase === "request" ? "Request" : "Response";
  const heading = document.createElement("b");
  heading.textContent = title;
  const note = document.createElement("span");
  note.textContent = detail;
  box.append(tag, heading, note);
  box.dataset.phase = phase;
  box.addEventListener("click", onClick);
  return box;
}

function edges(item, origin) {
  const box = item.getBoundingClientRect();
  return {
    left: box.left - origin.left,
    right: box.right - origin.left,
    top: box.top - origin.top,
    bottom: box.bottom - origin.top,
    midX: box.left - origin.left + box.width / 2,
    midY: box.top - origin.top + box.height / 2,
  };
}

function connect(stage, pairs) {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("class", "links");
  const marker = document.createElementNS(ns, "marker");
  marker.setAttribute("id", "to-box");
  marker.setAttribute("viewBox", "0 0 10 10");
  marker.setAttribute("refX", "9");
  marker.setAttribute("refY", "5");
  marker.setAttribute("markerWidth", "7");
  marker.setAttribute("markerHeight", "7");
  marker.setAttribute("orient", "auto");
  const head = document.createElementNS(ns, "path");
  head.setAttribute("d", "M 0 0 L 10 5 L 0 10 Z");
  head.setAttribute("fill", "context-stroke");
  marker.append(head);
  const defs = document.createElementNS(ns, "defs");
  defs.append(marker);
  svg.append(defs);
  stage.append(svg);

  let shown = 0;
  let animateFrom = 0;
  function ends(pair, origin) {
    const from = edges(pair.from, origin);
    const to = edges(pair.to, origin);
    if (pair.way === "down") return [from.midX, from.bottom, to.midX, to.top, colorOf(pair.kind), colorOf(pair.kind)];
    if (pair.way === "back") return [from.left, from.midY, to.right, to.midY, colorOf(pair.fromKind), colorOf(pair.toKind)];
    return [from.right, from.midY, to.left, to.midY, colorOf(pair.fromKind), colorOf(pair.toKind)];
  }
  function paint(animate) {
    const origin = stage.getBoundingClientRect();
    const visible = pairs.slice(0, shown);
    const lines = [...svg.querySelectorAll("line")];
    if (!animate && lines.length === visible.length) {
      visible.forEach((pair, index) => {
        const [x1, y1, x2, y2] = ends(pair, origin);
        const line = lines[index];
        line.setAttribute("x1", x1);
        line.setAttribute("y1", y1);
        line.setAttribute("x2", x2);
        line.setAttribute("y2", y2);
        const gradient = svg.querySelector("#" + line.dataset.grad);
        if (!gradient) return;
        gradient.setAttribute("x1", x1);
        gradient.setAttribute("y1", y1);
        gradient.setAttribute("x2", x2);
        gradient.setAttribute("y2", y2);
      });
      return;
    }
    svg.querySelectorAll("line, linearGradient, circle").forEach((node) => node.remove());
    let count = 0;
    function add(x1, y1, x2, y2, from, to, travel) {
      const id = "link-" + count;
      count += 1;
      const gradient = document.createElementNS(ns, "linearGradient");
      gradient.setAttribute("id", id);
      gradient.setAttribute("gradientUnits", "userSpaceOnUse");
      gradient.setAttribute("x1", x1);
      gradient.setAttribute("y1", y1);
      gradient.setAttribute("x2", x2);
      gradient.setAttribute("y2", y2);
      const start = document.createElementNS(ns, "stop");
      start.setAttribute("stop-color", from);
      const end = document.createElementNS(ns, "stop");
      end.setAttribute("offset", "1");
      end.setAttribute("stop-color", to);
      gradient.append(start, end);
      const line = document.createElementNS(ns, "line");
      line.setAttribute("x1", x1);
      line.setAttribute("y1", y1);
      line.setAttribute("x2", x2);
      line.setAttribute("y2", y2);
      line.setAttribute("stroke", "url(#" + id + ")");
      line.setAttribute("stroke-width", "2");
      line.dataset.grad = id;
      const length = Math.hypot(x2 - x1, y2 - y1) || 1;
      line.style.strokeDasharray = String(length);
      line.style.strokeDashoffset = travel ? String(length) : "0";
      svg.append(gradient, line);
      if (!travel) {
        line.setAttribute("marker-end", "url(#to-box)");
        return;
      }
      const dot = document.createElementNS(ns, "circle");
      dot.setAttribute("r", "4");
      dot.setAttribute("fill", to);
      const motion = document.createElementNS(ns, "animateMotion");
      motion.setAttribute("dur", "1.2s");
      motion.setAttribute("repeatCount", "1");
      motion.setAttribute("fill", "freeze");
      motion.setAttribute("path", "M " + x1 + " " + y1 + " L " + x2 + " " + y2);
      dot.append(motion);
      svg.append(dot);
      line.getBoundingClientRect();
      line.style.transition = "stroke-dashoffset 1.2s ease-out";
      line.style.strokeDashoffset = "0";
      line.addEventListener("transitionend", () => {
        line.setAttribute("marker-end", "url(#to-box)");
        dot.remove();
      }, { once: true });
    }
    visible.forEach((pair, index) => {
      const [x1, y1, x2, y2, from, to] = ends(pair, origin);
      add(x1, y1, x2, y2, from, to, animate && index >= animateFrom);
    });
  }

  if (linksObserver) linksObserver.disconnect();
  linksObserver = new ResizeObserver(() => paint(false));
  linksObserver.observe(stage);
  pairs.forEach((pair) => {
    linksObserver.observe(pair.from);
    linksObserver.observe(pair.to);
  });
  stage._repaint = () => paint(false);
  return (count, from) => {
    shown = count;
    animateFrom = from === undefined ? count : from;
    paint(true);
  };
}

function summary(payload) {
  const good = payload.status >= 200 && payload.status < 300;
  const detail = document.createElement("section");
  detail.className = "detail arriving";
  const top = document.createElement("div");
  top.className = "detail-top";
  const badge = document.createElement("span");
  badge.className = "badge " + (good ? "ok" : "err");
  badge.textContent = String(payload.status);
  const route = document.createElement("span");
  route.className = "route";
  route.textContent = payload.request.method + " " + payload.request.url;
  const elapsed = document.createElement("span");
  elapsed.className = "ms";
  elapsed.textContent = payload.elapsed + " ms";
  top.append(badge, route, elapsed);
  detail.append(top);
  return detail;
}

function requestCard(kind, payload) {
  const path = pathOf(payload.request.url);
  const open = (title, note, includeLog) => () => openModal(title, detailBlocks(payload, note, includeLog));
  if (kind === "gravitee") {
    const accepted = payload.trace.apiAnswered;
    const box = card("gateway " + (accepted ? "good" : "bad"), "request", "API key", graviteeNote(payload), open("Gravitee · request", accepted ? "Gravitee forwarded the call." : "Gravitee rejected the call.", true));
    box.dataset.kind = "gravitee";
    return box;
  }
  const css = kind === "api" ? "api" : "client";
  const title = kind === "api" ? "API" : "Client";
  return card(css, "request", payload.request.method, path, open(title + " · request", "This request was sent on."));
}

function responseCard(kind, payload) {
  const good = payload.status >= 200 && payload.status < 300;
  const tone = good ? "good" : "bad";
  const css = kind === "gravitee" ? "gateway" : kind;
  const name = kind === "gravitee" ? "Gravitee" : kind === "api" ? "API" : "Client";
  const box = card(css + " " + tone, "response", String(payload.status), shortBody(payload.body), () => openModal(name + " · response", detailBlocks(payload, "This response came back.", kind === "gravitee")));
  if (kind === "gravitee") box.dataset.kind = "gravitee";
  return box;
}

function briefHeaders(headers) {
  const names = Object.keys(headers || {}).slice(0, 3);
  if (!names.length) return "";
  return names.map((name) => name + ": " + headers[name]).join("\n");
}

function fillFlight(node, payload, kind) {
  node.replaceChildren();
  const tag = document.createElement("em");
  tag.textContent = kind === "request" ? "Request" : "Response";
  const title = document.createElement("b");
  const detail = document.createElement("span");
  if (kind === "request") {
    title.textContent = payload.request.method;
    const headers = briefHeaders(payload.request.headers);
    detail.textContent = pathOf(payload.request.url) + (headers ? "\n" + headers : "");
  } else {
    title.textContent = String(payload.status);
    detail.textContent = shortBody(payload.body);
  }
  node.append(tag, title, detail);
}

function placeFlight(stage, pair, node) {
  const origin = stage.getBoundingClientRect();
  const from = edges(pair.from, origin);
  const to = edges(pair.to, origin);
  const down = pair.way === "down";
  const x = down ? from.midX : (pair.way === "back" ? (from.left + to.right) / 2 : (from.right + to.left) / 2);
  const y = down ? (from.bottom + to.top) / 2 : from.midY;
  node.classList.toggle("down", down);
  node.style.left = x + "px";
  node.style.top = y + "px";
}

async function draw(payload, replay) {
  const participants = payload.trace.participants;
  renderLanes(participants, pathOf(payload.request.url));
  sequence.replaceChildren();
  empty.hidden = true;
  const stage = document.createElement("div");
  stage.className = "stage";
  stage.style.gridTemplateColumns = "repeat(" + participants.length + ", minmax(0, 1fr))";
  const requests = [];
  const responses = [];
  participants.forEach((kind, index) => {
    const column = document.createElement("div");
    column.className = "column";
    const request = requestCard(kind, payload);
    const response = responseCard(kind, payload);
    request.style.gridColumn = String(index + 1);
    request.style.gridRow = "1";
    response.style.gridColumn = String(index + 1);
    response.style.gridRow = "2";
    column.append(request, response);
    requests.push(request);
    responses.push(response);
    stage.append(column);
  });
  stage._payload = payload;
  sequence.append(stage);
  if (!replay) watchGravitee(payload);
  const pairs = [];
  for (let index = 0; index < participants.length - 1; index += 1) {
    pairs.push({ from: requests[index], to: requests[index + 1], way: "forward", fromKind: participants[index], toKind: participants[index + 1] });
  }
  const last = participants.length - 1;
  pairs.push({ from: requests[last], to: responses[last], way: "down", kind: participants[last] });
  for (let index = last; index >= 1; index -= 1) {
    pairs.push({ from: responses[index], to: responses[index - 1], way: "back", fromKind: participants[index], toKind: participants[index - 1] });
  }
  const setShown = connect(stage, pairs);
  if (replay) {
    setShown(pairs.length);
    sequence.append(summary(payload));
    return true;
  }
  const boxes = requests.concat(responses);
  let flight = null;
  let flightKind = "";
  function showFlight(pair, kind) {
    if (flight && flightKind !== kind) {
      flight.remove();
      flight = null;
    }
    flightKind = kind;
    if (!flight) {
      flight = document.createElement("div");
      flight.className = "flight";
      fillFlight(flight, payload, kind);
      placeFlight(stage, pair, flight);
      stage.append(flight);
      return;
    }
    fillFlight(flight, payload, kind);
    placeFlight(stage, pair, flight);
  }
  async function dismissFlight() {
    if (!flight) return true;
    const node = flight;
    flight = null;
    node.classList.add("leaving");
    await wait(280);
    node.remove();
    return generation === drawing;
  }
  if (!slowDraw) {
    setShown(pairs.length, 0);
    const outbound = pairs.find((pair) => pair.way === "forward") || pairs[0];
    const inbound = pairs.find((pair) => pair.way === "down") || pairs[pairs.length - 1];
    if (outbound) showFlight(outbound, "request");
    if (!await step(800)) return false;
    if (inbound) showFlight(inbound, "response");
    if (!await step(800)) return false;
    if (!await dismissFlight()) return false;
    sequence.append(summary(payload));
    return true;
  }
  boxes.forEach((item) => item.classList.add("held"));
  let cursor = 0;
  function reveal(item) { item.classList.remove("held"); }
  reveal(requests[0]);
  for (let index = 0; index < last; index += 1) {
    if (!await step()) return false;
    cursor += 1;
    setShown(cursor, cursor - 1);
    reveal(requests[index + 1]);
    showFlight(pairs[cursor - 1], "request");
  }
  if (!await step()) return false;
  cursor += 1;
  setShown(cursor, cursor - 1);
  reveal(responses[last]);
  showFlight(pairs[cursor - 1], "response");
  for (let index = last - 1; index >= 0; index -= 1) {
    if (!await step()) return false;
    cursor += 1;
    setShown(cursor, cursor - 1);
    reveal(responses[index]);
    showFlight(pairs[cursor - 1], "response");
  }
  if (!await step()) return false;
  if (!await dismissFlight()) return false;
  sequence.append(summary(payload));
  return true;
}

const STEP = 1400;
let generation = 0;
let selected = null;
let slowDraw = true;

async function step(ms) {
  await wait(ms === undefined ? STEP : ms);
  return generation === drawing;
}

let drawing = 0;

const entries = [];
let selectedEntry = 0;

function clock(ms) {
  if (ms < 1000) return Math.round(ms) + " ms";
  return (ms / 1000).toFixed(2) + " s";
}

function renderDetail(entry) {
  networkDetail.replaceChildren();
  if (!entry) {
    const hint = document.createElement("p");
    hint.className = "network-hint";
    hint.textContent = entries.length ? "Select a call." : "A call appears here after you press Call.";
    networkDetail.append(hint);
    return;
  }
  const title = document.createElement("h2");
  title.textContent = entry.method + " " + entry.path;
  const meta = document.createElement("div");
  meta.className = "meta";
  const status = document.createElement("span");
  status.className = "net-status " + (entry.ok ? "ok" : "err");
  status.textContent = String(entry.status);
  const time = document.createElement("span");
  time.textContent = clock(entry.elapsed);
  meta.append(status, time);
  networkDetail.append(title, meta);
  function block(label, text) {
    const heading = document.createElement("h3");
    heading.textContent = label;
    const pre = document.createElement("pre");
    pre.textContent = text;
    networkDetail.append(heading, pre);
  }
  block("URL", entry.url);
  const logged = graviteeLines(entry.payload && entry.payload.gravitee);
  if (logged.length) block("Gravitee log", logged.join("\n"));
  block("Request headers", headerLines(entry.requestHeaders));
  block("Response headers", headerLines(entry.responseHeaders));
  block("Response", pretty(entry.body));
}

function renderNetwork() {
  networkRows.replaceChildren();
  if (!entries.length) {
    networkScale.textContent = "Waterfall";
    renderDetail(null);
    return;
  }
  const origin = entries[0].started;
  const span = Math.max(...entries.map((entry) => entry.started + entry.elapsed)) - origin || 1;
  networkScale.textContent = clock(span);
  const chosen = entries.find((entry) => entry.id === selectedEntry) || entries[entries.length - 1];
  selectedEntry = chosen.id;
  entries.forEach((entry) => {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "net-row" + (entry.id === selectedEntry ? " selected" : "");
    const name = document.createElement("span");
    name.className = "net-name";
    const verb = document.createElement("b");
    verb.textContent = entry.method;
    name.append(verb, document.createTextNode(entry.path));
    name.title = entry.url;
    const status = document.createElement("span");
    status.className = "net-status " + (entry.ok ? "ok" : "err");
    status.textContent = String(entry.status);
    const time = document.createElement("span");
    time.className = "net-time";
    time.textContent = clock(entry.elapsed);
    const water = document.createElement("span");
    water.className = "water";
    const bar = document.createElement("i");
    if (!entry.ok) bar.className = "err";
    bar.style.left = ((entry.started - origin) / span) * 100 + "%";
    bar.style.width = (entry.elapsed / span) * 100 + "%";
    water.append(bar);
    row.append(name, status, time, water);
    row.addEventListener("click", () => showSaved(entry, false));
    networkRows.append(row);
  });
  renderDetail(chosen);
}

function renderHistory() {
  historyList.replaceChildren();
  if (!entries.length) {
    const hint = document.createElement("p");
    hint.className = "history-empty";
    hint.textContent = "Calls stay here until you refresh.";
    historyList.append(hint);
    return;
  }
  entries.slice().reverse().forEach((entry) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "history-item" + (entry.id === selectedEntry ? " selected" : "");
    const status = document.createElement("span");
    status.className = "net-status " + (entry.ok ? "ok" : "err");
    status.textContent = String(entry.status);
    const name = document.createElement("b");
    name.textContent = entry.name;
    const when = document.createElement("span");
    when.className = "when";
    when.textContent = entry.when + " · " + clock(entry.elapsed);
    button.append(status, name, when);
    button.addEventListener("click", () => showSaved(entry, true));
    historyList.append(button);
  });
}

function showSaved(entry, hide) {
  generation += 1;
  drawing = generation;
  document.querySelectorAll(".tab").forEach((tab) => { tab.disabled = false; });
  document.querySelector("#draw").disabled = selected === null;
  selectedEntry = entry.id;
  renderNetwork();
  renderHistory();
  closeModal();
  setLive(entry.name + " · " + entry.status, entry.ok ? "ok" : "err");
  draw(entry.payload, true);
  if (hide) setHistory(false);
}

function setHistory(open) {
  historyBoard.hidden = !open;
  historyToggle.setAttribute("aria-pressed", open ? "true" : "false");
  if (open) renderHistory();
}

function headerValue(headers, name) {
  const found = Object.keys(headers || {}).find((item) => item.toLowerCase() === name);
  return found ? headers[found] : "";
}

function refreshGravitee(payload) {
  const stage = sequence.querySelector(".stage");
  if (stage && stage._payload === payload) {
    const note = stage.querySelector('[data-kind="gravitee"][data-phase="request"] span');
    if (note) note.textContent = graviteeNote(payload);
    if (stage._repaint) stage._repaint();
  }
  const entry = entries.find((item) => item.payload === payload);
  if (entry && entry.id === selectedEntry) renderDetail(entry);
}

function watchGravitee(payload) {
  if (!payload.trace || payload.trace.participants.indexOf("gravitee") === -1) return;
  const requestId = headerValue(payload.responseHeaders, "x-gravitee-request-id");
  if (!requestId) return;
  const path = pathOf(payload.request.url);
  fetch("/api/gravitee?requestId=" + encodeURIComponent(requestId) + "&path=" + encodeURIComponent(path))
    .then((response) => response.json())
    .then((body) => {
      if (!body || !body.log) return;
      payload.gravitee = body.log;
      refreshGravitee(payload);
    })
    .catch(() => {});
}

function remember(payload, started, call) {
  entries.push({
    id: entries.length + 1,
    name: call.name,
    when: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
    method: payload.request.method,
    url: payload.request.url,
    path: pathOf(payload.request.url),
    status: payload.status,
    ok: payload.status >= 200 && payload.status < 300,
    elapsed: payload.elapsed,
    started,
    requestHeaders: payload.request.headers,
    responseHeaders: payload.responseHeaders,
    body: payload.body,
    payload,
  });
  selectedEntry = entries[entries.length - 1].id;
  renderNetwork();
  renderHistory();
}

networkToggle.addEventListener("click", () => {
  const open = network.hidden;
  network.hidden = !open;
  networkToggle.setAttribute("aria-pressed", open ? "true" : "false");
  if (open) renderNetwork();
});

historyToggle.addEventListener("click", () => setHistory(historyBoard.hidden));
document.querySelector("#history-close").addEventListener("click", () => setHistory(false));

async function fire(call, button) {
  const mine = ++generation;
  drawing = mine;
  slowDraw = document.querySelector("#slow").checked;
  document.querySelector("#draw").disabled = true;
  document.querySelectorAll(".tab").forEach((tab) => { tab.disabled = true; });
  closeModal();
  clearDiagram();
  empty.textContent = "Sending " + call.name + "…";
  setLive("Sending " + call.name, "busy");
  const started = performance.now();
  const response = await fetch("/api/calls/" + encodeURIComponent(call.id), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key: call.input ? call.input.value : "" }),
  });
  const payload = await response.json();
  if (!payload.error) remember(payload, started, call);
  if (payload.error) {
    empty.textContent = payload.error;
    setLive(payload.error, "err");
  } else if (mine === generation) {
    const finished = await draw(payload);
    if (finished && mine === generation) {
      const good = payload.status >= 200 && payload.status < 300;
      setLive(call.name + " · " + payload.status, good ? "ok" : "err");
      const chip = button.querySelector(".tab-status");
      chip.textContent = String(payload.status);
      chip.className = "tab-status " + (good ? "ok" : "err");
    }
  }
  if (mine === generation) {
    document.querySelectorAll(".tab").forEach((tab) => { tab.disabled = false; });
    document.querySelector("#draw").disabled = selected === null;
  }
}

async function load() {
  const response = await fetch("/api/calls");
  const spec = await response.json();
  document.querySelector("#title").textContent = spec.title || "Call stage";
  const calls = spec.calls || [];
  tabs.replaceChildren();
  panel.classList.remove("open");
  panelBody.replaceChildren();
  clearDiagram();
  if (!calls.length) {
    empty.textContent = "No calls are configured. Mount a calls file on this add-on.";
    return;
  }
  empty.textContent = "Choose a call, then press Call.";
  document.querySelector("#draw").addEventListener("click", () => { if (selected) fire(selected.call, selected.button); });
  function showPanel(call) {
    const open = Boolean(call.needsKey || call.hint);
    if (!open) {
      panel.classList.remove("open");
      return;
    }
    panelBody.replaceChildren();
    const heading = document.createElement("h2");
    heading.textContent = call.panel || (call.needsKey ? "Authorization" : "Details");
    panelBody.append(heading);
    if (call.needsKey) {
      if (!call.field) {
        const field = document.createElement("label");
        field.className = "key";
        const caption = document.createElement("span");
        caption.textContent = "Key for this call";
        const input = document.createElement("input");
        input.type = "password";
        input.autocomplete = "off";
        input.spellcheck = false;
        input.placeholder = "Paste the key";
        input.setAttribute("aria-label", "Key for " + call.name);
        field.append(caption, input);
        call.field = field;
        call.input = input;
      }
      panelBody.append(call.field);
    } else if (call.hint) {
      const hint = document.createElement("p");
      hint.className = "hint";
      hint.textContent = call.hint;
      panelBody.append(hint);
    }
    if (!panel.classList.contains("open")) requestAnimationFrame(() => panel.classList.add("open"));
  }
  for (const call of calls) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "tab";
    button.setAttribute("role", "tab");
    const verb = document.createElement("span");
    verb.className = "verb";
    verb.textContent = call.method;
    const label = document.createElement("span");
    label.textContent = call.name;
    const status = document.createElement("span");
    status.className = "tab-status";
    button.append(verb, label, status);
    button.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((tab) => tab.classList.remove("active"));
      button.classList.add("active");
      selected = { call, button };
      document.querySelector("#draw").disabled = false;
      showPanel(call);
    });
    tabs.append(button);
  }
}

load();
