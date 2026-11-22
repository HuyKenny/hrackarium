#!/usr/bin/env python3
"""Appends rules for old hrackarium.cz URLs (Wayback CDX, top-level product slugs) to data/redirects.txt: slug words -> taxonomy.classify -> live category.

    python3 scripts/redirect_map.py old-urls.txt live-paths.txt
old-urls.txt: one old path per line (scripts/hrackarium/old-urls in ai-workspace uses the same CDX query as vian); live-paths.txt: paths of the
live listing sitemap. Existing rules and live pages are kept; paths that do not classify get no rule (404 + client-side nearest page)."""
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import taxonomy as X  # noqa: E402

APP = Path(__file__).resolve().parent.parent
SKIP = re.compile(r"^/(wp-|feed|xmlrpc|sitemap|robots|admin|cart|kosik|login|tag/|author/|page/|search|\?)|\.(jpe?g|png|gif|webp|svg|pdf|css|js|xml|txt)$", re.I)
SPAM = re.compile(r"casino|kasino|poker|slot|sazk|viagra|cialis|pharma|porn|xxx|sex|erotic|escort|loan|pujck|kratom|cbd|hazard|bonus|crypto", re.I)

old = [l.strip() for l in open(sys.argv[1]) if l.strip()]
live = {l.strip() for l in open(sys.argv[2]) if l.strip()}
file = APP / "data/redirects.txt"
have = {l.split()[0].rstrip("/") for l in file.read_text().splitlines() if l.strip() and not l.startswith("#")}
new = []
for p in old:
    p = p.split("?")[0].rstrip("/")
    segs = [s for s in p.split("/") if s]
    if not segs or p in have or p + "/" in live or SKIP.search(p) or SPAM.search(p) or re.fullmatch(r"\d+", segs[-1]):
        continue
    text = " ".join(segs[-1].split("-"))
    cat = X.classify({"t": text})
    to = f"/{cat}/" if cat else None
    if to and to in live:
        new.append(f"{p}/ {to} 301")
print(len(old), "old,", len(new), "new rules")
if "--write" in sys.argv:
    with open(file, "a") as f:
        f.write("# Wayback product slugs -> classified category (scripts/redirect_map.py)\n" + "\n".join(new) + "\n")
else:
    for r in new[:15]:
        print(r)
