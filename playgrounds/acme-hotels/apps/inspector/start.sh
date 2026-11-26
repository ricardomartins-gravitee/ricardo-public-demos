#!/bin/sh
# The inspector image has one agent lane. This names the concierge, the booking desk and the loyalty desk
# from the gateway path, and loads the icons. The anchors are the lines of the pinned inspector image.
set -e
MARK="acme-hotels-agents"
cp /acme-hotels-plus-agents.js /app/public/agents.js
if ! grep -q "$MARK" /app/server.js; then
  node << 'JS'
const fs = require("fs");
const server = "/app/server.js";
const page = "/app/public/app.js";
const html = "/app/public/index.html";
let source = fs.readFileSync(server, "utf8");
const user = "const userText = outermost.userText || 'User request to agent';";
const named = "const speaker = agentOf(outermost && outermost.uri);\n      const userText = outermost.userText || (speaker && speaker.name) || 'User request to agent';";
if (!source.includes(user)) throw new Error("inspector server has no user-text line to name");
source = source.replace(user, named);
const hook = "function isNoise(evt) {";
const agentOf = [
  "/* acme-hotels-agents */",
  "function agentOf(uri) {",
  "  const value = uri || '';",
  "  if (value.includes('/hotel-agent')) return { id: 'concierge', name: 'Concierge', icon: 'ph-user-circle', color: '#1d4ed8' };",
  "  if (value.includes('/booking-desk')) return { id: 'booking', name: 'Booking desk', icon: 'ph-bed', color: '#0f766e' };",
  "  if (value.includes('/loyalty-desk')) return { id: 'loyalty', name: 'Loyalty desk', icon: 'ph-gift', color: '#b45309' };",
  "  return null;",
  "}",
  hook,
].join("\n");
if (!source.includes(hook)) throw new Error("inspector server has no noise filter");
source = source.replace(hook, agentOf);
const broadcast = "    ws.broadcast({\n      type:      'live-steps',\n      apiName:   flowName,";
const withAgent = "    const agent = agentOf(outermost && outermost.uri);\n    ws.broadcast({\n      type:      'live-steps',\n      apiName:   flowName,\n      agent,";
if (!source.includes(broadcast)) throw new Error("inspector server has no live-steps broadcast");
source = source.replace(broadcast, withAgent);
fs.writeFileSync(server, source);

let view = fs.readFileSync(page, "utf8");
const summary = "userText, totalTime, status, phases,";
if (!view.includes(summary)) throw new Error("inspector page has no flow summary");
view = view.replace(summary, summary + "\n      agent: msg.agent || null,");
const status = '<span class="flow-status ${statusClass}"></span>';
const badge = status + '\n      ${summary.agent ? `<span class="flow-agent" style="color:${summary.agent.color}"><i class="ph ${summary.agent.icon}"></i>${escapeHtml(summary.agent.name)}</span>` : \'\'}';
if (!view.includes(status)) throw new Error("inspector page has no flow status");
view = view.replace(status, badge);
const drawn = "stepsEl.appendChild(wrapper);";
if (!view.includes(drawn)) throw new Error("inspector page does not append a flow");
view = view.replace(drawn, drawn + "\n    if (summary.agent && window.decorateFlowAgent) window.decorateFlowAgent(wrapper, summary.agent);");
fs.writeFileSync(page, view);

let index = fs.readFileSync(html, "utf8");
const tag = '<script src="agents.js"></script>\n  <script src="app.js"></script>';
if (!index.includes('<script src="app.js"></script>')) throw new Error("inspector page has no app script");
index = index.replace('<script src="app.js"></script>', tag);
const style = '<style>.flow-agent{display:inline-flex;align-items:center;gap:.25rem;font-weight:600}.flow-agent-mark{display:flex;align-items:center;gap:.25rem;font-size:12px;font-weight:600;margin-bottom:.25rem}</style>';
index = index.replace("</head>", style + "\n</head>");
fs.writeFileSync(html, index);
JS
fi
exec node server.js
