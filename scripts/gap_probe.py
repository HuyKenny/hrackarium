#!/usr/bin/env python3
"""How many catalogue products does each wanted phrase match? (CI audit step; the catalogue is not available locally.)

    python3 scripts/gap_probe.py phrases.tsv [out.tsv]
phrases.tsv: phrase<TAB>volume. A product matches when every stem (first 5+ chars of each word, diacritics folded) occurs in its title.
Output per phrase: matching titles, how many are classified (and into which top categories) and how many are NOT (taxonomy gap)."""
import gzip
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalog as C  # noqa: E402
import taxonomy as X  # noqa: E402

fold = lambda s: "".join(c for c in unicodedata.normalize("NFKD", (s or "").lower()) if not unicodedata.combining(c))
STOP = {"pro", "deti", "detske", "detska", "detsky", "detskych", "na", "do", "od", "let", "roku", "hracky"}
shops = [s for s in json.load(open(C.APP / "data/shops.json"))["shops"] if s.get("enabled", True)]
rows = []
for s in shops:
    p = C.WEEKLY / f"{s['id']}.jsonl.gz"
    if not p.exists():
        p = C.RAW / f"{s['id']}.jsonl.gz"
    if not p.exists():
        continue
    with gzip.open(p, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            rows.append((fold(X.clean(r.get("t"))), r))
print(len(rows), "raw offers", file=sys.stderr)
out = []
for l in open(sys.argv[1], encoding="utf-8"):
    if "\t" not in l:
        continue
    ph, vol = l.rstrip("\n").split("\t")[:2]
    st = [w[:max(5, len(w) - 2)] for w in re.findall(r"[a-z0-9]+", fold(ph)) if w not in STOP and len(w) >= 3]
    hit = [r for t, r in rows if st and all(x in t for x in st)]
    cats, uncl, ex = Counter(), 0, []
    for r in hit:
        c = X.classify(r)
        if c:
            cats[c.split("/")[0]] += 1
        else:
            uncl += 1
            if len(ex) < 2:
                ex.append(X.clean(r.get("t"))[:50])
    out.append(f"{ph}\t{vol}\t{len(hit)}\t{sum(cats.values())}\t{uncl}\t{dict(cats.most_common(3))}\t{' | '.join(ex)}")
text = "phrase\tvolume\tmatch\tclassified\tunclassified\ttop cats\tunclassified examples\n" + "\n".join(out) + "\n"
(Path(sys.argv[2]).write_text(text) if len(sys.argv) > 2 else print(text))
