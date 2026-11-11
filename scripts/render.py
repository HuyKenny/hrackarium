"""HTML templates for hrackarium.cz (plain f-strings, no dependencies). Design „Hrací pokoj" — see static/assets/site.css.

Shapes: 2px ink borders, hard offset shadows, pill buttons, price tags on a string, age stickers. Palette: white paper,
ink #1D1B3A, tomato #FF5A3C, sky #3BA7F5, sun #FFC93C (accents only), mint #3CCB9A. Illustrations from Canva.
"""
import html
import json
import re

E = html.escape
PER_PAGE = 36
SPECULATION = ('<script type="speculationrules">{"prerender":[{"where":{"and":[{"href_matches":"/*"},{"not":{"href_matches":"/data/*"}},'
               '{"not":{"selector_matches":"[rel~=nofollow],[target=_blank]"}}]},"eagerness":"moderate"}]}</script>')
SEARCH_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg>'

# category -> icon file (static/img/ic/<name>.webp, cut from one Canva grid so they share one style)
ICON = {"lego": "kostky", "stavebnice": "kostky", "panenky": "panenka", "auta-a-vlacky": "auto", "rc-modely": "rc", "plysaci": "medved",
        "spolecenske-hry": "hra", "sberatelske-karty": "hra", "puzzle": "puzzle", "figurky-a-zviratka": "dino", "kreativni": "pastelky",
        "naucne": "mikroskop", "pro-nejmensi": "chrastitko", "hrajeme-si-na": "kuchynka", "venku": "kyblik", "elektronika": "rc",
        "kostymy-a-party": "party", "drevene": "vlak", "hudebni": "xylofon", "fan-darky": "party"}
NAV = [("/lego/", "kostky", "LEGO"), ("/panenky/", "panenka", "Panenky"), ("/auta-a-vlacky/", "auto", "Auta a vláčky"),
       ("/spolecenske-hry/", "hra", "Hry"), ("/puzzle/", "puzzle", "Puzzle"), ("/plysaci/", "medved", "Plyšáci"),
       ("/stavebnice/", "vlak", "Stavebnice"), ("/figurky-a-zviratka/", "dino", "Figurky"), ("/kreativni/", "pastelky", "Tvoření"),
       ("/pro-nejmensi/", "chrastitko", "Miminka"), ("/rc-modely/", "rc", "Na ovladač"), ("/venku/", "kyblik", "Ven")]


def kc(n):
    return f"{int(round(n)):,}".replace(",", " ") + " Kč"


def plural(n, one, few, many):
    return one if n == 1 else few if 1 < n < 5 else many


def shops_in(n):
    return f"v {n} obchodě" if n == 1 else f"ve {n} obchodech" if n in (2, 3, 4) else f"v {n} obchodech"


def age_label(m):
    if m is None:
        return ""
    if m < 12:
        return f"{m}+ m" if m else "0+"
    return f"{m // 12}+"


def age_text(m):
    if m is None:
        return ""
    if m < 12:
        return "od narození" if m == 0 else f"od {m} měsíců"
    y = m // 12
    return f"od {y} {plural(y, 'roku', 'let', 'let')}" if y > 1 else "od 1 roku"


def shorten(text, limit, keep_tail=""):
    """Search engines cut long titles/descriptions anyway; cut at a word boundary ourselves (keeping the brand tail of a title)."""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    tail = keep_tail if keep_tail and text.endswith(keep_tail) else ""
    room = limit - len(tail) - 1
    head = text[:len(text) - len(tail)][:room].rsplit(" ", 1)[0].rstrip(" ,;:-–—(")
    return head + "…" + tail


