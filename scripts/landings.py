"""Long-tail landing pages from declarative rules (content/landings/*.json) plus programmatic families.

A record says WHAT the page is (slug, h1, rules) and the engine finds the matching products. Rules match a folded
(lower-case, no diacritics) text built from the product title(s) (default) or, with "scope": "text", also the description start and the shops' own category paths,
so patterns are written without diacritics and with word boundaries:  {"any": ["\\\\bdo vany\\\\b"], "cat": ["pro-nejmensi"]}.

Rule keys: any / all / none (regex lists on the text), cat (category prefixes), brand (names), age [lo, hi] in months (null = open),
age_unknown (keep products without an age), price [lo, hi], sex ("m"/"f"), offers (min number of shops), lic (licence slug), lego (series slug).

Page record keys: slug, h1, title?, lead?, desc?, rules, min (default 6 products or the page is not created), index_min (default 12,
fewer = noindex,follow), parent (path of the hub page; breadcrumbs + chips), hubs (existing pages that should link here),
group (duplicate detection: two pages of one group with > 90 % the same products -> the later one is dropped), icon, home (featured on the home page).
"""
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import taxonomy as X

APP = Path(__file__).resolve().parent.parent
MIN_DEFAULT, INDEX_MIN_DEFAULT = 6, 12


def fold(s):
    return "".join(c for c in unicodedata.normalize("NFKD", (s or "").lower()) if not unicodedata.combining(c))


def hay(p):
    h = p.get("_h")
    if h is None:
        h = fold(" ".join([p["name"], p["dry"], p["desc"][:600], p.get("paths", "")]))
        p["_h"] = h
    return h


def title_hay(p):
    h = p.get("_t")
    if h is None:
        h = fold(p["name"] + " " + p["dry"])
        p["_t"] = h
    return h


def kc(n):
    return f"{int(round(n)):,}".replace(",", " ") + " Kč"


def compile_rules(r):
    rx = lambda lst: [re.compile(x) for x in lst]
    any_, all_, none_ = rx(r.get("any", [])), rx(r.get("all", [])), rx(r.get("none", []))
    cats, brands = tuple(r.get("cat", [])), {fold(b) for b in r.get("brand", [])}
    age, price, sex, offers = r.get("age"), r.get("price"), r.get("sex"), r.get("offers", 0)
    lic, lego, age_unknown = r.get("lic"), r.get("lego"), r.get("age_unknown", False)
    haystack = hay if r.get("scope") == "text" else title_hay     # default: product titles only; "scope": "text" adds description and the shops' category paths

    def pred(p):
        if cats and not p["cat"].startswith(cats):
            return False
        if offers and len(p["offers"]) < offers:
            return False
        if price and ((price[0] is not None and p["price"] < price[0]) or (price[1] is not None and p["price"] > price[1])):
            return False
        if sex and p["sex"] != sex:
            return False
        if lic and lic not in p["lic"]:
            return False
        if lego and p["lego"] != lego:
            return False
        if brands and fold(p["brand"]) not in brands:
            return False
        if age:
            a = p["age"]
            if a is None:
                if not age_unknown:
                    return False
            elif (age[0] is not None and a < age[0]) or (age[1] is not None and a > age[1]):
                return False
        if any_ or all_ or none_:
            h = haystack(p)
            if any_ and not any(x.search(h) for x in any_):
                return False
            if all_ and not all(x.search(h) for x in all_):
                return False
            if none_ and any(x.search(h) for x in none_):
                return False
        return True
    return pred


def load_records(only_kw2=False):
    recs = []
    for f in sorted((APP / "content/landings").glob("*.json")):
        if f.name.startswith("kw2") != only_kw2:      # keyword-wave candidates (kw2*.json) come last, after every hand-written and generated page
            continue
        data = json.loads(f.read_text())
        recs += data if isinstance(data, list) else data.get("pages", [])
    return recs


def age_between(lo, hi):
    return lambda p: p["age"] is not None and lo <= p["age"] <= hi


