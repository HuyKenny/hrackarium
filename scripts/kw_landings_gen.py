#!/usr/bin/env python3
"""content/landings/kw2.json from the keyword backlog (scripts/kw_analyze.py) + the licence x category family.

    python3 scripts/kw_landings_gen.py [--min-volume 60] [--limit 700]

Each candidate carries inferred rules (word stems that must be in the product title/brand, age window, sex, category hint) and an `evidence`
field (monthly searches). The build (scripts/landings.py) decides what really exists: fewer than `min` products = no page, the same product set
as an existing page (dedupe_all) = no page, below `index_min` = noindex. So over-generating here is safe; thin pages cannot appear."""
import csv
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import taxonomy as X  # noqa: E402

APP = Path(__file__).resolve().parent.parent
MIN_VOL = int(sys.argv[sys.argv.index("--min-volume") + 1]) if "--min-volume" in sys.argv else 60
LIMIT = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 700


def fold(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c))


IGNORE = set("pro na do od a s se z ze v ve u k o po za je to jak co kde kdy kolik deti dite detsky detska detske detskych hracky hracka hracek nejlepsi levne levny cena cenik akce sleva "
             "vyprodej darek darky vanocni vanoce tipy napady rok roky roku let lete leta letou leteho letych mesicu mesice rocni miminko miminka miminek holky holka holcicky holcicka "
             "divky kluky kluka kluk chlapce chlapec nejprodavanejsi dospele pravidla navod recenze cz online eshop obchod koupit".split())
# words that mean the phrase is not about toys we sell (people, food, cosmetics, other shops/brands, adult)
NOISE = re.compile(r"(ford model|kosmetic|kosmetik|makova|salad|red ?bull|douglas|rituals|essence|sephora|lindt|kinder|mixit|balea|caj|cokolad|muze|muz |zeny|zena|erotick|sexual|tereza|petr |kostkova|tesla|portal|stavebnik|veprov|"
                   r"recept|marinad|pepr|v troube|woody|harrelson|lena |salish|mattes|requiem|bazen intex|intex|virivk|free spin|coin master|dlazebni|veprove|marcipan|3d tisk|3d print|3d model|"
                   r"papirove|bazar|museum|store|lego cz|model o|glorious|skoda|modely aut|modely letad|modelova zeleznice|pandora|miyuki|komponenty|f1 ?lego|lego f1|barad|minas|roklinka|dungeons|"
                   r"spike|world cup|kostky jsou|hrac(i)? kostk|dlazebn|tesla|ok hracky|wiki hracky|wiky|daruj|mcdonald|happy meal|bambule|mrakyhracek|pompo|4kids|dracik|maxikov)")
CATS = {  # stem -> (parent path, category prefix for the rule or None)
    "odrazedl": ("/venku/odrazedla/", None), "houpack": ("/venku/zahrada/", None), "skluzavk": ("/venku/zahrada/", None), "auticko": ("/auta-a-vlacky/auticka/", None),
    "autodrah": ("/auta-a-vlacky/autodrahy/", None), "bruder": ("/znacky/bruder/", None), "lego": ("/lego/", ["lego"]), "puzzle": ("/puzzle/", ["puzzle"]), "koralk": ("/kreativni/koralky-a-sperky/", None),
    "deskov": ("/spolecenske-hry/deskove/", None), "hraci dek": ("/pro-nejmensi/hraci-deky/", None), "plysak": ("/plysaci/", ["plysaci"]), "plys": ("/plysaci/", ["plysaci"]), "kostk": ("/stavebnice/kostky-a-kompatibilni/", None),
    "robot": ("/naucne/roboti-a-programovani/", None), "pokus": ("/naucne/experimenty/", None), "funko": ("/figurky-a-zviratka/sberatelske/", None), "pop figur": ("/figurky-a-zviratka/sberatelske/", None),
    "dinosaur": ("/figurky-a-zviratka/dinosauri/", None), "stavebnic": ("/stavebnice/", ["stavebnice"]), "panenk": ("/panenky/", ["panenky"]), "kuchy": ("/hrajeme-si-na/kuchynky/", None), "figurk": ("/figurky-a-zviratka/", None),
}


SKIP_SLUGS = {"kostky-pravidla", "ford-model-t", "box-na-hracky", "regal-na-hracky", "plysak", "plysaci", "hracky", "lego", "stavebnice", "panenky", "puzzle", "plysove-hracky"}   # too generic or duplicates of a category


def stems(text):
    out = []
    for w in re.findall(r"[a-z0-9]+", fold(text)):
        if w in IGNORE or len(w) < 2:
            continue
        out.append(w)
    return out


