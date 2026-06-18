import os
import sys
import logging
from src.forecast.models import SeriesBatch, ForecastResult, TrendDirection
from src.forecast.baseline import BaselineForecastAdapter

logger = logging.getLogger(__name__)

HF_MODEL_ID = os.environ.get("TIMESFM_MODEL", "google/timesfm-2.0-500m-pytorch")


class TimesFMAdapter(BaselineForecastAdapter):

    def __init__(self):
        super().__init__()
        self._model = None
        self._loaded = False
        self._load_error = None
        self._baseline = BaselineForecastAdapter()

    def _load_model(self):
        if self._loaded:
            return self._model is not None
        enabled = os.environ.get("ENABLE_TIMESFM", "").lower() in ("true", "1", "yes")
        if not enabled:
            self._load_error = "ENABLE_TIMESFM not set"
            self._loaded = True
            self._model = None
            return False
        try:
            from timesfm import TimesFM_2p5_200M_torch
            import torch
            import numpy as np
        except ImportError as e:
            self._load_error = f"依赖缺失: {e}。请执行 pip install timesfm torch"
            self._loaded = True
            return False
        try:
            logger.info(f"正在从 HuggingFace Hub 加载 TimesFM 模型: {HF_MODEL_ID} (首次下载约需数分钟)...")
            self._model = TimesFM_2p5_200M_torch.from_pretrained(HF_MODEL_ID)
            self._model.compile()
            logger.info("TimesFM 模型加载完成")
            self._loaded = True
            return True
        except Exception as e:
            self._load_error = f"模型加载失败: {e}"
            self._loaded = True
            self._model = None
            return False

    def fit_or_prepare(self, series_batch: list[SeriesBatch], config: dict | None = None):
        self._load_model()

    def forecast(self, series_batch: list[SeriesBatch], horizon: int) -> list[ForecastResult]:
        if not self._load_model():
            return self._run_fallback(series_batch, horizon, self._load_error or "model not loaded")
        try:
            import numpy as np
            results = []
            for batch in series_batch:
                n = len(batch.values)
                if n < 3:
                    r = self._baseline._forecast_single(batch, horizon)
                    r.adapter_name = "timesfm"
                    r.was_fallback = True
                    r.explanation += " (TimesFM fallback: 数据不足)"
                    results.append(r)
                    continue
                inputs = [np.array(batch.values, dtype=np.float32)]
                pts, _ = self._model.forecast(horizon, inputs)
                raw = pts[0]
                point_forecast = [max(round(float(v), 1), 0) for v in raw[:horizon]]
                direction = self._compute_trend_direction(point_forecast)
                conf = self._compute_confidence(batch.values) * 0.8 + 0.2
                conf = min(conf, 1.0)
                lower = [max(round(float(v) * 0.8, 1), 0) for v in point_forecast]
                upper = [round(float(v) * 1.2, 1) for v in point_forecast]
                anomaly_flags = self.detect_anomaly_single(batch.values)
                r = ForecastResult(
                    entity_type=batch.entity_type,
                    entity_id=batch.entity_id,
                    metric_name=batch.metric_name,
                    horizon_days=horizon,
                    point_forecast=point_forecast,
                    lower_bound=lower,
                    upper_bound=upper,
                    trend_direction=direction,
                    trend_confidence=round(conf, 2),
                    anomaly_flags=anomaly_flags,
                    explanation="",
                    adapter_name="timesfm",
                )
                r.explanation = self.explain_forecast(r)
                results.append(r)
            return results
        except Exception as e:
            return self._run_fallback(series_batch, horizon, str(e))

    def _run_fallback(self, series_batch, horizon, reason):
        results = []
        for batch in series_batch:
            r = self._baseline._forecast_single(batch, horizon)
            r.adapter_name = "timesfm"
            r.was_fallback = True
            r.explanation += f" (TimesFM fallback: {reason})"
            results.append(r)
        return results

    def explain_forecast(self, result: ForecastResult) -> str:
        base = self._baseline.explain_forecast(result)
        if result.was_fallback:
            base += " (Baseline模式)"
        else:
            base += " (TimesFM模型)"
        return base
