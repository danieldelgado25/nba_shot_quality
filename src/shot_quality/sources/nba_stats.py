from __future__ import annotations

import polars as pl

from src.shot_quality.cache import RAW_DATA_DIR, cache_path_for, read_or_fetch
from src.shot_quality.schema import conform_to_schema

"""
Official nba.com sources via nba_api.

These only work from a network nba.com will answer: stats.nba.com and
cdn.nba.com sit behind Akamai bot protection that returns "Access Denied" to
datacenter IPs, so everything here fails from CI and from cloud VMs and has to
be run from a residential connection. reachability_report() makes that a
first-class, checkable condition instead of a confusing stack trace.
"""

SHOT_CHART_SOURCE_NAME = "nba_shotchartdetail"

# Fields this project depends on, per source. Checked at load time because the
# stats API changes its payloads without notice and a silently missing column
# would otherwise surface much later as a null feature.
EXPECTED_SHOT_CHART_FIELDS: list[str] = [
    "GAME_ID",
    "PERIOD",
    "MINUTES_REMAINING",
    "SECONDS_REMAINING",
    "SHOT_DISTANCE",
    "LOC_X",
    "LOC_Y",
    "ACTION_TYPE",
    "SHOT_TYPE",
    "SHOT_MADE_FLAG",
    "PLAYER_ID",
    "PLAYER_NAME",
]
EXPECTED_TRACKING_DEFENSE_FIELDS: list[str] = [
    "PLAYER_ID",
    "PLAYER_NAME",
    "DEF_RIM_FGM",
    "DEF_RIM_FGA",
    "DEF_RIM_FG_PCT",
]
EXPECTED_LINEUP_FIELDS: list[str] = [
    "GROUP_ID",
    "GROUP_NAME",
    "TEAM_ID",
    "MIN",
    "OFF_RATING",
    "DEF_RATING",
    "NET_RATING",
    "PACE",
]


class FieldContractError(RuntimeError):
    """
    Raised when an nba.com endpoint returns without a field this project needs.
    """


def check_expected_fields(
    data_frame: pl.DataFrame, expected_fields: list[str], endpoint: str
) -> pl.DataFrame:
    """
    Fail loudly when endpoint drops or renames a field the pipeline relies on.
    """
    missing = [field for field in expected_fields if field not in data_frame.columns]
    if missing:
        raise FieldContractError(
            f"{endpoint} response is missing expected field(s): {missing}. "
            f"Returned fields: {sorted(data_frame.columns)}"
        )
    return data_frame


def reachability_report() -> dict[str, str]:
    """
    Probe each nba.com host this project would use and report what happened.

    Returns a host -> outcome mapping ("ok" or a short failure description) so
    callers can degrade to the mirror source instead of dying mid-pipeline.
    """
    import urllib.error
    import urllib.request

    probes = {
        "stats.nba.com": "https://stats.nba.com/stats/scoreboardv2?GameDate=2025-01-15&LeagueID=00&DayOffset=0",
        "cdn.nba.com": "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json",
    }
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.nba.com/",
        "Accept": "application/json",
    }

    outcomes: dict[str, str] = {}
    for host, url in probes.items():
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                outcomes[host] = "ok" if response.status == 200 else f"http {response.status}"
        except urllib.error.HTTPError as error:
            outcomes[host] = f"http {error.code}"
        except OSError as error:
            # URLError, timeouts and connection resets all subclass OSError;
            # the caller only needs to know the host is unusable.
            outcomes[host] = f"{type(error).__name__}"
    return outcomes


def load_shot_chart(
    season: str, player_id: int = 0, team_id: int = 0, raw_data_dir: str = RAW_DATA_DIR
) -> pl.DataFrame:
    """
    Pull shotchartdetail for a season, normalized onto the canonical schema.

    season uses the API's own "2025-26" style label. player_id/team_id of 0 mean
    "all", which the endpoint allows only alongside a context filter, so callers
    normally pass one of them.
    """
    cache_name = f"shotchartdetail_{season.replace('-', '_')}_{player_id}_{team_id}"
    raw = read_or_fetch(
        cache_path_for(cache_name, raw_data_dir),
        lambda: _fetch_shot_chart(season, player_id, team_id),
        raw_data_dir,
    )
    return normalize_shot_chart(raw, season)


