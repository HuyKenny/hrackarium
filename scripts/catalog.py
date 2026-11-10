"""Merge offers from all shops into products and keep everything stable between runs.

Matching: EAN/GTIN first, then a set number (LEGO 42115, Playmobil 71148, Bruder 02752 …) for the brands that print it,
otherwise the offer stays its own product. Slugs, price history and a short snapshot of products that went out of stock
live in data/state/state.json.gz (CI keeps it encrypted as a release asset).
"""
import gzip
import json
import re
import statistics
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import taxonomy as X

APP = Path(__file__).resolve().parent.parent
RAW = APP / "data/raw"
STATE = APP / "data/state"
TODAY = date.today()
DAY = TODAY.toordinal()
GONE_DAYS = 45            # an out-of-stock product keeps its page ("momentálně nedostupné") this long, then 404
HISTORY_DAYS = 120


def norm_ean(e):
    d = re.sub(r"\D", "", str(e or ""))
    if len(d) in (8, 12, 13, 14) and set(d) != {"0"}:
        d = d.lstrip("0").zfill(13) if len(d) > 8 else d
        return d if len(d) <= 13 else ""
    return ""


def https(u):
    return "https://" + u[7:] if (u or "").startswith("http://") else (u or "")


def shop_fallback(shop, rec):
    """Single-brand shops (LEGO.com) name products without the brand ("Starter Kit"): their own category, unless vetoed."""
    return shop.get("fallback_cat") if shop.get("fallback_cat") and not X.veto(rec) else None


def load_offers(shops):
    out, dropped = [], Counter()
    for s in shops:
        p = RAW / f"{s['id']}.jsonl.gz"
        if not p.exists():
            continue
        with gzip.open(p, "rt", encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                cat = X.classify(r) or (shop_fallback(s, r))
                if not cat:
                    dropped[s["id"]] += 1
                    continue
                price = float(r["p"] or 0)
                if price <= 0 or not r.get("go"):
                    continue
                brand = X.brand_of(r) or s.get("brand", "")
                title = X.clean(r["t"])
                out.append({
                    "shop": s["id"], "oid": r["id"], "title": title, "desc": X.clean(re.sub(r"<[^>]+>", " ", r.get("d") or "")),
                    "brand": brand, "ean": norm_ean(r.get("ean")), "setno": X.set_number(r, brand),
                    "img": "" if s.get("no_images") else https(r.get("img")),
                    "imgs": [] if s.get("no_images") else [https(u) for u in r.get("imgs") or [] if u][:4],
                    "price": round(price), "was": round(float(r.get("was") or 0)), "url": r.get("url") or "", "go": r["go"],
                    "cat": cat, "age": X.age_of(r), "sex": X.gender_of(r), "path": r.get("cat") or "",
                })
    return out, dropped


class DSU:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)


def mixed(s):
    """Prefer normally cased titles over SHOUTING ones."""
    letters = [c for c in s if c.isalpha()]
    return sum(1 for c in letters if c.islower()) / (len(letters) or 1)


def cluster(offers, shop_rank):
    dsu = DSU()
    for i, o in enumerate(offers):
        dsu.find(i)
    first = {}
    for i, o in enumerate(offers):
        for key in (("e:" + o["ean"]) if o["ean"] else None, ("s:" + o["setno"]) if o["setno"] else None):
            if key:
                if key in first:
                    dsu.union(first[key], i)
                else:
                    first[key] = i
    groups = defaultdict(list)
    for i in range(len(offers)):
        groups[dsu.find(i)].append(offers[i])
    products = []
    for offs in groups.values():
        eans = sorted({o["ean"] for o in offs if o["ean"]})
        sets = sorted({o["setno"] for o in offs if o["setno"]})
        pid = ("e:" + eans[0]) if eans else ("s:" + sets[0]) if sets else f"o:{offs[0]['shop']}:{offs[0]['oid']}"
        # one offer per shop (the cheapest), cheapest first
        best = {}
        for o in sorted(offs, key=lambda o: o["price"]):
            best.setdefault(o["shop"], o)
        shop_offers = sorted(best.values(), key=lambda o: (o["price"], shop_rank.get(o["shop"], 99)))
        rep = sorted(offs, key=lambda o: (shop_rank.get(o["shop"], 99), -mixed(o["title"])))[0]
        name = rep["title"]
        brands = Counter(o["brand"] for o in offs if o["brand"])
        cats = Counter(o["cat"] for o in offs)
        cat = cats.most_common(1)[0][0]
        if cat.split("/")[0] in ("fan-darky", "drevene") and len(cats) > 1:   # broad buckets lose against a concrete category
            cat = next(c for c, _ in cats.most_common() if c.split("/")[0] not in ("fan-darky", "drevene"))
        ages = [o["age"] for o in offs if o["age"] is not None]
        sexes = {o["sex"] for o in offs if o["sex"]}
        desc = max((o["desc"] for o in offs), key=len)
        # bambule.cz thumbnails do not show in some visitors' browsers (10. 11. 2026): use any other shop's picture first
        img_order = sorted(offs, key=lambda o: (o["shop"] == "bambule", shop_rank.get(o["shop"], 99)))
        img = next((o["img"] for o in img_order if o["img"]), "")
        imgs = []
        for o in offs:
            for u in [o["img"]] + o["imgs"]:
                if u and u != img and u not in imgs:
                    imgs.append(u)
        products.append({
            "id": pid, "name": name, "brand": brands.most_common(1)[0][0] if brands else "", "ean": eans[0] if eans else "",
            "cat": cat, "age": min(ages) if ages else None, "sex": sexes.pop() if len(sexes) == 1 else "", "desc": desc,
            "img": img, "imgs": imgs[:6], "dry": " ".join(o["title"] for o in offs).lower(),
            "offers": [{"shop": o["shop"], "price": o["price"], "was": o["was"], "go": o["go"], "url": o["url"]} for o in shop_offers],
            "price": shop_offers[0]["price"],
            "lego": X.lego_series(name) if (brands.most_common(1)[0][0] if brands else "") == "LEGO" or cat == "lego" else "",
            "lic": X.licences_of(name),
        })
    return products


