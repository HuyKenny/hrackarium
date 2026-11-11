#!/usr/bin/env python3
"""Build the static hrackarium.cz site into dist/ from data/raw/*.jsonl.gz.

    HRK_ENV=production python3 scripts/build.py     # indexable build (default: staging = noindex everywhere)
    HRK_MAX_PRODUCTS=20000 python3 scripts/build.py  # cap product pages (staging on workers.dev has no shards)

Output is plain files: Workers static assets serve them for free. When the site has more files than one Worker version
may hold (100 000), scripts/deploy.py moves /produkt/<x>… into shard Workers (routes per first letter).
State (stable slugs, price history, gone products, content hashes) lives in data/state/state.json.gz.
"""
import base64
import hashlib
import json
import os
import re
import shutil
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog as C  # noqa: E402
import render as R  # noqa: E402
import taxonomy as X  # noqa: E402
import landings as LD  # noqa: E402
import texts as TX  # noqa: E402

APP = Path(__file__).resolve().parent.parent
DIST = APP / "dist"
BASE = os.environ.get("HRK_BASE", "https://hrackarium.cz")
ENV = os.environ.get("HRK_ENV", "staging")
GA4 = os.environ.get("GA4_ID", "")
INDEXNOW_KEY = os.environ.get("INDEXNOW_KEY", "")
MAX_PRODUCTS = int(os.environ.get("HRK_MAX_PRODUCTS", "0"))
MAX_PAGES = 30
JSON_ITEMS = 2500
E = R.E
TODAY = date.today()
TODAY_CZ = f"{TODAY.day}. {TODAY.month}. {TODAY.year}"
DAY = TODAY.toordinal()
SUFFIX = " | Hračkárium"


def log(m):
    print(m, file=sys.stderr, flush=True)


INLINE_SCRIPT = re.compile(rb'<script(?: type="speculationrules")?>(.*?)</script>', re.S)


class Out:
    def __init__(self, state):
        self.hashes = state.setdefault("hash", {})
        self.lastmod = state.setdefault("lastmod", {})
        self.changed, self.files, self.sitemap = [], 0, defaultdict(list)
        self.seen = set()
        self.script_hashes = set()      # CSP: our few inline scripts (consent bootstrap, a diagnostic page) are allowed by hash, not 'unsafe-inline'

    def write(self, rel, content):
        p = DIST / rel.lstrip("/")
        p.parent.mkdir(parents=True, exist_ok=True)
        data = content.encode() if isinstance(content, str) else content
        p.write_bytes(data)
        self.files += 1
        if rel.endswith(".html") and b"<script" in data:
            for m in INLINE_SCRIPT.finditer(data):
                self.script_hashes.add(base64.b64encode(hashlib.sha256(m.group(1)).digest()).decode())
        return data

    def page(self, path, html, group=None, index=True):
        if path in self.seen:
            raise SystemExit(f"duplicate page {path}")
        self.seen.add(path)
        data = self.write(path + "index.html", html)
        h = hashlib.md5(re.sub("Poslední aktualizace [^<]+".encode(), b"", data)).hexdigest()[:12]
        if self.hashes.get(path) != h:
            self.hashes[path] = h
            self.lastmod[path] = TODAY.isoformat()
            if index:
                self.changed.append(path)
        if group and index:
            self.sitemap[group].append(path)


def pop_key(p):
    return (-len(p["offers"]), -(1 if p["img"] else 0), -(1 if R.Site.discount(p) >= 10 else 0), p["price"])


def facets(items, S):
    ages = []
    for slug, lbl, lo, hi in X.AGE_BANDS:
        n = sum(1 for p in items if p["age"] is not None and lo <= p["age"] <= hi)
        if n:
            ages.append((lo, hi, lbl.replace("pro děti ", "").replace("pro ", ""), n))
    bc = Counter(p["brand"] for p in items if p["brand"])
    brands = [(i, b, n) for i, (b, n) in enumerate(bc.most_common(60))]
    sc = Counter(o["shop"] for p in items for o in p["offers"])
    return {"age": ages if len(ages) > 1 else [], "brand": brands if len(brands) > 1 else [], "shop": sc.most_common()}


def write_json(out, S, key, items):
    items = items[:JSON_ITEMS]
    bc = [b for b, _ in Counter(p["brand"] for p in items if p["brand"]).most_common(60)]
    bidx = {b: i for i, b in enumerate(bc)}
    out.write(f"data/l/{key}.json", json.dumps({"b": bc, "i": [S.item_json(p, bidx) for p in items]}, ensure_ascii=False, separators=(",", ":")))
    return f"/data/l/{key}.json"


