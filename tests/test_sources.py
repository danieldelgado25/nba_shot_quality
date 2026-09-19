import polars as pl
import pytest

from src.shot_quality.schema import CANONICAL_COLUMNS
from src.shot_quality.sources.mirror import normalize_mirror_shots
from src.shot_quality.sources.nba_stats import (
    EXPECTED_SHOT_CHART_FIELDS,
    FieldContractError,
    check_expected_fields,
    normalize_shot_chart,
)
from src.shot_quality.sources.shot_logs_2015 import normalize_shot_logs

"""
Source normalization tests, run against small hand-built frames so no network
call is made. Each source has a different notion of coordinates, clock and
outcome; these lock down the mapping onto the canonical schema.
"""


def _mirror_raw() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "game_id": [1, 1, 1],
            "period_number": [1, 2, 3],
            "clock_display_value": ["11:44", "5:00", "0:30"],
            "type_text": ["Jump Shot", "Free Throw - 1 of 2", "Driving Layup Shot"],
            "athlete_id_1": [100, 100, 200],
            "athlete_name_1": ["A Shooter", "A Shooter", "B Shooter"],
            "scoring_play": [True, True, False],
            "coordinate_x": [18.0, 41.75, 40.0],
            "coordinate_y": [0.0, 0.0, 2.0],
        }
    )


def test_mirror_normalization_drops_free_throws_and_fills_schema() -> None:
    result = normalize_mirror_shots(_mirror_raw(), season=2026)

    assert result.columns == CANONICAL_COLUMNS
    assert result.height == 2
    assert result["shot_type"].to_list() == ["Jump Shot", "Driving Layup Shot"]
    assert result["season"].to_list() == [2026, 2026]


def test_mirror_normalization_marks_unavailable_columns_null() -> None:
    result = normalize_mirror_shots(_mirror_raw(), season=2026)

    # The mirror has no tracking fields; they must be null rather than absent,
    # so the overlap analysis can count them as uncovered.
    assert result["defender_distance_ft"].null_count() == result.height
    assert result["shot_clock_seconds"].null_count() == result.height


def test_shot_log_normalization_maps_tracking_fields() -> None:
    raw = pl.DataFrame(
        {
            "GAME_ID": [21400899],
            "PERIOD": [1],
            "GAME_CLOCK": ["1:09"],
            "SHOT_CLOCK": [10.8],
            "SHOT_DIST": [7.7],
            "PTS_TYPE": [2],
            "CLOSE_DEF_DIST": [1.3],
            "DRIBBLES": [2],
            "TOUCH_TIME": [1.9],
            "player_id": [203148],
            "player_name": ["brian roberts"],
            "FGM": [1],
        }
    )

    result = normalize_shot_logs(raw)

    assert result.columns == CANONICAL_COLUMNS
    assert result["seconds_remaining_in_period"][0] == pytest.approx(69.0)
    assert result["defender_distance_ft"][0] == pytest.approx(1.3)
    assert result["made"][0] is True
    assert result["is_three"][0] is False
    # The shot logs carry no coordinates, so angle cannot be reconstructed.
    assert result["shot_angle_deg"].null_count() == 1


def _shot_chart_raw() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "GAME_ID": ["0022500001"],
            "PERIOD": [1],
            "MINUTES_REMAINING": [5],
            "SECONDS_REMAINING": [12],
            "SHOT_DISTANCE": [24],
            "LOC_X": [-220],
            "LOC_Y": [100],
            "ACTION_TYPE": ["Jump Shot"],
            "SHOT_TYPE": ["3PT Field Goal"],
            "SHOT_MADE_FLAG": [0],
            "PLAYER_ID": [1629029],
            "PLAYER_NAME": ["Luka Doncic"],
        }
    )


def test_shot_chart_normalization_converts_tenths_of_feet_and_clock() -> None:
    result = normalize_shot_chart(_shot_chart_raw(), season="2025-26")

    assert result["season"][0] == 2026
    assert result["seconds_remaining_in_period"][0] == pytest.approx(312.0)
    assert result["is_three"][0] is True
    assert result["made"][0] is False
    # LOC_X/LOC_Y are tenths of a foot from the hoop: 22 ft wide, 10 ft deep.
    assert result["shot_angle_deg"][0] == pytest.approx(65.56, abs=0.01)


def test_check_expected_fields_raises_on_a_dropped_field() -> None:
    incomplete = _shot_chart_raw().drop("SHOT_DISTANCE")

    with pytest.raises(FieldContractError, match="SHOT_DISTANCE"):
        check_expected_fields(incomplete, EXPECTED_SHOT_CHART_FIELDS, "shotchartdetail")
