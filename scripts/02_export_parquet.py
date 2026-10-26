"""Write one GeoParquet per file of the クママップ（過去） of Gifu Prefecture (H26 to R7).

The twelve files have different columns (a field name of a Shapefile is cut at ten characters, and the
fields change from year to year), so each is its own table, named h26 to h30 and r1 to r7. Every
column of the source is kept under its own name, as the source has it: text as text (empty is null,
digits stay full-width where the source has them), numbers as integers. Added: `row` (the position in
the file), `geometry` (WKB Point, longitude and latitude; see the card for the datum) and, for R2 to R7,
`source_x`, `source_y` (the plane rectangular coordinates of the Shapefile, metres).

    uv run python scripts/02_export_parquet.py [--version 2026-10-26]
"""

import argparse
import json
import sys
from pathlib import Path

import gifu as k
import pyarrow as pa
import pyarrow.parquet as pq
from shapely.geometry import Point

ROOT = Path(__file__).parents[1]


def column(values: list) -> pa.Array:
    vals = [v if v != "" else None for v in values]
    if all(v is None for v in vals):
        return pa.array(vals, type=pa.string())
    return pa.array(vals)


def table_of(name: str, data: bytes) -> pa.Table:
    head, body, pts, ll = k.layer(name, data)
    table = k.FILES[name][0]
    cols = {"row": pa.array(range(1, len(body) + 1), type=pa.int32())}
    for j, h in enumerate(head):
        cols[h] = column([r[j] for r in body])
    if table in k.PLANE_TABLES:
        cols["source_x"] = pa.array([p[0] for p in pts], type=pa.float64())
        cols["source_y"] = pa.array([p[1] for p in pts], type=pa.float64())
    cols["geometry"] = pa.array([Point(x, y).wkb for x, y in ll], type=pa.binary())
    geo = {"version": "1.1.0", "primary_column": "geometry",
           "columns": {"geometry": {"encoding": "WKB", "geometry_types": ["Point"]}}}  # fmt: skip
    return pa.table(cols).replace_schema_metadata({b"geo": json.dumps(geo).encode()})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default=None)
    args = ap.parse_args()
    runs = sorted((ROOT / "data" / "raw").glob("*/MANIFEST.json"))
    raw = runs[-1].parent if args.version is None else ROOT / "data" / "raw" / args.version
    out = ROOT / "data" / "parquet"
    out.mkdir(parents=True, exist_ok=True)
    counts, columns = {}, {}
    for name, (table, _, _) in k.FILES.items():
        t = table_of(name, (raw / name).read_bytes())
        pq.write_table(t, out / f"{table}.parquet", compression="zstd")
        counts[table] = t.num_rows
        columns[table] = [
            f for f in t.schema.names if f not in ("row", "geometry", "source_x", "source_y")
        ]
        print(table, t.num_rows)
    (out / "columns.json").write_text(
        json.dumps({"run": raw.name, "counts": counts, "source_columns": columns,
                    "files": {t: n for n, (t, _, _) in k.FILES.items()}}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
