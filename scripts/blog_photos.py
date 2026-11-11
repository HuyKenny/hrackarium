#!/usr/bin/env python3
"""Download the blog feature photos listed in content/guides/photos.json (Pexels CDN, no key needed) as 640/1200 px JPEGs into
static/img/blog/. Runs in CI before the build; files already present are kept. Photos are free to use (Pexels licence)."""
import json
import sys
import time
import urllib.request
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
OUT = APP / "static/img/blog"
SIZES = {"640": 640, "1200": 1200}


def get(url):
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "HrackariumBuild/1.0"}), timeout=60) as r:
                b = r.read()
            if len(b) > 3000:
                return b
        except Exception as e:
            err = type(e).__name__
        time.sleep(2 * (i + 1))
    raise RuntimeError(err)


def main():
    photos = json.loads((APP / "content/guides/photos.json").read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    bad = 0
    for slug, v in photos.items():
        for tag, w in SIZES.items():
            f = OUT / f"{slug}-{tag}.jpg"
            if f.exists():
                continue
            try:
                f.write_bytes(get(f'{v["src"]}?auto=compress&cs=tinysrgb&fit=crop&w={w}&h={round(w * 0.625)}'))
            except Exception as e:
                bad += 1
                print(f"photo {slug} {tag}: {e}")
    print(f"blog photos: {len(photos)} articles, {bad} failed")
    sys.exit(1 if bad > len(photos) // 4 else 0)


if __name__ == "__main__":
    main()
