"""Write data/README.md (the dataset card), data/LICENSE and data/provenance.yaml.

uv run python scripts/04_card.py
"""

import json
import sys
from pathlib import Path

import gifu as k

ROOT = Path(__file__).parents[1]
REPO = "gifu-bear-sighting"

CARD = """---
license: cc-by-4.0
license_name: cc-by-4.0
license_link: https://creativecommons.org/licenses/by/4.0/legalcode.ja
language:
- ja
tags:
- japan
- gifu
- bear
- wildlife
- geospatial
size_categories:
- 1K<n<10K
pretty_name: Bear sightings of Gifu Prefecture (クママップ過去分, H26 to R7)
---

# {repo}

The bear (ツキノワグマ) sighting records of Gifu Prefecture, FY2014 to FY2025 (平成26年度 to 令和7年度), as
the prefecture's environment and living policy division published them in its open data catalogue under
the title クママップ（過去）: {total:,} records in twelve tables, one per fiscal year, each with the
columns of its source file. As GeoParquet. The catalogue says that the latest information is on the
prefecture's integrated GIS (県域統合型GISぎふ, 岐阜県クママップ); that is not in this dataset.

## Source

- Catalogue entry: <{page}> (岐阜県オープンデータカタログ, {author}), titled 「{title}」, licence
  `{license_id}` (Creative Commons Attribution 2.1 Japan), metadata last modified {meta_modified}.
- Files: the twelve files of the entry as served (eleven zips, each with one point Shapefile, and one
  CSV, the R1 file), kept unchanged under `raw/{run}/` with their sha256 in `MANIFEST.json`, with the
  catalogue's `package.json`. Fetched {fetched}.

## Files

| Table | Fiscal year | Source file | Rows |
|---|---|---|---|
{table_rows}

`parquet/<table>.parquet`; `parquet/columns.json` lists the source columns of each table. The source
files are in `raw/{run}/`.

## Columns

The twelve files do not share their columns: the names of the Shapefile fields are cut at ten
characters by the format (for example `出没時間（`, `出没市町2`), and the fields change from year to year
(R1 to R7 have, among others, the month, the day, the time, the municipality, the former municipality,
the kind of place, the number of animals, the reporter, the cause predicted, the details, the mesh
number of the prefecture's grid). Every table keeps all columns of its file under the name the
source gives, as written: text as text (empty is null; digits and letters stay full-width where the
source has them, e.g. `１１月`, `Ｃ-137`), numbers as integers. Added to every table: `row` (the position
in the file) and `geometry` (the point as WKB, longitude and latitude). R2 to R7 also have `source_x`,
`source_y`, the coordinates of the Shapefile.

The year is not in the records: month and day are, and the year is the fiscal year of the file (a
fiscal year runs from April to March).

## Coordinates

| Files | Source coordinates | Written as |
|---|---|---|
| H26 to H30 | longitude and latitude in the Shapefile, `.prj` WGS 84 | as they are, WGS84 assumed |
| R1 | the CSV's columns `JGD2011_10進_X` (longitude) and `JGD2011_10進_Y` (latitude) | as they are (JGD2011, which agrees with WGS84 to about a metre) |
| R2 to R7 | plane rectangular coordinates in metres, no `.prj` | projected from JGD2011 / Japan Plane Rectangular CS VII (EPSG:6675) to longitude and latitude |

The zone of R2 to R7 is an inference, not stated by the source: the values are metres from an origin;
Gifu lies wholly in zone VII; and with that reading {plane_ok:,} of the {plane_n:,} points of R2 to R7 fall in
the municipality that their own record names (the municipalities of 国土数値情報 N03, 2026-01-01; the
rest were not examined one by one). A reading as zone IX of the Tokyo Datum (EPSG:30169) gave none.
The source does not say whether the coordinates are JGD2000 or JGD2011; they are treated as the same
here (the small shift between the two datums is not applied). The geometry
column carries no crs in its metadata, which means the default, WGS84 (OGC:CRS84).

## What was changed

- Nothing in the attributes. Added `row`, `geometry` (and `source_x`, `source_y`), typed the dBASE
  numeric fields as integers, made empty fields null, and projected the points of R2 to R7. The Parquet
  was checked against the source files with a second reader (the `.dbf` and the `.shp` parsed by hand,
  the CSV with its own reader), every row and column.
- Nothing was removed, merged or corrected.

## Known issues

- Twelve tables, not one: the columns differ from year to year and the meaning of a column is the
  source's. A record is a report; one animal can be reported more than once.
- {staff_text}
- The catalogue entry is called 過去 (past) and the prefecture points to its GIS for the latest data;
  new fiscal years are added to this entry from time to time (R5, R6 in October 2025, R7 in October 2025).
- The points of R2 to R7 depend on the reading of the coordinate system above; the original
  coordinates are in `source_x`, `source_y`.

## Licence

The catalogue states Creative Commons Attribution 2.1 Japan (`cc-by-21-jp`) for the entry. This
dataset is offered under CC BY 4.0 on that basis (a later version of the same licence family, with the
same attribution condition) and the credit is to Gifu Prefecture:

> 出典：岐阜県「クママップ（過去）」（{page}）を加工して作成
"""


def main() -> int:
    run = sorted((ROOT / "data" / "raw").glob("*/MANIFEST.json"))[-1].parent
    m = json.loads((run / "MANIFEST.json").read_text())
    cols = json.loads((ROOT / "data/parquet/columns.json").read_text())
    assert cols["run"] == run.name
    total = sum(cols["counts"].values())
    table_rows = "\n".join(
        f"| `{t}` | {label} (FY{fy}) | `{n}` | {cols['counts'][t]:,} |"
        for n, (t, fy, label) in k.FILES.items()
    )
    staff = sorted(
        {
            c
            for t, cs in cols["source_columns"].items()
            for c in cs
            if c.startswith(("入力者氏名", "入力者担当"))
        }
    )
    staff_text = (
        "Some tables have columns with the name of the municipal staff member who entered the record ("
        + ", ".join(f"`{c}`" for c in staff)
        + "). They are in the source as published, under the same licence, and are kept as they are; "
        "downstream users may prefer to drop them."
    )
    ok = json.loads((ROOT / "data/docs/plane_check.json").read_text())
    card = CARD.format(
        repo=REPO, total=total, page=k.PACKAGE_URL, author=m["author"], title=m["title"],
        license_id=m["license_id"], meta_modified=m["metadata_modified"][:10], run=run.name,
        fetched=run.name, table_rows=table_rows, staff_text=staff_text,
        plane_ok=ok["ok"], plane_n=ok["n"],
    )  # fmt: skip
    data = ROOT / "data"
    (data / "README.md").write_text(card, encoding="utf-8")
    (data / "LICENSE").write_text(
        "CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/legalcode)\n\n"
        "The records are from 岐阜県 クママップ（過去）, published in the prefecture's open data catalogue\n"
        f"under Creative Commons Attribution 2.1 Japan ({k.PACKAGE_URL}), processed as described in README.md.\n"
        f"Credit: 出典：岐阜県「クママップ（過去）」（{k.PACKAGE_URL}）を加工して作成\n",
        encoding="utf-8",
    )
    (data / "provenance.yaml").write_text(
        f"source: 岐阜県 クママップ（過去）\nurl: {k.PACKAGE_URL}\nlicense: {m['license_id']}\nrun: {run.name}\n"
        f"retrieved: {run.name}\nmetadata_modified: {m['metadata_modified']}\nrows: {total}\n",
        encoding="utf-8",
    )
    print("wrote data/README.md, LICENSE, provenance.yaml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
