#!/usr/bin/env python3
"""Builds content/keywords/seeds.txt (one seed per line, optional TAB + questions|new|trending) for scripts/kw_collect.py.
Seeds come from what the site already knows (consumer words for the categories, live brand list, licences, LEGO series) crossed with
the modifiers people really type (age, gender, occasion, "nejlepší", "jak vybrat", materials). Order = priority, so a quota-limited run still
collects the most valuable seeds first. Brand counts: live /znacky/ page saved to /tmp/brands.tsv (slug TAB name TAB products)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import taxonomy as X  # noqa: E402

APP = Path(__file__).resolve().parent.parent
seeds = []


def add(s, typ=""):
    s = s.strip()
    if s and (s, typ) not in seeds:
        seeds.append((s, typ))


CORE = ["hračky", "hračky pro děti", "hračky pro holky", "hračky pro kluky", "lego", "stavebnice", "panenky", "autíčka", "auta na dálkové ovládání", "autodráha", "vláčkodráha",
        "plyšák", "puzzle", "deskové hry", "společenské hry", "karetní hry", "odrážedlo", "kočárek pro panenky", "domeček pro panenky", "dětská kuchyňka", "doktorský kufřík",
        "dětské nářadí", "kostky", "magnetická stavebnice", "dřevěné hračky", "hračky do vany", "hračky na písek", "hračky na zahradu", "dětský bazén", "skluzavka", "houpačka",
        "hudební nástroje pro děti", "kreativní sady", "modelína", "korálky", "vědecké sady", "pokusy pro děti", "robot pro děti", "interaktivní hračky", "hračky pro miminka",
        "chrastítko", "hrací deka", "tahací hračky", "figurky", "dinosauři hračky", "zvířátka figurky", "sběratelské karty", "pokémon karty", "funko pop", "dětské kostýmy",
        "party doplňky", "adventní kalendář", "adventní kalendář pro děti", "adventní kalendář lego", "adventní kalendář pro holky", "adventní kalendář pro kluky"]
for c in CORE:
    add(c)
BASE = ["lego", "stavebnice", "panenky", "autíčka", "puzzle", "deskové hry", "plyšáci", "odrážedlo", "autodráha", "vláčkodráha", "dětská kuchyňka", "kočárek pro panenky",
        "magnetická stavebnice", "RC auto", "hračky do vany", "dřevěné hračky", "kreativní sady", "figurky", "karetní hry", "společenské hry", "hračky pro miminka", "interaktivní hračky",
        "vědecké hračky", "hračky na zahradu", "dětské nářadí"]
for b in BASE:
    add(f"nejlepší {b}")
    add(f"jak vybrat {b}", "questions")
    add(f"{b} pro holky")
    add(f"{b} pro kluky")
    add(f"{b} od kolika let", "questions")
for n in range(1, 13):
    kluk = {1: "roční dítě", 2: "dvouleté dítě"}.get(n)
    add(f"hračky pro {n}letého kluka" if n > 2 else f"hračky pro {kluk}")
    add(f"hračky pro {n}letou holku" if n > 2 else f"hračky pro {kluk}")
    add(f"dárek pro {n}letého kluka")
    add(f"dárek pro {n}letou holku")
    add(f"hračky pro děti od {n} let")
for n in range(1, 11):
    add(f"co koupit dítěti k {n}. narozeninám", "questions")
    add(f"dárek k {n}. narozeninám dítěte")
OCC = ["dárek pro dítě", "vánoční dárky pro děti", "co dát dítěti k vánocům", "dárek na mikuláše pro děti", "mikulášská nadílka", "velikonoční dárky pro děti", "dárek ke dni dětí",
       "dárek k narozeninám pro dítě", "dárek pro dítě do 500 kč", "dárek pro dítě do 300 kč", "dárek pro dítě do 1000 kč", "hračky black friday", "hračky vánoce", "dárek pro sourozence",
       "dárek pro vnoučata", "dárek pro kmotřence", "dárek do školky", "dárek pro prvňáčka", "dárek k zápisu do školy", "dárek na rozloučení se školkou", "dárek k narození miminka",
       "hračky na cesty", "hračky do auta", "hračky do letadla", "hračky do kočárku", "hračky na dovolenou", "hračky do deště", "hračky na ven", "hračky na pláž", "hračky na sníh"]
for o in OCC:
    add(o)
MAT = ["dřevěné puzzle", "dřevěná kuchyňka", "dřevěné kostky", "dřevěný vláček", "plyšové hračky", "magnetické kostky", "svítící hračky", "hračky na baterie", "hračky se zvukem",
       "antistresové hračky", "montessori hračky", "vzdělávací hračky", "naučné hračky", "hračky pro rozvoj řeči", "motorické hračky", "senzorické hračky", "hračky pro děti s adhd",
       "hračky pro autistické děti", "ekologické hračky", "recyklované hračky", "hračky z gumy", "velké hračky", "malé hračky", "retro hračky", "hračky pro dvojčata"]
for m in MAT:
    add(m)
brands = []
bt = Path("/tmp/brands.tsv")
if bt.exists():
    for line in bt.read_text().splitlines():
        slug, name, n = line.split("\t")
        brands.append((int(n), name))
brands.sort(reverse=True)
skip = {"mamido", "ostatní", "bez značky"}
top = [n for c, n in brands if n.lower() not in skip][:90]
for b in top:
    add(b)
for b in top[:30]:
    add(f"{b} hračky")
for s, n, _ in X.LICENCES:
    add(f"{n} hračky")
for s, n, _ in X.LEGO_SERIES:
    add(n if n.lower().startswith("lego") else f"lego {n}")
out = APP / "content/keywords/seeds.txt"
out.write_text("\n".join(f"{s}\t{t}" if t else s for s, t in seeds) + "\n")
print(len(seeds), "seeds ->", out)
