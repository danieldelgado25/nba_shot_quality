from __future__ import annotations

import urllib.request

import polars as pl

from src.shot_quality.cache import RAW_DATA_DIR, cache_path_for, read_or_fetch
from src.shot_quality.geometry import add_shot_geometry, clock_display_to_seconds
from src.shot_quality.schema import conform_to_schema

"""
Current/recent-season shot data from the hoopR NBA data mirror (ESPN-derived,
published as per-season parquet on GitHub).

This exists because nba.com's own hosts (stats.nba.com, cdn.nba.com) are served
behind Akamai bot protection that refuses datacenter IPs, so nba_api cannot run
from CI or a cloud VM. The mirror is a stand-in for shotchartdetail's shot
location / period / clock / outcome fields, not for the tracking or lineup
endpoints, which have no public mirror.
"""

SOURCE_NAME = "hoopr_mirror"
MIRROR_URL_TEMPLATE = (
    "https://github.com/sportsdataverse/hoopR-nba-data/raw/main/"
    "nba/shots/parquet/shots_{season}.parquet"
)

# ESPN records free throws in the same feed as field goals; they are not shot
# attempts for the purposes of a shot-quality model.
FREE_THROW_MARKER = "Free Throw"


def load_mirror_shots(season: int, raw_data_dir: str = RAW_DATA_DIR) -> pl.DataFrame:
    """
    Load one season of mirrored shot data, normalized onto the canonical schema.

    season is labelled the way hoopR labels it: the year the season ends.
    """
    cache_path = cache_path_for(f"shots_{season}", raw_data_dir)
    raw = read_or_fetch(cache_path, lambda: _download_season(season), raw_data_dir)
    return normalize_mirror_shots(raw, season)


def normalize_mirror_shots(raw: pl.DataFrame, season: int) -> pl.DataFrame:
    """
    Map mirrored ESPN shot rows onto the canonical schema.

    Note what is *absent*: no shot clock, no defender distance, no dribbles and
    no touch time. Whether that leaves enough shared signal with the 2014-15
    logs is exactly what the Phase 0 overlap table reports.
    """
    field_goals = raw.filter(~pl.col("type_text").str.contains(FREE_THROW_MARKER))

    normalized = field_goals.with_columns(
        [
            pl.lit(SOURCE_NAME).alias("source"),
            pl.lit(season).alias("season"),
            pl.col("game_id").cast(pl.Utf8).alias("game_id"),
            pl.col("period_number").cast(pl.Int32).alias("period"),
            clock_display_to_seconds("clock_display_value").alias(
                "seconds_remaining_in_period"
            ),
            pl.col("type_text").alias("shot_type"),
            pl.col("athlete_id_1").cast(pl.Utf8).alias("shooter_id"),
            pl.col("athlete_name_1").alias("shooter_name"),
            pl.col("scoring_play").cast(pl.Boolean).alias("made"),
        ]
    )
    # coordinate_x runs baseline-to-baseline (0 at mid-court), coordinate_y runs
    # sideline-to-sideline (0 on the centre line); both are already in feet.
    normalized = add_shot_geometry(normalized, "coordinate_x", "coordinate_y")
    return conform_to_schema(normalized, SOURCE_NAME)


def _download_season(season: int) -> pl.DataFrame:
    """
    Fetch one season's parquet from the mirror into memory.
    """
    url = MIRROR_URL_TEMPLATE.format(season=season)
    with urllib.request.urlopen(url) as response:
        payload = response.read()
    return pl.read_parquet(payload)
