import polars as pl

from src.shot_quality.overlap import (
    build_overlap_table,
    column_coverage,
    shared_feature_set,
)
from src.shot_quality.schema import CANONICAL_COLUMNS, conform_to_schema

"""
Overlap-analysis tests. The behaviour that matters is that a column which is
present but entirely null counts as unavailable - that is the difference
between "the schema has a shot clock" and "the data has a shot clock".
"""


def _source_frame(**columns) -> pl.DataFrame:
    row_count = len(next(iter(columns.values())))
    frame = pl.DataFrame({**columns, "season": [2026] * row_count})
    return conform_to_schema(frame, "test_source")


def test_column_coverage_reports_fraction_non_null() -> None:
    frame = _source_frame(shot_distance_ft=[1.0, None, 3.0, 4.0])

    coverage = column_coverage(frame)

    assert coverage["shot_distance_ft"] == 0.75
    assert coverage["defender_distance_ft"] == 0.0


def test_overlap_table_covers_every_canonical_column() -> None:
    table = build_overlap_table({"a": _source_frame(shot_distance_ft=[1.0])})

    assert table.get_column("column").to_list() == CANONICAL_COLUMNS


def test_all_null_column_is_not_shared() -> None:
    with_clock = _source_frame(shot_distance_ft=[1.0], shot_clock_seconds=[14.0])
    without_clock = _source_frame(shot_distance_ft=[2.0])

    table = build_overlap_table({"with": with_clock, "without": without_clock})
    shared = dict(zip(table.get_column("column"), table.get_column("shared_by_all")))

    assert shared["shot_distance_ft"] is True
    assert shared["shot_clock_seconds"] is False


def test_shared_feature_set_keeps_candidate_order() -> None:
    frame = _source_frame(
        period=[1],
        seconds_remaining_in_period=[120.0],
        shot_distance_ft=[18.0],
        is_three=[False],
    )

    assert shared_feature_set({"a": frame, "b": frame}) == [
        "period",
        "seconds_remaining_in_period",
        "shot_distance_ft",
        "is_three",
    ]
