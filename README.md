# NBA Shot Quality & Live Game Analytics

Expected field-goal probability (xFG) for NBA shot attempts, plus the live-data
plumbing needed to score shots as they happen. Built to the phased roadmap in
`docs/roadmap.md`; this repository currently covers **Phase 0 — setup and data
validation**.

## What Phase 0 established

Run `python main.py` to regenerate `reports/phase0_validation.md`. The findings
that shape every later phase:

- **nba.com refuses this machine.** Both `stats.nba.com` (`shotchartdetail`,
  `leaguedashptstats`, `leaguedashlineups`) and `cdn.nba.com` (live play-by-play)
  sit behind Akamai bot protection that returns `Access Denied` / times out from
  datacenter IPs — in Python *and* in a real browser. `nba_api` therefore works
  from a residential connection only, and never from CI. The endpoint wrappers
  live in `src/shot_quality/sources/nba_stats.py`; `reachability_report()` probes
  both hosts so a pipeline can degrade deliberately instead of crashing.
- **A usable substitute exists for shot data only.** The hoopR NBA data mirror
  (ESPN-derived, per-season parquet on GitHub) covers 2002-2026 with shot
  coordinates, period, game clock and outcome — roughly `shotchartdetail`'s
  field set. There is **no** public mirror for the tracking-defense or lineup
  endpoints, so Phases 2-3 will need a residential-network run or a cached pull.
- **`shotchartdetail` has no shot clock.** The roadmap lists shot clock as a
  current-season feature; the endpoint does not return one. Shot clock exists
  only in the 2014-15 shot logs, so it cannot be a live feature.
- **Shot angle is unavailable historically.** The 2014-15 logs carry
  `SHOT_DIST` but no coordinates, so angle cannot be reconstructed for them.
- **Measured shared feature set:** `period`, `seconds_remaining_in_period`,
  `shot_distance_ft`, `is_three`. That is thin, which suggests a change to the
  Phase 1 plan: train the live-usable model on the *mirror* (2002-2026, which
  does have angle and far more rows) and use the 2014-15 logs solely for the
  defender-distance study, rather than training both on the 2014-15 season.
- **The defender-distance effect must be conditioned on shot distance.** Raw
  make rate by defender bucket is non-monotonic because tightly contested shots
  are disproportionately layups; the report includes the conditioned version.

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

Sources are kept behind one canonical schema (`schema.CANONICAL_COLUMNS`) so a
column a source cannot populate becomes an explicit null rather than a missing
key — that is what makes the coverage numbers in the overlap table meaningful.

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

Phase 1 (shot-quality model) per the roadmap, with the training-source change
noted above.
