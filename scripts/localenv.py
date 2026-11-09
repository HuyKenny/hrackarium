"""Local development only: load API keys from the workspace credentials/ folder into os.environ.
In GitHub Actions the same names come from repository secrets. Values are never printed.
This file holds no secrets itself — only file and key NAMES."""
import os
from pathlib import Path

CRED = Path(os.environ.get("HRK_CRED_DIR", "/home/kenny/ai/credentials"))
MAP = {
    ".hrackarium-credentials.env": None,  # everything
}


def load():
    feeds = CRED / ".hrackarium-feeds.json"          # {"<feed_key>": "<url>"} — same content as the FEEDS_JSON secret
    if feeds.exists():
        os.environ.setdefault("FEEDS_JSON", feeds.read_text())
    for name, keys in MAP.items():
        p = CRED / name
        if not p.exists():
            continue
        for line in p.read_text().splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                if keys is None or k in keys:
                    os.environ.setdefault(k, v.strip().strip("\"'"))
