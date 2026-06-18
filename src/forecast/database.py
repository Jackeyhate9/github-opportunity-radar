import json
import sqlite3
from datetime import datetime, timezone
from src.config import settings


def init_forecast_tables(conn: sqlite3.Connection | None = None):
    if conn is None:
        conn = sqlite3.connect(str(settings.db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS historical_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            value REAL NOT NULL,
            source TEXT DEFAULT 'scraper',
            quality_flags TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_hm_entity
            ON historical_metrics(entity_type, entity_id, metric_name);
        CREATE INDEX IF NOT EXISTS idx_hm_ts
            ON historical_metrics(entity_type, entity_id, metric_name, timestamp);

        CREATE TABLE IF NOT EXISTS metric_forecasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            horizon_days INTEGER NOT NULL,
            forecast_json TEXT NOT NULL,
            trend_direction TEXT DEFAULT '',
            trend_confidence REAL DEFAULT 0,
            anomaly_flags TEXT DEFAULT '',
            adapter_name TEXT DEFAULT 'baseline',
            was_fallback INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_mf_entity
            ON metric_forecasts(entity_type, entity_id, metric_name);
    """)
    conn.commit()


def insert_historical_metric(conn, entity_type, entity_id, metric_name,
                              timestamp, value, source="scraper", quality_flags=""):
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO historical_metrics
           (entity_type, entity_id, metric_name, timestamp, value, source, quality_flags, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (entity_type, entity_id, metric_name, timestamp, value, source, quality_flags, now)
    )


def get_historical_metrics(conn, entity_type, entity_id, metric_name,
                            limit=90):
    cur = conn.execute(
        """SELECT timestamp, value FROM historical_metrics
           WHERE entity_type=? AND entity_id=? AND metric_name=?
           ORDER BY timestamp ASC LIMIT ?""",
        (entity_type, entity_id, metric_name, limit)
    )
    rows = cur.fetchall()
    timestamps = [r["timestamp"] for r in rows]
    values = [r["value"] for r in rows]
    return timestamps, values


def save_forecast(conn, entity_type, entity_id, metric_name,
                   horizon_days, forecast_json, trend_direction,
                   trend_confidence, anomaly_flags, adapter_name, was_fallback):
    now = datetime.now(timezone.utc).isoformat()
    flags_str = ",".join(anomaly_flags) if isinstance(anomaly_flags, list) else anomaly_flags
    conn.execute(
        """INSERT INTO metric_forecasts
           (entity_type, entity_id, metric_name, horizon_days, forecast_json,
            trend_direction, trend_confidence, anomaly_flags, adapter_name, was_fallback, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (entity_type, entity_id, metric_name, horizon_days,
         json.dumps(forecast_json, ensure_ascii=False),
         trend_direction, trend_confidence, flags_str, adapter_name,
         1 if was_fallback else 0, now)
    )


def get_latest_forecasts(conn, entity_type, entity_id):
    cur = conn.execute(
        """SELECT * FROM metric_forecasts
           WHERE entity_type=? AND entity_id=?
           ORDER BY created_at DESC""",
        (entity_type, entity_id)
    )
    rows = cur.fetchall()
    results = []
    for r in rows:
        d = dict(r)
        try:
            d["forecast_json"] = json.loads(d["forecast_json"])
        except (json.JSONDecodeError, TypeError):
            pass
        results.append(d)
    return results
