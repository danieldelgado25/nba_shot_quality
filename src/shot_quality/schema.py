from __future__ import annotations

"""
Canonical shot-event schema.

Every data source in src/shot_quality/sources is normalized into these column
names so the modeling layer never has to know which source a row came from.
Sources differ in *which* of these columns they can populate; that difference is
the whole point of the Phase 0 overlap analysis (see overlap.py).
"""

# Identity / context columns present in every source.
IDENTITY_COLUMNS: list[str] = [
    "source",  # short name of the originating data source
    "season",  # NBA season, labelled by the year the season ends (2015 = 2014-15)
    "game_id",  # source-native game identifier (not stable across sources)
    "period",  # 1-4 for regulation quarters, 5+ for overtimes
]

# Shot-description columns. Not all sources populate all of them.
SHOT_COLUMNS: list[str] = [
    "seconds_remaining_in_period",  # game clock, seconds left in the period
    "shot_distance_ft",  # straight-line distance from the hoop, in feet
    "shot_angle_deg",  # 0 = straight on, 90 = from the baseline corner
    "is_three",  # True if the attempt is worth three points
    "shot_type",  # source-native description (e.g. "Pullup Jump Shot")
    "shot_clock_seconds",  # seconds left on the shot clock at release
    "defender_distance_ft",  # distance of the closest defender at release
    "dribbles",  # dribbles taken by the shooter on the possession
    "touch_time_seconds",  # how long the shooter held the ball before shooting
    "shooter_id",
    "shooter_name",
]

# The supervised target.
TARGET_COLUMN = "made"

CANONICAL_COLUMNS: list[str] = IDENTITY_COLUMNS + SHOT_COLUMNS + [TARGET_COLUMN]

# Features the roadmap's Phase 1 baseline is allowed to use: they must be
# derivable from *both* the historical training source and whatever runs live.
# Phase 0 verifies this list against the sources rather than assuming it.
CANDIDATE_LIVE_FEATURES: list[str] = [
    "period",
    "seconds_remaining_in_period",
    "shot_distance_ft",
    "shot_angle_deg",
    "is_three",
    "shot_clock_seconds",
]


def conform_to_schema(data_frame, source_name: str):
    """
    Return data_frame with exactly CANONICAL_COLUMNS, in order.

    Columns the source cannot populate are added as nulls, which is what makes
    the coverage counts in overlap.py meaningful: a column that exists but is
    entirely null is treated as unavailable, not as available-and-empty.
    """
    import polars as pl

    missing = [column for column in CANONICAL_COLUMNS if column not in data_frame.columns]
    data_frame = data_frame.with_columns(
        [pl.lit(None).alias(column) for column in missing if column != "source"]
    )
    if "source" in missing:
        data_frame = data_frame.with_columns(pl.lit(source_name).alias("source"))
    return data_frame.select(CANONICAL_COLUMNS)
