#!/usr/bin/env python3
"""Deploy dist/ as Workers static assets — no Worker script anywhere, so no request is ever billed.

    python3 scripts/deploy.py staging       # one Worker "hrackarium-staging" on workers.dev (noindex build, must fit one Worker)
    python3 scripts/deploy.py production    # main Worker on hrackarium.cz/* (+ www) and, if needed, shard Workers

A Worker version holds at most 100 000 files. When dist/ is bigger, product pages /produkt/<x>… are moved into shard
Workers by the first character of the slug; each shard gets the route hrackarium.cz/produkt/<x>* (more specific routes
win over hrackarium.cz/*). Every shard is assets-only too.
Needs CLOUDFLARE_API_TOKEN + CLOUDFLARE_ACCOUNT_ID in the environment (GitHub secrets). Prints no secrets.
"""
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
DIST = APP / "dist"
LIMIT = 95_000
WRANGLER = "wrangler@4.151.3"
ZONE = "hrackarium.cz"


def count(d):
    return sum(1 for p in d.rglob("*") if p.is_file())


def wrangler(cfg, name):
    path = APP / f".wrangler-{name}.json"
    path.write_text(json.dumps(cfg, indent=1))
    r = subprocess.run(["npx", "--yes", WRANGLER, "deploy", "--config", str(path)], cwd=APP)
    path.unlink(missing_ok=True)
    if r.returncode:
        sys.exit(f"deploy of {name} failed")


def base_cfg(name, directory):
    return {"name": name, "compatibility_date": "2026-10-01", "preview_urls": False, "observability": {"enabled": False},
            "assets": {"directory": str(directory), "html_handling": "auto-trailing-slash", "not_found_handling": "404-page"}}


def plan_shards(slugs_by_char, room):
    """Greedy: consecutive first characters into shards of <= LIMIT files each."""
    shards, cur, n = [], [], 0
    for ch in sorted(slugs_by_char):
        c = slugs_by_char[ch]
        if cur and n + c > LIMIT - 200:
            shards.append(cur)
            cur, n = [], 0
        cur.append(ch)
        n += c
    if cur:
        shards.append(cur)
    return shards


def main():
    env = sys.argv[1] if len(sys.argv) > 1 else "staging"
    total = count(DIST)
    print(f"dist: {total} files")
    if env == "staging":
        if total > LIMIT:
            sys.exit(f"staging must fit one Worker ({total} > {LIMIT}); build with HRK_MAX_PRODUCTS")
        cfg = base_cfg("hrackarium-staging", DIST)
        cfg["workers_dev"] = True
        wrangler(cfg, "hrackarium-staging")
        return
    shard_dirs = []
    if total > LIMIT:
        prod = DIST / "produkt"
        by_char = Counter(p.name[0] for p in prod.iterdir() if p.is_dir())
        need = total - LIMIT + 2000
        moved, shards = 0, plan_shards(by_char, need)
        for i, chars in enumerate(shards):
            d = APP / f"dist-s{i:02d}"
            shutil.rmtree(d, ignore_errors=True)
            (d / "produkt").mkdir(parents=True)
            for ch in chars:
                for p in list(prod.glob(f"{ch}*")):
                    shutil.move(str(p), d / "produkt" / p.name)
            shutil.copy(DIST / "404.html", d / "404.html")
            shutil.copy(DIST / "_headers", d / "_headers")
            shard_dirs.append((f"hrackarium-s{i:02d}", d, chars))
            moved += count(d)
            if count(DIST) <= LIMIT:
                break
        print(f"sharded: {len(shard_dirs)} shard Workers, main keeps {count(DIST)} files")
    for name, d, chars in shard_dirs:
        if count(d) > LIMIT:
            sys.exit(f"shard {name} too big")
        cfg = base_cfg(name, d)
        cfg["workers_dev"] = False
        cfg["routes"] = [{"pattern": f"{ZONE}/produkt/{c}*", "zone_name": ZONE} for c in chars]
        wrangler(cfg, name)
    cfg = base_cfg("hrackarium", DIST)
    cfg["workers_dev"] = False
    cfg["routes"] = [{"pattern": f"{ZONE}/*", "zone_name": ZONE}, {"pattern": f"www.{ZONE}/*", "zone_name": ZONE}]
    wrangler(cfg, "hrackarium")


if __name__ == "__main__":
    main()
