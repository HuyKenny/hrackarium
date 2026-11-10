// Tiny static server for CI: serves dist/ with the REAL _headers rules applied (CSP, caching, Link …) and 404.html,
// so the visual/CSP/Lighthouse checks see what visitors see on Cloudflare.   node scripts/serve.mjs [port]
import { createServer } from "node:http";
import { readFileSync, existsSync, statSync } from "node:fs";
import { join, extname, normalize } from "node:path";

const root = "dist", port = +(process.argv[2] || 8765);
const MIME = { ".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "text/javascript", ".json": "application/json", ".svg": "image/svg+xml", ".webp": "image/webp",
  ".png": "image/png", ".ico": "image/x-icon", ".woff2": "font/woff2", ".xml": "application/xml", ".txt": "text/plain; charset=utf-8", ".webmanifest": "application/manifest+json" };
const rules = []; let cur = null;
for (const line of readFileSync(join(root, "_headers"), "utf8").split("\n")) {
  if (!line.trim() || line.startsWith("#")) continue;
  if (!/^\s/.test(line)) { cur = { re: new RegExp("^" + line.trim().replace(/[.+?^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*") + "$"), h: [] }; rules.push(cur); }
  else { const i = line.indexOf(":"); cur.h.push([line.slice(0, i).trim(), line.slice(i + 1).trim()]); }
}
const headersFor = (p) => { const m = new Map(); for (const r of rules) if (r.re.test(p)) for (const [k, v] of r.h) m.set(k, m.has(k) ? m.get(k) + ", " + v : v); return m; };
createServer((req, res) => {
  const url = new URL(req.url, "http://x"); let p = decodeURIComponent(url.pathname);
  let f = normalize(join(root, p));
  if (!f.startsWith(root)) { res.writeHead(400); return res.end(); }
  if (existsSync(f) && statSync(f).isDirectory()) f = join(f, "index.html");
  let status = 200;
  if (!existsSync(f)) { f = join(root, "404.html"); status = 404; }
  const h = Object.fromEntries(headersFor(p)); h["Content-Type"] = MIME[extname(f)] || "application/octet-stream";
  res.writeHead(status, h); res.end(readFileSync(f));
}).listen(port, () => console.log("serving dist on " + port));