def img_url(u, size="card"):
    """Smaller renditions straight from the shops' own image CDNs (measured 10. 11. 2026: LEGO.com 548 -> 17 kB, Myshoptet orig 380 -> 29 kB,
    Sparkys 328 -> 101 kB, SEVT 77 -> 38 kB). No resizing on our side. size: "card" (~360 px wide) or "main" (product gallery, ~700 px)."""
    if not u:
        return u
    card = size == "card"
    if "bambule.cz/data/cache/thumb_" in u and card:
        return re.sub(r"thumb_\d+-\d+-\d+", "thumb_400-400-12", u)
    if "i.actva.cz" in u and card:
        return u.replace("/600x600/", "/300x300/")
    if "cdn.myshoptet.com" in u and "/user/shop/orig/" in u:
        return u.replace("/user/shop/orig/", "/user/shop/detail/" if card else "/user/shop/big/")
    if "www.lego.com/cdn/" in u and "format=" in u:
        return re.sub(r"&width=\d+", "", u) + ("&width=360" if card else "&width=720")
    if "cdn.sevt.cz" in u and "width=" in u:
        return re.sub(r"width=\d+", "width=360" if card else "width=600", u)
    if "sparkys.cz/data/cache/thumb_" in u and card:
        return re.sub(r"thumb_\d+-\d+-12-0", "thumb_300-300-12-0", u)
    return u


def pager_html(path, cur, pages):
    if pages <= 1:
        return ""
    url = lambda k: path if k == 1 else f"{path}strana-{k}/"
    show = sorted({1, pages, cur - 2, cur - 1, cur, cur + 1, cur + 2} & set(range(1, pages + 1)))
    out, last = [], 0
    for k in show:
        if k - last > 1:
            out.append('<span class="gap">…</span>')
        out.append(f'<a aria-current="page" class="on">{k}</a>' if k == cur else f'<a href="{url(k)}">{k}</a>')
        last = k
    prev = f'<a class="pp" href="{url(cur - 1)}" rel="prev" aria-label="Předchozí strana">‹</a>' if cur > 1 else ""
    nxt = f'<a class="pp" href="{url(cur + 1)}" rel="next" aria-label="Další strana">›</a>' if cur < pages else ""
    return f'<nav class="pager" aria-label="Stránkování">{prev}{"".join(out)}{nxt}</nav>'


def ld(x):
    return f'<script type="application/ld+json">{json.dumps(x, ensure_ascii=False, separators=(",", ":"))}</script>'


OPERATOR = {"name": "Ha Duy Huy", "address": "Bartáková 36, 140 00 Praha", "ico": "07876823", "ds": "dxmsrdt",
            "vat": "není plátce DPH", "email": "info@hrackarium.cz"}   # public business-register data (ARES), used as site operator on legal pages
LOGO = ('<img src="/img/ui/robot-96.webp" alt="" width="44" height="44"><span class="wm">Hračk<b>árium</b></span>')


