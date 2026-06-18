from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class TrendDirection(str, Enum):
    rising = "rising"
    falling = "falling"
    flat = "flat"
    volatile = "volatile"


class TrendLabel(str, Enum):
    heating_up = "heating_up"
    cooling_down = "cooling_down"
    stable = "stable"
    noisy = "noisy"
    insufficient_data = "insufficient_data"


@dataclass
class SeriesPoint:
    timestamp: str
    value: float


@dataclass
class SeriesBatch:
    entity_type: str
    entity_id: str
    metric_name: str
    timestamps: list[str]
    values: list[float]
    frequency: str = "daily"
    source: str = "scraper"
    quality_flags: list[str] = field(default_factory=list)

    def to_points(self) -> list[SeriesPoint]:
        return [SeriesPoint(t, v) for t, v in zip(self.timestamps, self.values)]

    @property
    def length(self) -> int:
        return len(self.timestamps)

    @property
    def is_empty(self) -> bool:
        return self.length == 0


@dataclass
class ForecastResult:
    entity_type: str
    entity_id: str
    metric_name: str
    horizon_days: int
    point_forecast: list[float]
    lower_bound: list[float]
    upper_bound: list[float]
    trend_direction: TrendDirection
    trend_confidence: float
    anomaly_flags: list[str]
    explanation: str
    adapter_name: str
    was_fallback: bool = False
    insufficient_history: bool = False


@dataclass
class ForecastFeatures:
    forecast_growth_7d: float = 0.0
    forecast_growth_14d: float = 0.0
    forecast_growth_30d: float = 0.0
    forecast_acceleration: float = 0.0
    forecast_volatility: float = 0.0
    forecast_confidence: float = 0.0
    anomaly_score: float = 0.0
    trend_label: TrendLabel = TrendLabel.insufficient_data
    explanation: str = ""


@dataclass
class ForecastSignal:
    forecast_signal_score: float = 50.0
    score_delta_reason: str = ""
