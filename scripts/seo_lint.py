#!/usr/bin/env python3
"""Technical SEO lint of the built site (dist/). Runs in GitHub Actions after the build; nothing runs on the Pi.

    python3 scripts/seo_lint.py [dist] [report.json]

HARD errors (exit 1): invalid JSON-LD, missing/wrong canonical on an indexable page, noindex page listed in a sitemap,
indexable page missing <title>/<h1>/description, sitemap URL without a file, internal link to a page that does not exist
(non-product pages), sitemap over the 50 000 URL limit.
SOFT findings (reported only): long titles/descriptions, duplicate titles, images without alt, orphan products.
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

DIST = Path(sys.argv[1] if len(sys.argv) > 1 else "dist")
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/seo-report.json")
BASE = "https://hrackarium.cz"

pages = {}
for f in DIST.rglob("index.html"):
    d = f.parent.relative_to(DIST).as_posix()
    pages["/" if d == "." else "/" + d + "/"] = f
files = {"/" + p.relative_to(DIST).as_posix() for p in DIST.rglob("*") if p.is_file()}

RX = dict(
    title=re.compile(r"<title>(.*?)</title>", re.S), desc=re.compile(r'<meta name="description" content="([^"]*)"'),
    robots=re.compile(r'<meta name="robots" content="([^"]*)"'), canon=re.compile(r'<link rel="canonical" href="([^"]*)"'),
    h1=re.compile(r"<h1[ >]"), ld=re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S),
    img_noalt=re.compile(r"<img(?![^>]*\balt=)[^>]*>"), href=re.compile(r'href="(/[^"#?]*)"'), lang=re.compile(r'<html lang="cs"'))

hard, soft = defaultdict(list), defaultdict(list)
titles = defaultdict(list)
linked = Counter()
indexable = set()
n_prod = 0
for path, f in pages.items():
    html = f.read_text(errors="replace")
    is_prod = path.startswith("/produkt/")
    n_prod += is_prod
    t = RX["title"].search(html)
    robots = (RX["robots"].search(html) or [None, ""])[1]
    noindex = "noindex" in robots
    if not noindex:
        indexable.add(path)
    for m in RX["href"].finditer(html):
        h = m.group(1)
        linked[h] += 1
        if not is_prod and h.endswith("/") and h not in pages and h != "/" and not h.startswith(("/data/", "/img/", "/assets/")):
            hard["broken internal link"].append(f"{path} -> {h}")
    if noindex and path != "/404/":
        continue
    if not t or not t.group(1).strip():
        hard["missing title"].append(path)
    else:
        title = t.group(1).strip()
        titles[title].append(path)
        if len(title) > 75:
            soft["title > 75 chars"].append(path)
    d = RX["desc"].search(html)
    if not d or len(d.group(1)) < 40:
        hard["missing/short description"].append(path)
    elif len(d.group(1)) > 175:
        soft["description > 175 chars"].append(path)
    if len(RX["h1"].findall(html)) != 1:
        hard["h1 count != 1"].append(path)
    c = RX["canon"].search(html)
    pg = re.match(r"(.*/)strana-\d+/$", path)
    expected = BASE + path
    if not c or c.group(1) != expected:
        hard["canonical != own URL"].append(f"{path} ({c.group(1) if c else 'none'})")
    if not RX["lang"].search(html):
        hard["html lang missing"].append(path)
    for m in RX["ld"].finditer(html):
        try:
            data = json.loads(m.group(1))
            for x in (data if isinstance(data, list) else [data]):
                if x.get("@type") == "Product":
                    off = x.get("offers") or {}
                    if not (off.get("lowPrice") or off.get("price")) or not off.get("priceCurrency"):
                        hard["Product JSON-LD without price/currency"].append(path)
                    if not x.get("name"):
                        hard["Product JSON-LD without name"].append(path)
        except ValueError:
            hard["invalid JSON-LD"].append(path)
    if RX["img_noalt"].search(html):
        soft["<img> without alt attribute"].append(path)

for title, ps in titles.items():
    if len(ps) > 1:
        soft["duplicate title"].append(f"{title[:70]} x{len(ps)}")

# sitemaps
in_sitemap = set()
for sm in DIST.glob("sitemap-*.xml"):
    urls = re.findall(r"<loc>([^<]+)</loc>", sm.read_text())
    if len(urls) > 50000:
        hard["sitemap over 50 000 URLs"].append(sm.name)
    for u in urls:
        p = u.replace(BASE, "")
        in_sitemap.add(p)
        if p not in pages:
            hard["sitemap URL has no page"].append(p)
        elif p not in indexable:
            hard["noindex page in sitemap"].append(p)
missing = [p for p in indexable if p not in in_sitemap and not re.search(r"/strana-\d+/$", p) and p != "/hledat/"]
soft["indexable page not in sitemap"] = missing[:50] + ([f"... {len(missing)} total"] if len(missing) > 50 else [])
orphans = [p for p in in_sitemap if p.startswith("/produkt/") and linked[p] == 0]
soft["orphan product (no internal link)"] = orphans[:30] + ([f"... {len(orphans)} total"] if len(orphans) > 30 else [])
for need in ("/robots.txt", "/sitemap_index.xml", "/404.html", "/.well-known/security.txt", "/favicon.ico", "/site.webmanifest"):
    if need not in files:
        hard["missing file"].append(need)
robots_txt = (DIST / "robots.txt").read_text() if (DIST / "robots.txt").exists() else ""
if "Sitemap:" not in robots_txt:
    hard["robots.txt without Sitemap"].append("robots.txt")

report = {"pages": len(pages), "products": n_prod, "indexable": len(indexable), "in_sitemap": len(in_sitemap),
          "hard": {k: {"count": len(v), "examples": v[:5]} for k, v in hard.items()},
          "soft": {k: {"count": len(v), "examples": v[:5]} for k, v in soft.items() if v}}
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1))
print(f"seo lint: {len(pages)} pages ({n_prod} products), {len(indexable)} indexable, {len(in_sitemap)} in sitemaps")
for k, v in report["hard"].items():
    print(f"  HARD {v['count']:>6}  {k}  e.g. {v['examples'][:2]}")
for k, v in report["soft"].items():
    print(f"  soft {v['count']:>6}  {k}  e.g. {v['examples'][:1]}")
sys.exit(1 if hard else 0)
