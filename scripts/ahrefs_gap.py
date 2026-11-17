#!/usr/bin/env python3
"""Content gap from Ahrefs exports (reports/hrackarium/ahrefs-2026-11/kw-<domain>.json, top-<domain>.json) vs our live pages.

    python3 scripts/ahrefs_gap.py /tmp/hrk-paths.txt [dir]

Merges the competitors' top-10 keywords (diacritics folded), drops competitor brand navigation and noise, maps each phrase to one of our live paths by
word stems (>= 5 chars) and prints the uncovered phrases ranked by how many competitors rank and their summed traffic. Ahrefs CZ volumes are
unreliable: only the ORDER of traffic and the number of competitors are used."""
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

D = Path(sys.argv[2] if len(sys.argv) > 2 else "/home/kenny/ai/reports/hrackarium/ahrefs-2026-11")
fold = lambda s: "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c))
BRAND = re.compile(r"\b(bambule|dracik|pompo|4kids|ministerstvo|mrakyhracek|maxikov|heureka|smyk|alza|mall|toys|kidsworld|hamleys|lamps|wiky|albi|ok hracky|hracky ok|hracky pompo|datart)\b")
NOISE = re.compile(r"\b(recept|vepr|film|pdf|hra online|zdarma|kosmetick|tereza|petr|tesla|erotick|sex|douglas|redbull|red bull|rituals|essence|kinder|mixit|lindt|balea)\b")
rows = defaultdict(lambda: {"doms": {}, "traffic": 0, "urls": set(), "phrase": ""})
for f in D.glob("kw-*.json"):
    dom = f.stem[3:]
    for k in json.loads(f.read_text()).get("keywords", []):
        key = " ".join(re.findall(r"[a-z0-9]+", fold(k["keyword"])))
        if not key or BRAND.search(key) or NOISE.search(key):
            continue
        r = rows[key]
        r["phrase"] = r["phrase"] or k["keyword"]
        r["doms"][dom] = k["best_position"]
        r["traffic"] += k.get("sum_traffic") or 0
        r["urls"].add(re.sub(r"https?://(www\.)?", "", k["best_position_url"])[:80])
stem = lambda w: w[: max(5, len(w) - 2)] if len(w) > 5 else w
paths = [p.strip() for p in Path(sys.argv[1]).read_text().split() if p.strip()]
pstems = [(p, {stem(w) for w in re.findall(r"[a-z0-9]+", fold(p))}) for p in paths]
unc = []
for key, r in rows.items():
    st = {stem(w) for w in key.split() if len(w) > 2}
    hit = next((p for p, ps in pstems if st and st <= ps), None)
    r["page"] = hit
    if not hit:
        unc.append((len(r["doms"]), r["traffic"], key, r))
unc.sort(key=lambda x: (-x[0], -x[1]))
print(f"{len(rows)} competitor top-10 phrases; covered by a live page: {sum(1 for r in rows.values() if r['page'])}; uncovered: {len(unc)}")
for n, t, key, r in unc[:120]:
    print(f"{n} dom {t:6d}  {r['phrase']:40} {sorted(r['urls'])[0]}")
