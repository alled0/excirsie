"""
Session persistence helpers for Taharrak.

  save_csv        — write a per-rep workout log to a timestamped CSV file
  persist_session — save session summary + rep log to SQLite
"""

import csv
import time
from datetime import datetime

from taharrak.database import save_session
from taharrak.ui import rating


def save_csv(trackers: list):
    """Export every rep across all trackers to a timestamped CSV file."""
    all_rows = []
    for tr in trackers:
        all_rows.extend(tr.all_rep_logs())
    if not all_rows:
        return
    all_rows.sort(key=lambda r: r["timestamp"])
    fname = f"workout_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(fname, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_rows[0].keys())
        writer.writeheader()
        writer.writerows(all_rows)
    print(f"Workout log saved → {fname}")


def persist_session(cfg: dict, trackers: list, exercise,
                    weight_kg: float, set_count: int, session_start: float):
    """Aggregate tracker data and write the session record to SQLite."""
    all_scores = []
    all_reps   = 0
    all_logs   = []
    for tr in trackers:
        all_scores += tr.form_scores
        all_reps   += tr.total_reps
        all_logs   += tr.all_rep_logs()

    avg  = sum(all_scores) / len(all_scores) if all_scores else 0.0
    best = max(all_scores) if all_scores else 0

    session_data = {
        "created_at":    datetime.now().isoformat(),
        "exercise_key":  exercise.key,
        "exercise_name": exercise.name,
        "weight_kg":     weight_kg,
        "sets_done":     set_count,
        "total_reps":    all_reps,
        "avg_score":     round(avg, 1),
        "best_score":    best,
        "duration_secs": int(time.time() - session_start),
        "rating":        rating(avg),
    }
    save_session(cfg, session_data, all_logs)
