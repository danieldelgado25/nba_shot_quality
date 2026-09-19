import polars as pl

from src.shot_quality.cache import cache_path_for, read_or_fetch

"""
Cache tests: a hit must not re-fetch, a miss must persist the snapshot.
"""


def test_cache_miss_fetches_and_writes_snapshot(tmp_path) -> None:
    cache_path = str(tmp_path / "shots_2026.parquet")
    fetch_calls = []

    def fetch() -> pl.DataFrame:
        fetch_calls.append(1)
        return pl.DataFrame({"a": [1, 2]})

    result = read_or_fetch(cache_path, fetch, str(tmp_path))

    assert len(fetch_calls) == 1
    assert result["a"].to_list() == [1, 2]
    assert (tmp_path / "shots_2026.parquet").exists()


def test_cache_hit_does_not_fetch(tmp_path) -> None:
    cache_path = str(tmp_path / "shots_2026.parquet")
    pl.DataFrame({"a": [99]}).write_parquet(cache_path)

    def fetch() -> pl.DataFrame:
        raise AssertionError("fetch must not run on a cache hit")

    assert read_or_fetch(cache_path, fetch, str(tmp_path))["a"].to_list() == [99]


def test_cache_path_for_joins_directory_and_name(tmp_path) -> None:
    assert cache_path_for("shots_2026", str(tmp_path)).endswith("shots_2026.parquet")
