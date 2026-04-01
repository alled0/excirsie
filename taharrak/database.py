"""
SQLite session history for Taharrak.
Database lives at ~/.taharrak/sessions.db
"""

import os
import sqlite3
from datetime import datetime


def _db_path(cfg: dict) -> str:
    p = os.path.expanduser(cfg.get("db_path", "~/.taharrak/sessions.db"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def _connect(cfg: dict) -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path(cfg))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(cfg: dict):
    """Create tables if they don't exist."""
    with _connect(cfg) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at    TEXT    NOT NULL,
            exercise_key  TEXT    NOT NULL,
            exercise_name TEXT    NOT NULL,
            weight_kg     REAL    NOT NULL DEFAULT 0.0,
            sets_done     INTEGER NOT NULL DEFAULT 0,
            total_reps    INTEGER NOT NULL DEFAULT 0,
            avg_score     REAL    NOT NULL DEFAULT 0.0,
            best_score    INTEGER NOT NULL DEFAULT 0,
            duration_secs INTEGER NOT NULL DEFAULT 0,
            rating        TEXT    NOT NULL DEFAULT 'C',
            notes         TEXT    DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS rep_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id   INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            timestamp    TEXT    NOT NULL,
            side         TEXT    NOT NULL,
            set_num      INTEGER NOT NULL,
            rep_num      INTEGER NOT NULL,
            score        INTEGER NOT NULL,
            duration_s   REAL    NOT NULL,
            min_angle    REAL    NOT NULL,
            max_angle    REAL    NOT NULL,
            swing_frames INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS personal_bests (
            exercise_key   TEXT PRIMARY KEY,
            best_avg_score REAL    NOT NULL DEFAULT 0.0,
            best_rep_score INTEGER NOT NULL DEFAULT 0,
            best_reps      INTEGER NOT NULL DEFAULT 0,
            achieved_at    TEXT    NOT NULL
        );
        """)


def save_session(cfg: dict, session_data: dict, rep_rows: list) -> int:
    """Insert session + rep_log, update personal_bests. Returns session id."""
    with _connect(cfg) as conn:
        cur = conn.execute("""
            INSERT INTO sessions
              (created_at, exercise_key, exercise_name, weight_kg,
               sets_done, total_reps, avg_score, best_score,
               duration_secs, rating, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (
            session_data["created_at"],
            session_data["exercise_key"],
            session_data["exercise_name"],
            session_data["weight_kg"],
            session_data["sets_done"],
            session_data["total_reps"],
            session_data["avg_score"],
            session_data["best_score"],
            session_data["duration_secs"],
            session_data["rating"],
            session_data.get("notes", ""),
        ))
        session_id = cur.lastrowid

        if rep_rows:
            conn.executemany("""
                INSERT INTO rep_log
                  (session_id, timestamp, side, set_num, rep_num,
                   score, duration_s, min_angle, max_angle, swing_frames)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, [
                (session_id, r["timestamp"], r["side"], r["set_num"],
                 r["rep_num"], r["score"], r["duration_s"],
                 r["min_angle"], r["max_angle"], r["swing_frames"])
                for r in rep_rows
            ])

        # Update personal bests
        key        = session_data["exercise_key"]
        avg_score  = session_data["avg_score"]
        best_score = session_data["best_score"]
        total_reps = session_data["total_reps"]
        now        = session_data["created_at"]

        existing = conn.execute(
            "SELECT * FROM personal_bests WHERE exercise_key=?", (key,)
        ).fetchone()

        if existing is None:
            conn.execute("""
                INSERT INTO personal_bests
                  (exercise_key, best_avg_score, best_rep_score, best_reps, achieved_at)
                VALUES (?,?,?,?,?)
            """, (key, avg_score, best_score, total_reps, now))
        else:
            new_avg  = max(existing["best_avg_score"], avg_score)
            new_rep  = max(existing["best_rep_score"], best_score)
            new_reps = max(existing["best_reps"],      total_reps)
            conn.execute("""
                UPDATE personal_bests
                SET best_avg_score=?, best_rep_score=?, best_reps=?, achieved_at=?
                WHERE exercise_key=?
            """, (new_avg, new_rep, new_reps, now, key))

    return session_id


def get_last_sessions(cfg: dict, exercise_key: str, limit: int = 10) -> list:
    """Return last N sessions for this exercise, newest first."""
    with _connect(cfg) as conn:
        rows = conn.execute("""
            SELECT created_at, weight_kg, sets_done, total_reps,
                   avg_score, best_score, rating, duration_secs
            FROM sessions
            WHERE exercise_key=?
            ORDER BY created_at DESC
            LIMIT ?
        """, (exercise_key, limit)).fetchall()
    return [dict(r) for r in rows]


def get_last_weight(cfg: dict, exercise_key: str) -> float:
    """Return weight used in the most recent session for this exercise."""
    with _connect(cfg) as conn:
        row = conn.execute("""
            SELECT weight_kg FROM sessions
            WHERE exercise_key=?
            ORDER BY created_at DESC LIMIT 1
        """, (exercise_key,)).fetchone()
    return float(row["weight_kg"]) if row else 0.0


def check_overload_suggestion(cfg: dict, exercise_key: str, current_weight: float) -> bool:
    """
    Returns True if the last N sessions at current_weight all hit avg_score >= threshold.
    N and threshold come from config.
    """
    n         = cfg.get("overload_sessions_needed", 3)
    min_score = cfg.get("overload_min_avg_score",   75)
    with _connect(cfg) as conn:
        rows = conn.execute("""
            SELECT avg_score FROM sessions
            WHERE exercise_key=? AND ABS(weight_kg - ?) < 0.1
            ORDER BY created_at DESC LIMIT ?
        """, (exercise_key, current_weight, n)).fetchall()
    if len(rows) < n:
        return False
    return all(r["avg_score"] >= min_score for r in rows)


def get_personal_bests(cfg: dict, exercise_key: str) -> dict:
    with _connect(cfg) as conn:
        row = conn.execute(
            "SELECT * FROM personal_bests WHERE exercise_key=?", (exercise_key,)
        ).fetchone()
    if row:
        return dict(row)
    return {"best_avg_score": 0.0, "best_rep_score": 0, "best_reps": 0, "achieved_at": "—"}
