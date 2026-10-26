"""Shared helpers: the クママップ（過去） of Gifu Prefecture (open data catalogue) and how to read its files."""

import csv
import io
import zipfile

CKAN = "https://gifu-opendata.pref.gifu.lg.jp"
PACKAGE = "c11265-010"
PACKAGE_URL = f"{CKAN}/dataset/{PACKAGE}"
API_PACKAGE = f"{CKAN}/api/3/action/package_show?id={PACKAGE}"
LICENSE_ID = "cc-by-21-jp"
# the file name in the catalogue -> (table, fiscal year as a calendar year, Japanese year label)
FILES = {
    "h26kumashutsubotsu.zip": ("h26", 2014, "H26"), "h27kumashutsubotsu.zip": ("h27", 2015, "H27"),
    "h28kumashutsubotsu.zip": ("h28", 2016, "H28"), "h29kumashutsubotsu.zip": ("h29", 2017, "H29"),
    "h30kumashutsubotsu.zip": ("h30", 2018, "H30"), "reiwa1.csv": ("r1", 2019, "R1"),
    "reiwa2.zip": ("r2", 2020, "R2"), "reiwa3.zip": ("r3", 2021, "R3"), "reiwa4.zip": ("r4", 2022, "R4"),
    "kumamapreiwa5.zip": ("r5", 2023, "R5"), "kumamapreiwa6.zip": ("r6", 2024, "R6"),
    "reiwa7.zip": ("r7", 2025, "R7"),
}  # fmt: skip
ENCODING = "cp932"
N03_URL = "https://nlftp.mlit.go.jp/ksj/gml/data/N03/N03-2026/N03-20260101_21_GML.zip"
N03_PAGE_URL = "https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N03-2026.html"
# R2 to R7 have no .prj and hold plane rectangular coordinates in metres. They are read as JGD2011 /
# Japan Plane Rectangular CS VII (Gifu lies wholly in zone VII; JGD2000, EPSG:2449, gives the same
# municipalities): 03_verify.py checks that the points fall in the municipality each record names.
PLANE_EPSG = 6675
PLANE_TABLES = ("r2", "r3", "r4", "r5", "r6", "r7")
MUNICIPALITY_FIELD = {
    "r2": "出没市町村",
    "r3": "市町村名",
    "r4": "市町村名",
    "r5": "市町村名",
    "r6": "市町村名",
    "r7": "市町村名",
}
BBOX = (136.1, 35.0, 137.9, 36.6)  # lon min, lat min, lon max, lat max: Gifu with a margin
# columns that hold the name of the municipal staff member who entered a record: in the raw files, not in the Parquet
STAFF_COLUMNS = ("入力者氏名", "入力者担当")
R1_LON, R1_LAT = "JGD2011_10進_X", "JGD2011_10進_Y"


def csv_layer(data: bytes):
    """reiwa1.csv: (field names, records as lists of strings, points from the JGD2011 X/Y columns)."""
    rows = list(csv.reader(io.StringIO(data.decode(ENCODING), newline="")))
    head, body = rows[0], rows[1:]
    if len(set(head)) != len(head):
        raise ValueError("duplicate column names")
    i, j = head.index(R1_LON), head.index(R1_LAT)
    if any(len(r) != len(head) for r in body):
        raise ValueError("ragged row")
    return head, body, [(float(r[i]), float(r[j])) for r in body]


def zip_layer(data: bytes):
    """A zip with one point Shapefile: (field names, records as lists of strings or ints, points)."""
    import shapefile

    z = zipfile.ZipFile(io.BytesIO(data))
    names = {n.lower(): n for n in z.namelist() if not n.endswith("/")}
    shp = [n for n in names if n.endswith(".shp")]
    if len(shp) != 1:
        raise ValueError(f"expected one .shp, found {shp}")
    base = shp[0][:-4]
    sf = shapefile.Reader(
        shp=io.BytesIO(z.read(names[base + ".shp"])), shx=io.BytesIO(z.read(names[base + ".shx"])),
        dbf=io.BytesIO(z.read(names[base + ".dbf"])), encoding=ENCODING)  # fmt: skip
    if sf.shapeTypeName != "POINT":
        raise ValueError(sf.shapeTypeName)
    head = [f[0] for f in sf.fields[1:]]
    if len(set(head)) != len(head):
        raise ValueError("duplicate field names")
    body, pts = [], []
    for sr in sf.iterShapeRecords():
        body.append(list(sr.record))
        pts.append(tuple(sr.shape.points[0]))
    return head, body, pts


def to_lonlat(table: str, pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """The points as (longitude, latitude): as they are, or from plane rectangular x (east), y (north)."""
    if table not in PLANE_TABLES:
        return pts
    from pyproj import Transformer

    t = Transformer.from_crs(PLANE_EPSG, 6668)  # (northing, easting) -> (latitude, longitude)
    out = []
    for x, y in pts:
        lat, lon = t.transform(y, x)
        out.append((lon, lat))
    return out


def layer(name: str, data: bytes):
    """(field names, records, source points, points as (lon, lat)), every point inside Gifu's box."""
    table = FILES[name][0]
    head, body, pts = csv_layer(data) if name.endswith(".csv") else zip_layer(data)
    ll = to_lonlat(table, pts)
    for i, (x, y) in enumerate(ll):
        if not (BBOX[0] <= x <= BBOX[2] and BBOX[1] <= y <= BBOX[3]):
            raise ValueError(f"{name} row {i}: point outside Gifu ({y}, {x})")
    return head, body, pts, ll
