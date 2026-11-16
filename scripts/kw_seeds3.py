#!/usr/bin/env python3
"""Seeds of the 3rd wave (16. 11. 2026) -> content/keywords/seeds3.txt; scripts/kw_collect.py skips every seed that is already cached.
Focus: leaf category x property/material, LEGO motifs and sets, seasonal (advent, Christmas, Mikuláš), storage hubs, trending/new on the biggest categories."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import taxonomy as X  # noqa: E402

APP = Path(__file__).resolve().parent.parent
seeds = []


def add(s, typ=""):
    s = s.strip().lower()
    if s and (s, typ) not in seeds:
        seeds.append((s, typ))


LEAF = {"autodráhy": ["dřevěná", "na baterie", "pro nejmenší"], "puzzle": ["dřevěné", "magnetické", "podlahové", "3d", "pro nejmenší"], "stavebnice": ["magnetické", "dřevěné", "kovové", "pro nejmenší"],
        "panenky": ["interaktivní", "pro nejmenší", "v šatičkách", "s doplňky"], "plyšáci": ["velcí", "svítící", "interaktivní", "mluvící", "pro miminka"], "autíčka": ["dřevěná", "kovová", "na baterie", "na dálkové ovládání", "velká"],
        "vláčkodráhy": ["dřevěné", "elektrické", "na baterie"], "kuchyňky": ["dřevěné", "elektronické", "velké", "s příslušenstvím"], "odrážedla": ["dřevěná", "pro roční", "skládací", "s brzdou"],
        "hračky do vody": ["pro miminka", "do vany"], "hudební nástroje": ["dětské", "dřevěné", "pro miminka"], "deskové hry": ["pro 2 hráče", "kooperativní", "pro nejmenší", "cestovní", "rodinné"],
        "kreativní sady": ["pro holky", "pro kluky", "výtvarné"], "vědecké sady": ["chemické", "pro kluky", "pro holky"], "roboti": ["programovatelní", "na dálkové ovládání", "interaktivní"],
        "figurky zvířátka": ["dinosauři", "domácí", "z lesa"], "hračky pro miminka": ["dřevěné", "senzorické", "do postýlky"]}
for noun, mods in LEAF.items():
    for m in mods:
        add(f"{m} {noun}" if not m.startswith(("pro ", "na ", "s ", "v ", "do ")) else f"{noun} {m}")
for name in [n for _, (n, par, *_r) in X.TREE.items() if par]:
    add(f"{name.lower()} levně")
    add(f"nejlepší {name.lower()}")
for n in ("lego pán prstenů", "lego dungeons and dragons", "lego ninjago", "lego speed champions", "lego technic auta", "lego city policie", "lego city hasiči", "lego friends", "lego star wars sety", "lego harry potter hrad",
          "lego minecraft", "lego jurassic world", "lego marvel", "lego disney", "lego creator 3v1", "lego classic kostky", "lego architecture", "lego ideas", "lego icons", "lego botanical", "lego modular",
          "lego kolejiště", "lego vlak", "lego ledové království", "lego sonic", "lego mario", "lego pokémon", "lego dots", "lego art", "lego duplo zvířátka", "lego duplo vláček", "lego bricks", "lego sety do 500 kč", "lego sety do 1000 kč",
          "levné lego", "lego výprodej", "lego akce", "lego pro dospělé", "lego pro holky", "lego pro kluky 8 let"):
    add(n)
for s in ("adventní kalendář lego city", "adventní kalendář lego friends", "adventní kalendář playmobil", "adventní kalendář barbie", "adventní kalendář hot wheels", "adventní kalendář paw patrol", "adventní kalendář pokémon",
          "adventní kalendář pro miminka", "adventní kalendář plyšový", "adventní kalendář s hračkami", "adventní kalendář pro kluky", "adventní kalendář pro holky", "adventní kalendář dřevěný", "adventní kalendář kreativní",
          "vánoční dárek pro 3letého", "vánoční dárek pro 5letého", "vánoční dárek pro 8letého", "vánoční dárek pro 10letého", "vánoční dárek pro 12letého", "vánoční dárek pro miminko", "vánoční dárek pro batole",
          "mikulášská nadílka pro děti", "balíček na mikuláše hračky", "hračky pod stromeček", "dárkové sady hračky", "nejlepší hračky vánoce 2026", "hit vánoce hračky 2026", "top hračky 2026"):
    add(s)
for s in ("box na hračky", "bedna na hračky", "regál na hračky", "organizér na hračky", "úložný box lego", "stůl na lego", "podložka na lego", "pytel na hračky", "koš na hračky", "police na hračky"):
    add(s)
for s in ("hračky", "dětské hračky", "dřevěné hračky", "plyšové hračky", "stavebnice", "puzzle", "panenky", "autíčka", "deskové hry", "lego"):
    add(s, "trending")
    add(s, "new")
for s in ("hračky pro 1 rok", "hračky pro 2 roky", "hračky pro 3 roky", "hračky pro 4 roky", "hračky pro 5 let", "hračky pro 6 let", "hračky pro 7 let", "hračky pro 8 let", "hračky pro 9 let", "hračky pro 10 let", "hračky pro 12 let",
          "hračky pro teenagery", "dárek pro 13letého", "hračky pro dívky 10 let", "hračky pro chlapce 10 let"):
    add(s)
out = APP / "content/keywords/seeds3.txt"
out.write_text("".join(f"{s}\t{t}\n" if t else f"{s}\n" for s, t in seeds))
print(len(seeds), "seeds ->", out)
