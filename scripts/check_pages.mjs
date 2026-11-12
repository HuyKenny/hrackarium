// Visual check of the built site inside GitHub Actions (nothing runs on the Raspberry Pi):
// serves dist/ on localhost (no Cloudflare in between), opens key pages at phone, tablet and desktop widths,
// fails on horizontal scrolling (any element wider than the viewport) and saves screenshots as a build artifact.
//   CHROME_PATH=/usr/bin/google-chrome node scripts/check_pages.mjs http://localhost:8765 /tmp/shots
import puppeteer from "puppeteer-core";
import { readFileSync, mkdirSync, writeFileSync } from "node:fs";

const [base, outDir] = [process.argv[2] || "http://localhost:8765", process.argv[3] || "/tmp/shots"];
mkdirSync(outDir, { recursive: true });
const sm = readFileSync("dist/sitemap-products-1.xml", "utf8").match(/<loc>[^<]+<\/loc>/g) || [];
const products = sm.slice(0, 3).map((l) => new URL(l.slice(5, -6)).pathname);
const reported = ["/produkt/prebijena-drevena-stolni-hra-albi/", "/produkt/epee-stavebnicovy-model-katedrala-svateho-vita/", "/produkt/lego-harry-potter-76475-zapovezeny-les-expecto-patronum-2/"];   // pages reported by the owner
const pages = [...reported, "/", "/lego/", "/darky/", "/spolecenske-hry/", "/sberatelske-karty/", "/znacky/", "/postavicky/", "/jak-srovnavame/", "/obchody/", "/kontakt/", "/ochrana-osobnich-udaju/", "/hledat/?q=lego", ...products];
const widths = [360, 390, 820, 1366];
const browser = await puppeteer.launch({ executablePath: process.env.CHROME_PATH || "/usr/bin/google-chrome", args: ["--no-sandbox", "--disable-gpu", "--hide-scrollbars"] });
const page = await browser.newPage();
await page.setRequestInterception(true);
page.on("request", (r) => (r.url().startsWith(base) ? r.continue() : r.respond({ status: 204, body: "" })));   // shop images & GA stay offline (see check_images.mjs for the online check)
const problems = [];
let cur = { w: 0, p: "" };
page.on("console", (m) => { const t = m.text(); if (/Content Security Policy|Refused to|violates the following/i.test(t)) problems.push({ w: cur.w, p: cur.p, issue: "CSP: " + t.slice(0, 160) }); });
page.on("pageerror", (e) => problems.push({ w: cur.w, p: cur.p, issue: "JS error: " + String(e).slice(0, 160) }));
for (const w of widths) {
  await page.setViewport({ width: w, height: 900, isMobile: w < 800, hasTouch: w < 800 });
  for (const p of pages) {
    cur = { w, p };
    const res = await page.goto(base + p, { waitUntil: "networkidle0", timeout: 60000 }).catch((e) => null);
    if (!res || res.status() >= 400) { problems.push({ w, p, issue: `HTTP ${res ? res.status() : "error"}` }); continue; }
    const over = await page.evaluate(() => {
      const W = document.documentElement.clientWidth, bad = [];
      if (document.documentElement.scrollWidth > W + 1) bad.push(`page scrollWidth ${document.documentElement.scrollWidth} > ${W}`);
      for (const e of document.querySelectorAll("body *")) {
        const r = e.getBoundingClientRect();
        if (r.width && r.right > W + 1 && getComputedStyle(e).position !== "fixed") { bad.push(`${e.tagName}.${String(e.className).slice(0, 40)} right=${Math.round(r.right)}`); }
        const s = getComputedStyle(e);
        if ((s.overflowX === "auto" || s.overflowX === "scroll") && e.scrollWidth > e.clientWidth + 2) bad.push(`scroller ${e.tagName}.${String(e.className).slice(0, 40)}`);
        if (bad.length > 5) break;
      }
      return bad;
    });
    if (over.length) problems.push({ w, p, issue: over.join(" | ") });
    if (w === 390 || w === 1366) await page.screenshot({ path: `${outDir}/${w}${p.replace(/[^a-z0-9]+/gi, "_") || "_home"}.png` });
  }
}
// 404 helper: a dead address must land on the nearest category (the server still answers 404), nonsense must stay on the 404 page with suggestions
await page.setViewport({ width: 390, height: 900, isMobile: true, hasTouch: true });
for (const [bad, want] of [["/produkt/lego-creator-neexistuje-xyz-123/", "/lego/"], ["/produkt/odrazedlo-neexistuje-xyz-77/", "/venku/"], ["/qwzxv-nic-takoveho/", null]]) {
  cur = { w: 390, p: bad };
  let first = null;
  const onRes = (x) => { if (first === null && x.url() === base + bad) first = x.status(); };
  page.on("response", onRes);
  await page.goto(base + bad, { waitUntil: "networkidle0", timeout: 60000 }).catch(() => null);
  page.off("response", onRes);
  if (first !== 404) problems.push({ w: 390, p: bad, issue: `dead URL answered ${first} (must stay 404)` });
  await new Promise((x) => setTimeout(x, 2500));
  const path = new URL(page.url()).pathname;
  if (want && !path.startsWith(want)) problems.push({ w: 390, p: bad, issue: `404 redirect went to ${path}, expected ${want}…` });
  if (!want) {
    const n = await page.evaluate(() => document.querySelectorAll("#nf-sugg li").length);
    if (path !== bad || n < 1) problems.push({ w: 390, p: bad, issue: `nonsense URL: path ${path}, suggestions ${n}` });
  }
}
await browser.close();
writeFileSync(`${outDir}/report.json`, JSON.stringify({ pages: pages.length, widths, problems }, null, 1));
console.log(`checked ${pages.length} pages x ${widths.length} widths, problems: ${problems.length}`);
for (const x of problems.slice(0, 30)) console.log(`  ${x.w}px ${x.p}: ${x.issue}`);
process.exit(problems.length ? 1 : 0);
