import math
from abc import ABC, abstractmethod
from src.forecast.models import SeriesBatch, ForecastResult, TrendDirection


class ForecastAdapter(ABC):

    @abstractmethod
    def fit_or_prepare(self, series_batch: list[SeriesBatch], config: dict | None = None):
        raise NotImplementedError

    @abstractmethod
    def forecast(self, series_batch: list[SeriesBatch], horizon: int) -> list[ForecastResult]:
        raise NotImplementedError

    @abstractmethod
    def detect_anomaly(self, series_batch: list[SeriesBatch]) -> list[list[str]]:
        raise NotImplementedError

    @abstractmethod
    def explain_forecast(self, result: ForecastResult) -> str:
        raise NotImplementedError

    @classmethod
    def _trend_window(cls, values: list[float]) -> list[float]:
        """Use recent window for trend: min(last 30, or 50% of data)."""
        if len(values) < 7:
            return values
        window = min(30, max(7, len(values) // 2))
        return values[-window:]

    @classmethod
    def _compute_trend_direction(cls, values: list[float]) -> TrendDirection:
        if len(values) < 3:
            return TrendDirection.flat
        recent = cls._trend_window(values)
        n = len(recent)
        x = list(range(n))
        y = recent
        sx = sum(x)
        sy = sum(y)
        sxx = sum(xi * xi for xi in x)
        sxy = sum(xi * yi for xi, yi in zip(x, y))
        denom = n * sxx - sx * sx
        if denom == 0:
            return TrendDirection.flat
        slope = (n * sxy - sx * sy) / denom

        residuals = [y[i] - (slope * x[i] + (sy - slope * sx) / n) for i in range(n)]
        mse = sum(r * r for r in residuals) / n if n else 0
        mean_y = sy / n if n else 1
        cv = math.sqrt(mse) / max(mean_y, 1)

        if cv > 0.4:
            return TrendDirection.volatile
        if slope > 0.01 * mean_y:
            return TrendDirection.rising
        if slope < -0.01 * mean_y:
            return TrendDirection.falling
        return TrendDirection.flat

    @classmethod
    def _compute_confidence(cls, values: list[float]) -> float:
        if len(values) < 3:
            return 0.3
        recent = cls._trend_window(values)
        n = len(recent)
        x = list(range(n))
        y = recent
        sx = sum(x)
        sy = sum(y)
        sxx = sum(xi * xi for xi in x)
        syy = sum(yi * yi for yi in y)
        sxy = sum(xi * yi for xi, yi in zip(x, y))

        denom = math.sqrt((n * sxx - sx * sx) * (n * syy - sy * sy))
        if denom == 0:
            return 0.3
        r = (n * sxy - sx * sy) / denom
        return max(0.0, min(1.0, abs(r)))