def generated_records(products, by_cat, reserved):
    """Matrix families that would be silly to write by hand."""
    recs = []
    pop = lambda p: len(p["offers"]) >= 2

    # ---- toys by child's age (global, not per category): what parents type ("hračky pro děti od 3 let")
    recs += [
        {"slug": "hracky-pro-miminka", "h1": "Hračky pro miminka", "parent": "/kategorie/", "group": "vek", "home": True, "icon": "chrastitko", "_pred": age_between(0, 11), "hubs": ["/pro-nejmensi/"]},
        {"slug": "hracky-pro-miminka-od-6-mesicu", "h1": "Hračky pro miminka od 6 měsíců", "parent": "/hracky-pro-miminka/", "group": "vek", "icon": "chrastitko", "_pred": age_between(5, 7)},
        {"slug": "hracky-pro-rocni-dite", "h1": "Hračky pro roční dítě", "parent": "/hracky-pro-miminka/", "group": "vek", "icon": "chrastitko", "_pred": age_between(9, 18)},
        {"slug": "hracky-pro-batolata", "h1": "Hračky pro batolata", "parent": "/kategorie/", "group": "vek", "icon": "chrastitko", "_pred": age_between(12, 35)},
        {"slug": "hracky-pro-predskolaky", "h1": "Hračky pro předškoláky", "parent": "/kategorie/", "group": "vek", "icon": "pastelky", "_pred": age_between(36, 71)},
        {"slug": "hracky-pro-skolaky", "h1": "Hračky pro školáky", "parent": "/kategorie/", "group": "vek", "icon": "mikroskop", "_pred": age_between(72, 143)},
        {"slug": "hracky-pro-teenagery", "h1": "Hračky a dárky pro teenagery", "parent": "/kategorie/", "group": "vek", "icon": "hra", "_pred": age_between(144, 216)},
    ]
    for n in range(2, 13):
        recs.append({"slug": f"hracky-pro-deti-od-{n}-let", "h1": f"Hračky pro děti od {n} let", "parent": "/kategorie/", "group": "vek", "icon": "party",
                     "_pred": age_between(n * 12 - 6, n * 12 + 5)})

    # ---- gifts for boys / girls by price (the shops themselves say who a toy is for)
    for who, sex, noun in (("kluky", "m", "kluky"), ("holky", "f", "holky")):
        for cap in (300, 500, 1000, 2000):
            recs.append({"slug": f"darky-pro-{who}-do-{cap}-kc", "h1": f"Dárky pro {who} do {cap} Kč", "parent": f"/darek-pro-{'kluka' if sex == 'm' else 'holku'}/", "group": f"darky-{sex}-cap",
                         "hubs": ["/darky/"], "icon": "party", "rules": {"sex": sex, "price": [None, cap]}, "lead": f"Hračky, které obchody řadí pro {noun}, do {cap} Kč."})
    # ---- sex x top category and sex x age (what parents type: "stavebnice pro kluky", "hračky pro holky od 5 let")
    sex_name = (("m", "kluky"), ("f", "holky"))
    for top in X.TOP:
        items = by_cat.get(top, [])
        if len(items) < 60:
            continue
        for sex, who in sex_name:
            sel = [p for p in items if p["sex"] == sex]
            if 12 <= len(sel) < len(items) * 0.97:
                recs.append({"slug": f"{top}/pro-{who}", "h1": f"{X.TREE[top][2]} pro {who}", "parent": f"/{top}/", "group": f"{top}-sex", "icon": None, "items": sel,
                             "title": f"{X.TREE[top][2]} pro {who} – srovnání cen"})
    for sex, who in sex_name:
        for n in range(2, 13):
            sel = [p for p in products if p["sex"] == sex and p["age"] is not None and n * 12 - 6 <= p["age"] <= n * 12 + 5]
            recs.append({"slug": f"hracky-pro-{who}-od-{n}-let", "h1": f"Hračky pro {who} od {n} let", "parent": f"/hracky-pro-{who}/", "group": f"vek-{sex}", "icon": "party", "items": sel})
    # ---- Christmas, curated by what is compared in many shops (popular = safe gift)
    xm = {"parent": "/vanocni-darky/", "group": "vanoce", "icon": "party", "hubs": ["/darky/"]}
    recs += [
        {"slug": "vanocni-darky", "h1": "Vánoční dárky pro děti 2026", "home": True, "parent": "/darky/", "group": "vanoce-hub", "icon": "party", "hubs": ["/darky/"],
         "_pred": lambda p: len(p["offers"]) >= 4 and p["age"] is not None and p["cat"].split("/")[0] not in ("fan-darky", "kostymy-a-party"), "min": 12},
        {**xm, "slug": "vanocni-darky/pro-kluky", "h1": "Vánoční dárky pro kluky", "_pred": lambda p: p["sex"] == "m" and len(p["offers"]) >= 3},
        {**xm, "slug": "vanocni-darky/pro-holky", "h1": "Vánoční dárky pro holky", "_pred": lambda p: p["sex"] == "f" and len(p["offers"]) >= 3},
        {**xm, "slug": "vanocni-darky/do-500-kc", "h1": "Vánoční dárky do 500 Kč", "_pred": lambda p: p["price"] <= 500 and len(p["offers"]) >= 3 and p["cat"].split("/")[0] not in ("fan-darky", "kostymy-a-party")},
        {**xm, "slug": "vanocni-darky/do-1000-kc", "h1": "Vánoční dárky do 1 000 Kč", "_pred": lambda p: 300 < p["price"] <= 1000 and len(p["offers"]) >= 4 and p["cat"].split("/")[0] not in ("fan-darky", "kostymy-a-party")},
        {**xm, "slug": "vanocni-darky/nad-2000-kc", "h1": "Velké vánoční dárky nad 2 000 Kč", "_pred": lambda p: p["price"] > 2000 and len(p["offers"]) >= 3},
        {**xm, "slug": "darky-na-mikulase-do-bote", "h1": "Dárky na Mikuláše do boty", "parent": "/vanocni-darky/", "_pred": lambda p: 29 <= p["price"] <= 150 and len(p["offers"]) >= 2 and p["cat"].split("/")[0] not in ("fan-darky", "kostymy-a-party", "elektronika")},
        {**xm, "slug": "hracky-do-adventniho-kalendare", "h1": "Hračky do adventního kalendáře", "parent": "/adventni-kalendare/", "_pred": lambda p: 20 <= p["price"] <= 120 and p["cat"].split("/")[0] in ("figurky-a-zviratka", "kreativni", "auta-a-vlacky", "puzzle", "stavebnice", "plysaci", "hrajeme-si-na")},
    ]
    # ---- occasions
    oc = {"parent": "/darky/", "group": "prilezitosti", "icon": "party", "hubs": ["/darky/"]}
    big = ("stavebnice", "lego", "spolecenske-hry", "kreativni", "naucne", "puzzle", "auta-a-vlacky", "figurky-a-zviratka")
    recs += [
        {**oc, "slug": "darek-pro-prvnacka", "h1": "Dárek pro prvňáčka", "_pred": lambda p: p["age"] is not None and 66 <= p["age"] <= 90 and len(p["offers"]) >= 2 and p["cat"].split("/")[0] in big},
        {**oc, "slug": "darek-k-zakonceni-skolky", "h1": "Dárek k ukončení školky", "_pred": lambda p: p["age"] is not None and 48 <= p["age"] <= 84 and len(p["offers"]) >= 2 and p["cat"].split("/")[0] in big},
        {**oc, "slug": "darek-k-1-narozeninam", "h1": "Dárek k 1. narozeninám", "_pred": lambda p: p["age"] is not None and 6 <= p["age"] <= 18 and len(p["offers"]) >= 2},
        {**oc, "slug": "darek-k-narozeni-miminka", "h1": "Dárek k narození miminka", "_pred": lambda p: p["age"] is not None and p["age"] <= 6 and 150 <= p["price"] <= 1500},
        {**oc, "slug": "darek-k-narozeninam-dite", "h1": "Dárek k narozeninám dítěte", "_pred": lambda p: len(p["offers"]) >= 5 and p["age"] is not None and p["cat"].split("/")[0] in big},
    ]
    # ---- category x price tier (stavebnice do 500 Kč ...)
    for top in X.TOP:
        items = by_cat.get(top, [])
        if len(items) < 60:
            continue
        name = X.TREE[top][0]
        for cap in (300, 500, 1000, 2000):
            sel = [p for p in items if p["price"] <= cap]
            if 12 <= len(sel) < len(items) * 0.97:
                recs.append({"slug": f"{top}/do-{cap}-kc", "h1": f"{X.TREE[top][2]} do {cap} Kč", "parent": f"/{top}/", "group": f"{top}-cap", "icon": None, "items": sel})
    # ---- LEGO by price
    lego = by_cat.get("lego", [])
    for cap in (500, 1000, 2000, 3000):
        recs.append({"slug": f"lego/do-{cap}-kc", "h1": f"LEGO do {cap} Kč", "parent": "/lego/", "group": "lego-cap", "icon": "kostky", "items": [p for p in lego if p["price"] <= cap]})
    recs.append({"slug": "lego/nad-3000-kc", "h1": "Velké LEGO sety nad 3 000 Kč", "parent": "/lego/", "group": "lego-cap", "icon": "kostky", "items": [p for p in lego if p["price"] > 3000]})
    # ---- brand x category (Schleich koně, Bruder traktory ...)
    by_brand_cat = defaultdict(list)
    for p in products:
        if p["brand"]:
            by_brand_cat[(X.slugify(p["brand"]), p["cat"].split("/")[0])].append(p)
    brand_total = defaultdict(int)
    for (b, c), ps in by_brand_cat.items():
        brand_total[b] += len(ps)
    names = {}
    for ps in by_brand_cat.values():
        names.setdefault(X.slugify(ps[0]["brand"]), ps[0]["brand"])
    ranked = sorted(((b, c, ps) for (b, c), ps in by_brand_cat.items() if len(ps) >= 8 and brand_total[b] > len(ps) + 5 and b != c), key=lambda x: -len(x[2]))[:700]
    for b, c, ps in ranked:
        recs.append({"slug": f"znacky/{b}/{c}", "h1": f"{names[b]} – {X.TREE[c][2].lower()}", "parent": f"/znacky/{b}/", "group": "brand-cat", "icon": None, "items": ps,
                     "title": f"{names[b]} {X.TREE[c][0].lower()} – srovnání cen", "index_min": 15})
    return recs


