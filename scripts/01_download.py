"""Download the クママップ（過去） of Gifu Prefecture (H26 to R7) from the prefecture's open data catalogue.

Saves the catalogue's metadata (package_show) and the twelve files (eleven zips with a point
Shapefile each, and one CSV) as served, with sha256 and the Last-Modified, in
data/raw/<version>/MANIFEST.json; and the municipalities of Gifu (N03), used only to check the
coordinates, under data/docs/ (not published). Stops when the catalogue does not say cc-by-21-jp or
lists other files than the scripts know. The version is the UTC date of the run.

    uv run python scripts/01_download.py [--version 2026-10-26]
"""

import argparse
import datetime as dt
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

import gifu as k

ROOT = Path(__file__).parents[1]
UA = "gifu-bear-sighting/0.1 (+https://github.com/yuiseki/gifu-bear-sighting)"


def get(url: str) -> tuple[bytes, dict]:
    with urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": UA}), timeout=120
    ) as r:
        return r.read(), {h.lower(): v for h, v in r.headers.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default=dt.datetime.now(dt.UTC).strftime("%Y-%m-%d"))
    args = ap.parse_args()
    raw = ROOT / "data" / "raw" / args.version
    docs = ROOT / "data" / "docs"
    raw.mkdir(parents=True, exist_ok=True)
    docs.mkdir(parents=True, exist_ok=True)
    body, _ = get(k.API_PACKAGE)
    pkg = json.loads(body)["result"]
    if pkg["license_id"] != k.LICENSE_ID:
        raise SystemExit(f"license_id is {pkg['license_id']!r}, not {k.LICENSE_ID}: stopping")
    (raw / "package.json").write_bytes(body)
    names = {r["url"].rsplit("/", 1)[1] for r in pkg["resources"]}
    if names != set(k.FILES):
        raise SystemExit(f"the files of the entry changed: {sorted(names ^ set(k.FILES))}")
    files = {
        "package.json": {
            "url": k.API_PACKAGE,
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
        }
    }
    for r in pkg["resources"]:
        name = r["url"].rsplit("/", 1)[1]
        time.sleep(1)
        data, h = get(r["url"])
        (raw / name).write_bytes(data)
        files[name] = {"url": r["url"], "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                       "last_modified": h.get("last-modified"), "resource_name": r["name"],
                       "resource_last_modified": r["last_modified"]}  # fmt: skip
        print(name, len(data))
    time.sleep(1)
    n03, _ = get(k.N03_URL)
    (docs / Path(k.N03_URL).name).write_bytes(n03)
    manifest = {
        "retrieved": args.version, "page": k.PACKAGE_URL, "title": pkg["title"],
        "license_id": pkg["license_id"], "metadata_modified": pkg["metadata_modified"],
        "notes": pkg["notes"], "author": pkg["author"], "files": files,
        "n03": {"url": k.N03_URL, "sha256": hashlib.sha256(n03).hexdigest()},
    }  # fmt: skip
    (raw / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