def rx(w):
    return r"\b" + (w[: max(4, len(w) - 2)] if len(w) > 4 else w) + r"\w*"


def age_window(key):
    m = re.search(r"\b(\d{1,2})\s?-?\s?(let|lete|leta|letou|leteho|letych|roku|roky|rok)\b", key)
    if m:
        n = int(m.group(1))
        return [n * 12 - 6, n * 12 + 5] if "rok" not in m.group(2) else [n * 12 - 3, n * 12 + 8]
    if re.search(r"\b(rocni|1 roc)", key):
        return [9, 18]
    if re.search(r"\bdvouleta?|dvouleteho", key):
        return [21, 29]
    if re.search(r"\bmiminko|miminka|miminek", key):
        return [0, 11]
    return None


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", fold(s)).strip("-")[:64].rstrip("-")


def main():
    rows = list(csv.DictReader(open(APP / "content/keywords/backlog.tsv"), delimiter="\t"))
    seen, recs = {}, []
    for r in rows:
        vol = int(r["volume"])
        if vol < MIN_VOL or r["intent"] in ("brand-nav", "question"):
            continue
        key = " ".join(re.findall(r"[a-z0-9]+", fold(r["phrase"])))
        if NOISE.search(key):
            continue
        sex = "m" if re.search(r"\b(kluk|kluci|kluky|kluka|chlap)", key) else "f" if re.search(r"\b(holk|holc|dev[ck]|divk|dcer)", key) else None
        age = age_window(key)
        core = [w for w in stems(key) if not re.fullmatch(r"\d+", w) and w not in ("rok", "let")]
        if not core and not (sex or age):
            continue
        if not core and not (sex and age):       # only gender or only age: existing hubs cover them
            continue
        sig = tuple(sorted({w[: max(4, len(w) - 2)] if len(w) > 4 else w for w in core})) + (sex or "", str(age))
        if sig in seen:
            seen[sig]["evidence"] += vol
            continue
        rules = {}
        if core:
            rules["all"] = [rx(w) for w in core]
        if sex:
            rules["sex"] = sex
        if age:
            rules["age"] = age
        parent, cat = "/kategorie/", None
        for stem, (p, c) in CATS.items():
            if stem in key:
                parent, cat = p, c
                break
        if cat:
            rules["cat"] = cat
        h1 = r["phrase"][:1].upper() + r["phrase"][1:]
        if slugify(r["phrase"]) in SKIP_SLUGS:
            continue
        rec = {"slug": slugify(r["phrase"]), "h1": h1, "parent": parent, "hubs": [parent], "group": "kw2", "dedupe_all": True, "rules": rules, "min": 8, "index_min": 15,
               "evidence": vol, "intent": r["intent"], "title": f"{h1} – srovnání cen"}
        seen[sig] = rec
        recs.append(rec)
        if len(recs) >= LIMIT:
            break
    # family: licence x top category (popular licences only; the build keeps the combinations that have products)
    uni = list(csv.DictReader(open(APP / "content/keywords/universe.tsv"), delimiter="\t"))
    pop = {}
    for u in uni:
        k = fold(u["phrase"])
        for s, n, _ in X.LICENCES:
            if fold(n) in k:
                pop[s] = pop.get(s, 0) + int(u["volume"])
    top_lic = [s for s, _ in sorted(pop.items(), key=lambda kv: -kv[1])[:28]]
    names = {s: n for s, n, _ in X.LICENCES}
    tops = [t for t in X.TOP if t not in ("lego", "fan-darky", "kostymy-a-party", "elektronika", "hudebni")]
    fam = 0
    for s in top_lic:
        for t in tops:
            recs.append({"slug": f"hracky-{s}/{t}", "h1": f"{names[s]}: {X.TREE[t][2].lower()}", "parent": f"/hracky-{s}/", "hubs": [], "group": "lic-cat", "dedupe_all": True,
                         "rules": {"lic": s, "cat": [t]}, "min": 8, "index_min": 12, "evidence": pop[s], "intent": "licence x category",
                         "title": f"{names[s]} {X.TREE[t][0].lower()} – srovnání cen"})
            fam += 1
    (APP / "content/landings/kw2.json").write_text(json.dumps(recs, ensure_ascii=False, indent=1) + "\n")
    print(f"{len(recs) - fam} phrase pages + {fam} licence x category candidates -> content/landings/kw2.json (top licences: {', '.join(names[s] for s in top_lic[:8])} ...)")


if __name__ == "__main__":
    main()