def jaccard(a, b):
    return len(a & b) / max(1, len(a | b))


def plan(products, reserved=()):
    """Evaluate all records. Returns a list of landing dicts (path, h1, items, ...) in priority order; skips tiny, duplicate and reserved ones."""
    by_cat = defaultdict(list)
    for p in products:
        by_cat[p["cat"]].append(p)
        if "/" in p["cat"]:
            by_cat[p["cat"].split("/")[0]].append(p)
    recs = load_records() + generated_records(products, by_cat, reserved) + load_records(only_kw2=True)
    seen_paths, groups, out, dropped = set(reserved), defaultdict(list), [], defaultdict(int)
    all_sets = []        # product-id sets of every accepted page: records with "dedupe_all" must differ from all of them
    for r in recs:
        path = "/" + r["slug"].strip("/") + "/"
        if path in seen_paths:
            dropped["path exists"] += 1
            continue
        if "items" in r:
            items = r["items"]
        else:
            pred = r.get("_pred") or compile_rules(r.get("rules", {}))
            cats = tuple((r.get("rules") or {}).get("cat", []))
            pool = [p for p in products if p["cat"].startswith(cats)] if cats else products
            items = [p for p in pool if pred(p)]
        items = [p for p in items if p.get("page", True)]
        if len(items) < r.get("min", MIN_DEFAULT):
            dropped["too few"] += 1
            continue
        ids = {p["id"] for p in items}
        g = r.get("group") or r["slug"].split("/")[0]
        if any(jaccard(ids, o) > 0.9 for o in groups[g]):
            dropped["duplicate of a sibling"] += 1
            continue
        if r.get("dedupe_all") and any(0.85 <= len(ids) / max(1, len(o)) <= 1 / 0.85 and jaccard(ids, o) > 0.85 for o in all_sets):
            dropped["same products as an existing page"] += 1
            continue
        all_sets.append(ids)
        groups[g].append(ids)
        seen_paths.add(path)
        prices = sorted(p["price"] for p in items)
        out.append({"path": path, "slug": r["slug"].strip("/"), "h1": r["h1"], "title": r.get("title"), "lead": r.get("lead"), "desc": r.get("desc"), "items": items,
                    "parent": r.get("parent"), "hubs": r.get("hubs", []), "group": g, "icon": r.get("icon"), "home": r.get("home", False),
                    "index": len(items) >= r.get("index_min", INDEX_MIN_DEFAULT), "lo": prices[0], "n": len(items)})
    return out, dict(dropped)