def normalize_shot_chart(raw: pl.DataFrame, season: str) -> pl.DataFrame:
    """
    Map shotchartdetail rows onto the canonical schema.

    LOC_X/LOC_Y are tenths of a foot measured from the hoop, so distance and
    angle are computed here rather than via geometry.add_shot_geometry, which
    expects the mid-court-origin frame the mirror source uses.

    Note for anyone comparing against the roadmap: shotchartdetail carries no
    shot-clock field. Shot clock is available only in the 2014-15 shot logs.
    """
    check_expected_fields(raw, EXPECTED_SHOT_CHART_FIELDS, "shotchartdetail")

    horizontal_feet = pl.col("LOC_X").cast(pl.Float64) / 10.0
    vertical_feet = pl.col("LOC_Y").cast(pl.Float64) / 10.0

    normalized = raw.with_columns(
        [
            pl.lit(SHOT_CHART_SOURCE_NAME).alias("source"),
            pl.lit(_season_end_year(season)).alias("season"),
            pl.col("GAME_ID").cast(pl.Utf8).alias("game_id"),
            pl.col("PERIOD").cast(pl.Int32).alias("period"),
            (
                pl.col("MINUTES_REMAINING").cast(pl.Float64) * 60.0
                + pl.col("SECONDS_REMAINING").cast(pl.Float64)
            ).alias("seconds_remaining_in_period"),
            pl.col("SHOT_DISTANCE").cast(pl.Float64).alias("shot_distance_ft"),
            pl.arctan2(horizontal_feet.abs(), vertical_feet)
            .degrees()
            .alias("shot_angle_deg"),
            pl.col("SHOT_TYPE").str.contains("3PT").alias("is_three"),
            pl.col("ACTION_TYPE").alias("shot_type"),
            pl.col("PLAYER_ID").cast(pl.Utf8).alias("shooter_id"),
            pl.col("PLAYER_NAME").alias("shooter_name"),
            (pl.col("SHOT_MADE_FLAG") == 1).alias("made"),
        ]
    )
    return conform_to_schema(normalized, SHOT_CHART_SOURCE_NAME)


def load_tracking_defense(season: str, raw_data_dir: str = RAW_DATA_DIR) -> pl.DataFrame:
    """
    Pull leaguedashptstats defensive tracking stats (rim protection, opponent
    FG% when defended), kept in the endpoint's own column names because Phase 2
    consumes it as a team/player adjustment rather than as shot rows.
    """
    cache_name = f"leaguedashptstats_defense_{season.replace('-', '_')}"
    raw = read_or_fetch(
        cache_path_for(cache_name, raw_data_dir),
        lambda: _fetch_tracking_defense(season),
        raw_data_dir,
    )
    return check_expected_fields(raw, EXPECTED_TRACKING_DEFENSE_FIELDS, "leaguedashptstats")


def load_lineups(season: str, raw_data_dir: str = RAW_DATA_DIR) -> pl.DataFrame:
    """
    Pull leaguedashlineups five-man unit ratings for the Phase 3 dashboard.
    """
    cache_name = f"leaguedashlineups_{season.replace('-', '_')}"
    raw = read_or_fetch(
        cache_path_for(cache_name, raw_data_dir),
        lambda: _fetch_lineups(season),
        raw_data_dir,
    )
    return check_expected_fields(raw, EXPECTED_LINEUP_FIELDS, "leaguedashlineups")


def _fetch_shot_chart(season: str, player_id: int, team_id: int) -> pl.DataFrame:
    """
    nba_api call for shotchartdetail, isolated so tests never import nba_api.
    """
    from nba_api.stats.endpoints import shotchartdetail

    endpoint = shotchartdetail.ShotChartDetail(
        team_id=team_id,
        player_id=player_id,
        season_nullable=season,
        season_type_all_star="Regular Season",
        context_measure_simple="FGA",
    )
    return pl.from_pandas(endpoint.get_data_frames()[0])


def _fetch_tracking_defense(season: str) -> pl.DataFrame:
    """
    nba_api call for leaguedashptstats with PtMeasureType="Defense".
    """
    from nba_api.stats.endpoints import leaguedashptstats

    endpoint = leaguedashptstats.LeagueDashPtStats(
        season=season,
        season_type_all_star="Regular Season",
        player_or_team="Player",
        pt_measure_type="Defense",
    )
    return pl.from_pandas(endpoint.get_data_frames()[0])


def _fetch_lineups(season: str) -> pl.DataFrame:
    """
    nba_api call for leaguedashlineups (five-man units).
    """
    from nba_api.stats.endpoints import leaguedashlineups

    endpoint = leaguedashlineups.LeagueDashLineups(
        season=season,
        season_type_all_star="Regular Season",
        group_quantity=5,
        measure_type_detailed_defense="Advanced",
    )
    return pl.from_pandas(endpoint.get_data_frames()[0])


def _season_end_year(season: str) -> int:
    """
    Convert an API season label ("2025-26") to the year the season ends (2026).
    """
    start_year = int(season.split("-")[0])
    return start_year + 1
