from __future__ import annotations

import polars as pl

"""
Court geometry helpers.

Shot coordinates arrive in two different frames depending on the source, so the
conversion to (distance, angle, is_three) lives here rather than in each loader.
"""

# Half court is 47 ft from mid-court to the baseline; the hoop centre sits
# 5.25 ft in from the baseline, so it is 41.75 ft from mid-court along the
# length of the floor.
HOOP_DISTANCE_FROM_MIDCOURT_FT = 41.75

# NBA three-point line: a 23.75 ft arc that flattens to 22 ft in the corners,
# where the corner begins 22 ft off the centre line of the floor.
ARC_THREE_DISTANCE_FT = 23.75
CORNER_THREE_DISTANCE_FT = 22.0
CORNER_THREE_Y_CUTOFF_FT = 22.0


def add_shot_geometry(
    data_frame: pl.DataFrame,
    length_axis_column: str,
    width_axis_column: str,
) -> pl.DataFrame:
    """
    Derive shot_distance_ft, shot_angle_deg and is_three from court coordinates.

    length_axis_column runs baseline-to-baseline with 0 at mid-court (so the two
    hoops sit at +/- HOOP_DISTANCE_FROM_MIDCOURT_FT); width_axis_column runs
    sideline-to-sideline with 0 on the centre line. Shots are folded onto a
    single half court via the absolute value of the length axis, which is safe
    here because no source distinguishes offensive direction in a way the model
    uses.
    """
    distance_along_length = (
        HOOP_DISTANCE_FROM_MIDCOURT_FT - pl.col(length_axis_column).abs()
    )
    distance_across_width = pl.col(width_axis_column).abs()

    return data_frame.with_columns(
        [
            (distance_along_length.pow(2) + distance_across_width.pow(2))
            .sqrt()
            .alias("shot_distance_ft"),
            # atan2(across, along): 0 degrees is straight on, 90 is from the
            # baseline. Shots released behind the baseline give a negative
            # along-component and therefore an angle above 90, which is correct.
            pl.arctan2(distance_across_width, distance_along_length)
            .degrees()
            .alias("shot_angle_deg"),
        ]
    ).with_columns(classify_three_point(distance_across_width).alias("is_three"))


def classify_three_point(distance_across_width: pl.Expr) -> pl.Expr:
    """
    Three-point rule expressed against an already-computed shot_distance_ft.

    Kept separate from add_shot_geometry so the corner/arc rule can be unit
    tested on its own, and because ESPN's shot-type text only marks *made*
    threes, which makes the text field unusable as a label.
    """
    in_corner = distance_across_width >= CORNER_THREE_Y_CUTOFF_FT
    return pl.when(in_corner).then(
        pl.col("shot_distance_ft") >= CORNER_THREE_DISTANCE_FT
    ).otherwise(pl.col("shot_distance_ft") >= ARC_THREE_DISTANCE_FT)


def clock_display_to_seconds(clock_column: str) -> pl.Expr:
    """
    Convert a "MM:SS" or "M:SS.s" game clock string to seconds remaining.
    """
    minutes = pl.col(clock_column).str.split(":").list.get(0).cast(pl.Float64)
    seconds = pl.col(clock_column).str.split(":").list.get(1).cast(pl.Float64)
    return minutes * 60.0 + seconds
