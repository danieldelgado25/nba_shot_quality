# NBA Shot Quality & Live Game Analytics — Project Roadmap

**Author:** Daniel Delgado
**Purpose of this document:** A build brief for an autonomous coding agent (Devin) to scope, plan, and execute against. Written to be specific enough to act on without a long clarification loop.

**Target:** A working MVP live before the 2026-27 NBA season tips off (~4 weeks out), with planned in-season iteration afterward.

---

## 1. The idea, and the one thing to fix about it first

The original framing — "real-time shot-make projections before the shot is released, using player movement data" — is the right instinct (this is exactly what NBA teams pay Second Spectrum for), but it has a data problem: **raw player-tracking data (X/Y positions of all 10 players + ball, 25x/sec) is not publicly available.** The NBA stopped exposing it around 2016. No public API, scrape, or Kaggle dataset gives you *live* tracking for the current season.

This doesn't kill the project — it means the MVP needs to be honest about what "real-time" and "movement data" mean:

- **"Movement data"** → aggregated, NBA-published tracking stats (closeout distance buckets, touches, drive counts — see §3) instead of raw frame-by-frame positions.
- **"Real-time"** → predictions that update live, in-game, as plays happen (fully achievable via the NBA's live play-by-play feed) rather than a prediction fired 0.3 seconds before a shooter releases the ball (not achievable without proprietary data).
- **Genuine pre-release shot prediction** → possible only via computer vision on broadcast video, which is a real but much harder path — staged as **Phase 4 (stretch)**, not the MVP.

This keeps the project's ambition intact while making the MVP something that can actually ship in a month.

---

## 2. Recommended MVP scope

Two complementary components, both buildable entirely from public official NBA data:

### A. Shot Quality Model ("xFG" — expected field goal probability)
A model that estimates the probability a given shot attempt goes in, based on shot location, shot clock, game context, and shooter tendencies. This is the shot-prediction-classifier idea, reframed around available data.

### B. Live Lineup Efficiency & Clutch Dashboard
A live-updating view of on/off lineup net ratings and clutch-time (last 5 min, ≤5 pt game) performance splits, refreshed during live games via play-by-play polling. This is lower-risk, fully supported by public endpoints, and gives you a second strong deliverable if the shot-quality model underperforms.

Both plug into the same live-data plumbing, so building them together isn't much more work than building one.

---

## 3. Data sources (all public, via `nba_api` — the same package already used in `nba_optimizer`)

| Need | Endpoint / Source | Notes |
|---|---|---|
| Historical shot-by-shot training data **with defender distance** | Kaggle "NBA Shot Logs 2014-15" | One season only, static. Fields: shot distance, shot clock, touch time, dribbles, **closest defender + distance**, make/miss. This is the richest labeled dataset you'll find — use it to learn how defender proximity affects FG%, even though it's not current. |
| Current-season shot-by-shot data | `nba_api.stats.endpoints.shotchartdetail` | Shot location, distance, shot clock, quarter, time remaining, make/miss. **No defender distance field.** |
| Current-season aggregated tracking stats | `nba_api.stats.endpoints.leaguedashptstats` (`PtMeasureType='Defense'` and `'CatchShoot'`/`'PullUpShot'`) | This is the NBA's own public tracking-derived data: shots defended by closeout-distance bucket (0-2ft, 2-4ft, 4-6ft, 6ft+), catch-and-shoot vs. pull-up splits. Updated daily during the season. This is your best real substitute for per-shot defender distance. |
| Live in-game data | `nba_api.live.nba.endpoints` (`playbyplay`, `boxscore`, `scoreboard`) | This is genuinely live (seconds of lag), used by NBA.com itself. Gives shot location/type/result the moment it happens, current lineups on court, score, clock. This is what "real-time" means for this MVP. |
| Lineup on/off data | `nba_api.stats.endpoints.leaguedashlineups` | Net rating, pace, and efficiency by 5-man lineup combination. |

**Key honesty point for whoever picks this up (including Devin):** the model trained on 2014-15 data (with defender distance) and the model run live (without it) are not the same model. Plan for two variants from day one — see Phase 2.

---

## 4. Phased roadmap

### Phase 0 — Setup & data validation (Days 1-3)
- Stand up the project on top of the existing `wide-receiver-predictor`-style structure (pipeline/tests separated from a thin API layer) — you already know this pattern from `fantasy-web-app`.
- Pull and validate: the Kaggle 2014-15 shot log, current-season `shotchartdetail` for a handful of games, and `leaguedashptstats` defense data. Confirm field overlap between the historical and current-season data (shot distance, shot clock, quarter/time — the model's live-usable feature set).
- **Definition of done:** a notebook showing all three sources loaded, joined where possible, with row counts and a feature-overlap table.

### Phase 1 — Shot Quality Model v1 (Days 4-12)
- Train a baseline model **using only features available both historically and live** (shot distance, angle, shot clock, quarter, time remaining, shot type) — no defender distance yet. Gradient-boosted trees (XGBoost or LightGBM) are the standard choice for this kind of tabular sports data and will likely outperform a neural net here; this also gives you a second modeling approach on your resume beyond the Ridge/MLP/LSTM you've already used elsewhere.
- Train a second version **including defender distance**, using only the 2014-15 data, to quantify how much defender proximity matters (this becomes a genuinely interesting analysis/chart even if it can't run live).
- Evaluate with log loss, Brier score, and calibration plots (not just accuracy — a well-calibrated 34% vs. a well-calibrated 62% matters more than raw hit rate for a probability model).
- **Definition of done:** a saved model artifact, a calibration plot, and a short write-up quantifying the defender-distance effect.

### Phase 2 — Live inference pipeline (Days 13-20)
- Build a poller against the live play-by-play endpoint during an actual live game (or a replayed historical game if the season hasn't started yet) that, for each shot event, computes the model's pre-registered probability and compares it to the outcome.
- Blend in the daily-updated `leaguedashptstats` defense numbers as a team/player-level adjustment factor (e.g., "this shooter is being guarded by a team that ranks 3rd in contest rate at 0-2ft") — this is your honest stand-in for real-time defender distance.
- Expose results via a small API + simple frontend (reuse the Flask/React pattern from `fantasy-web-app`).
- **Definition of done:** running the poller against a live or replayed game produces a running log of shot-by-shot predicted vs. actual outcomes.

### Phase 3 — Lineup Efficiency & Clutch Dashboard (Days 15-25, parallel to Phase 2)
- Pull lineup net ratings and filter play-by-play for clutch-time windows (≤5 min, ≤5 pt margin).
- Build a dashboard view: best/worst 5-man units, clutch on/off splits, updated as games complete.
- **Definition of done:** a dashboard showing at least one full team's lineup data end-to-end.

### Phase 4 — Stretch: computer vision on broadcast video (post-season-start, ongoing)
- Explore player detection + tracking on broadcast footage (not raw tracking data — actual video) using an off-the-shelf object detector (e.g., YOLO) plus a tracker, to approximate player positions and closest-defender distance directly from video frames.
- This is a genuinely hard, multi-week-plus research problem (camera angle changes, occlusion, broadcast cuts, calibrating pixel space to court space) — treat it as an ongoing side-track you tinker with during the season, not a launch requirement. If it works even partially on a handful of clips, that alone is a strong standalone talking point.

---

## 5. What "MVP by season start" honestly means

By tip-off, realistic: Phase 0-2 done (a shot-quality model with a live-updating demo against real play-by-play) and Phase 3 in progress. Phase 4 is explicitly a during-season stretch goal, not a launch blocker — pitching it as "day-one CV" risks an MVP that slips past the season start trying to solve the hardest part first.

## 6. For Devin specifically

- Start with Phase 0 as a standalone, verifiable task before touching modeling — the data-overlap validation determines what's even possible in later phases.
- Each phase above has an explicit "definition of done" — treat these as acceptance criteria, not suggestions.
- Flag immediately (don't silently work around) if `leaguedashptstats` or the live endpoints return different fields than described here — the NBA's stats API changes occasionally without notice, and this roadmap's Phase 2 design depends on the fields listed in §3.
- Prefer XGBoost/LightGBM over a neural net for Phase 1 unless there's a specific reason found during Phase 0 to expect nonlinear interactions a tree model can't capture — this keeps iteration fast during the compressed timeline.
