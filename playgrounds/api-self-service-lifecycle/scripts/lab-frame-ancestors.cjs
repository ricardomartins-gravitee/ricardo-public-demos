"use strict";

// MCPJam sends frame-ancestors 'self', so the Lab UI on port 9000 cannot show it.
// This runs inside that process and lets those two pages frame it.
const http = require("http");
const ANCESTORS = "frame-ancestors 'self' http://localhost:9000 http://127.0.0.1:9000";

function loosen(value) {
  if (Array.isArray(value)) return value.map(loosen);
  if (typeof value !== "string" || !value.includes("frame-ancestors")) return value;
  return value.replace(/frame-ancestors[^;]*/, ANCESTORS);
}

function loosenHeaders(headers) {
  if (!headers || typeof headers !== "object") return headers;
  if (Array.isArray(headers)) {
    return headers.map((item, index) => (index % 2 === 1 ? loosen(item) : item));
  }
  const next = { ...headers };
  for (const key of Object.keys(next)) {
    if (key.toLowerCase() === "content-security-policy") next[key] = loosen(next[key]);
  }
  return next;
}

const proto = http.ServerResponse.prototype;
const setHeader = proto.setHeader;
proto.setHeader = function (name, value) {
  const key = String(name).toLowerCase();
  if (rewritten(this) && key === "content-length") return this;
  if (key === "content-security-policy") value = loosen(value);
  if (rewritten(this) && key === "cache-control") return this;
  return setHeader.call(this, name, value);
};
if (typeof proto.setHeaders === "function") {
  const setHeaders = proto.setHeaders;
  proto.setHeaders = function (headers) {
    return setHeaders.call(this, loosenHeaders(headers));
  };
}
const writeHead = proto.writeHead;
proto.writeHead = function (status, reason, headers) {
  if (rewritten(this)) fresh(this);
  if (reason && typeof reason === "object") return writeHead.call(this, status, loosenHeaders(reason));
  if (headers) return writeHead.call(this, status, reason, loosenHeaders(headers));
  return writeHead.apply(this, arguments);
};

// MCPJam stops at startup when another page frames it. The Lab UI is that page.
// The rewritten check is longer, so this response drops Content-Length and is not cached.
const FRAMED = "(()=>{try{if(window.self===window.top)return!1;try{const e=window.top.location.origin===window.location.origin,n=Cot.test(window.location.pathname);if(e&&n)return!1}catch{}return!0}catch{return!0}})()";
const SHOWN = "(!1)";
const chunks = new WeakMap();

function kind(res) {
  const path = ((res.req && res.req.url) || "").split("?")[0];
  if (path.includes("app-bootstrap") && path.endsWith(".js")) return "boot";
  if (path.includes("/assets/index-") && path.endsWith(".js")) return "index";
  if (path === "/" || path === "/index.html") return "html";
  return "";
}

function rewritten(res) {
  return kind(res) !== "";
}

function fresh(res) {
  if (res.headersSent) return;
  try { res.removeHeader("content-length"); } catch (e) {}
  setHeader.call(res, "cache-control", "no-store");
}

function take(chunk, encoding) {
  if (chunk == null) return null;
  return Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk, typeof encoding === "string" ? encoding : "utf8");
}

const write = proto.write;
proto.write = function (chunk, encoding, cb) {
  if (!rewritten(this)) return write.apply(this, arguments);
  const part = take(chunk, encoding);
  if (part) {
    const list = chunks.get(this) || [];
    list.push(part);
    chunks.set(this, list);
  }
  if (typeof encoding === "function") encoding();
  else if (typeof cb === "function") cb();
  return true;
};

const end = proto.end;
proto.end = function (chunk, encoding, cb) {
  if (!rewritten(this)) return end.apply(this, arguments);
  const list = chunks.get(this) || [];
  const part = take(chunk, encoding);
  if (part) list.push(part);
  let body = Buffer.concat(list).toString("utf8");
  if (kind(this) === "boot") body = body.split(FRAMED).join(SHOWN);
  if (kind(this) === "index") body = body.replace(/app-bootstrap-[A-Za-z0-9_-]+\.js(?!\?)/g, "$&?embed=lab");
  if (kind(this) === "html") body = body.replace(/src="(\/assets\/index-[^"]+\.js)"/g, 'src="$1?embed=lab"');
  fresh(this);
  return end.call(this, body, "utf8", typeof encoding === "function" ? encoding : cb);
};
