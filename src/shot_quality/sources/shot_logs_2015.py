from __future__ import annotations

import os

import polars as pl

from src.shot_quality.geometry import clock_display_to_seconds
from src.shot_quality.schema import conform_to_schema

"""
Loader for the 2014-15 "NBA Shot Logs" dataset.

This is the only public shot-level dataset that carries closest-defender
distance, which is why the roadmap uses it to quantify the defender-proximity
effect even though it is a single, historical season.

The file is not committed (16 MB, and it is someone else's dataset); see the
README for how to place it at DEFAULT_SHOT_LOGS_PATH.
"""

SOURCE_NAME = "shot_logs_2014_15"
SEASON = 2015
DEFAULT_SHOT_LOGS_PATH = "data/raw/shot_logs_2014_15.csv"


def load_shot_logs_2015(path: str = DEFAULT_SHOT_LOGS_PATH) -> pl.DataFrame:
    """
    Load the shot-log CSV and normalize it onto the canonical schema.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"2014-15 shot logs not found at {path}. See README section "
            "'Getting the data' for how to download it."
        )
    return normalize_shot_logs(pl.read_csv(path))


def normalize_shot_logs(raw: pl.DataFrame) -> pl.DataFrame:
    """
    Map the raw shot-log columns onto the canonical schema.

    Rows whose SHOT_CLOCK is null are kept: the null means the shot clock was
    off (under 24 seconds left in the period), which is information, not a
    defect, and dropping them would bias the late-period end of the data.
    """
    normalized = raw.with_columns(
        [
            pl.lit(SOURCE_NAME).alias("source"),
            pl.lit(SEASON).alias("season"),
            pl.col("GAME_ID").cast(pl.Utf8).alias("game_id"),
            pl.col("PERIOD").cast(pl.Int32).alias("period"),
            clock_display_to_seconds("GAME_CLOCK").alias("seconds_remaining_in_period"),
            pl.col("SHOT_DIST").cast(pl.Float64).alias("shot_distance_ft"),
            (pl.col("PTS_TYPE") == 3).alias("is_three"),
            pl.col("SHOT_CLOCK").cast(pl.Float64).alias("shot_clock_seconds"),
            pl.col("CLOSE_DEF_DIST").cast(pl.Float64).alias("defender_distance_ft"),
            pl.col("DRIBBLES").cast(pl.Int32).alias("dribbles"),
            pl.col("TOUCH_TIME").cast(pl.Float64).alias("touch_time_seconds"),
            pl.col("player_id").cast(pl.Utf8).alias("shooter_id"),
            pl.col("player_name").cast(pl.Utf8).alias("shooter_name"),
            (pl.col("FGM") == 1).alias("made"),
        ]
    )
    return conform_to_schema(normalized, SOURCE_NAME)
