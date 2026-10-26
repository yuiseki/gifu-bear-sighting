import io
import zipfile

import gifu as k
import pytest


def test_files_cover_h26_to_r7():
    tables = [v[0] for v in k.FILES.values()]
    assert tables == ["h26", "h27", "h28", "h29", "h30", "r1", "r2", "r3", "r4", "r5", "r6", "r7"]
    assert [v[1] for v in k.FILES.values()] == list(range(2014, 2026))


def test_plane_tables_are_r2_to_r7():
    assert set(k.PLANE_TABLES) == {"r2", "r3", "r4", "r5", "r6", "r7"}
    assert set(k.MUNICIPALITY_FIELD) == set(k.PLANE_TABLES)


def test_to_lonlat_passes_geographic_points_and_projects_plane_ones():
    assert k.to_lonlat("h26", [(137.0, 36.0)]) == [(137.0, 36.0)]
    # the origin of zone VII is 36 N, 137 10' E
    ((lon, lat),) = k.to_lonlat("r7", [(0.0, 0.0)])
    assert abs(lat - 36.0) < 1e-6 and abs(lon - (137 + 10 / 60)) < 1e-6


def test_csv_layer_reads_the_jgd2011_columns():
    head = ["ID", k.R1_LON, k.R1_LAT]
    data = ("\n".join([",".join(head), "1,137.1,35.5", "2,137.2,35.6"]) + "\n").encode("cp932")
    h, body, pts = k.csv_layer(data)
    assert h == head and body[1][0] == "2" and pts == [(137.1, 35.5), (137.2, 35.6)]


def test_zip_layer_needs_one_shp():
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("a.txt", "x")
    with pytest.raises(ValueError):
        k.zip_layer(b.getvalue())
