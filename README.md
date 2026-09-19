# NBA Shot Quality & Live Game Analytics

Expected field-goal probability (xFG) for NBA shot attempts, plus the live-data
plumbing needed to score shots as they happen. Follows the roadmap in
`docs/roadmap.md`. Phase 0 (setup and data checks) is done.

## What Phase 0 found

Run `python main.py` to regenerate `reports/phase0_validation.md`.

- **nba.com blocks this machine.** `stats.nba.com` (`shotchartdetail`,
  `leaguedashptstats`, `leaguedashlineups`) times out and `cdn.nba.com` (live
  play-by-play) returns Akamai `Access Denied` from datacenter IPs, in Python
  and in a real browser. So `nba_api` only works from a home connection, not
  from CI. Those wrappers are in `src/shot_quality/sources/nba_stats.py`, and
  `reachability_report()` checks both hosts so a pipeline can skip them instead
  of crashing.
- **There is a stand-in for shot data only.** The hoopR NBA mirror
  (ESPN-derived, one parquet per season on GitHub) covers 2002-2026 with shot
  coordinates, period, game clock and outcome, which is close to what
  `shotchartdetail` returns. Nothing similar exists for the tracking-defense or
  lineup endpoints, so Phases 2-3 need a run from a home network or a cached
  pull.
- **`shotchartdetail` has no shot clock.** The roadmap lists shot clock as a
  current-season feature, but the endpoint does not return one. It only exists
  in the 2014-15 shot logs, so it can't be a live feature.
- **No shot angle in the old logs.** The 2014-15 logs have `SHOT_DIST` but no
  coordinates, so angle can't be worked back out of them.
- **Shared feature set, as measured:** `period`,
  `seconds_remaining_in_period`, `shot_distance_ft`, `is_three`. That is thin,
  so Phase 1 trains the live model on the mirror (2002-2026, has angle and many
  more rows) and uses the 2014-15 logs only for the defender-distance study.
- **Defender distance has to be compared within a shot-distance bucket.** Make
  rate by raw defender bucket goes the wrong way because tightly guarded shots
  are mostly layups; the report shows both versions.

## Layout

```
src/shot_quality/
  schema.py       canonical shot-event schema every source is normalized into
  geometry.py     court coordinates -> distance, angle, three-point flag
  cache.py        read-through parquet snapshots of raw pulls
  overlap.py      feature-coverage and shared-feature analysis
  report.py       Phase 0 markdown report generation
  sources/
    shot_logs_2015.py  Kaggle 2014-15 shot logs (has defender distance)
    mirror.py          hoopR/ESPN season parquet (works without nba.com access)
    nba_stats.py       official nba_api endpoints + field-contract checks
main.py           Phase 0 entrypoint
tests/            unit tests; no test touches the network
notebooks/        00_phase0_data_validation.ipynb (Phase 0 definition of done)
```

Every source is mapped onto one schema (`schema.CANONICAL_COLUMNS`), so a column
a source can't fill shows up as an all-null column instead of a missing key.
That is what the coverage numbers in the overlap table count.

## Getting the data

```bash
pip install -r requirements.txt
```

- **Mirror shots** download automatically on first use into `data/raw/`.
- **2014-15 shot logs** are not committed. Download `shot_logs.csv` from the
  Kaggle "NBA shot logs" dataset and save it as
  `data/raw/shot_logs_2014_15.csv` (128,069 rows, header starting `GAME_ID,
  MATCHUP,LOCATION,...`).

```bash
python main.py            # regenerate the Phase 0 report
python -m pytest -q       # unit tests
ruff check .              # lint
```

## Next

Phase 1, the shot-quality model, using the training sources described above.
