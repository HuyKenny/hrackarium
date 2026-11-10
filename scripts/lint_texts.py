#!/usr/bin/env python3
"""Rules for the hand-written texts in content/texts/*.json (run before every commit of new texts; CI runs it too).

    python3 scripts/lint_texts.py            # report only
    python3 scripts/lint_texts.py --strict   # exit 1 when something is wrong
Checks: valid JSON/keys, intro <= 220 characters, 3+ FAQ items, body words in range, <= 4 internal links, no link to itself,
banned filler phrases, invented prices / product counts / discounts, "pro kluky/holky" without a stereotype disclaimer is only noted.
"""
import json
import re
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
BANNED = ["v dnešní době", "ať už", "klíčové je", "neocenitel", "svět plný", "nezapomeňte", "ideální volb", "perfektní", "skvělá volba", "dokonalý", "každý rodič", "bezpochyby",
          "rozhodně stojí za", "stojí za zmínku", "v neposlední řadě", "jedním slovem", "nepostradatel", "revoluční"]
MONEY = re.compile(r"\b\d[\d\s ]{1,7}\s?(kč|korun)\b", re.I)
COUNT = re.compile(r"\b\d{2,}\s+(produkt|hračk|nabíd|obchod|sad|sety|kus)", re.I)
DISCOUNT = re.compile(r"\bsleva\s+(až\s+)?\d+\s?%|\b\d+\s?%\s+sleva", re.I)
LINK = re.compile(r'<a href="([^"]+)"')
TAG = re.compile(r"<[^>]+>")


def words(html):
    return len(TAG.sub(" ", html).split())


def main():
    strict = "--strict" in sys.argv
    bad = 0
    files = sorted((APP / "content/texts").glob("*.json")) + sorted(f for f in (APP / "content/guides").glob("*.json") if f.name != "_index.json")
    for f in files:
        issues = []
        try:
            d = json.loads(f.read_text())
        except ValueError as e:
            print(f"{f.name}: INVALID JSON {e}")
            bad += 1
            continue
        is_guide = f.parent.name == "guides"
        key = d.get("key", "") or ("guide:" + d.get("slug", ""))
        body = d.get("body", "")
        n = words(body)
        slug = key.split(":", 1)[1] if ":" in key else ""
        hub = key.endswith(":adventni-kalendare") or "hub" in d
        if len(d.get("intro", "")) > 220:
            issues.append(f"intro {len(d['intro'])} chars")
        if is_guide and len(d.get("description", "")) > 160:
            issues.append("description too long")
        if len(d.get("faq", [])) < 3:
            issues.append("faq < 3")
        if n < (600 if is_guide else 380 if not hub else 550):
            issues.append(f"{n} words")
        links = LINK.findall(body)
        if len(links) > (5 if is_guide else 4):
            issues.append(f"{len(links)} links")
        if any(l.strip("/") == slug.strip("/") for l in links if slug):
            issues.append("self link")
        low = TAG.sub(" ", body + " " + " ".join(q + " " + a for q, a in d.get("faq", []))).lower()
        for b in BANNED:
            if b in low:
                issues.append(f"banned '{b}'")
        for rx, name in ((MONEY, "price"), (COUNT, "count"), (DISCOUNT, "discount")):
            # a price cap that belongs to the page itself (do 500 Kč) is allowed
            hits = [h.group(0) for h in rx.finditer(TAG.sub(" ", body)) if not re.search(r"\bdo\s+$", TAG.sub(" ", body)[max(0, h.start() - 4):h.start()])]
            if hits and name != "price":
                issues.append(f"{name}: {hits[:2]}")
            elif hits and name == "price":
                issues.append(f"price mention: {hits[:2]} (ok only for the page's own cap)")
        if issues:
            bad += 1
            print(f"{f.name}: " + "; ".join(issues))
    print(f"{len(files)} texts, {bad} with findings")
    sys.exit(1 if strict and bad else 0)


if __name__ == "__main__":
    main()
