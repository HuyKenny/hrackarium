#!/usr/bin/env python3
"""Download toy offers from the affiliate networks into data/raw/<shop>.jsonl.gz (one slim JSON object per offer).

    python3 scripts/fetch.py            # all enabled shops in data/shops.json
    python3 scripts/fetch.py bambule    # only these shop ids
    FETCH_LIMIT=300 python3 scripts/fetch.py bambule   # tiny sample for local work

Keys come from the environment (GitHub secrets; locally scripts/localenv.py reads ~/ai/credentials/):
  CJ_API_KEY, CJ_CID, CJ_PID          CJ GraphQL product search
  FEEDS_JSON                          {"<feed_key>": "<feed url>"} for eHub / Dognet XML feeds (URLs carry tokens)

This repository is PUBLIC and so are its Actions logs: nothing here may print a key, a feed URL or a raw API error body.
Only shop ids, counts and exception class names are logged; every feed URL is registered with ::add-mask:: first.
Safety: a failed download keeps the previous file; so does a feed that shrank below 50 % of the previous run.
"""
import gzip
import json
import os
import re
import signal
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree as ET

APP = Path(__file__).resolve().parent.parent
RAW = APP / "data/raw"
UA = "HrackariumFeed/1.0 (+https://hrackarium.cz)"
EHUB_CLICK = "https://ehub.cz/system/scripts/click.php?a_aid={aid}&a_bid={bid}&desturl="
EHUB_AID = "052443b7"          # public: part of every eHub click link
LIMIT = int(os.environ.get("FETCH_LIMIT", "0"))

sys.path.insert(0, str(APP / "scripts"))
if not os.environ.get("GITHUB_ACTIONS"):
    import localenv
    localenv.load()


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def mask_feed_urls():
    """GitHub masks a secret only as a whole string; the single URLs inside FEEDS_JSON would show up in a traceback."""
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    try:
        feeds = json.loads(os.environ.get("FEEDS_JSON") or "{}")
    except ValueError:
        return
    for u in feeds.values():
        print(f"::add-mask::{u}", flush=True)
        for part in re.findall(r"[A-Za-z0-9_\-]{12,}", u):   # tokens alone, in case a URL gets split or re-encoded
            print(f"::add-mask::{part}", flush=True)


def price_of(s):
    s = (s or "").strip()
    cur = (re.findall(r"[A-Za-z]{3}", s) or [""])[0].upper()
    n = re.sub(r"[^\d,.]", "", s)
    if "," in n and "." in n:
        n = n.replace(",", "")
    n = n.replace(",", ".")
    try:
        return float(n), cur
    except ValueError:
        return 0.0, cur


def local(tag):
    return tag.rsplit("}", 1)[-1]


def path_ok(shop, path):
    inc, exc = shop.get("include"), shop.get("exclude")
    if inc and not re.search(inc, path):
        return False
    if exc and re.search(exc, path):
        return False
    return True


# ---------------------------------------------------------------- CJ

def cj_gql(query):
    req = urllib.request.Request("https://ads.api.cj.com/query", data=json.dumps({"query": query}).encode(),
                                 headers={"Authorization": "Bearer " + os.environ["CJ_API_KEY"], "Content-Type": "application/json"})
    for attempt in range(7):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                x = json.load(r)
            if "errors" in x:
                raise RuntimeError("CJ GraphQL error")
            return x["data"]["shoppingProducts"]
        except Exception as e:  # CJ answers 403 for a short while after bursts
            if attempt == 6:
                raise
            wait = (30 if "403" in str(e) else 6) * (attempt + 1)
            log(f"  CJ retry {attempt + 1} in {wait}s: {type(e).__name__}")
            time.sleep(wait)