def sanity(products):
    """Price errors in feeds: an offer under 45 % of the same product's other offers is dropped."""
    dropped = 0
    for p in products:
        if len(p["offers"]) < 3:
            continue
        keep = []
        for o in p["offers"]:
            others = [x["price"] for x in p["offers"] if x is not o]
            if o["price"] < 0.45 * statistics.median(others):
                dropped += 1
            else:
                keep.append(o)
        p["offers"] = keep
        p["price"] = keep[0]["price"]
    return dropped


# ---------------------------------------------------------------- slugs, history, gone products

def product_slug(p):
    s = X.slugify(p["name"])
    if p["brand"] and not s.startswith(X.slugify(p["brand"])) and X.slugify(p["brand"]) not in s:
        s = X.slugify(p["brand"]) + "-" + s
    return s[:90].rsplit("-", 1)[0] if len(s) > 90 else s


def assign_slugs(products, state):
    slugs = state.setdefault("slugs", {})
    used = set(slugs.values())
    new = 0
    for p in products:
        if p["id"] in slugs:
            continue
        base = product_slug(p) or "hracka"
        s, i = base, 2
        while s in used:
            s, i = f"{base}-{i}", i + 1
        slugs[p["id"]] = s
        used.add(s)
        new += 1
    for p in products:
        p["slug"] = slugs[p["id"]]
    return new


def price_history(products, state):
    """Change points [day, price] per product; the 30-day low is what shoppers care about (and it is honest:
    only prices we saw ourselves)."""
    ph = state.setdefault("ph", {})
    for p in products:
        h = ph.setdefault(p["id"], [])
        if not h or h[-1][1] != p["price"] or DAY - h[-1][0] >= 7:
            if h and h[-1][0] == DAY:
                h[-1][1] = p["price"]
            else:
                h.append([DAY, p["price"]])
        while len(h) > 1 and h[1][0] <= DAY - HISTORY_DAYS:
            h.pop(0)
        p["hist"] = h
        prices = [x[1] for x in h if x[0] >= DAY - 30] + ([h[0][1]] if h and h[0][0] < DAY - 30 else [])
        p["low30"] = min(prices) if prices else p["price"]
        p["since"] = h[0][0]
    live = {p["id"] for p in products}
    for k in list(ph):
        if k not in live and (not ph[k] or ph[k][-1][0] < DAY - HISTORY_DAYS):
            ph.pop(k)


def gone_products(products, state, last_seen_snapshot):
    """Products that disappeared keep a "momentálně nedostupné" page for GONE_DAYS (search engines and links keep
    working; the page points to similar toys), then they 404."""
    gone = state.setdefault("gone", {})
    live = {p["id"] for p in products}
    for pid, snap in last_seen_snapshot.items():
        if pid not in live and pid not in gone:
            gone[pid] = dict(snap, day=DAY)
    for pid in list(gone):
        if pid in live or gone[pid]["day"] < DAY - GONE_DAYS:
            gone.pop(pid)
    state["snap"] = {p["id"]: {"slug": p["slug"], "name": p["name"], "brand": p["brand"], "cat": p["cat"], "img": p["img"],
                               "price": p["price"]} for p in products if p.get("page")}
    return gone


def load_state():
    p = STATE / "state.json.gz"
    if p.exists():
        with gzip.open(p, "rt", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state):
    STATE.mkdir(parents=True, exist_ok=True)
    with gzip.open(STATE / "state.json.gz", "wt", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, separators=(",", ":"))
