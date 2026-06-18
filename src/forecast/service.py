import sqlite3
from datetime import datetime, timezone
from src.config import settings
from src.forecast.models import SeriesBatch, ForecastResult
from src.forecast.adapter import ForecastAdapter
from src.forecast.baseline import BaselineForecastAdapter
from src.forecast.timesfm_adapter import TimesFMAdapter
from src.forecast.database import (
    init_forecast_tables, get_historical_metrics, insert_historical_metric,
    save_forecast, get_latest_forecasts,
)


class ForecastService:

    def __init__(self):
        self._baseline = BaselineForecastAdapter()
        self._timesfm = TimesFMAdapter()
        self._conn = None

    @property
    def conn(self):
        if self._conn is None:
            self._conn = sqlite3.connect(str(settings.db_path))
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def get_adapter(self, prefer_timesfm: bool = False) -> ForecastAdapter:
        if prefer_timesfm:
            self._timesfm.fit_or_prepare([])
            if self._timesfm._model is not None:
                return self._timesfm
        return self._baseline

    def forecast_series(self, series_batch: list[SeriesBatch],
                         horizon: int = 30,
                         prefer_timesfm: bool = False) -> list[ForecastResult]:
        adapter = self.get_adapter(prefer_timesfm)
        adapter.fit_or_prepare(series_batch)
        results = adapter.forecast(series_batch, horizon)
        for r in results:
            adapter_name = "timesfm" if isinstance(adapter, TimesFMAdapter) and not r.was_fallback else "baseline"
            save_forecast(
                self.conn,
                entity_type=r.entity_type,
                entity_id=r.entity_id,
                metric_name=r.metric_name,
                horizon_days=r.horizon_days,
                forecast_json={
                    "point_forecast": r.point_forecast,
                    "lower_bound": r.lower_bound,
                    "upper_bound": r.upper_bound,
                },
                trend_direction=r.trend_direction.value,
                trend_confidence=r.trend_confidence,
                anomaly_flags=r.anomaly_flags,
                adapter_name=adapter_name,
                was_fallback=r.was_fallback,
            )
        self.conn.commit()
        return results

    def load_metrics(self, entity_type: str, entity_id: str,
                      metric_names: list[str], limit: int = 90) -> list[SeriesBatch]:
        batches = []
        for m in metric_names:
            ts, vs = get_historical_metrics(self.conn, entity_type, entity_id, m, limit=limit)
            if ts:
                batches.append(SeriesBatch(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    metric_name=m,
                    timestamps=ts,
                    values=vs,
                    frequency="daily",
                    source="scraper",
                ))
        return batches

    def get_forecast_for_entity(self, entity_type: str, entity_id: str):
        return get_latest_forecasts(self.conn, entity_type, entity_id)

    def store_metrics(self, entity_type: str, entity_id: str,
                       metric_name: str, timestamps: list[str],
                       values: list[float], source: str = "scraper"):
        for ts, val in zip(timestamps, values):
            insert_historical_metric(
                self.conn, entity_type, entity_id, metric_name, ts, val, source=source
            )
        self.conn.commit()
