#!/usr/bin/env python3
"""One-off helper: pick a Pexels feature photo for every guide and write content/guides/photos.json.
The API key is read from the environment (PEXELS_API_KEY) or, locally, from ~/ai/credentials; only the public photo ids go into the repo.
CI downloads the files with scripts/blog_photos.py (no key needed)."""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
OUT = APP / "content/guides/photos.json"
Q = {
    "black-friday-hracky-jak-poznat-slevu": "shopping sale discount gifts", "co-koupit-diteti-k-1-narozeninam": "baby first birthday toys",
    "co-koupit-diteti-k-3-narozeninam": "toddler birthday gift toys", "co-koupit-diteti-k-5-narozeninam": "child birthday present",
    "darek-pro-dite-6-let-tipy": "child opening gift", "darek-pro-holku-10-let-tipy": "girl playing creative toys", "darek-pro-kluka-10-let-tipy": "boy building toys",
    "darek-pro-kluka-12-let-tipy": "teenage boy playing game", "drevene-hracky-nebo-plastove": "wooden toys", "hracky-do-vany-bezpecnost-a-cisteni": "bath toys rubber duck",
    "hracky-na-cesty-s-detmi": "child travelling car toys", "hracky-na-rozvoj-reci": "parent child reading talking", "hracky-podle-vyvoje-ditete-1-3-roky": "toddler playing blocks",
    "hracky-podle-vyvoje-ditete-3-6-let": "preschool child playing", "hracky-pro-dvoulete-deti-co-vybrat": "two year old playing toys",
    "hracky-pro-holky-a-kluky-bez-stereotypu": "children playing together toys", "hracky-pro-miminka-podle-mesicu": "baby rattle toy", "hracky-pro-sourozence-co-koupit": "siblings playing together",
    "hracky-pro-tri-lete-dite-co-koupit": "three year old child playing", "jak-chranit-sberatelske-karty": "trading cards collection", "jak-naplanovat-vanocni-darky-pro-deti": "christmas presents children",
    "jak-organizovat-detsky-pokoj-a-hracky": "kids room toys storage", "jak-porovnat-ceny-hracek": "price comparison shopping toys", "jak-poskladat-puzzle-tipy": "jigsaw puzzle",
    "jak-poznat-bezpecnou-hracku-ce-znaceni": "safe toys children", "jak-poznat-originalni-lego-a-padelky": "lego bricks", "jak-poznat-padelek-pokemon-karet": "pokemon cards",
    "jak-skladovat-a-trizdit-lego": "lego bricks sorting", "jak-vybrat-adventni-kalendar-pro-dite": "advent calendar", "jak-vybrat-autodrahu": "toy race track cars",
    "jak-vybrat-deskovou-hru-pro-deti": "board game family", "jak-vybrat-detskou-kuchynku": "toy kitchen child cooking", "jak-vybrat-hracku-podle-povahy-ditete": "child playing curious",
    "jak-vybrat-hracky-na-zahradu-a-ven": "children playing garden outdoors", "jak-vybrat-interaktivni-hracky": "robot toy child", "jak-vybrat-kostym-na-karneval": "kids costume carnival",
    "jak-vybrat-lego-podle-veku": "child building lego", "jak-vybrat-odrazedlo": "balance bike child", "jak-vybrat-panenku-pro-holcicku": "girl doll playing", "jak-vybrat-plysaka-a-jak-ho-prat": "teddy bear plush",
    "jak-vybrat-puzzle-podle-veku": "child puzzle pieces", "jak-vybrat-rc-auto-pro-dite": "remote control car", "jak-vybrat-stavebnici-pro-deti": "building blocks child", "jak-vybrat-vlackodrahu": "toy train wooden railway",
    "jak-zacit-hrat-magic-the-gathering": "fantasy trading card game cards", "jak-zacit-sbirat-pokemon-karty": "pokemon cards collecting", "lego-nebo-kompatibilni-stavebnice": "colorful building bricks",
    "lego-pro-dospele-jak-zacit": "man building lego set at table", "lego-technic-nebo-lego-city-rozdily": "lego technic", "lego-vs-playmobil-rozdily": "toy figures playmobil", "levne-hracky-jak-neplytvat": "piggy bank coins toys",
    "magneticke-stavebnice-jak-vybrat": "magnetic building tiles", "male-dily-a-hracky-pro-deti-do-3-let": "toddler small toys safe", "montessori-hracky-podle-veku": "montessori wooden toys",
    "nejlepsi-deskove-hry-pro-dva": "two people playing board game", "rodinne-deskovky-jak-vybrat": "family playing board game",
}


def key():
    k = os.environ.get("PEXELS_API_KEY")
    if k:
        return k
    for f in Path("/home/kenny/ai/credentials").glob(".*-credentials.env"):
        for line in f.read_text().splitlines():
            if line.startswith("PEXELS_API_KEY="):
                return line.split("=", 1)[1].strip().strip("\"'")
    sys.exit("no PEXELS_API_KEY")


def main():
    k = key()
    have = json.loads(OUT.read_text()) if OUT.exists() else {}
    used = {v["id"] for v in have.values()}
    for slug, q in Q.items():
        if slug in have:
            continue
        url = "https://api.pexels.com/v1/search?" + urllib.parse.urlencode({"query": q, "orientation": "landscape", "per_page": 15, "size": "medium", "locale": "en-US"})
        req = urllib.request.Request(url, headers={"Authorization": k, "User-Agent": "MalinaCron/1.0"})
        res = json.load(urllib.request.urlopen(req, timeout=30))
        for ph in res.get("photos", []):
            if ph["id"] in used or ph["width"] < 1600:
                continue
            have[slug] = {"id": ph["id"], "by": ph["photographer"], "page": ph["url"], "src": ph["src"]["original"], "alt": (ph.get("alt") or q)[:140], "q": q}
            used.add(ph["id"])
            break
        else:
            print("no photo for", slug)
        time.sleep(0.6)
    OUT.write_text(json.dumps(have, ensure_ascii=False, indent=1))
    print(len(have), "photos")


if __name__ == "__main__":
    main()
