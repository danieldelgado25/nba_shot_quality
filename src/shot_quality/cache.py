from __future__ import annotations

import os
from collections.abc import Callable

import polars as pl

"""
Read-through snapshot cache for raw source pulls.

Remote sources here are either rate limited (nba_api) or re-published daily
(the hoopR mirror), so a local parquet snapshot is what keeps a given dataset
build reproducible after the upstream file changes.
"""

RAW_DATA_DIR = "data/raw"


def read_or_fetch(
    cache_path: str,
    fetch: Callable[[], pl.DataFrame],
    raw_data_dir: str = RAW_DATA_DIR,
) -> pl.DataFrame:
    """
    Return the parquet snapshot at cache_path if it exists, otherwise call
    fetch(), write the snapshot, and return the fetched frame.
    """
    if os.path.exists(cache_path):
        return pl.read_parquet(cache_path)
    data_frame = fetch()
    os.makedirs(raw_data_dir, exist_ok=True)
    data_frame.write_parquet(cache_path)
    return data_frame


def cache_path_for(name: str, raw_data_dir: str = RAW_DATA_DIR) -> str:
    """
    Build the snapshot path for a named pull (e.g. "shots_2026").
    """
    return os.path.join(raw_data_dir, f"{name}.parquet")