class Site:
    def __init__(self, base, env, ga, css, js, shops, stats):
        self.base, self.env, self.ga, self.css, self.js = base, env, ga, css, js
        self.shops = shops
        self.stats = stats
        self.pg = None
        self.pending_ld = None

    def url(self, path):
        return self.base + path

    def layout(self, path, title, desc, body, crumbs=None, noindex=False, jsonld=None, preload_img=None, og_img=None, full=False):
        title, desc = shorten(title, 68, " | Hračkárium"), shorten(desc, 160)      # BEFORE the " – strana N" suffix, so paginated titles stay distinct
        robots = "noindex,follow" if (noindex or getattr(self, "pg_noindex", False) or self.env != "production") else "index,follow,max-image-preview:large"
        if self.pg and self.pg[1] > 1:
            n = self.pg[1]
            path = f"{self.pg[0]}strana-{n}/"
            title = re.sub(r"( \| Hračkárium)$", f" – strana {n}\\1", title)
            desc = f"Strana {n}: {desc}"
            jsonld = [x for x in (jsonld or []) if x and x.get("@type") != "FAQPage"]
            body = re.sub(r'<section class="faq">.*?</section>', "", body, flags=re.S)
            body = re.sub(r'<div class="prose">.*?</div><!--/prose-->', "", body, flags=re.S)
            body = re.sub(r"</h1>", f' <small class="pgn">strana {n}</small></h1>', body, count=1)
        lds = list(jsonld or [])
        if self.pending_ld:
            lds.append(self.pending_ld)
            self.pending_ld = None
        head_ld = "".join(ld(x) for x in lds if x)
        cr = ""
        if crumbs:
            head_ld += ld({"@context": "https://schema.org", "@type": "BreadcrumbList",
                           "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": n, "item": self.url(u)} for i, (n, u) in enumerate(crumbs)]})
            cr = '<nav class="crumbs" aria-label="Drobečková navigace">' + "<i>/</i>".join(
                f'<a href="{u}">{E(n)}</a>' if i < len(crumbs) - 1 else f"<span>{E(n)}</span>" for i, (n, u) in enumerate(crumbs)) + "</nav>"
        pre = f'<link rel="preload" as="image" href="{E(preload_img)}" fetchpriority="high">' if preload_img else ""
        ga = ""
        if self.ga and self.env == "production":
            # Consent Mode v2: Google Tag Manager is in the page source (so Google's tag check finds it) but every storage
            # type starts as denied; app.js switches analytics_storage to granted only after "Souhlasím" (remembered in localStorage).
            boot = ('window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}'
                    'var g="denied";try{if(localStorage.getItem("hrk-consent")==="yes")g="granted"}catch(e){}'
                    'gtag("consent","default",{analytics_storage:g,ad_storage:"denied",ad_user_data:"denied",ad_personalization:"denied",wait_for_update:500});'
                    'gtag("set","ads_data_redaction",true);')
            if self.ga.startswith("GTM-"):      # Tag Manager container
                lib = f'dataLayer.push({{"gtm.start":Date.now(),event:"gtm.js"}});</script><script async src="https://www.googletagmanager.com/gtm.js?id={self.ga}"></script>'
            else:                                # plain GA4 measurement id (G-...), configured here, no container needed
                lib = f'gtag("js",new Date());gtag("config","{self.ga}");</script><script async src="https://www.googletagmanager.com/gtag/js?id={self.ga}"></script>'
            ga = f'<meta name="ga4" content="{self.ga}"><script>{boot}{lib}'
        content = body if full else f'<div class="wrap page">{cr}{body}</div>'
        if full and crumbs:
            content = content.replace("<!--crumbs-->", cr, 1)
        ok = getattr(self, "nav_ok", None)
        nav = "".join(f'<li><a href="{u}"><img src="/img/ic/{i}.webp" alt="" width="40" height="40" loading="lazy">{n}</a></li>' for u, i, n in NAV if ok is None or u.strip("/") in ok)
        og = og_img or f"{self.base}/img/ui/og.png"
        n_shops = self.stats["shops"]
        return f"""<!doctype html><html lang="cs"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(title)}</title><meta name="description" content="{E(desc)}"><link rel="canonical" href="{self.url(path)}"><meta name="robots" content="{robots}">
<meta property="og:title" content="{E(title)}"><meta property="og:description" content="{E(desc)}"><meta property="og:url" content="{self.url(path)}"><meta property="og:type" content="website"><meta property="og:locale" content="cs_CZ"><meta property="og:site_name" content="Hračkárium"><meta property="og:image" content="{E(og)}"><meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#FF5A3C"><link rel="icon" href="/favicon.ico" sizes="48x48"><link rel="icon" href="/favicon-192.png" type="image/png" sizes="192x192"><link rel="apple-touch-icon" href="/favicon-180.png"><link rel="manifest" href="/site.webmanifest">
<link rel="preload" href="/fonts/bricolage-cs.woff2" as="font" type="font/woff2" crossorigin><link rel="preload" href="/fonts/figtree-cs.woff2" as="font" type="font/woff2" crossorigin><link rel="stylesheet" href="/assets/{self.css}">{pre}{SPECULATION}{ga}{head_ld}</head><body>
<a class="skip" href="#main">Přeskočit na obsah</a>
<div class="strip"><p>Ceny hraček {"z" if n_shops == 1 else "ze"} {n_shops} {plural(n_shops, "obchodu", "obchodů", "obchodů")} na jednom místě · ceny aktualizujeme každý den · nakupujete přímo v e‑shopu</p></div>
<header class="top"><div class="wrap"><a class="logo" href="/" aria-label="Hračkárium – úvod">{LOGO}</a>
<form class="search" role="search" action="/hledat/" method="get"><label class="sr" for="q">Hledat hračku, značku nebo LEGO set</label>{SEARCH_ICON}<input id="q" name="q" type="search" placeholder="Hledat hračku, značku nebo číslo LEGO setu" autocomplete="off"><button type="submit">Hledat</button><div class="sugg" id="sugg" role="listbox"></div></form>
<nav class="hl" aria-label="Rychlé odkazy"><a href="/darky/"><img src="/img/ic/party.webp" alt="" width="28" height="28">Dárky</a><a href="/slevy/"><img src="/img/ui/tag.svg" alt="" width="28" height="28">Slevy</a></nav></div></header>
<nav class="cn" aria-label="Kategorie"><ul>{nav}<li class="more"><a href="/kategorie/"><span class="dots">•••</span>Vše</a></li></ul></nav>
<main id="main">{content}</main>
<footer><div class="wrap cols"><div class="fabout"><a class="logo" href="/">{LOGO}</a><p>Srovnáváme ceny hraček v českých e‑shopech. Nic neprodáváme: koupíte přímo v obchodě a za stejnou cenu. Když nakoupíte přes náš odkaz, obchod nám může zaplatit malou provizi — z ní web žije.</p></div>
<div><h3>Kategorie</h3><ul><li><a href="/lego/">LEGO</a></li><li><a href="/stavebnice/">Stavebnice</a></li><li><a href="/spolecenske-hry/">Společenské hry</a></li><li><a href="/puzzle/">Puzzle</a></li><li><a href="/panenky/">Panenky</a></li><li><a href="/auta-a-vlacky/">Auta a vláčky</a></li><li><a href="/plysaci/">Plyšáci</a></li><li><a href="/kategorie/">Všechny kategorie</a></li></ul></div>
<div><h3>Dárky</h3><ul><li><a href="/darky/">Dárky podle věku</a></li><li><a href="/darek-pro-kluka/">Dárek pro kluka</a></li><li><a href="/darek-pro-holku/">Dárek pro holku</a></li><li><a href="/hracky-do-300-kc/">Hračky do 300 Kč</a></li><li><a href="/hracky-do-500-kc/">Hračky do 500 Kč</a></li><li><a href="/slevy/">Slevy na hračky</a></li>{"".join(f'<li><a href="{u}">{E(t)}</a></li>' for u, t in getattr(self, "footer_links", []))}</ul></div>
<div><h3>Hračkárium</h3><ul><li><a href="/jak-srovnavame/">Jak srovnáváme</a></li><li><a href="/kontakt/">Kontakt</a></li>{'<li><a href="/pruvodce/">Průvodce výběrem</a></li>' if getattr(self, "has_guides", False) else ""}<li><a href="/obchody/">Obchody</a></li><li><a href="/znacky/">Značky</a></li><li><a href="/postavicky/">Hračky podle postaviček</a></li><li><a href="/ochrana-osobnich-udaju/">Ochrana osobních údajů</a></li><li><a href="#" id="consent-open">Nastavení cookies</a></li></ul></div></div>
<div class="wrap fine"><p>Ceny a dostupnost se mohou v obchodě změnit; platí údaj v e‑shopu v okamžiku nákupu. Poslední aktualizace {self.stats["updated"]}.</p>
<p>Provozovatel: {OPERATOR["name"]}, {OPERATOR["address"]}, IČO {OPERATOR["ico"]}, {OPERATOR["vat"]}. <a href="/kontakt/">Kontakt</a> · <a href="mailto:{OPERATOR["email"]}">{OPERATOR["email"]}</a></p></div></footer>
<div class="consent" id="consent" role="dialog" aria-label="Cookies" hidden><p>Smíme měřit návštěvnost (Google Analytics)? Bez souhlasu nic neměříme.</p>
<div class="row"><button class="btn" data-consent="yes">Souhlasím</button><button class="btn btn--g" data-consent="no">Nesouhlasím</button><a href="/ochrana-osobnich-udaju/" class="lnk">Více</a></div></div>
<script src="/assets/{self.js}" defer></script></body></html>"""

    # ------------------------------------------------------------ pieces

    def shop(self, sid):
        return self.shops.get(sid, {"name": sid, "color": "#888"})

    def go_attrs(self, shop):
        return f'rel="sponsored nofollow noopener" target="_blank" data-go="{E(shop)}"'

    @staticmethod
    def discount(p):
        o = p["offers"][0]
        was = max(o.get("was") or 0, p.get("low30_prev") or 0)
        if o.get("was") and o["was"] > o["price"]:
            d = round((o["was"] - o["price"]) / o["was"] * 100)
            return d if d <= 80 else 0      # "−99 %" is a broken "was" price in the feed, not a real sale
        return 0

    def tag(self, price, prefix="", big=False):
        pre = f"<small>{prefix}</small>" if prefix else ""
        return f'<span class="ptag{" ptag--xl" if big else ""}"><i></i>{pre}{kc(price)}</span>'

    def card(self, p, lazy=True):
        n = len(p["offers"])
        href = f'/produkt/{p["slug"]}/'
        img = E(img_url(p["img"]) or "/img/ui/placeholder.svg")
        load = ' loading="lazy" decoding="async"' if lazy else ' fetchpriority="high"'
        age = f'<span class="sticker" title="Doporučený věk {age_text(p["age"])}">{age_label(p["age"])}</span>' if p.get("age") is not None else ""
        d = self.discount(p)
        sale = f'<span class="flag">−{d} %</span>' if d >= 10 else ""
        where = shops_in(n)
        alt_u = next((img_url(u) for u in p.get("imgs") or [] if u and u != p["img"]), "")
        alt = f' data-alt="{E(alt_u)}"' if alt_u and p["img"] else ""
        return (f'<li class="pc"><a class="pc__img" href="{href}" tabindex="-1" aria-hidden="true"><img src="{img}" alt=""{load}{alt} referrerpolicy="no-referrer" width="220" height="220">{sale}{age}</a>'
                f'<div class="pc__b">{f"<span class=pc__brand>{E(p["brand"])}</span>" if p["brand"] else ""}<h3><a href="{href}">{E(p["name"])}</a></h3>'
                f'<div class="pc__f">{self.tag(p["price"], "od" if n > 1 else "")}<span class="pc__n">{where}</span></div></div></li>')

    def item_json(self, p, bidx):
        """Compact row for client-side filtering: [name, slug, img, price, shops, brand#, age, sex, discount, shopmask]."""
        return [p["name"], p["slug"], img_url(p["img"]), p["price"], len(p["offers"]), bidx.get(p["brand"], -1),
                -1 if p["age"] is None else p["age"], p["sex"], self.discount(p), [o["shop"] for o in p["offers"]]]

    def grid(self, items, first_lazy=True):
        return '<ul class="grid">' + "".join(self.card(p, lazy=first_lazy or i > 3) for i, p in enumerate(items)) + "</ul>"

    def faq(self, qa):
        if not qa:
            return "", None
        h = '<section class="faq"><h2>Časté otázky</h2>' + "".join(f"<details><summary>{E(q)}</summary><div>{a}</div></details>" for q, a in qa) + "</section>"
        data = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": re.sub(r"<[^>]+>", "", a)}} for q, a in qa]}
        return h, data

    def chips(self, links, cls="chips"):
        return f'<ul class="{cls}">' + "".join(f'<li><a href="{u}">{E(t)}{f"<small>{n}</small>" if n else ""}</a></li>' for u, t, n in links) + "</ul>" if links else ""

    def listing(self, items, json_url, order="pop", facets=None):
        """Server-rendered page of the listing + filters that the script runs over the listing's JSON."""
        path, cur, pages = self.pg or ("", 1, 1)
        chunk = items[(cur - 1) * PER_PAGE:cur * PER_PAGE]
        self.pending_ld = {"@context": "https://schema.org", "@type": "ItemList", "numberOfItems": len(items),
                           "itemListElement": [{"@type": "ListItem", "position": i + 1, "url": self.url(f'/produkt/{p["slug"]}/'), "name": p["name"]}
                                               for i, p in enumerate(chunk[:24], (cur - 1) * PER_PAGE)]} if chunk else None
        filt = self.filters(items, facets or {})
        return (f'<div class="layout">{filt}<div class="results"><div class="listhead"><p><b id="count">{len(items)}</b> {plural(len(items), "hračka", "hračky", "hraček")}</p>'
                f'<button class="btn btn--g ftoggle" type="button" aria-controls="filters">Filtry</button>'
                f'<label class="sort">Řadit <select id="sort"><option value="pop">nejvíc obchodů</option><option value="price"{" selected" if order == "price" else ""}>nejlevnější</option>'
                f'<option value="pricedesc">nejdražší</option><option value="sale">největší sleva</option></select></label></div>'
                f'<ul class="grid" id="plist" data-json="{json_url}" data-page="{cur}" data-order="{order}">{"".join(self.card(p, lazy=i > 3) for i, p in enumerate(chunk))}</ul>'
                f'{pager_html(path, cur, pages) if path else ""}</div></div>')

    def filters(self, items, facets):
        h = '<form class="card filters" id="filters" aria-label="Filtry">'
        ages = facets.get("age")
        if ages:
            h += '<fieldset><legend>Věk dítěte</legend>' + "".join(
                f'<label><input type="checkbox" name="age" value="{lo}-{hi}"> {E(lbl)}<span class="count">{n}</span></label>' for lo, hi, lbl, n in ages) + "</fieldset>"
        h += ('<fieldset><legend>Cena</legend><div class="fprice"><input type="number" name="pmin" min="0" step="50" placeholder="od" aria-label="Cena od (Kč)">'
              '<span>–</span><input type="number" name="pmax" min="0" step="50" placeholder="do" aria-label="Cena do (Kč)"><span>Kč</span></div>'
              '<div class="fquick">' + "".join(f'<button type="button" data-pmax="{x}">do {x} Kč</button>' for x in (300, 500, 1000, 2000)) + "</div></fieldset>")
        brands = facets.get("brand")
        if brands:
            srch = '<input class="fsearch" type="search" placeholder="Hledat značku" aria-label="Hledat značku">' if len(brands) > 10 else ""
            h += (f'<fieldset><legend>Značka</legend>{srch}<div class="flinks">' + "".join(
                f'<label><input type="checkbox" name="brand" value="{i}"> {E(b)}<span class="count">{n}</span></label>' for i, b, n in brands) + "</div></fieldset>")
        shops = facets.get("shop")
        if shops and len(shops) > 1:
            h += '<fieldset><legend>Obchod</legend>' + "".join(
                f'<label><input type="checkbox" name="shop" value="{E(s)}"> {E(self.shop(s)["name"])}<span class="count">{n}</span></label>' for s, n in shops) + "</fieldset>"
        h += ('<fieldset><legend>Jen</legend><label><input type="checkbox" name="multi" value="1"> ve více obchodech</label>'
              '<label><input type="checkbox" name="sale" value="1"> ve slevě</label></fieldset>')
        return h + '<button class="btn btn--g freset" type="button" hidden>Zrušit filtry</button><div class="fbar"><button class="btn fclose" type="button">Zobrazit</button></div></form>'

    def band(self, h1, lead, icon=None, extra=""):
        art = f'<img class="band__ic" src="/img/ic/{icon}.webp" alt="" width="96" height="96">' if icon else ""
        return (f'<section class="band"><div class="wrap"><div class="band__t"><!--crumbs--><h1>{h1}</h1><p class="lead">{lead}</p>{extra}</div>{art}</div></section>')