def cj_offers(shop):
    pid = os.environ.get("CJ_PID") or ""
    base = f'companyId:"{os.environ["CJ_CID"]}", partnerIds:["{shop["advertiser"]}"], currency:"CZK", availability:IN_STOCK'
    fields = ("id itemGroupId title description brand gtin mpn link imageLink additionalImageLink productType ageGroup gender color "
              f'condition price{{ amount currency }} salePrice{{ amount }} linkCode(pid:"{pid}"){{ clickUrl }}')
    got = {}

    def grab(lo, hi):
        """One query returns both the total and the first 1 000 rows; split the price band only when it does not fit.
        CJ fails for offset >= 10 000 and its paging order is unstable, so bands of <= 1 000 rows are the only safe way."""
        if LIMIT and len(got) >= LIMIT:
            return
        x = cj_gql('{ shoppingProducts(%s, lowPrice:%s, highPrice:%s, limit:1000){ totalCount resultList{ %s } } }' % (base, lo, hi, fields))
        time.sleep(0.6)
        n = x["totalCount"]
        if n <= 1000 or hi - lo < 0.02 or LIMIT:
            for p in x["resultList"]:
                got[p["id"]] = p
            if n > 1000 and hi - lo < 0.02:   # many items at one price: a second pass catches what the unstable order hid
                x = cj_gql('{ shoppingProducts(%s, lowPrice:%s, highPrice:%s, limit:1000, offset:1000){ resultList{ %s } } }' % (base, lo, hi, fields))
                for p in x["resultList"]:
                    got[p["id"]] = p
            return
        mid = float(int((lo + hi) / 2)) if hi - lo >= 50 else round((lo + hi) / 2, 2)
        grab(lo, mid)
        grab(round(mid + 0.01, 2), hi)

    edges = [0, 100, 200, 300, 400, 500, 650, 800, 1000, 1300, 1700, 2200, 3000, 4500, 7000, 500000]
    for lo, hi in zip(edges, edges[1:]):
        grab(lo if lo == 0 else lo + 0.01, hi)
    for p in got.values():
        path = " | ".join(p.get("productType") or [])
        if not path_ok(shop, path):
            continue
        if (p.get("condition") or "new").lower() not in ("new", ""):
            continue
        price = float(p["price"]["amount"])
        sale = float((p.get("salePrice") or {}).get("amount") or 0)
        go = ((p.get("linkCode") or {}).get("clickUrl")) or p.get("link")
        yield {"id": p["id"], "g": p.get("itemGroupId") or "", "t": p["title"], "d": (p.get("description") or "")[:1500],
               "b": p.get("brand") or "", "ean": p.get("gtin") or "", "mpn": p.get("mpn") or "",
               "img": p.get("imageLink") or "", "imgs": (p.get("additionalImageLink") or [])[:5],
               "p": sale if 0 < sale < price else price, "was": price if 0 < sale < price else 0,
               "url": p.get("link") or "", "go": go, "cat": path, "age": p.get("ageGroup") or "", "sex": p.get("gender") or ""}


# ---------------------------------------------------------------- XML feeds (Heureka SHOPITEM / Google RSS)

def xml_items(resp):
    for _, el in ET.iterparse(resp, events=("end",)):
        t = local(el.tag)
        if t not in ("item", "SHOPITEM", "entry"):
            continue
        d, params, imgs = {}, [], []
        for ch in el:
            k = local(ch.tag)
            if k == "PARAM":
                params.append(((ch.findtext("PARAM_NAME") or "").strip().lower(), (ch.findtext("VAL") or "").strip()))
            elif k in ("IMGURL_ALTERNATIVE", "additional_image_link"):
                imgs.append((ch.text or "").strip())
            else:
                d.setdefault(k, (ch.text or "").strip())
        el.clear()
        yield t, d, params, imgs


def xml_offers(shop, resp, link_of):
    for kind, d, params, imgs in xml_items(resp):
        if kind == "SHOPITEM":
            pid, title, url, img = d.get("ITEM_ID"), d.get("PRODUCTNAME") or d.get("PRODUCT"), d.get("URL"), d.get("IMGURL")
            price, cur = price_of(d.get("PRICE_VAT") or d.get("PRICE"))
            ean, brand, cat, desc = d.get("EAN", ""), d.get("MANUFACTURER", ""), d.get("CATEGORYTEXT", ""), d.get("DESCRIPTION", "")
            was = 0
        else:
            pid, title, url, img = d.get("id"), d.get("title"), d.get("link"), d.get("image_link")
            if (d.get("availability") or "in stock").lower().replace("_", " ") not in ("in stock", "instock", "preorder", "backorder"):
                continue
            regular, cur = price_of(d.get("price"))
            sale, _ = price_of(d.get("sale_price"))
            price, was = (sale, regular) if 0 < sale < regular else (regular, 0)
            ean, brand, cat, desc = d.get("gtin", ""), d.get("brand", ""), d.get("product_type", "") or d.get("google_product_category", ""), d.get("description", "")
        if cur and cur != "CZK":
            continue
        if not (pid and title and url and price > 0) or not path_ok(shop, cat or ""):
            continue
        plain, go = link_of((url or "").replace("&amp;", "&"))
        age = next((v for k, v in params if k in ("věk", "vek", "věk dítěte", "doporučený věk", "minimální věk")), "")
        yield {"id": pid, "g": d.get("ITEMGROUP_ID") or d.get("item_group_id") or "", "t": title,
               "d": re.sub(r"<[^>]+>", " ", desc or "")[:1500], "b": brand or "", "ean": ean or "", "mpn": d.get("PRODUCTNO") or d.get("mpn") or "",
               "img": img or "", "imgs": [i for i in imgs if i][:5], "p": price, "was": was, "url": plain, "go": go,
               "cat": cat or "", "age": age, "sex": ""}


