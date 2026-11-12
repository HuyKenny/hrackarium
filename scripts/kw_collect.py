#!/usr/bin/env python3
"""Batch keyword collection from Marketing Miner (keyword_suggestions) with a resumable cache.

    python3 scripts/kw_collect.py test                 # 3 seeds, shows the data shape
    python3 scripts/kw_collect.py run seeds.txt        # one seed per line; "seed<TAB>questions|new|trending" = suggestion type
    python3 scripts/kw_collect.py status

Every (seed, type) result is written to content/keywords/cache/<slug>.json BEFORE the next call, so an interrupted or quota-limited run
resumes without repeating calls. One call = one item of the MM daily quota; the run stops cleanly when the quota is exhausted (HTTP 429/403 or
an error text mentioning limit/quota). Uses the OAuth client of bin/mm.py (credentials/.marketingminer-credentials.env)."""
import importlib.util
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
CACHE = APP / "content/keywords/cache"
spec = importlib.util.spec_from_file_location("mm", "/home/kenny/ai/bin/mm.py")
mm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mm)


def slug(seed, typ):
    s = unicodedata.normalize("NFKD", seed.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-") + (f"--{typ}" if typ else "")


def call(sess, seed, typ):
    args = {"keyword": seed, "lang": "cs", "limit": 100, "with_keyword_data": True}
    if typ:
        args["suggestions_type"] = typ
    for attempt in range(4):
        try:
            res = mm.rpc(sess[0], sess[1], "tools/call", {"name": "keyword_suggestions", "arguments": args}, timeout=120)
            content = res.get("structuredContent")
            if content is None:
                content = json.loads(res["content"][0]["text"])
            return content
        except SystemExit as e:           # mm.rpc exits with the JSON-RPC error text
            msg = str(e).lower()
            if any(w in msg for w in ("quota", "limit", "exceed")):
                raise RuntimeError("quota: " + str(e)[:200])
            time.sleep(5 * (attempt + 1))
        except Exception as e:
            time.sleep(5 * (attempt + 1))
            err = e
    raise RuntimeError(f"failed after retries: {seed}")


def run(seeds, pause=1.2):
    CACHE.mkdir(parents=True, exist_ok=True)
    sess = mm.session()
    done = 0
    for seed, typ in seeds:
        f = CACHE / (slug(seed, typ) + ".json")
        if f.exists():
            continue
        try:
            data = call(sess, seed, typ)
        except RuntimeError as e:
            print("STOP:", e)
            break
        f.write_text(json.dumps({"seed": seed, "type": typ, "data": data}, ensure_ascii=False))
        n = len(((data or {}).get("data") or data or {}).get("suggestions", [])) if isinstance(data, dict) else 0
        done += 1
        print(f"{done:4d} {seed} [{typ or 'all'}] ok")
        time.sleep(pause)
    print("calls this run:", done, "| cached total:", len(list(CACHE.glob('*.json'))))


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "status":
        print(len(list(CACHE.glob("*.json"))), "cached seeds")
    elif cmd == "test":
        run([("hračky", ""), ("adventní kalendář pro děti", ""), ("lego city", "questions")])
        for f in sorted(CACHE.glob("*.json"))[:3]:
            d = json.loads(f.read_text())
            body = d["data"]
            print(f.name, type(body).__name__, list(body)[:6] if isinstance(body, dict) else "")
            print(json.dumps(body, ensure_ascii=False)[:700])
    elif cmd == "run":
        seeds = []
        for line in Path(sys.argv[2]).read_text().splitlines():
            if line.strip() and not line.startswith("#"):
                p = line.split("\t")
                seeds.append((p[0].strip(), p[1].strip() if len(p) > 1 else ""))
        run(seeds)


if __name__ == "__main__":
    main()
