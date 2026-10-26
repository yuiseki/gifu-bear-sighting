# gifu-bear-sighting

Reproducible collection of the クママップ（過去） (bear sightings, H26 to R7) of Gifu Prefecture from its
open data catalogue. The dataset card is generated into `data/README.md` (not tracked; the data is
published at https://huggingface.co/datasets/yuiseki/gifu-bear-sighting).

```
uv run python scripts/01_download.py      # the twelve files, the catalogue metadata and N03 of Gifu (data/raw/<date>, data/docs)
uv run python scripts/02_export_parquet.py
uv run python scripts/03_verify.py        # each Parquet vs its file, parsed by hand; the municipality check
uv run python scripts/04_card.py
uv run python src/publish.py [--push]     # dry run by default
```

Code: MIT. Data: CC BY 4.0, see the card.
