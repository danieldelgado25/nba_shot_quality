from __future__ import annotations

import os

from src.shot_quality.report import build_phase0_report
from src.shot_quality.sources.mirror import load_mirror_shots
from src.shot_quality.sources.nba_stats import reachability_report
from src.shot_quality.sources.shot_logs_2015 import load_shot_logs_2015

"""
Phase 0 entrypoint: load every available source, validate the overlap between
them, and write the report artifact.
"""

# Seasons pulled from the mirror: the most recent completed season plus the one
# in progress, which is enough to see whether the schema is stable year to year.
MIRROR_SEASONS = [2025, 2026]
REPORT_PATH = "reports/phase0_validation.md"


def main() -> None:
    """
    Build and write the Phase 0 validation report.
    """
    sources = {"shot_logs_2014_15": load_shot_logs_2015()}
    for season in MIRROR_SEASONS:
        sources[f"hoopr_mirror_{season}"] = load_mirror_shots(season)

    report = build_phase0_report(sources, reachability_report())

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as report_file:
        report_file.write(report)

    print(report)


if __name__ == "__main__":
    main()
