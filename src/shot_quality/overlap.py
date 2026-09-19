from __future__ import annotations

import polars as pl

from src.shot_quality.schema import CANDIDATE_LIVE_FEATURES, CANONICAL_COLUMNS

"""
Feature-overlap analysis: the Phase 0 deliverable.

Which features a model may use is decided by the intersection of what the
historical training source has and what the live-inference source has. This
module computes that intersection from the data instead of from the docs.
"""

# A column counts as available only if this fraction of its rows are non-null.
# Below it, the column exists in name only and would poison a "shared feature".
MINIMUM_COVERAGE = 0.5


def column_coverage(data_frame: pl.DataFrame) -> dict[str, float]:
    """
    Fraction of non-null rows for each canonical column in data_frame.
    """
    row_count = data_frame.height
    if row_count == 0:
        return {column: 0.0 for column in CANONICAL_COLUMNS}
    non_null_counts = data_frame.select(
        [pl.col(column).is_not_null().sum().alias(column) for column in CANONICAL_COLUMNS]
    ).row(0)
    return {
        column: count / row_count
        for column, count in zip(CANONICAL_COLUMNS, non_null_counts)
    }


def build_overlap_table(sources: dict[str, pl.DataFrame]) -> pl.DataFrame:
    """
    One row per canonical column, one coverage column per source, plus a
    shared_by_all flag marking the columns usable as model features.
    """
    coverages = {name: column_coverage(frame) for name, frame in sources.items()}

    table = pl.DataFrame({"column": CANONICAL_COLUMNS})
    for name, coverage in coverages.items():
        table = table.with_columns(
            pl.Series(name, [round(coverage[column], 4) for column in CANONICAL_COLUMNS])
        )

    source_names = list(sources.keys())
    shared = [
        all(coverages[name][column] >= MINIMUM_COVERAGE for name in source_names)
        for column in CANONICAL_COLUMNS
    ]
    return table.with_columns(pl.Series("shared_by_all", shared))


def shared_feature_set(sources: dict[str, pl.DataFrame]) -> list[str]:
    """
    Candidate live features that clear MINIMUM_COVERAGE in every source.

    This is the feature list Phase 1's baseline model is allowed to train on.
    """
    overlap = build_overlap_table(sources)
    shared_columns = (
        overlap.filter(pl.col("shared_by_all")).get_column("column").to_list()
    )
    return [column for column in CANDIDATE_LIVE_FEATURES if column in shared_columns]
