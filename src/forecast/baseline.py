import math
import statistics
from src.forecast.models import SeriesBatch, ForecastResult, TrendDirection
from src.forecast.adapter import ForecastAdapter


class BaselineForecastAdapter(ForecastAdapter):

    def __init__(self):
        self._prepared = False

    def fit_or_prepare(self, series_batch: list[SeriesBatch], config: dict | None = None):
        self._prepared = True

    def forecast(self, series_batch: list[SeriesBatch], horizon: int) -> list[ForecastResult]:
        results = []
        for batch in series_batch:
            r = self._forecast_single(batch, horizon)
            r.explanation = self.explain_forecast(r)
            results.append(r)
        return results

    def _forecast_single(self, batch: SeriesBatch, horizon: int) -> ForecastResult:
        values = batch.values
        n = len(values)
        if n < 2:
            return ForecastResult(
                entity_type=batch.entity_type,
                entity_id=batch.entity_id,
                metric_name=batch.metric_name,
                horizon_days=horizon,
                point_forecast=[0.0] * horizon,
                lower_bound=[0.0] * horizon,
                upper_bound=[0.0] * horizon,
                trend_direction=TrendDirection.flat,
                trend_confidence=0.0,
                anomaly_flags=[],
                explanation="数据不足 (仅1条记录，无法预测)",
                adapter_name="baseline",
                insufficient_history=True,
            )

        last_val = values[-1]

        if n < 5:
            std = statistics.pstdev(values) if n >= 2 else last_val * 0.2
            point_forecast = [round(last_val, 1)] * horizon
            lower_bound = [round(max(last_val - 1.96 * std, 0), 1) for _ in range(horizon)]
            upper_bound = [round(last_val + 1.96 * std, 1) for _ in range(horizon)]
            trend_dir = TrendDirection.flat
            conf = 0.3
            return ForecastResult(
                entity_type=batch.entity_type,
                entity_id=batch.entity_id,
                metric_name=batch.metric_name,
                horizon_days=horizon,
                point_forecast=point_forecast[:horizon],
                lower_bound=lower_bound[:horizon],
                upper_bound=upper_bound[:horizon],
                trend_direction=trend_dir,
                trend_confidence=round(conf, 2),
                anomaly_flags=[],
                explanation="历史数据偏少 ({} 条)，预测参考价值有限".format(n),
                adapter_name="baseline",
                insufficient_history=n < 3,
            )

        ma_window = min(n, 7)
        ma = sum(values[-ma_window:]) / ma_window

        recent_vals = values[-(min(30, len(values))):]
        rn = len(recent_vals)
        xr = list(range(rn))
        yr = recent_vals
        sxr = sum(xr)
        syr = sum(yr)
        sxxr = sum(xi * xi for xi in xr)
        sxyr = sum(xi * yi for xi, yi in zip(xr, yr))
        slope = (rn * sxyr - sxr * syr) / max(rn * sxxr - sxr * sxr, 1)

        trend_dir = self._compute_trend_direction(values)
        conf = self._compute_confidence(values)

        use_exponential = "exponential" if n >= 5 else "linear"
        point_forecast = []
        lower_bound = []
        upper_bound = []

        if use_exponential == "exponential":
            alpha = 0.3
            smoothed = values[0]
            for v in values:
                smoothed = alpha * v + (1 - alpha) * smoothed
            base = smoothed
            for i in range(1, horizon + 1):
                pred = base + slope * i * 0.5
                pred = max(pred, 0)
                point_forecast.append(round(pred, 1))
        else:
            base = last_val
            for i in range(1, horizon + 1):
                pred = base + slope * i
                pred = max(pred, 0)
                point_forecast.append(round(pred, 1))

        std = statistics.pstdev(values) if n >= 2 else last_val * 0.1
        for pf in point_forecast:
            lower_bound.append(round(max(pf - 1.96 * std, 0), 1))
            upper_bound.append(round(pf + 1.96 * std, 1))

        anomaly_flags = self.detect_anomaly_single(values)

        return ForecastResult(
            entity_type=batch.entity_type,
            entity_id=batch.entity_id,
            metric_name=batch.metric_name,
            horizon_days=horizon,
            point_forecast=point_forecast[:horizon],
            lower_bound=lower_bound[:horizon],
            upper_bound=upper_bound[:horizon],
            trend_direction=trend_dir,
            trend_confidence=round(conf, 2),
            anomaly_flags=anomaly_flags,
            explanation="",
            adapter_name="baseline",
            was_fallback=False,
            insufficient_history=False,
        )

    def detect_anomaly(self, series_batch: list[SeriesBatch]) -> list[list[str]]:
        return [self.detect_anomaly_single(b.values) for b in series_batch]

    def detect_anomaly_single(self, values: list[float]) -> list[str]:
        flags = []
        if len(values) < 3:
            return flags
        mean_val = statistics.mean(values)
        std = statistics.pstdev(values) if len(values) >= 2 else mean_val * 0.1
        if std == 0:
            return flags
        last = values[-1]
        if abs(last - mean_val) > 2.5 * std:
            flags.append("spike")
        second_last = values[-2] if len(values) >= 2 else None
        if second_last is not None and second_last > 0:
            ratio = last / second_last
            if ratio > 2.0:
                flags.append("sudden_surge" if ratio > 1 else "sudden_drop")
            elif ratio < 0.5:
                flags.append("sudden_drop")
        return flags

    def explain_forecast(self, result: ForecastResult) -> str:
        if result.insufficient_history:
            return f"「{result.metric_name}」历史数据不足，无法预测"
        parts = []
        dir_map = {
            TrendDirection.rising: "上升",
            TrendDirection.falling: "下降",
            TrendDirection.flat: "平稳",
            TrendDirection.volatile: "波动大",
        }
        dir_cn = dir_map.get(result.trend_direction, "未知")
        parts.append(f"未来 {result.horizon_days} 天预计{dir_cn}")
        conf_pct = int(result.trend_confidence * 100)
        parts.append(f"置信度 {conf_pct}%")
        if result.anomaly_flags:
            parts.append(f"异常标记: {', '.join(result.anomaly_flags)}")
        return "，".join(parts)
