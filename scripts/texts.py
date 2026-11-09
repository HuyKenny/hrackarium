"""Category texts: hand-written ones from content/texts.json win; otherwise a short, honest text built from the data
(price range, brands, shops, age) — nothing invented, every number comes from the current catalogue."""
import json
import statistics
from collections import Counter
from pathlib import Path

import render as R
import taxonomy as X

APP = Path(__file__).resolve().parent.parent
_T = None


def _load():
    global _T
    if _T is None:
        p = APP / "content/texts.json"
        _T = json.loads(p.read_text()) if p.exists() else {}
    return _T


def get(key):
    return _load().get(key)


def generated(key, items, h1, S):
    if not items:
        return "", []
    E = R.E
    ps = sorted(p["price"] for p in items)
    lo, med, hi = ps[0], int(statistics.median(ps)), ps[-1]
    n = len(items)
    brands = [b for b, _ in Counter(p["brand"] for p in items if p["brand"]).most_common(6)]
    shops = Counter(o["shop"] for p in items for o in p["offers"])
    multi = [p for p in items if len(p["offers"]) > 1]
    cheap = sum(1 for p in items if p["price"] <= 500)
    ages = [p["age"] for p in items if p["age"] is not None]
    noun = h1[:1].lower() + h1[1:] if not h1.isupper() and not h1.startswith(("LEGO", "Hračky ")) else h1
    q = []
    q.append((f"Kolik stojí {noun}?",
              f"Teď je skladem {n} {R.plural(n, 'položka', 'položky', 'položek')} od {R.kc(lo)} do {R.kc(hi)}. Polovina stojí méně než {R.kc(med)}"
              + (f" a {cheap} {R.plural(cheap, 'kus', 'kusy', 'kusů')} seženete do 500 Kč." if cheap else ".")))
    if len(brands) >= 2:
        q.append((f"Které značky jsou nejčastější?", "Nejvíc nabídek mají " + ", ".join(E(b) for b in brands[:5]) + "."))
    if shops:
        top = shops.most_common(3)
        q.append(("Ve kterých obchodech je nejvíc nabídek?",
                  ", ".join(f"{E(S.shop(s)['name'])} ({c})" for s, c in top) + f". Celkem srovnáváme {len(shops)} {R.plural(len(shops), 'obchod', 'obchody', 'obchodů')}."))
    if multi:
        save = [p["offers"][-1]["price"] - p["price"] for p in multi]
        best = max(save)
        q.append(("Vyplatí se ceny porovnávat?",
                  f"U {len(multi)} {R.plural(len(multi), 'hračky', 'hraček', 'hraček')} z této stránky máme víc obchodů najednou. Rozdíl mezi nejlevnějším a nejdražším obchodem je u nich v průměru "
                  f"{R.kc(sum(save) / len(save))}, nejvíc {R.kc(best)}."))
    if ages and len(ages) >= n * 0.3:
        c = Counter(min(a // 12, 12) for a in ages).most_common(1)[0][0]
        q.append(("Pro jak staré děti se hodí?",
                  f"Nejčastěji uváděný doporučený věk je od {c} {R.plural(c, 'roku', 'let', 'let') if c != 1 else 'roku'}. Věk každé hračky vidíte na samolepce u obrázku; "
                  "u dětí do 3 let vždy zkontrolujte upozornění na malé díly."))
    prose = (f"<h2>{E(h1)}: přehled nabídky</h2><p>Na této stránce je {n} {R.plural(n, 'hračka', 'hračky', 'hraček')} skladem v českých e‑shopech, "
             f"ceny od {R.kc(lo)} do {R.kc(hi)}. Řadíme je podle toho, v kolika obchodech je najdete — u takových hraček má srovnání největší smysl. "
             "Filtry vlevo zúží výběr podle věku dítěte, ceny, značky nebo obchodu.</p>")
    return prose, q
