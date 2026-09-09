#!/usr/bin/env python3
"""Download and unzip IMDB-BINARY (TUDataset) into a local ``data/`` directory.

The sandbox used for development cannot reach the dataset host (returns 403; only
github/pypi are reachable). Run this on a machine with open internet access (e.g.
the Lightning AI studio):

    python scripts/fetch_imdb_binary.py            # -> src/data/IMDB-BINARY/
    python scripts/fetch_imdb_binary.py --data-root /some/where

Then run the real-data grid:

    python -m experimentation.cli run --config imdb --workers $(nproc) --evaluate --figures

This script uses only the Python standard library (urllib + zipfile); no new
dependencies. The real dataset is intentionally NOT committed to the repo.
"""

from __future__ import annotations

import argparse
import io
from pathlib import Path
import sys
import urllib.request
import zipfile


DATASET_NAME = "IMDB-BINARY"
# Canonical TUDataset mirror maintained by Christopher Morris et al.
DOWNLOAD_URL = "https://www.chrsmrrs.com/graphkerneldatasets/IMDB-BINARY.zip"
DEFAULT_DATA_ROOT = Path(__file__).resolve().parents[1] / "data"


def fetch(data_root: Path, url: str = DOWNLOAD_URL) -> Path:
    data_root.mkdir(parents=True, exist_ok=True)
    target_dir = data_root / DATASET_NAME
    marker = target_dir / f"{DATASET_NAME}_A.txt"
    if marker.is_file():
        print(f"Already present: {marker}")
        return target_dir

    print(f"Downloading {url} ...")
    request = urllib.request.Request(url, headers={"User-Agent": "thesis-experimentation/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310 - trusted dataset host
        payload = response.read()
    print(f"Downloaded {len(payload):,} bytes; extracting into {data_root} ...")
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        archive.extractall(data_root)

    if not marker.is_file():
        raise SystemExit(
            f"Extraction did not produce {marker}. Inspect the archive layout under {data_root}."
        )
    print(f"Ready: {target_dir}")
    return target_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch IMDB-BINARY into data/")
    parser.add_argument("--data-root", default=str(DEFAULT_DATA_ROOT), help="Directory to unzip the dataset into")
    parser.add_argument("--url", default=DOWNLOAD_URL, help="Override the download URL")
    args = parser.parse_args(argv)
    fetch(Path(args.data_root), args.url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