def open_url(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=300)


_FEED_CACHE = {}


def feed_urls(shop):
    feeds = json.loads(os.environ.get("FEEDS_JSON") or "{}")
    keys = shop.get("feed_keys") or [shop["feed_key"]]
    urls = [feeds[k] for k in keys if feeds.get(k)]
    if not urls:
        raise RuntimeError("feed URL missing in FEEDS_JSON")
    return urls


def cached(url):
    """Download each feed once per run (several shops can share one network export)."""
    if url not in _FEED_CACHE:
        import tempfile
        f = tempfile.TemporaryFile()
        with open_url(url) as r:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
        _FEED_CACHE[url] = f
    f = _FEED_CACHE[url]
    f.seek(0)
    return f


def on_domain(shop, url):
    d = shop.get("domain", "")
    host = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
    return not shop.get("domain_filter") or host == d or host.endswith("." + d)


def ehub_offers(shop):
    pre = EHUB_CLICK.format(aid=EHUB_AID, bid=shop["a_bid"])
    for url in feed_urls(shop):
        for rec in xml_offers(shop, cached(url), lambda u: (u, u) if "click.php" in u else (u, pre + quote(u, safe=""))):
            if on_domain(shop, rec["url"]):
                yield rec


def dognet_offers(shop):
    chid = shop["chid"]
    for url in feed_urls(shop):
        for rec in xml_offers(shop, cached(url), lambda u: (u, u) if "go.dognet.com" in u else (u, f"https://go.dognet.com/?chid={chid}&url=" + quote(u, safe=""))):
            if on_domain(shop, rec["url"]):
                yield rec


SOURCES = {"cj": cj_offers, "ehub": ehub_offers, "dognet": dognet_offers}


def count_lines(p):
    try:
        with gzip.open(p, "rt", encoding="utf-8") as f:
            return sum(1 for _ in f)
    except (OSError, EOFError):
        return 0


SHOP_BUDGET = int(os.environ.get("FETCH_SHOP_BUDGET", "900"))  # seconds per shop; a stuck API must not eat the whole job


class Overtime(BaseException):  # not Exception: retry loops must not swallow it
    pass


def _overtime(signum, frame):
    raise Overtime(f"over {SHOP_BUDGET}s budget")


def run(shop):
    dest = RAW / f"{shop['id']}.jsonl.gz"
    tmp = RAW / f"{shop['id']}.tmp.gz"
    prev = count_lines(dest) if dest.exists() else 0
    t0 = time.time()
    signal.signal(signal.SIGALRM, _overtime)
    signal.alarm(SHOP_BUDGET)
    try:
        n = 0
        seen = set()
        with gzip.open(tmp, "wt", encoding="utf-8") as out:
            for rec in SOURCES[shop["network"]](shop):
                if rec["id"] in seen:
                    continue
                seen.add(rec["id"])
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n += 1
    except (Exception, Overtime) as e:
        signal.alarm(0)
        tmp.unlink(missing_ok=True)
        msg = f"HTTP {e.code}" if isinstance(e, urllib.error.HTTPError) else type(e).__name__
        log(f"{shop['id']}: FAILED ({msg}) — keeping previous file ({prev} offers)")
        return {"shop": shop["id"], "ok": False, "offers": prev, "error": msg}
    signal.alarm(0)
    if n == 0 or (prev and n < prev * 0.5 and not LIMIT):
        tmp.unlink(missing_ok=True)
        log(f"{shop['id']}: only {n} offers (previous {prev}) — keeping previous file")
        return {"shop": shop["id"], "ok": False, "offers": prev, "error": f"shrank to {n}"}
    tmp.replace(dest)
    log(f"{shop['id']}: {n} offers in {time.time() - t0:.0f}s")
    return {"shop": shop["id"], "ok": True, "offers": n, "seconds": round(time.time() - t0)}


def main():
    mask_feed_urls()
    only = set(sys.argv[1:])
    RAW.mkdir(parents=True, exist_ok=True)
    shops = json.load(open(APP / "data/shops.json"))["shops"]
    report = []
    for s in shops:
        if (only and s["id"] not in only) or (not only and s.get("enabled") is False):
            continue
        report.append(run(s))
    old = {}
    rp = RAW / "fetch-report.json"
    if rp.exists():
        old = {r["shop"]: r for r in json.load(open(rp)).get("shops", [])}
    for r in report:
        old[r["shop"]] = r
    json.dump({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "shops": list(old.values())}, open(rp, "w"), indent=1)


if __name__ == "__main__":
    main()