def kids_map(landings):
    """path of a hub page -> [(path, h1, n)] of landing pages that belong under it (parent) or want a link from it (hubs)."""
    kids = defaultdict(list)
    for L in landings:
        for hub in set(([L["parent"]] if L["parent"] else []) + list(L["hubs"])):
            kids[hub].append((L["path"], L["h1"], L["n"]))
    return kids


# ---------------------------------------------------------------- guides (content/guides): index = metadata + product-pick rules, <slug>.json = text
def load_guides():
    gd = APP / "content/guides"
    if not (gd / "_index.json").exists():
        return []
    meta = {g["slug"]: g for g in json.loads((gd / "_index.json").read_text())}
    out = []
    for slug, g in meta.items():
        f = gd / f"{slug}.json"
        if f.exists():
            t = json.loads(f.read_text())
            out.append({**g, "intro": t.get("intro", ""), "body": t.get("body", ""), "faq": t.get("faq", []), "description": t.get("description")})
    return out


def guide_picks(products, g, limit=8):
    rules = dict(g.get("rules") or {})
    if g.get("cat"):
        rules["cat"] = g["cat"]
    pred = compile_rules(rules)
    cats = tuple(rules.get("cat", []))
    pool = [p for p in products if p["cat"].startswith(cats)] if cats else products
    items = [p for p in pool if pred(p) and p["img"] and p.get("page", True)]
    items.sort(key=lambda p: (-len(p["offers"]), p["price"]))
    return items[:limit]
