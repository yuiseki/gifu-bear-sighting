"""Check every Parquet against its file as served, with a second reader of Shapefiles and CSVs.

The export reads the zips with pyshp. Here the .dbf (cp932) and the .shp are parsed by hand from their
byte layout (the header, the field descriptors, the records; a point record is its type and two
doubles), and the CSV of R1 is read with pyarrow as strings. For every row of every file: each
column equals the source's (empty is null, a number is the integer of its digits), `row` is the
position, the plane coordinates equal the .shp's, and the point equals the coordinates (R1: the
JGD2011 X and Y columns; H26 to H30: the .shp; R2 to R7: the .shp projected from JGD2011 / plane
rectangular CS VII). Also: no record is marked deleted; the sha256 of each file equals the
manifest's; and for R2 to R7 at least 99% of the points fall in the municipality that the record names
(the municipalities of N03, 2026-01-01), which is the check behind reading these files as zone VII.

    uv run python scripts/03_verify.py
"""

import csv
import hashlib
import io
import json
import struct
import sys
import zipfile
from pathlib import Path

import gifu as k
import pyarrow.parquet as pq
import shapefile
from pyproj import Transformer
from shapely import from_wkb
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

ROOT = Path(__file__).parents[1]


def read_dbf(b: bytes):
    """(field names, field types, records as lists of str/int/None) of a dBASE III file."""
    n, hlen, rlen = struct.unpack("<IHH", b[4:12])
    fields, pos = [], 32
    while b[pos] != 0x0D:
        raw = b[pos : pos + 32]
        fields.append((raw[:11].split(b"\0")[0].decode(k.ENCODING), chr(raw[11]), raw[16]))
        pos += 32
    recs = []
    for i in range(n):
        rec = b[hlen + i * rlen : hlen + (i + 1) * rlen]
        assert rec[:1] == b" ", f"record {i} is marked deleted"
        off, row = 1, []
        for _, typ, ln in fields:
            v = rec[off : off + ln]
            off += ln
            s = v.decode(k.ENCODING).rstrip(" \0")
            row.append((int(s) if s.strip() else None) if typ == "N" else (s or None))
        recs.append(row)
    return [f[0] for f in fields], recs


def read_points(b: bytes):
    pts, pos = [], 100
    while pos < len(b):
        _, words = struct.unpack(">ii", b[pos : pos + 8])
        typ = struct.unpack("<i", b[pos + 8 : pos + 12])[0]
        assert typ == 1, f"shape type {typ}"
        pts.append(struct.unpack("<2d", b[pos + 12 : pos + 28]))
        pos += 8 + words * 2
    return pts


def main() -> int:
    run = sorted((ROOT / "data" / "raw").glob("*/MANIFEST.json"))[-1].parent
    manifest = json.loads((run / "MANIFEST.json").read_text())
    cols = json.loads((ROOT / "data/parquet/columns.json").read_text())
    plane = Transformer.from_crs(k.PLANE_EPSG, 6668)
    with zipfile.ZipFile(ROOT / "data" / "docs" / Path(k.N03_URL).name) as z:
        stem = next(n[:-4] for n in z.namelist() if n.endswith(".shp"))
        sf = shapefile.Reader(shp=io.BytesIO(z.read(stem + ".shp")), shx=io.BytesIO(z.read(stem + ".shx")),
                              dbf=io.BytesIO(z.read(stem + ".dbf")), encoding="utf-8")  # fmt: skip
    polys = [
        (sr.record.as_dict()["N03_004"], shape(sr.shape.__geo_interface__))
        for sr in sf.iterShapeRecords()
    ]
    tree = STRtree([p for _, p in polys])
    total = 0
    plane_ok = plane_n = 0
    for name, (table, _, _) in k.FILES.items():
        path = run / name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest["files"][name]["sha256"], (
            name
        )
        d = pq.read_table(ROOT / "data" / "parquet" / f"{table}.parquet").to_pydict()
        if name.endswith(".csv"):
            rows = list(csv.reader(io.StringIO(path.read_bytes().decode(k.ENCODING), newline="")))
            head, recs = rows[0], [[(c or None) for c in r] for r in rows[1:]]
            li, la = head.index(k.R1_LON), head.index(k.R1_LAT)
            lonlat = [(float(r[li]), float(r[la])) for r in recs]
            plane_xy = None
        else:
            z = zipfile.ZipFile(path)
            nm = {n.lower(): n for n in z.namelist()}
            base = next(n for n in nm if n.endswith(".shp"))[:-4]
            head, recs = read_dbf(z.read(nm[base + ".dbf"]))
            plane_xy = read_points(z.read(nm[base + ".shp"]))
            assert len(plane_xy) == len(recs)
            if table in k.PLANE_TABLES:
                lonlat = [(plane.transform(y, x)[1], plane.transform(y, x)[0]) for x, y in plane_xy]
            else:
                lonlat = plane_xy
        n = len(recs)
        assert len(d["row"]) == n == cols["counts"][table], (table, n)
        assert d["row"] == list(range(1, n + 1))
        kept = [h for h in head if h not in k.STAFF_COLUMNS]
        assert cols["source_columns"][table] == kept, table
        assert cols["dropped_columns"][table] == [h for h in head if h in k.STAFF_COLUMNS], table
        assert not set(d) & set(k.STAFF_COLUMNS), table
        for j, h in enumerate(head):
            if h in k.STAFF_COLUMNS:
                continue
            want = [r[j] for r in recs]
            assert d[h] == want, (table, h)
        for i in range(n):
            g = from_wkb(d["geometry"][i])
            assert (g.x, g.y) == lonlat[i], (table, i)
            if plane_xy is not None and table in k.PLANE_TABLES:
                assert (d["source_x"][i], d["source_y"][i]) == plane_xy[i], (table, i)
        msg = f"{table}: {n} rows equal the source"
        if table in k.PLANE_TABLES:
            fld = d[k.MUNICIPALITY_FIELD[table]]
            ok = 0
            for i in range(n):
                p = Point(*lonlat[i])
                hit = [polys[t][0] for t in tree.query(p) if polys[t][1].contains(p)]
                name_ = (fld[i] or "").lstrip("0123456789")
                ok += bool(hit) and (hit[0] == name_ or name_ in hit[0] or hit[0] in name_)
            assert ok / n >= 0.99, (
                f"{table}: only {ok} of {n} points are in the municipality they name"
            )
            msg += f"; {ok} of {n} points are in the municipality the record names"
            plane_ok += ok
            plane_n += n
        print(msg, flush=True)
        total += n
    (ROOT / "data" / "docs" / "plane_check.json").write_text(
        json.dumps({"ok": plane_ok, "n": plane_n}) + "\n"
    )
    print(f"OK: {total} rows in {len(k.FILES)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
