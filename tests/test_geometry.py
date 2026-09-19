import polars as pl
import pytest

from src.shot_quality.geometry import (
    HOOP_DISTANCE_FROM_MIDCOURT_FT,
    add_shot_geometry,
    clock_display_to_seconds,
)

"""
Geometry tests. The three-point classification is the load-bearing part: the
mirror source's shot-type text only marks made threes, so is_three has to be
derived from coordinates, and an off-by-a-few-feet transform would silently
mislabel a fifth of the dataset.
"""


def _frame(rows: list[tuple[float, float]]) -> pl.DataFrame:
    return pl.DataFrame(
        {"x": [row[0] for row in rows], "y": [row[1] for row in rows]}
    )


def test_shot_at_the_rim_has_zero_distance_and_angle() -> None:
    result = add_shot_geometry(_frame([(HOOP_DISTANCE_FROM_MIDCOURT_FT, 0.0)]), "x", "y")

    assert result["shot_distance_ft"][0] == pytest.approx(0.0)
    assert result["shot_angle_deg"][0] == pytest.approx(0.0)
    assert result["is_three"][0] is False


def test_baseline_shot_has_ninety_degree_angle() -> None:
    # Level with the hoop along the length of the court, 10 ft to the side.
    result = add_shot_geometry(_frame([(HOOP_DISTANCE_FROM_MIDCOURT_FT, 10.0)]), "x", "y")

    assert result["shot_angle_deg"][0] == pytest.approx(90.0)
    assert result["shot_distance_ft"][0] == pytest.approx(10.0)


def test_both_ends_of_the_court_fold_onto_one_half() -> None:
    result = add_shot_geometry(
        _frame([(HOOP_DISTANCE_FROM_MIDCOURT_FT - 5.0, 3.0), (-HOOP_DISTANCE_FROM_MIDCOURT_FT + 5.0, -3.0)]),
        "x",
        "y",
    )

    assert result["shot_distance_ft"][0] == pytest.approx(result["shot_distance_ft"][1])
    assert result["shot_angle_deg"][0] == pytest.approx(result["shot_angle_deg"][1])


def test_corner_three_uses_the_twenty_two_foot_line() -> None:
    # 22.0 ft across the floor, level with the hoop: a corner three at exactly
    # the line distance, which the 23.75 ft arc rule would wrongly call a two.
    result = add_shot_geometry(_frame([(HOOP_DISTANCE_FROM_MIDCOURT_FT, 22.0)]), "x", "y")

    assert result["is_three"][0] is True


def test_long_two_inside_the_arc_is_not_a_three() -> None:
    # 23 ft straight on is beyond the corner line but inside the arc.
    result = add_shot_geometry(
        _frame([(HOOP_DISTANCE_FROM_MIDCOURT_FT - 23.0, 0.0)]), "x", "y"
    )

    assert result["is_three"][0] is False


def test_shot_from_behind_the_baseline_exceeds_ninety_degrees() -> None:
    result = add_shot_geometry(
        _frame([(HOOP_DISTANCE_FROM_MIDCOURT_FT + 3.0, 5.0)]), "x", "y"
    )

    assert result["shot_angle_deg"][0] > 90.0


def test_clock_display_converts_minutes_and_seconds() -> None:
    frame = pl.DataFrame({"clock": ["11:44", "0:05.3"]})

    seconds = frame.select(clock_display_to_seconds("clock").alias("s"))["s"].to_list()

    assert seconds == pytest.approx([704.0, 5.3])