def svg_history(hist, today):
    """Tiny step chart of our own price observations (no JS)."""
    if not hist or len(hist) < 2:
        return ""
    pts = hist + [[today, hist[-1][1]]]
    x0, x1 = pts[0][0], max(pts[-1][0], pts[0][0] + 1)
    ys = [p[1] for p in pts]
    lo, hi = min(ys), max(ys)
    if hi == lo:
        hi = lo + 1
    W, H = 320, 90
    X = lambda d: round((d - x0) / (x1 - x0) * (W - 10) + 5, 1)
    Y = lambda v: round(H - 12 - (v - lo) / (hi - lo) * (H - 30), 1)
    d = f"M{X(pts[0][0])},{Y(pts[0][1])}"
    for a, b in zip(pts, pts[1:]):
        d += f" H{X(b[0])} V{Y(b[1])}"
    return (f'<svg class="hist" viewBox="0 0 {W} {H}" role="img" aria-label="Vývoj nejnižší ceny: od {kc(lo)} do {kc(hi)}">'
            f'<path d="{d}" fill="none" stroke="#FF5A3C" stroke-width="3" stroke-linejoin="round"/>'
            f'<text x="5" y="{H - 1}" font-size="11">{kc(lo)}</text><text x="{W - 5}" y="12" font-size="11" text-anchor="end">{kc(hi)}</text></svg>')
