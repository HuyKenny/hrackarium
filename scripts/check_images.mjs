// Real-Chrome image check inside GitHub Actions (nothing runs on the Pi): serves dist/ with the same headers as production
// (_headers "/*" block, incl. CSP), opens product pages WITH shop images allowed and reports every image that did not load,
// why (requestfailed errorText, HTTP status, CSP console message) and whether our script swapped in the placeholder.
import puppeteer from "puppeteer-core";
import http from "node:http";
import { readFileSync, existsSync, statSync, writeFileSync, mkdirSync } from "node:fs";
import { join, extname } from "node:path";

const root = "dist", out = process.argv[2] || "/tmp/imgcheck";
mkdirSync(out, { recursive: true });
const hdrText = readFileSync(join(root, "_headers"), "utf8");
const globalHeaders = {};
let inAll = false;
for (const line of hdrText.split("\n")) {
  if (/^\S/.test(line)) inAll = line.trim() === "/*";
  else if (inAll && line.includes(":")) { const i = line.indexOf(":"); globalHeaders[line.slice(0, i).trim()] = line.slice(i + 1).trim(); }
}
const types = { ".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "text/javascript", ".json": "application/json", ".webp": "image/webp", ".png": "image/png", ".svg": "image/svg+xml", ".woff2": "font/woff2", ".ico": "image/x-icon", ".xml": "application/xml", ".txt": "text/plain" };
const server = http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split("?")[0]);
  let f = join(root, p);
  if (existsSync(f) && statSync(f).isDirectory()) f = join(f, "index.html");
  if (!existsSync(f)) { res.writeHead(404, globalHeaders); return res.end("not found"); }
  res.writeHead(200, { ...globalHeaders, "Content-Type": types[extname(f)] || "application/octet-stream" });
  res.end(readFileSync(f));
}).listen(8766);

const sm = readFileSync(join(root, "sitemap-products-1.xml"), "utf8").match(/<loc>[^<]+<\/loc>/g) || [];
const pick = sm.filter((_, i) => i % Math.max(1, Math.floor(sm.length / 6)) === 0).slice(0, 6).map((l) => new URL(l.slice(5, -6)).pathname);
const pages = ["/produkt/epee-stavebnicovy-model-katedrala-svateho-vita/", "/produkt/lego-harry-potter-76475-zapovezeny-les-expecto-patronum-2/", "/lego/", "/stavebnice/", ...pick].filter((p) => existsSync(join(root, p, "index.html")));
const browser = await puppeteer.launch({ executablePath: process.env.CHROME_PATH || "/usr/bin/google-chrome", args: ["--no-sandbox", "--disable-gpu"] });
const report = [];
for (const mobile of [false, true]) {
  const page = await browser.newPage();
  await page.setViewport({ width: mobile ? 390 : 1366, height: 900, isMobile: mobile, hasTouch: mobile });
  const failed = [], bad = [], csp = [];
  page.on("requestfailed", (r) => { if (r.resourceType() === "image") failed.push(`${r.failure()?.errorText} ${r.url().slice(0, 110)}`); });
  page.on("response", (r) => { if (r.request().resourceType() === "image" && r.status() >= 400) bad.push(`HTTP ${r.status()} ${r.url().slice(0, 110)}`); });
  page.on("console", (m) => { if (/Content Security Policy|Refused to load/i.test(m.text())) csp.push(m.text().slice(0, 160)); });
  await page.evaluateOnNewDocument(() => {
    window.__imgErr = [];
    window.addEventListener("error", (e) => { const t = e.target; if (t && t.tagName === "IMG") window.__imgErr.push({ src: (t.currentSrc || t.src || "").slice(0, 120), complete: t.complete, w: t.naturalWidth, lazy: t.loading, cls: (t.parentElement && t.parentElement.className) || "", id: t.id }); }, true);
  });
  for (const p of pages) {
    failed.length = bad.length = csp.length = 0;
    await page.goto(`http://localhost:8766${p}`, { waitUntil: "networkidle2", timeout: 90000 }).catch(() => null);
    await new Promise((r) => setTimeout(r, 4000));
    const imgs = await page.evaluate(() => [...document.querySelectorAll("img")].filter((i) => !i.src.startsWith(location.origin)).map((i) => ({ src: i.currentSrc || i.src, ok: i.complete && i.naturalWidth > 0, lazy: i.loading === "lazy" })));
    const placeholders = await page.evaluate(() => [...document.querySelectorAll("img")].filter((i) => i.src.includes("placeholder.svg")).length);
    const errs = await page.evaluate(() => window.__imgErr || []);
    const notOk = imgs.filter((i) => !i.ok && !i.lazy);
    report.push({ mobile, p, shopImages: imgs.length, notLoaded: notOk.length, placeholders, errs, failed: [...failed], bad: [...bad], csp: [...csp] });
  }
  await page.close();
}
await browser.close(); server.close();
writeFileSync(join(out, "images.json"), JSON.stringify(report, null, 1));
let problems = 0;
for (const r of report) {
  const flag = r.placeholders || r.failed.length || r.bad.length || r.csp.length ? "PROBLEM" : "ok";
  if (flag !== "ok") problems++;
  console.log(`${flag} ${r.mobile ? "m" : "d"} ${r.p} images=${r.shopImages} notLoaded=${r.notLoaded} placeholders=${r.placeholders}`);
  for (const x of [...r.failed, ...r.bad, ...r.csp].slice(0, 6)) console.log("   ", x);
  for (const e of (r.errs || []).slice(0, 6)) console.log("    img error event:", JSON.stringify(e));
}
console.log(`image check: ${report.length} page views, ${problems} with problems`);