def paged(out, S, path, items, render, group="listings", index=True, per=None):
    pages = max(1, min(-(-len(items) // (per or R.PER_PAGE)), MAX_PAGES))
    for k in range(1, pages + 1):
        S.pg = (path, k, pages)
        S.pg_noindex = k == 1 and not index          # thin listing: noindex AND out of the sitemap (they must agree)
        out.page(path if k == 1 else f"{path}strana-{k}/", render(), group if k == 1 else None, index=index if k == 1 else False)
    S.pg = None
    S.pg_noindex = False


def price_stats(items):
    ps = sorted(p["price"] for p in items)
    if not ps:
        return 0, 0, 0
    return ps[0], int(statistics.median(ps)), ps[-1]


# ======================================================================= main

def main():
    import faulthandler
    faulthandler.dump_traceback_later(int(os.environ.get("HRK_BUILD_WATCHDOG", "1200")), exit=True)   # a hung build prints where it is stuck, then stops
    t0 = time.time()
    shops = [s for s in json.load(open(APP / "data/shops.json"))["shops"] if s.get("enabled", True)]
    rank = {s["id"]: i for i, s in enumerate(shops)}
    state = C.load_state()
    log("full run: range from fresh feeds" if C.full_mode() else "price run: range frozen at the last weekly run, only prices refreshed")
    offers, dropped = C.load_offers(shops)
    if not offers:
        sys.exit("no offers — refusing to build an empty site")
    log(f"{len(offers)} toy offers; not toys / unclassified: {dict(dropped)}")
    products = C.cluster(offers, rank)
    bad = C.sanity(products)
    products = [p for p in products if p["offers"]]
    new_slugs = C.assign_slugs(products, state)
    C.price_history(products, state)
    present = sorted({o["shop"] for p in products for o in p["offers"]})
    multi = sum(1 for p in products if len(p["offers"]) > 1)
    log(f"{len(products)} products ({multi} in 2+ shops), {bad} price errors dropped, {new_slugs} new slugs")

    products.sort(key=pop_key)
    for i, p in enumerate(products):
        p["nkey"] = X.slugify(p["name"])            # computed once: product pages compare it 400x each
        p["page"] = not MAX_PRODUCTS or i < MAX_PRODUCTS
        p["index"] = len(p["offers"]) > 1 or len(p["desc"]) >= 120
    name_count = Counter(p["nkey"] for p in products)           # different products (EAN) with one name -> titles must still differ
    for p in products:
        p["dup"] = name_count[p["nkey"]] > 1
    gone = C.gone_products(products, state, state.get("snap", {}))

    shop_meta = {s["id"]: {"name": s["name"], "color": s.get("color", "#888"), "domain": s["domain"]} for s in shops}
    stats = {"products": len(products), "shops": len(present), "offers": sum(len(p["offers"]) for p in products), "updated": TODAY_CZ}

    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    out = Out(state)
    for f in (APP / "static").rglob("*"):
        if f.is_file():
            rel = f.relative_to(APP / "static").as_posix()
            if rel not in ("assets/site.css", "assets/app.js"):
                out.write(rel, f.read_bytes())
    css = (APP / "static/assets/site.css").read_bytes()
    js = (APP / "static/assets/app.js").read_bytes()
    css_name = f"site.{hashlib.md5(css).hexdigest()[:8]}.css"
    js_name = f"app.{hashlib.md5(js).hexdigest()[:8]}.js"
    out.write("assets/" + css_name, css)
    out.write("assets/" + js_name, js)
    S = R.Site(BASE, ENV, GA4, css_name, js_name, shop_meta, stats)
    S.nav_ok = {p["cat"].split("/")[0] for p in products}

    # ---------------- groupings
    by_cat, by_top = defaultdict(list), defaultdict(list)
    by_brand, by_series, by_lic = defaultdict(list), defaultdict(list), defaultdict(list)
    for p in products:
        by_cat[p["cat"]].append(p)
        top = p["cat"].split("/")[0]
        by_top[top].append(p)
        if p["brand"]:
            by_brand[X.slugify(p["brand"])].append(p)
        if p["cat"] == "lego" and p["lego"]:
            by_series[p["lego"]].append(p)
        for lic in p["lic"]:
            by_lic[lic].append(p)
    brand_name = {b: Counter(p["brand"] for p in ps).most_common(1)[0][0] for b, ps in by_brand.items()}
    reserved = set(X.TREE) | {"lego", "znacky", "produkt", "darky", "data", "hledat", "kategorie", "obchody", "slevy", "postavicky"}
    brand_pages = {b: ps for b, ps in by_brand.items() if len(ps) >= 3 and b}
    series_pages = {s: ps for s, ps in by_series.items() if len(ps) >= 3 and s != "ostatni"}
    lic_name = {s: n for s, n, _ in X.LICENCES}
    lic_pages = {s: ps for s, ps in by_lic.items() if len(ps) >= 6}
    cat_age = {}
    for top, ps in by_top.items():
        for slug, lbl, lo, hi in X.AGE_BANDS:
            sel = [p for p in ps if p["age"] is not None and lo <= p["age"] <= hi]
            if len(sel) >= 12:
                cat_age[(top, slug)] = sel
    S.ctx = {"by_cat": by_cat, "series": series_pages, "lic": lic_pages, "brands": brand_pages, "cat_age": cat_age, "brand_name": brand_name}
    S.lic_name = lic_name
    # ---------------- long-tail landing pages (rules in content/landings/*.json + families in landings.py)
    gift = gift_pages(products)
    reserved = ({f"/{k}/" for k in X.TREE} | {f"/lego/{x}/" for x in series_pages} | {f"/znacky/{b}/" for b in brand_pages} | {f"/hracky-{x}/" for x in lic_pages}
                | set(gift) | {f"/{t}/{ab}/" for (t, ab) in cat_age} | {"/", "/kategorie/", "/znacky/", "/postavicky/", "/darky/", "/slevy/", "/obchody/", "/jak-srovnavame/", "/hledat/"})
    landings, dropped = LD.plan(products, reserved)
    S.landings = {L["path"]: L for L in landings}
    S.kids = LD.kids_map(landings)
    S.footer_links = [(L["path"], L["h1"]) for L in landings if L["slug"] in ("adventni-kalendare", "vanocni-darky")]
    guides = LD.load_guides()
    S.guides = {f"/pruvodce/{g['slug']}/": g for g in guides}
    S.has_guides = bool(guides)
    S.guide_links = defaultdict(list)
    for g in guides:
        for rel in g.get("related", []):
            S.guide_links[rel].append((f"/pruvodce/{g['slug']}/", g["h1"], 0))
    (APP / "data/state").mkdir(parents=True, exist_ok=True)
    (APP / "data/state/landings.tsv").write_text("\n".join(f"{L['path']}\t{L['n']}\t{'index' if L['index'] else 'noindex'}\t{L['group']}\t{L['lo']}" for L in landings))
    dup_titles = Counter((L.get("title") or L["h1"]) for L in landings)
    log(f"landings: duplicate titles: {[t for t, c in dup_titles.items() if c > 1][:8]}")
    log(f"landings: {len(landings)} pages ({sum(1 for L in landings if L['index'])} indexable), dropped {dropped}")

    # ---------------- product pages
    for p in products:
        if p["page"]:
            out.page(f"/produkt/{p['slug']}/", product_page(S, p), "products", index=p["index"])
    for pid, g in gone.items():
        path = f"/produkt/{g['slug']}/"
        if path not in out.seen:
            out.page(path, gone_page(S, g), None, index=False)

    # ---------------- categories (top + sub)
    for top in X.TOP:
        items = sorted(by_top.get(top, []), key=pop_key)
        if not items:
            continue
        subs = [(k, by_cat[k]) for k in X.TREE if X.TREE[k][1] == top and by_cat.get(k)]
        jsn = write_json(out, S, top.replace("/", "-"), items)
        paged(out, S, f"/{top}/", items, lambda: category_page(S, top, items, subs, jsn), "listings")
        for k, ps in subs:
            ps = sorted(ps, key=pop_key)
            j2 = write_json(out, S, k.replace("/", "-"), ps)
            paged(out, S, f"/{k}/", ps, lambda: category_page(S, k, ps, [], j2), "listings", index=len(ps) >= 4)
    for (top, ab), ps in cat_age.items():
        ps = sorted(ps, key=pop_key)
        j = write_json(out, S, f"{top}-{ab}", ps)
        paged(out, S, f"/{top}/{ab}/", ps, lambda: cat_age_page(S, top, ab, ps, j), "listings")
    for s, ps in series_pages.items():
        ps = sorted(ps, key=pop_key)
        j = write_json(out, S, f"lego-{s}", ps)
        paged(out, S, f"/lego/{s}/", ps, lambda: series_page(S, s, ps, j), "listings")

    # ---------------- brands, characters
    for b, ps in brand_pages.items():
        ps = sorted(ps, key=pop_key)
        j = write_json(out, S, f"z-{b}", ps)
        paged(out, S, f"/znacky/{b}/", ps, lambda: brand_page(S, b, ps, j), "listings", index=len(ps) >= 5)
    out.page("/znacky/", brands_index(S, brand_pages, brand_name), "pages")
    for s, ps in lic_pages.items():
        ps = sorted(ps, key=pop_key)
        j = write_json(out, S, f"p-{s}", ps)
        paged(out, S, f"/hracky-{s}/", ps, lambda: licence_page(S, s, ps, j), "listings")
    out.page("/postavicky/", licences_index(S, lic_pages), "pages")

    # ---------------- gifts, price pages, sale
    for path, (h1, lead, ps, kind) in gift.items():
        ps = sorted(ps, key=pop_key)
        j = write_json(out, S, "g-" + path.strip("/").replace("/", "-"), ps)
        paged(out, S, path, ps, lambda: gift_page(S, path, h1, lead, ps, j, kind), "pages")
    out.page("/darky/", gifts_index(S, gift), "pages")
    for L in landings:
        ps = sorted(L["items"], key=pop_key)
        j = write_json(out, S, "x-" + L["slug"].replace("/", "-"), ps)
        paged(out, S, L["path"], ps, lambda: landing_page(S, L, ps, j), "landings", index=L["index"])

    # ---------------- guides (articles)
    for path, g in S.guides.items():
        out.page(path, guide_page(S, g, LD.guide_picks(products, g), out.seen), "guides")
    if S.guides:
        paged(out, S, "/pruvodce/", list(S.guides.items()), lambda: guides_index(S, S.guides), "pages", per=BLOG_PER_PAGE)

    # ---------------- static pages, search, home, 404
    out.page("/kategorie/", categories_index(S, by_top, by_cat), "pages")
    out.page("/obchody/", shops_page(S, shops, present, products), "pages")
    out.page("/jak-srovnavame/", about_page(S, present), "pages")
    out.page("/kontakt/", contact_page(S), "pages")
    out.page("/ochrana-osobnich-udaju/", privacy_page(S), "pages")
    out.page("/hledat/", search_page(S), None, index=False)
    out.page("/diagnostika-obrazku/", diag_page(S, products), None, index=False)
    out.page("/", home_page(S, products, by_top, series_pages, lic_pages, gift), "pages")
    out.write("404.html", S.layout("/404/", "Stránka nenalezena" + SUFFIX, "Tahle stránka neexistuje.",
                                   '<div class="e404"><div><h1>Tady nic není. Ani pod postelí.</h1><p class="lead">Hračka mohla zmizet z nabídky obchodů, nebo vedla stará adresa. '
                                   'Zkuste ji vyhledat nahoře, nebo začněte <a class="lnk" href="/">na úvodní stránce</a>.</p>'
                                   '<p><a class="btn" href="/kategorie/">Všechny kategorie</a></p><div id="nf-sugg" class="nf-sugg" hidden></div></div><img src="/img/ui/404.webp" alt="Robot nakukuje do prázdné truhly na hračky" width="640" height="472"></div>', noindex=True))
    write_search(out, products, by_top, series_pages, brand_pages, brand_name, lic_pages, landings, list(by_cat))

    # ---------------- sitemaps, robots, headers, redirects
    sm = []
    for group, paths in out.sitemap.items():
        for i in range(0, len(paths), 40000):
            name = f"sitemap-{group}-{i // 40000 + 1}.xml"
            body = "".join(f"<url><loc>{BASE}{p}</loc><lastmod>{state['lastmod'].get(p, TODAY.isoformat())}</lastmod></url>" for p in paths[i:i + 40000])
            out.write(name, f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>')
            sm.append(name)
    out.write("sitemap_index.xml", '<?xml version="1.0" encoding="UTF-8"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
              + "".join(f"<sitemap><loc>{BASE}/{n}</loc><lastmod>{TODAY.isoformat()}</lastmod></sitemap>" for n in sm) + "</sitemapindex>")
    if ENV == "production":
        out.write("robots.txt", f"User-agent: *\nDisallow: /data/\nDisallow: /hledat/\n\nSitemap: {BASE}/sitemap_index.xml\n")
        out.write("llms.txt", llms_txt(stats, by_top, series_pages))
    else:
        out.write("robots.txt", "User-agent: *\nDisallow: /\n")
    noidx = "" if ENV == "production" else "  X-Robots-Tag: noindex\n"
    sec = ("  X-Content-Type-Options: nosniff\n  Referrer-Policy: strict-origin-when-cross-origin\n"
           "  Strict-Transport-Security: max-age=63072000; includeSubDomains; preload\n  X-Frame-Options: DENY\n"
           "  Cross-Origin-Opener-Policy: same-origin\n  Cross-Origin-Resource-Policy: same-site\n  X-Permitted-Cross-Domain-Policies: none\n"
           "  Permissions-Policy: accelerometer=(), autoplay=(), camera=(), display-capture=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), "
           "midi=(), payment=(), usb=(), xr-spatial-tracking=(), interest-cohort=()\n")
    csp = ("  Content-Security-Policy: default-src 'none'; img-src 'self' https: data:; "
           "script-src 'self' 'inline-speculation-rules' https://www.googletagmanager.com " + " ".join(f"'sha256-{h}'" for h in sorted(out.script_hashes)) + "; "
           "connect-src 'self' https://*.googletagmanager.com https://*.google-analytics.com https://*.analytics.google.com; style-src 'self' 'unsafe-inline'; "
           "font-src 'self'; manifest-src 'self'; object-src 'none'; frame-src 'none'; worker-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; "
           "upgrade-insecure-requests\n")
    preload = f"  Link: </assets/{css_name}>; rel=preload; as=style, </fonts/bricolage-cs.woff2>; rel=preload; as=font; type=font/woff2; crossorigin, </fonts/figtree-cs.woff2>; rel=preload; as=font; type=font/woff2; crossorigin\n"
    html_cache = "  Cache-Control: public, max-age=300, stale-while-revalidate=86400\n"
    out.write("_headers", "/assets/*\n  Cache-Control: public, max-age=31536000, immutable\n/fonts/*\n  Cache-Control: public, max-age=31536000, immutable\n"
              "/data/*\n  Cache-Control: public, max-age=3600\n  X-Robots-Tag: noindex\n"
              "/img/*\n  Cache-Control: public, max-age=604800, stale-while-revalidate=2592000\n"
              "/favicon*\n  Cache-Control: public, max-age=604800\n"
              "/*.xml\n  Cache-Control: public, max-age=3600\n"
              "/\n" + html_cache + preload + "/*/\n" + html_cache + preload +
              "/*\n" + sec + csp + noidx)
    out.write("_redirects", redirects_file(out.seen))
    if INDEXNOW_KEY:
        out.write(f"{INDEXNOW_KEY}.txt", INDEXNOW_KEY)

    unlink_missing(out.seen)
    for k in list(out.hashes):
        if k not in out.seen:
            out.hashes.pop(k, None)
            out.lastmod.pop(k, None)
    C.save_state(state)
    (APP / "data/state/changed.txt").write_text("\n".join(out.changed))
    report = {"at": time.strftime("%Y-%m-%d %H:%M"), "env": ENV, "files": out.files, "products": len(products), "multi_shop": multi,
              "product_pages": sum(1 for p in products if p["page"]), "indexable_products": sum(1 for p in products if p["page"] and p["index"]),
              "gone_pages": len(gone), "categories": len(by_cat), "brands": len(brand_pages), "lego_series": len(series_pages),
              "characters": len(lic_pages), "gift_pages": len(gift), "changed": len(out.changed), "shops": present,
              "per_shop": dict(Counter(o["shop"] for p in products for o in p["offers"]))}
    json.dump(report, open(APP / "data/state/build-report.json", "w"), indent=1)
    log(json.dumps(report, ensure_ascii=False))
    log(f"built {out.files} files in {time.time() - t0:.0f}s")


def unlink_missing(seen):
    """Hand-written texts may link a page that this build does not have (too few products today): keep the words, drop the link."""
    rx = re.compile(r'<a href="(/[^"#?]*)">(.*?)</a>')
    fixed = 0
    for f in DIST.rglob("index.html"):
        if f.parts[len(DIST.parts)] == "produkt":
            continue
        html = f.read_text()
        if 'class="prose"' not in html and 'class="faq"' not in html:
            continue
        fix = lambda part: rx.sub(lambda m: m.group(0) if (m.group(1) in seen or not m.group(1).endswith("/") or m.group(1) == "/") else m.group(2), part.group(0))
        new = re.sub(r'<div class="prose">.*?</div><!--/prose-->|<div class="prose"[^>]*>.*?</div>|<section class="faq">.*?</section>', fix, html, flags=re.S)
        if new != html:
            f.write_text(new)
            fixed += 1
    log(f"texts: removed dead internal links on {fixed} pages")


def redirects_file(seen):
    """Old hrackarium.cz URLs -> new pages. A target that does not exist in this build falls back to its parent / home."""
    if not (APP / "data/redirects.txt").exists():
        return ""
    rules, src_seen = [], set()
    for l in (APP / "data/redirects.txt").read_text().splitlines():
        if not l.strip() or l.startswith("#"):
            continue
        src, to, code = l.split()
        if src in src_seen or src in seen:
            continue
        src_seen.add(src)
        if to not in seen and (to.startswith("/darek-pro-") or to.startswith("/hracky-")):
            to = "/darky/" if to.startswith("/darek") else "/postavicky/"
        while to != "/" and to not in seen and not to.endswith((".xml", ".txt")):      # sitemap_index.xml etc. are files, not pages
            to = to.rstrip("/").rsplit("/", 1)[0] + "/"
        rules.append(f"{src} {to} {code}")
    static = [r for r in rules if "*" not in r.split()[0]]
    dyn = [r for r in rules if "*" in r.split()[0]]
    if len(static) > 2000 or len(dyn) > 100:
        sys.exit("too many _redirects rules")
    return "# Generated by build.py (static rules first).\n" + "\n".join(static + dyn) + "\n"


# ======================================================================= page builders

def cat_name(k):
    return X.TREE[k][0]


def crumbs_for(k):
    out = [("Hračkárium", "/")]
    parent = X.TREE[k][1]
    if parent:
        out.append((cat_name(parent), f"/{parent}/"))
    out.append((cat_name(k), f"/{k}/"))
    return out


def product_page(S, p):
    k = p["cat"]
    top = k.split("/")[0]
    n = len(p["offers"])
    best = p["offers"][0]
    bs = S.shop(best["shop"])
    code = re.sub(r"\D", "", p["ean"])[-4:] or p["slug"][-4:]
    uniq = f" (kód {code})" if p.get("dup") else ""
    core = f"{p['name']} – srovnání cen" + (f" ({n} obchody)" if 1 < n < 5 else f" ({n} obchodů)" if n >= 5 else "")
    # shorten the descriptive part, never the distinguishing code: titles of same-named products must stay unique
    title = R.shorten(core, 68 - len(SUFFIX) - len(uniq)) + uniq + SUFFIX
    desc = (f"{p['name']}: {'nejnižší cena ' + R.kc(p['price']) + ' ze ' + str(n) + ' obchodů' if n > 1 else 'cena ' + R.kc(p['price']) + ' v obchodě ' + bs['name']}"
            f"{', ' + R.age_text(p['age']) if p['age'] is not None else ''}. Porovnejte nabídky a kupte přímo v e‑shopu.")
    imgs = [p["img"]] + p["imgs"] if p["img"] else p["imgs"]
    imgs = [u for u in imgs if u][:6]
    thumb_srcs = [R.img_url(u, "card") for u in imgs]       # 60 px thumbnails need the small rendition
    imgs = [R.img_url(u, "main") for u in imgs]
    main_img = E(imgs[0]) if imgs else "/img/ui/placeholder.svg"
    thumbs = "".join(f'<button type="button" data-src="{E(u)}"{" class=on" if i == 0 else ""} aria-label="Obrázek {i + 1}"><img src="{E(thumb_srcs[i])}" alt="" loading="lazy" referrerpolicy="no-referrer" width="60" height="60"></button>'
                     for i, u in enumerate(imgs)) if len(imgs) > 1 else ""
    age = f'<span class="sticker" style="width:64px;height:64px;font-size:1.15rem">{R.age_label(p["age"])}</span>' if p["age"] is not None else ""
    gal = f'<div class="gal"><div class="gal__main"><img id="gmain" src="{main_img}" alt="{E(p["name"])}" referrerpolicy="no-referrer" width="560" height="560" fetchpriority="high">{age}</div><div class="thumbs">{thumbs}</div></div>'

    meta = []
    if p["brand"] and X.slugify(p["brand"]) in S.ctx["brands"]:
        meta.append(f'<a href="/znacky/{X.slugify(p["brand"])}/">{E(p["brand"])}</a>')
    elif p["brand"]:
        meta.append(f"<span>{E(p['brand'])}</span>")
    if p["age"] is not None:
        band = next((b for b in X.AGE_BANDS if b[2] <= p["age"] <= b[3]), None)
        if band and (top, band[0]) in S.ctx["cat_age"]:
            meta.append(f'<a class="m-age" href="/{top}/{band[0]}/">{R.age_text(p["age"])}</a>')
        else:
            meta.append(f'<span class="m-age">{R.age_text(p["age"])}</span>')
    meta.append(f'<a href="/{k}/">{E(cat_name(k))}</a>')
    if p["lego"] and p["lego"] in S.ctx["series"]:
        meta.append(f'<a href="/lego/{p["lego"]}/">{E(series_name(p["lego"]))}</a>')
    for lic in p["lic"][:2]:
        if lic in S.ctx["lic"]:
            meta.append(f'<a href="/hracky-{lic}/">{E(S.lic_name[lic])}</a>')

    low = ""
    if p["since"] <= DAY - 7:
        low = (f'<p class="low">Tohle je nejnižší cena, jakou jsme za posledních 30 dní viděli.</p>' if p["price"] <= p["low30"]
               else f'<p>Nejnižší cena za posledních 30 dní u nás: <b>{R.kc(p["low30"])}</b>.</p>')
    else:
        low = f'<p>Cenu sledujeme od {date.fromordinal(p["since"]).day}. {date.fromordinal(p["since"]).month}. {date.fromordinal(p["since"]).year}.</p>'
    save = ""
    if n > 1 and p["offers"][-1]["price"] > p["price"]:
        save = f' Rozdíl mezi obchody: <b>{R.kc(p["offers"][-1]["price"] - p["price"])}</b>.'
    bestbox = (f'<div class="best"><div class="best__top">{S.tag(p["price"], "od" if n > 1 else "", big=True)}<div><b>{"Nejlevněji v obchodě" if n > 1 else "V obchodě"} {E(bs["name"])}</b></div>'
               f'<a class="btn btn--lg" href="{E(best["go"])}" {S.go_attrs(best["shop"])}>Do obchodu</a></div>{low.replace("</p>", save + "</p>", 1) if save else low}</div>')

    rows = []
    for i, o in enumerate(p["offers"]):
        m = S.shop(o["shop"])
        was = f'<s>{R.kc(o["was"])}</s>' if o.get("was") and o["was"] > o["price"] else ""
        diff = f'<small>o {R.kc(o["price"] - p["price"])} dráž</small>' if i else '<small>nejlepší cena</small>' if n > 1 else ""
        rows.append(f'<li class="ticket{" best1" if i == 0 and n > 1 else ""}"><span class="stripe" style="background:{m["color"]}"></span>'
                    f'<span class="sname"><b>{E(m["name"])}{"<span class=tag-best>nejlevněji</span>" if i == 0 and n > 1 else ""}</b>{diff}</span>'
                    f'<span class="tprice">{was}{R.kc(o["price"])}</span><a class="btn{" btn--g" if i else ""}" href="{E(o["go"])}" {S.go_attrs(o["shop"])}>Do obchodu</a></li>')
    offers_html = f'<h2 id="nabidky">{"Ceny v obchodech" if n > 1 else "Kde koupit"}</h2><ul class="offers">{"".join(rows)}</ul>'

    spec = [("Značka", E(p["brand"]) if p["brand"] else "neuvedena"), ("Kategorie", f'<a href="/{k}/">{E(cat_name(k))}</a>')]
    if p["age"] is not None:
        spec.append(("Doporučený věk", R.age_text(p["age"])))
    m = X.LEGO_SET.search(p["name"])
    if p["brand"] in ("LEGO", "Playmobil", "Cobi", "Bruder") and m:
        spec.append(("Číslo setu", m.group(1)))
    spec.append(("Počet obchodů", str(n)))
    spec.append(("Cena", f"{R.kc(p['price'])}" + (f" – {R.kc(p['offers'][-1]['price'])}" if n > 1 else "")))
    spec_html = '<h2>Parametry</h2><table class="spec">' + "".join(f"<tr><th>{a}</th><td>{b}</td></tr>" for a, b in spec) + "</table>"
    desc_html = ""
    if len(p["desc"]) > 40:
        desc_html = f'<h2>Popis</h2><div class="desc clamp" id="desc">{E(p["desc"])}</div><button class="more" type="button" data-more="desc">Celý popis</button><p class="disc">Popis převzatý od obchodu.</p>'
    hist = R.svg_history(p["hist"], DAY)
    hist_html = f"<h2>Vývoj ceny</h2>{hist}<p class=\"disc\">Nejnižší cena napříč obchody, jak jsme ji zaznamenali my.</p>" if hist else ""

    sim = [q for q in S.ctx["by_cat"].get(k, []) if q is not p and q["page"]]
    if p["lego"]:
        sim = [q for q in S.ctx["series"].get(p["lego"], []) if q is not p and q["page"]] + sim
    seen_sim, uniq = {p["id"], p["nkey"]}, []
    for q in sim:                       # series and category lists overlap; also skip a different listing with the same name
        key = (q["id"], q["nkey"])
        if key[0] in seen_sim or key[1] in seen_sim:
            continue
        seen_sim.update(key)
        uniq.append(q)
    sim = sorted(uniq[:400], key=lambda q: (abs(q["price"] - p["price"]) / max(p["price"], 1) - 0.2 * len(q["offers"])))[:8]
    sim_html = f'<section class="sec"><div class="sec__h"><h2>Podobné hračky</h2><a href="/{k}/">Vše v kategorii {E(cat_name(k))} →</a></div>{S.grid(sim)}</section>' if sim else ""

    ld = {"@context": "https://schema.org", "@type": "Product", "name": p["name"], "image": imgs[:3] or None, "url": S.url(f"/produkt/{p['slug']}/"),
          "description": (p["desc"][:300] or p["name"]), "category": cat_name(k),
          "offers": {"@type": "AggregateOffer", "priceCurrency": "CZK", "lowPrice": p["price"], "highPrice": p["offers"][-1]["price"],
                     "offerCount": n, "availability": "https://schema.org/InStock"}}
    if p["brand"]:
        ld["brand"] = {"@type": "Brand", "name": p["brand"]}
    if p["ean"] and len(p["ean"]) == 13:
        ld["gtin13"] = p["ean"]
    ld = {k2: v for k2, v in ld.items() if v}

    body = (f'<div class="prod">{gal}<div><h1>{E(p["name"])}</h1><div class="meta">{"".join(meta)}</div>{bestbox}{offers_html}{spec_html}{desc_html}{hist_html}</div></div>{sim_html}')
    cr = crumbs_for(k) + [(p["name"][:60], f"/produkt/{p['slug']}/")]
    return S.layout(f"/produkt/{p['slug']}/", title, desc, body, crumbs=cr, jsonld=[ld], preload_img=imgs[0] if imgs else None,
                    og_img=imgs[0] if imgs else None, noindex=not p["index"])


def gone_page(S, g):
    k = g["cat"] if g["cat"] in X.TREE else "lego"
    sim = sorted([q for q in S.ctx["by_cat"].get(k, []) if q["page"]], key=lambda q: abs(q["price"] - g["price"]))[:8]
    body = (f'<div class="prod"><div class="gal"><div class="gal__main"><img src="{E(g["img"] or "/img/ui/placeholder.svg")}" alt="{E(g["name"])}" width="560" height="560"></div></div>'
            f'<div><h1>{E(g["name"])}</h1><div class="gone"><b>Momentálně nedostupné.</b> Žádný ze sledovaných obchodů teď tuhle hračku nemá skladem. '
            f'Naposledy stála {R.kc(g["price"])}. Mrkněte na podobné hračky níže, nebo se vraťte později.</div>'
            f'<p><a class="btn" href="/{k}/">{E(cat_name(k))}</a></p></div></div>'
            f'<section class="sec"><h2>Podobné hračky skladem</h2>{S.grid(sim)}</section>')
    return S.layout(f"/produkt/{g['slug']}/", f"{g['name']} – momentálně nedostupné" + SUFFIX, f"{g['name']} teď není skladem. Podobné hračky a jejich ceny.",
                    body, crumbs=crumbs_for(k) + [(g["name"][:60], f"/produkt/{g['slug']}/")], noindex=True)


def listing_body(S, path, h1, lead, items, jsn, icon, chips="", texts_key=None, extra_ld=None, links=None):
    t = TX.get(texts_key) if texts_key else None
    intro = t["intro"] if t and t.get("intro") else ""
    lead_html = intro or lead
    kids = [k for k in getattr(S, "kids", {}).get(path, []) if k[0] != path]
    cats = list(links or [])
    if kids:
        seen = {u for u, _, _ in cats}
        cats += [k for k in sorted(kids, key=lambda k: -k[2])[:24] if k[0] not in seen]
    gl = getattr(S, "guide_links", {}).get(path, [])
    if gl:
        chips = (chips or "") + '<p class="muted" style="margin:8px 0 4px;font-weight:700">Průvodce</p>' + S.chips(gl[:4])
    band = S.band(h1, lead_html, icon, chips)
    prose, qa = TX.generated(texts_key, items, h1, S) if texts_key else ("", [])
    if t and t.get("body"):
        prose = t["body"]
    if t and t.get("faq"):
        qa = t["faq"]
    faq_html, faq_ld = S.faq(qa)
    body = band + f'<div class="wrap">{S.listing(items, jsn, facets=dict(facets(items, S), cats=cats))}' + \
        (f'<div class="prose">{prose}</div><!--/prose-->' if prose else "") + faq_html + "</div>"
    return body, [faq_ld] + (extra_ld or [])


def category_page(S, k, items, subs, jsn):
    name, parent, h1, blurb = X.TREE[k]
    lo, med, hi = price_stats(items)
    n = len(items)
    title = f"{h1} – srovnání cen ({n} {R.plural(n, 'hračka', 'hračky', 'hraček')})" + SUFFIX
    desc = f"{h1}: {n} {R.plural(n, 'hračka', 'hračky', 'hraček')} z {S.stats['shops']} českých e‑shopů, ceny od {R.kc(lo)}. Porovnejte a kupte nejlevněji."
    chips = []
    for sk, ps in subs:
        chips.append((f"/{sk}/", cat_name(sk), len(ps)))
    top = k.split("/")[0]
    if not parent:
        chips += [(f"/{top}/{ab}/", lbl.replace("pro děti ", "").replace("pro ", ""), len(S.ctx["cat_age"][(top, ab)])) for ab, lbl, _, _ in X.AGE_BANDS if (top, ab) in S.ctx["cat_age"]]
    if k == "lego":
        chips = [(f"/lego/{s}/", series_name(s), len(ps)) for s, ps in sorted(S.ctx["series"].items(), key=lambda x: -len(x[1]))] + chips
    lead = f"{blurb or h1}. {n} {R.plural(n, 'hračka', 'hračky', 'hraček')}, ceny od {R.kc(lo)}."
    body, lds = listing_body(S, f"/{k}/", h1, lead, items, jsn, R.ICON.get(top), "", texts_key=f"cat:{k}", links=chips)
    return S.layout(f"/{k}/", title, desc, body, crumbs=crumbs_for(k), jsonld=lds, full=True)


def cat_age_page(S, top, ab, items, jsn):
    band = next(b for b in X.AGE_BANDS if b[0] == ab)
    h1 = f"{X.TREE[top][2]} {band[1]}"
    lo, med, hi = price_stats(items)
    title = f"{h1} – ceny od {R.kc(lo)}" + SUFFIX
    desc = f"{h1}: {len(items)} hraček s doporučeným věkem v tomto rozmezí, ceny od {R.kc(lo)} v českých e‑shopech."
    lead = f"Vybrali jsme hračky, u kterých výrobce nebo obchod uvádí doporučený věk v rozmezí {band[1].replace('pro děti ', '').replace('pro ', '')}."
    others = [(f"/{top}/{b[0]}/", b[1].replace("pro děti ", "").replace("pro ", ""), 0) for b in X.AGE_BANDS if (top, b[0]) in S.ctx["cat_age"] and b[0] != ab]
    body, lds = listing_body(S, f"/{top}/{ab}/", h1, lead, items, jsn, R.ICON.get(top), "", texts_key=f"age:{top}:{ab}", links=others)
    return S.layout(f"/{top}/{ab}/", title, desc, body, crumbs=crumbs_for(top) + [(band[1], f"/{top}/{ab}/")], jsonld=lds, full=True)


def series_name(s):
    return next((n for k, n, _ in X.LEGO_SERIES if k == s), s)


def series_page(S, s, items, jsn):
    name = series_name(s)
    lo, med, hi = price_stats(items)
    title = f"{name} – srovnání cen setů od {R.kc(lo)}" + SUFFIX
    desc = f"{name}: {len(items)} setů z českých e‑shopů, ceny od {R.kc(lo)}. Porovnejte ceny jednotlivých setů a kupte nejlevněji."
    lead = f"{len(items)} {R.plural(len(items), 'set', 'sety', 'setů')} řady {name.replace('LEGO ', '')} skladem v českých obchodech, ceny od {R.kc(lo)} do {R.kc(hi)}."
    others = [(f"/lego/{k}/", series_name(k), 0) for k, ps in sorted(S.ctx["series"].items(), key=lambda x: -len(x[1])) if k != s][:14]
    body, lds = listing_body(S, f"/lego/{s}/", name, lead, items, jsn, "kostky", "", texts_key=f"lego:{s}", links=others)
    return S.layout(f"/lego/{s}/", title, desc, body, crumbs=[("Hračkárium", "/"), ("LEGO", "/lego/"), (name, f"/lego/{s}/")], jsonld=lds, full=True)


def brand_page(S, b, items, jsn):
    name = S.ctx["brand_name"][b]
    lo, med, hi = price_stats(items)
    cats = Counter(p["cat"].split("/")[0] for p in items).most_common(6)
    title = f"Hračky {name} – srovnání cen" + SUFFIX
    desc = f"{name}: {len(items)} {R.plural(len(items), 'hračka', 'hračky', 'hraček')} skladem v českých e‑shopech, ceny od {R.kc(lo)}. Porovnejte a kupte nejlevněji."
    lead = f"{len(items)} {R.plural(len(items), 'produkt', 'produkty', 'produktů')} značky {E(name)} skladem, nejčastěji v kategoriích " + \
        ", ".join(f'<a class="lnk" href="/{c}/">{E(cat_name(c).lower())}</a>' for c, _ in cats[:3]) + "."
    body, lds = listing_body(S, f"/znacky/{b}/", f"Hračky {E(name)}", lead, items, jsn, None, "", texts_key=f"brand:{b}")
    return S.layout(f"/znacky/{b}/", title, desc, body, crumbs=[("Hračkárium", "/"), ("Značky", "/znacky/"), (name, f"/znacky/{b}/")], jsonld=lds, full=True)


def licence_page(S, s, items, jsn):
    name = S.lic_name[s]
    lo, med, hi = price_stats(items)
    title = f"{name} hračky – srovnání cen od {R.kc(lo)}" + SUFFIX
    desc = f"Hračky {name}: {len(items)} produktů z českých e‑shopů – stavebnice, plyšáci, figurky a další, ceny od {R.kc(lo)}."
    cats = Counter(p["cat"].split("/")[0] for p in items).most_common(5)
    lead = f"Všechno s motivem {E(name)} na jednom místě: " + ", ".join(cat_name(c).lower() for c, _ in cats) + f". Celkem {len(items)} hraček."
    body, lds = listing_body(S, f"/hracky-{s}/", f"Hračky {E(name)}", lead, items, jsn, None, "", texts_key=f"lic:{s}")
    return S.layout(f"/hracky-{s}/", title, desc, body, crumbs=[("Hračkárium", "/"), ("Postavičky", "/postavicky/"), (name, f"/hracky-{s}/")], jsonld=lds, full=True)


BLOG_PHOTOS = json.loads((APP / "content/guides/photos.json").read_text()) if (APP / "content/guides/photos.json").exists() else {}


def blog_photo(g, size):
    """Feature photo of an article (downloaded into static/img/blog by scripts/blog_photos.py); None when it is not there."""
    ph = BLOG_PHOTOS.get(g["slug"])
    return (ph, f"/img/blog/{g['slug']}-{size}.jpg") if ph and (APP / f"static/img/blog/{g['slug']}-{size}.jpg").exists() else (None, None)


def reading_min(g):
    words = len(re.sub(r"<[^>]+>", " ", g["intro"] + " " + g["body"]).split())
    return max(2, round(words / 190))


def guide_page(S, g, picks, seen):
    path = f"/pruvodce/{g['slug']}/"
    title = (g.get("title") or g["h1"]) + SUFFIX
    desc = g.get("description") or (re.sub(r"<[^>]+>", "", g["intro"]) or g["h1"])[:155]
    faq_html, faq_ld = S.faq(g.get("faq", []))
    rel = [(u, t) for u, t in ((r, S.landings[r]["h1"] if r in S.landings else None) for r in g.get("related", [])) if t]
    rel += [(r, cat_name(r.strip("/"))) for r in g.get("related", []) if r.strip("/") in X.TREE]
    rel_html = ("<h2>Související stránky</h2>" + S.chips([(u, t, 0) for u, t in rel[:8]])) if rel else ""
    picks_html = (f'<section class="sec"><div class="sec__h"><h2>Výběr z nabídky</h2></div>{S.grid(picks)}</section>') if len(picks) >= 4 else ""
    ph, img = blog_photo(g, "1200")
    fig = ""
    if ph:
        fig = (f'<figure class="post__img"><img src="{img}" srcset="{blog_photo(g, "640")[1]} 640w, {img} 1200w" sizes="(max-width:800px) 92vw, 760px" width="1200" height="750" alt="{E(ph["alt"])}" fetchpriority="high">'
               f'<figcaption>Foto: <a href="{E(ph["page"])}" rel="noopener" target="_blank">{E(ph["by"])} / Pexels</a></figcaption></figure>')
    body = (f'<article class="post"><header class="post__h"><p class="post__meta"><a href="/pruvodce/">Blog</a> · {reading_min(g)} min čtení</p><h1>{E(g["h1"])}</h1>'
            f'<p class="lead">{g["intro"]}</p></header>{fig}<div class="prose">{g["body"]}</div>'
            f'{picks_html}<div class="post__rel">{rel_html}</div>{faq_html}</article>')
    art = {"@context": "https://schema.org", "@type": "BlogPosting", "headline": g["h1"], "description": desc, "mainEntityOfPage": S.url(path),
           "datePublished": g.get("date", "2026-11-10"), "dateModified": TODAY.isoformat(),
           "author": {"@type": "Organization", "name": "Hračkárium", "url": BASE + "/"}, "publisher": {"@type": "Organization", "name": "Hračkárium", "url": BASE + "/", "logo": {"@type": "ImageObject", "url": BASE + "/favicon-512.png"}}}
    if ph:
        art["image"] = [S.url(img)]
    return S.layout(path, title, desc, body, crumbs=[("Hračkárium", "/"), ("Blog", "/pruvodce/"), (g["h1"], path)], jsonld=[art, faq_ld], preload_img=img if ph else None, og_img=S.url(img) if ph else None)


BLOG_PER_PAGE = 12


def guides_index(S, guides):
    path, cur, pages = S.pg or ("/pruvodce/", 1, 1)
    chunk = list(guides.items())[(cur - 1) * BLOG_PER_PAGE:cur * BLOG_PER_PAGE]
    cards = []
    for i, (p, g) in enumerate(chunk):
        ph, img = blog_photo(g, "640")
        pic = f'<img src="{img}" width="640" height="400" alt="{E(ph["alt"])}"{"" if i < 3 else " loading=lazy"}>' if ph else ""
        ex = re.sub(r"<[^>]+>", "", g["intro"])
        ex = ex if len(ex) <= 140 else ex[:140].rsplit(" ", 1)[0] + "…"
        cards.append(f'<li class="bc"><a class="bc__img" href="{p}" tabindex="-1" aria-hidden="true">{pic}</a><div class="bc__b"><p class="post__meta">{reading_min(g)} min čtení</p>'
                     f'<h2><a href="{p}">{E(g["h1"])}</a></h2><p>{E(ex)}</p></div></li>')
    body = ('<div class="blogh"><h1>Blog Hračkária</h1><p class="lead">Jak vybrat, co koupit a na co si dát pozor. Praktické rady podle věku dítěte, typu hračky a příležitosti.</p></div>'
            f'<ul class="blog">{"".join(cards)}</ul>{R.pager_html(path, cur, pages)}')
    return S.layout("/pruvodce/", "Blog o hračkách – rady, tipy a průvodce výběrem" + SUFFIX, "Blog Hračkária: jak vybrat LEGO, deskové hry, puzzle, hračky podle věku a dárky pro děti. Praktické rady a tipy pro rodiče.", body,
                    crumbs=[("Hračkárium", "/"), ("Blog", "/pruvodce/")])


def landing_page(S, L, items, jsn):
    h1, path = L["h1"], L["path"]
    lo, med, hi = price_stats(items)
    n = len(items)
    shops = len({o["shop"] for p in items for o in p["offers"]})
    title = (L.get("title") or f"{h1} – srovnání cen od {R.kc(lo)}") + (SUFFIX if "Hračkárium" not in (L.get("title") or "") else "")
    if len(title) > 72 and not L.get("title"):
        title = f"{h1} – ceny od {R.kc(lo)}" + SUFFIX
    desc = L.get("desc") or f"{h1}: {n} {R.plural(n, 'hračka', 'hračky', 'hraček')} z {shops} českých e‑shopů, ceny od {R.kc(lo)}. Porovnejte nabídky a kupte nejlevněji."
    lead = L.get("lead") or f"{n} {R.plural(n, 'hračka', 'hračky', 'hraček')} z {shops} {R.plural(shops, 'obchodu', 'obchodů', 'obchodů')}, ceny od {R.kc(lo)} do {R.kc(hi)}."
    sibs = [k for k in S.kids.get(L["parent"], []) if k[0] != path] if L["parent"] and L["parent"] != "/kategorie/" else []
    chips = [(u, t, c) for u, t, c in sorted(sibs, key=lambda k: -k[2])[:16]]
    icon = L.get("icon") or (R.ICON.get(path.strip("/").split("/")[0]) if L["parent"] in (None, "/kategorie/") else None)
    body, lds = listing_body(S, path, h1, lead, items, jsn, icon, "", texts_key="landing:" + L["slug"], links=chips)
    cr = [("Hračkárium", "/")]
    par = L["parent"]
    if par and par != "/kategorie/":
        pname = S.landings[par]["h1"] if par in S.landings else (cat_name(par.strip("/")) if par.strip("/") in X.TREE else {"/darky/": "Dárky", "/lego/": "LEGO", "/znacky/": "Značky"}.get(par, None))
        if pname is None and par.startswith("/znacky/"):
            pname = S.ctx["brand_name"].get(par.strip("/").split("/")[1], par.strip("/").split("/")[1])
        if pname:
            cr.append((pname, par))
    cr.append((h1, path))
    return S.layout(path, title, desc, body, crumbs=cr, jsonld=lds, full=True)


def gift_pages(products):
    """Gift landings from what people search: by age (1–12), boy/girl (only where the shop says so), price caps, sale."""
    out = {}
    fits = lambda p, y: p["age"] is not None and p["age"] <= y * 12 and p["age"] >= max(0, y - 4) * 12 and p["cat"].split("/")[0] not in ("fan-darky",)
    for y in range(1, 13):
        ps = [p for p in products if fits(p, y)]
        if len(ps) >= 24:
            word = "roční" if y == 1 else f"{y}leté"
            out[f"/darky/{y}-let/" if y > 1 else "/darky/1-rok/"] = (f"Dárek pro {word} dítě", f"Hračky vhodné pro {'roční' if y == 1 else str(y) + 'leté'} děti podle doporučeného věku.", ps, ("age", y))
        for sex, who, noun in (("m", "kluka", "kluky"), ("f", "holku", "holky")):
            ps2 = [p for p in ps if p["sex"] == sex]
            if len(ps2) >= 24:
                out[f"/darek-pro-{who}-{y}-{'rok' if y == 1 else 'roky' if y < 5 else 'let'}/"] = (
                    f"Dárek pro {who} {y} {'rok' if y == 1 else 'roky' if y < 5 else 'let'}", f"Hračky, které obchody řadí pro {noun}, s doporučeným věkem do {y} let.", ps2, ("sexage", sex, y))
    for sex, who, noun in (("m", "kluka", "kluky"), ("f", "holku", "holky")):
        ps = [p for p in products if p["sex"] == sex]
        if len(ps) >= 24:
            out[f"/darek-pro-{who}/"] = (f"Dárek pro {who}", f"Hračky, které obchody samy řadí do sekce pro {noun}.", ps, ("sex", sex))
    for cap in (300, 500, 1000):
        ps = [p for p in products if p["price"] <= cap and p["cat"].split("/")[0] not in ("fan-darky", "kostymy-a-party")]
        out[f"/hracky-do-{cap}-kc/"] = (f"Hračky do {cap} Kč", f"Dárky a hračky, které seženete do {cap} Kč.", ps, ("cap", cap))
    sale = [p for p in products if R.Site.discount(p) >= 10]
    if sale:
        out["/slevy/"] = ("Slevy na hračky", "Hračky, které mají v obchodě teď sníženou cenu proti původní.", sale, ("sale",))
    return out


def gift_page(S, path, h1, lead, items, jsn, kind):
    lo, med, hi = price_stats(items)
    title = f"{h1} – {len(items)} tipů, ceny od {R.kc(lo)}" + SUFFIX
    desc = f"{h1}: {len(items)} hraček z českých e‑shopů, ceny od {R.kc(lo)}. Vyberte podle věku, ceny a značky, kupte nejlevněji."
    sib = []
    if kind[0] in ("age", "sexage"):
        sib = [(f"/darky/{y}-let/" if y > 1 else "/darky/1-rok/", f"{y} {'rok' if y == 1 else 'roky' if y < 5 else 'let'}", 0) for y in range(1, 13)]
    sib = [x for x in sib if x[0] != path]
    body, lds = listing_body(S, path, h1, lead, items, jsn, "party", S.chips(sib), texts_key="gift:" + path.strip("/"))
    return S.layout(path, title, desc, body, crumbs=[("Hračkárium", "/"), ("Dárky", "/darky/"), (h1, path)], jsonld=lds, full=True)


def gifts_index(S, gift):
    ages = "".join(f'<li><a href="{p}">{v[3][1]}<small>{"rok" if v[3][1] == 1 else "roky" if v[3][1] < 5 else "let"}</small></a></li>' for p, v in gift.items() if v[3][0] == "age")
    other = S.chips([(p, v[0], len(v[2])) for p, v in gift.items() if v[3][0] != "age"] + [(u, t, n) for u, t, n in sorted(S.kids.get("/darky/", []), key=lambda k: -k[2])[:40]])
    body = (f'<h1>Dárky pro děti podle věku</h1><p class="lead">Vyberte věk dítěte. Ukážeme hračky, u kterých výrobce nebo obchod uvádí, že se pro ten věk hodí — od nejsrovnávanějších.</p>'
            f'<ul class="ages">{ages}</ul><h2 style="margin-top:34px">Další tipy na dárky</h2>{other}')
    t = TX.get("darky:index") or {}
    lds = []
    if t.get("body"):
        body += f'<div class="prose">{t["body"]}</div>'
    if t.get("faq"):
        fh, fl = S.faq(t["faq"])
        body += fh
        lds.append(fl)
    if t.get("intro"):
        body = body.replace('<p class="lead">Vyberte věk dítěte.', f'<p class="lead">{t["intro"]} Vyberte věk dítěte.', 1)
    return S.layout("/darky/", "Dárky pro děti podle věku – tipy a ceny" + SUFFIX, "Tipy na dárky pro děti od 1 do 12 let, dárky pro kluky i holky a hračky do 300, 500 a 1000 Kč se srovnáním cen.",
                    body, crumbs=[("Hračkárium", "/"), ("Dárky", "/darky/")], jsonld=lds)


def brands_index(S, pages, names):
    groups = defaultdict(list)
    for b, ps in sorted(pages.items(), key=lambda x: names[x[0]].lower()):
        ch = X.slugify(names[b])[:1].upper() or "#"
        groups[ch if ch.isalpha() else "#"].append((b, ps))
    top = sorted(pages.items(), key=lambda x: -len(x[1]))[:24]
    body = '<h1>Značky hraček</h1><p class="lead">Všechny značky, které teď mají hračky skladem ve sledovaných obchodech.</p>' + \
        S.chips([(f"/znacky/{b}/", names[b], len(ps)) for b, ps in top]) + "".join(
            f'<p class="letter">{ch}</p><div class="cols3">' + "".join(f'<a href="/znacky/{b}/">{E(names[b])} <small>{len(ps)}</small></a>' for b, ps in lst) + "</div>"
            for ch, lst in sorted(groups.items()))
    return S.layout("/znacky/", "Značky hraček A–Z" + SUFFIX, f"{len(pages)} značek hraček se srovnáním cen: LEGO, Playmobil, Schleich, Ravensburger a další.",
                    body, crumbs=[("Hračkárium", "/"), ("Značky", "/znacky/")])


def licences_index(S, pages):
    items = sorted(pages.items(), key=lambda x: -len(x[1]))
    body = ('<h1>Hračky podle postaviček</h1><p class="lead">Bluey, Stitch, Tlapková patrola, Minecraft a další hrdinové z pohádek, filmů a her.</p>'
            '<ul class="tiles">' + "".join(f'<li><a href="/hracky-{s}/">{E(S.lic_name[s])}<small>{len(ps)} hraček</small></a></li>' for s, ps in items) + "</ul>")
    return S.layout("/postavicky/", "Hračky podle postaviček z pohádek a her" + SUFFIX, "Hračky s oblíbenými postavičkami – Bluey, Stitch, Tlapková patrola, Minecraft, Pokémon a další se srovnáním cen.",
                    body, crumbs=[("Hračkárium", "/"), ("Postavičky", "/postavicky/")])


def categories_index(S, by_top, by_cat):
    tiles = "".join(f'<li><a href="/{t}/"><img src="/img/ic/{R.ICON.get(t, "kostky")}.webp" alt="" width="72" height="72" loading="lazy">{E(cat_name(t))}<small>{len(by_top[t])} hraček</small></a></li>'
                    for t in X.TOP if by_top.get(t))
    subs = "".join(f'<h2 style="margin-top:28px"><a href="/{t}/" style="color:inherit;text-decoration:none">{E(cat_name(t))}</a></h2>' + S.chips(
        [(f"/{k}/", cat_name(k), len(by_cat[k])) for k in X.TREE if X.TREE[k][1] == t and by_cat.get(k)]) for t in X.TOP if by_top.get(t))
    topics = ""
    groups = [("Hračky podle věku", "vek"), ("Kam a na co", None), ("Podle potřeb dítěte", "potreby"), ("Dárky a příležitosti", "prilezitosti"), ("Vánoce a advent", "vanoce")]
    kid = sorted(S.kids.get("/kategorie/", []), key=lambda k: -k[2])
    if kid:
        topics = '<h2 style="margin-top:34px">Další témata a nápady</h2>' + S.chips([(u, t, n) for u, t, n in kid[:120]])
    body = f'<h1>Všechny kategorie hraček</h1><ul class="tiles">{tiles}</ul>{subs}{topics}'
    return S.layout("/kategorie/", "Kategorie hraček" + SUFFIX, "Přehled všech kategorií hraček: LEGO, stavebnice, panenky, společenské hry, puzzle, plyšáci a další.",
                    body, crumbs=[("Hračkárium", "/"), ("Kategorie", "/kategorie/")])


def shops_page(S, shops, present, products):
    cnt = Counter(o["shop"] for p in products for o in p["offers"])
    lis = "".join(f'<li style="--c:{s.get("color", "#888")}"><h3>{E(s["name"])}</h3><p class="muted">{cnt.get(s["id"], 0)} hraček skladem</p><p><a class="lnk" href="https://{s["domain"]}/" rel="nofollow noopener" target="_blank">{E(s["domain"])}</a></p></li>'
                  for s in shops if s["id"] in present)
    body = f'<h1>Obchody, které srovnáváme</h1><p class="lead">Ceny a dostupnost bereme z produktových feedů těchto e‑shopů a ceny aktualizujeme každý den, nabídku produktů jednou týdně.</p><ul class="shoplist">{lis}</ul>'
    return S.layout("/obchody/", "Obchody s hračkami, které srovnáváme" + SUFFIX, "Seznam českých e‑shopů s hračkami, jejichž ceny Hračkárium srovnává.", body,
                    crumbs=[("Hračkárium", "/"), ("Obchody", "/obchody/")])


def about_page(S, present):
    body = (f'<div class="prose" style="margin-top:0"><h1>Jak srovnáváme ceny hraček</h1>'
            f'<p>Hračkárium je srovnávač cen hraček. Nic neprodáváme a nesbíráme objednávky. Každý den obnovíme ceny a jednou týdně nabídku produktů z {len(present)} českých e‑shopů, roztřídíme je do kategorií a stejné hračky z různých obchodů spojíme dohromady, abyste viděli, kde je nejlevnější.</p>'
            '<h2>Jak poznáme, že jde o stejnou hračku</h2><p>Párujeme podle čárového kódu (EAN). U stavebnic LEGO, Playmobil, Cobi a Bruder navíc podle čísla setu, které mají v názvu. Když si nejsme jistí, necháme hračku zvlášť — raději dvě karty než špatné srovnání.</p>'
            '<h2>Odkud jsou ceny</h2><p>Ceny, dostupnost, obrázky a popisy posílají obchody v produktových feedech. Cena se v obchodě může mezi naší aktualizací a vaším nákupem změnit; platí vždy cena v e‑shopu. Vývoj ceny a „nejnižší cenu za 30 dní“ počítáme jen z hodnot, které jsme sami zaznamenali.</p>'
            '<h2>Doporučený věk</h2><p>Věk přebíráme od výrobce nebo obchodu (např. „od 3 let“, „3+“). Hračky s malými díly nejsou vhodné pro děti do 3 let — řiďte se vždy upozorněním na obalu.</p>'
            '<h2>Jak web vydělává</h2><p>Když přes náš odkaz nakoupíte, obchod nám může zaplatit provizi z partnerského programu (CJ, eHub a dalších sítí). Cenu pro vás to nemění a pořadí nabídek neovlivňuje: řadíme vždy od nejlevnější.</p>'
            '<h2>Kontakt</h2><p>Chybu v ceně nebo zařazení nám napište na <a class="lnk" href="mailto:info@hrackarium.cz">info@hrackarium.cz</a>. Provozovatel a další údaje jsou na stránce <a class="lnk" href="/kontakt/">Kontakt</a>.</p></div>')
    return S.layout("/jak-srovnavame/", "Jak srovnáváme ceny hraček" + SUFFIX, "Jak Hračkárium získává ceny hraček, páruje stejné produkty mezi obchody a z čeho žije.", body,
                    crumbs=[("Hračkárium", "/"), ("Jak srovnáváme", "/jak-srovnavame/")])


def contact_page(S):
    o = R.OPERATOR
    body = (f'<div class="prose" style="margin-top:0"><h1>Kontakt</h1><p>Hračkárium je srovnávač cen hraček. Nic neprodáváme, objednávky vyřizují e‑shopy, na které odkazujeme. '
            f'S dotazem k objednávce se proto obracejte přímo na obchod.</p>'
            f'<h2>Provozovatel webu</h2><table class="spec"><tr><th>Jméno</th><td>{o["name"]}</td></tr><tr><th>Sídlo</th><td>{o["address"]}</td></tr>'
            f'<tr><th>IČO</th><td>{o["ico"]}</td></tr><tr><th>DPH</th><td>{o["vat"][0].upper() + o["vat"][1:]}</td></tr>'
            f'<tr><th>Datová schránka</th><td>{o["ds"]}</td></tr><tr><th>E‑mail</th><td><a class="lnk" href="mailto:{o["email"]}">{o["email"]}</a></td></tr></table>'
            '<h2>Co nám napsat</h2><p>Chybná cena nebo zařazení hračky, nefunkční odkaz, nevhodný popis, nebo návrh obchodu, který bychom měli srovnávat. U chyby prosím pošlete odkaz na stránku.</p></div>')
    return S.layout("/kontakt/", "Kontakt a provozovatel" + SUFFIX, "Kontakt na provozovatele srovnávače cen hraček Hračkárium.", body,
                    crumbs=[("Hračkárium", "/"), ("Kontakt", "/kontakt/")])


def privacy_page(S):
    body = ('<div class="prose" style="margin-top:0"><h1>Ochrana osobních údajů a cookies</h1>'
            f'<h2>Správce údajů</h2><p>{R.OPERATOR["name"]}, {R.OPERATOR["address"]}, IČO {R.OPERATOR["ico"]}, {R.OPERATOR["vat"]}. Kontakt: <a class="lnk" href="mailto:{R.OPERATOR["email"]}">{R.OPERATOR["email"]}</a>. Dozorovým úřadem je Úřad pro ochranu osobních údajů (uoou.cz), u kterého můžete podat stížnost.</p>'
            '<p>Hračkárium nemá registraci, účty ani formuláře. Neukládáme o vás žádné osobní údaje.</p>'
            '<h2>Měření návštěvnosti</h2><p>Google Analytics 4 (Google Ireland Ltd.) je na stránce přítomná ve výchozím režimu „bez souhlasu“ (Google Consent Mode): dokud nedáte souhlas v liště, nenastavují cookies, neukládají identifikátory a o návštěvě se do Googlu posílá jen anonymní signál bez cookies. Po souhlasu měříme, které stránky lidé čtou a na které obchody klikají. Souhlas můžete kdykoli změnit odkazem „Nastavení cookies“ v patičce.</p>'
            '<h2>Odkazy do obchodů</h2><p>Odkazy do e‑shopů vedou přes partnerské sítě (např. CJ, eHub), které si mohou uložit cookie, aby obchod poznal, že jste přišli od nás. Řídí se zásadami té sítě a obchodu.</p>'
            '<h2>Kontakt</h2><p><a class="lnk" href="mailto:info@hrackarium.cz">info@hrackarium.cz</a></p></div>')
    return S.layout("/ochrana-osobnich-udaju/", "Ochrana osobních údajů" + SUFFIX, "Jak Hračkárium zachází s osobními údaji a cookies.", body,
                    crumbs=[("Hračkárium", "/"), ("Ochrana osobních údajů", "/ochrana-osobnich-udaju/")])


def diag_page(S, products):
    """Self-service check for "images do not show in my browser": one real product image per image host, loaded live in the visitor's
    browser (no referrer / default referrer) with the result next to it. noindex, not linked anywhere."""
    seen, rows = {}, []
    for p in products:
        u = R.img_url(p["img"]) if p["img"] else ""
        m = re.match(r"https://([^/]+)/", u or "")
        if m and m.group(1) not in seen:
            seen[m.group(1)] = u
    for host, u in sorted(seen.items()):
        rows.append(f'<tr data-u="{E(u)}"><td>{E(host)}</td><td class="r1">…</td><td><img alt="" width="48" height="48" style="object-fit:contain"></td></tr>')
    js = ("<script>(function(){var rows=[].slice.call(document.querySelectorAll('tr[data-u]'));function t(u,pol,cb){var i=new Image();i.referrerPolicy=pol;var d=false;"
          "var k=setTimeout(function(){if(!d){d=true;cb('časový limit')}},15000);i.onload=function(){if(!d){d=true;clearTimeout(k);cb('OK '+i.naturalWidth+'×'+i.naturalHeight)}};"
          "i.onerror=function(){if(!d){d=true;clearTimeout(k);cb('CHYBA')}};i.src=u}"
          "rows.forEach(function(r){var u=r.dataset.u;t(u,'no-referrer',function(x){r.querySelector('.r1').textContent=x;if(x.indexOf('OK')==0)r.querySelector('img').src=u;});"
          "});"
          "document.getElementById('ua').textContent=navigator.userAgent;"
          "})();</script>")
    body = ('<h1>Diagnostika obrázků</h1><p class="lead">Tahle stránka načte jednu fotku z každého obchodu přímo ve vašem prohlížeči. '
            'Pošlete nám prosím screenshot celé tabulky. Řádky s „CHYBA“ ukazují obchody, jejichž fotky váš prohlížeč nebo síť nepustí.</p>'
            f'<p class="muted" id="ua"></p><table class="spec"><tr><th>Server s fotkami</th><th>Výsledek</th><th>Náhled</th></tr>{"".join(rows)}</table>{js}')
    return S.layout("/diagnostika-obrazku/", "Diagnostika obrázků" + SUFFIX, "Kontrola načítání obrázků v prohlížeči.", body, noindex=True)


def search_page(S):
    body = ('<h1>Hledání</h1><p class="lead" id="sq">Napište, co hledáte, do pole nahoře.</p><ul class="grid" id="sres"></ul>')
    return S.layout("/hledat/", "Hledání hraček" + SUFFIX, "Hledání v hračkách na Hračkárium.cz", body, noindex=True)


def home_page(S, products, by_top, series, lic, gift):
    st = S.stats
    hot = [p for p in products if len(p["offers"]) > 1 and p["img"]][:10] or products[:10]
    sale = sorted([p for p in products if R.Site.discount(p) >= 15 and p["img"]], key=lambda p: -R.Site.discount(p))[:10]
    tiles = "".join(f'<li><a href="/{t}/"><img src="/img/ic/{R.ICON.get(t, "kostky")}.webp" alt="" width="72" height="72" loading="lazy">{E(cat_name(t))}<small>{len(by_top[t])}</small></a></li>'
                    for t in sorted([t for t in X.TOP if by_top.get(t)], key=lambda t: (t in ("fan-darky", "kostymy-a-party", "sberatelske-karty"), -len(by_top[t])))[:12])
    ages = "".join(f'<li><a href="{p}">{v[3][1]}<small>{"rok" if v[3][1] == 1 else "roky" if v[3][1] < 5 else "let"}</small></a></li>' for p, v in gift.items() if v[3][0] == "age")
    lego = S.chips([(f"/lego/{s}/", series_name(s), len(ps)) for s, ps in sorted(series.items(), key=lambda x: -len(x[1]))[:14]])
    chars = S.chips([(f"/hracky-{s}/", S.lic_name[s], len(ps)) for s, ps in sorted(lic.items(), key=lambda x: -len(x[1]))[:16]])
    feat = [L for L in S.landings.values() if L["home"]]
    featured = (f'<section class="sec"><div class="sec__h"><h2>Hledáte nejčastěji</h2></div>' + S.chips([(L["path"], L["h1"], L["n"]) for L in sorted(feat, key=lambda L: -L["n"])[:12]]) + "</section>") if feat else ""
    guides_sec = (f'<section class="sec"><div class="sec__h"><h2>Z blogu</h2><a href="/pruvodce/">Všechny články →</a></div>' + S.chips([(p, g["h1"], 0) for p, g in list(S.guides.items())[:8]]) + "</section>") if getattr(S, "guides", None) else ""
    row = lambda ps: '<ul class="grid grid--5">' + "".join(S.card(p) for p in ps) + "</ul>"
    body = f"""<section class="hero"><div class="wrap"><div><h1>Hračky za <em>nejlepší cenu</em>, bez běhání po obchodech</h1>
<p class="lead">Porovnáváme ceny {R.plural(st['products'], 'hračky', 'hraček', 'hraček')} z {st['shops']} českých e‑shopů. Najděte LEGO, deskovku nebo dárek k Vánocům a kupte tam, kde je to nejlevnější.</p>
<div class="row"><a class="btn btn--lg" href="/darky/">Dárky podle věku</a><a class="btn btn--g btn--lg" href="/lego/">LEGO sety</a></div>
<div class="hero__stats"><div><b>{R.kc(st['products']).replace(chr(160) + 'Kč', '')}</b><span>hraček skladem</span></div><div><b>{st['shops']}</b><span>obchodů</span></div><div><b>denně</b><span>nové ceny</span></div></div></div>
<div class="hero__art"><img src="/img/ui/hero-1200.webp" srcset="/img/ui/hero-640.webp 640w, /img/ui/hero-1200.webp 1200w" sizes="(max-width:980px) 92vw, 600px" alt="Police plná hraček s cenovkami" width="1200" height="631" fetchpriority="high"><span class="note" style="right:4%;bottom:-6px">ceny z {st['shops']} obchodů!</span></div></div></section>
<div class="wrap"><section class="sec"><div class="sec__h"><h2>Co hledáte?</h2><a href="/kategorie/">Všechny kategorie →</a></div><ul class="tiles">{tiles}</ul></section>
<section class="sec"><div class="sec__h"><h2>Dárek podle věku</h2><a href="/darky/">Další tipy →</a></div><ul class="ages">{ages}</ul></section>
<section class="sec"><div class="sec__h"><h2>Nejvíc srovnávané</h2><a href="/kategorie/">Procházet →</a></div>{row(hot)}</section>
{f'<section class="sec"><div class="sec__h"><h2>Teď ve slevě</h2><a href="/slevy/">Všechny slevy →</a></div>{row(sale)}</section>' if sale else ''}
{featured}<section class="sec"><div class="sec__h"><h2>LEGO podle řady</h2><a href="/lego/">Všechno LEGO →</a></div>{lego}</section>
<section class="sec"><div class="sec__h"><h2>Oblíbené postavičky</h2><a href="/postavicky/">Všechny →</a></div>{chars}</section>
{guides_sec}
<section class="sec"><h2>Jak to funguje</h2><ol class="steps"><li><h3>Najdete hračku</h3><p>Podle kategorie, věku dítěte, značky nebo postavičky. Nebo ji prostě napíšete do hledání.</p></li>
<li><h3>Porovnáte obchody</h3><p>Stejnou hračku z různých e‑shopů dáme vedle sebe, od nejlevnější. Vidíte i vývoj ceny.</p></li>
<li><h3>Koupíte v e‑shopu</h3><p>Odkaz vás pošle rovnou do obchodu. Platíte tam, za stejnou cenu jako bez nás.</p></li></ol></section></div>"""
    ld = [{"@context": "https://schema.org", "@type": "WebSite", "name": "Hračkárium", "url": BASE + "/",
           "potentialAction": {"@type": "SearchAction", "target": BASE + "/hledat/?q={q}", "query-input": "required name=q"}},
          {"@context": "https://schema.org", "@type": "Organization", "name": "Hračkárium", "url": BASE + "/", "logo": BASE + "/favicon-512.png"}]
    return S.layout("/", "Hračkárium – srovnání cen hraček z českých e‑shopů", f"Srovnání cen hraček z {st['shops']} českých e‑shopů: LEGO, stavebnice, deskové hry, puzzle, panenky a dárky podle věku. Najděte nejlevnější nabídku.",
                    body, jsonld=ld, preload_img="/img/ui/hero-1200.webp", full=True)


def write_search(out, products, by_top, series, brands, brand_name, lic, landings=(), cats=()):
    """Header suggestions: categories/series/brands/characters (small, loaded on focus) + product index split by the
    first two letters of each word, so a query loads one small file."""
    sug = [[cat_name(t), f"/{t}/", "kategorie"] for t in X.TOP if by_top.get(t)]
    sug += [[series_name(s), f"/lego/{s}/", "LEGO řada"] for s in series]
    sug += [[brand_name[b], f"/znacky/{b}/", "značka"] for b in sorted(brands, key=lambda b: -len(brands[b]))]
    sug += [[f"Hračky {n}", f"/hracky-{s}/", "postavička"] for s, n, _ in X.LICENCES if s in lic]
    sug += [[L["h1"], L["path"], "téma"] for L in landings if L["index"] and L["n"] >= 15][:900]
    out.write("data/sug.json", json.dumps(sug, ensure_ascii=False, separators=(",", ":")))
    # index for the 404 page (loaded only there): label + path, most general first; the script sends a dead URL to the best match
    r404 = [[cat_name(t), f"/{t}/"] for t in X.TOP if by_top.get(t)]
    r404 += [[cat_name(k), f"/{k}/"] for k in cats if "/" in k and k in X.TREE]
    r404 += [[series_name(s), f"/lego/{s}/"] for s in series]
    r404 += [[n, f"/hracky-{s}/"] for s, n, _ in X.LICENCES if s in lic]
    r404 += [[brand_name[b], f"/znacky/{b}/"] for b in sorted(brands, key=lambda b: -len(brands[b]))]
    r404 += [[L["h1"], L["path"]] for L in landings if L["index"]]
    out.write("data/r404.json", json.dumps(r404, ensure_ascii=False, separators=(",", ":")))
    buckets = defaultdict(list)
    for i, p in enumerate(products):
        if not p["page"]:
            continue
        row = [p["name"], p["slug"], p["price"], len(p["offers"]), R.img_url(p["img"])]
        keys = set()
        for w in re.findall(r"[a-z0-9]+", X.slugify(p["name"]).replace("-", " ")):
            if len(w) >= 2:
                keys.add(w[:2])
        for k in keys:
            buckets[k].append(row)
    for k, rows in buckets.items():
        out.write(f"data/s/{k}.json", json.dumps(rows[:4000], ensure_ascii=False, separators=(",", ":")))


def llms_txt(stats, by_top, series):
    lines = ["# Hračkárium (hrackarium.cz)", "", f"> Srovnávač cen hraček z {stats['shops']} českých e-shopů ({stats['products']} hraček skladem, ceny aktualizujeme denně).", "",
             "## Kategorie"] + [f"- [{cat_name(t)}]({BASE}/{t}/)" for t in X.TOP if by_top.get(t)] + ["", "## LEGO řady"] + \
            [f"- [{series_name(s)}]({BASE}/lego/{s}/)" for s in series] + ["", "## O webu", f"- [Jak srovnáváme]({BASE}/jak-srovnavame/)", f"- [Dárky podle věku]({BASE}/darky/)"]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
