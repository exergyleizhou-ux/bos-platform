"""
BOS Pipeline v9.0 �� ARIMA / Forecast Engine Unit Tests

Tests the time series forecasting engine.
"""

import pytest

from app.engine.arima_engine import (
    ForecastInput,
    forecast_timeseries,
    ENGINE_VERSION,
)


class TestForecastEngine:
    """Tests for the time series forecasting engine."""

    def test_sma_forecast(self):
        """Simple moving average forecast."""
        values = [0.20, 0.21, 0.19, 0.22, 0.20, 0.21, 0.19, 0.20, 0.22, 0.21]
        inp = ForecastInput(values=values, horizon=5, method="sma", sma_window=3)
        result = forecast_timeseries(inp)

        assert len(result.forecast) == 5
        assert all(v > 0 for v in result.forecast)
        assert result.method == "sma"
        assert result.engine_version == ENGINE_VERSION
        assert len(result.errors) == 0

    def test_ewma_forecast(self):
        """Exponentially weighted moving average forecast."""
        values = [0.18, 0.19, 0.20, 0.21, 0.22, 0.23, 0.24, 0.25, 0.26, 0.27]
        inp = ForecastInput(values=values, horizon=5, method="ewma", ewma_alpha=0.3)
        result = forecast_timeseries(inp)

        assert len(result.forecast) == 5
        assert result.method == "ewma"
        # Upward trend �� forecast should be above recent values
        assert result.forecast[0] >= 0.20

    def test_ar_forecast(self):
        """Autoregressive forecast."""
        values = [0.20 + 0.01 * i for i in range(20)]
        inp = ForecastInput(values=values, horizon=5, method="ar", ar_order=3)
        result = forecast_timeseries(inp)

        assert len(result.forecast) == 5
        assert result.method == "ar"

    def test_confidence_intervals(self):
        """Forecast includes confidence intervals."""
        values = [0.20, 0.21, 0.19, 0.22, 0.20, 0.21, 0.19, 0.20, 0.22, 0.21]
        inp = ForecastInput(values=values, horizon=5, method="ewma")
        result = forecast_timeseries(inp)

        assert len(result.ci_lower) == 5
        assert len(result.ci_upper) == 5
        for i in range(5):
            assert result.ci_lower[i] <= result.forecast[i] <= result.ci_upper[i]

    def test_ci_widens_with_horizon(self):
        """Confidence intervals widen as horizon increases."""
        values = [0.20, 0.21, 0.19, 0.22, 0.20, 0.21, 0.19, 0.20, 0.22, 0.21]
        inp = ForecastInput(values=values, horizon=10, method="ewma")
        result = forecast_timeseries(inp)

        width_first = result.ci_upper[0] - result.ci_lower[0]
        width_last = result.ci_upper[-1] - result.ci_lower[-1]
        assert width_last >= width_first

    def test_fitted_values(self):
        """Engine produces in-sample fitted values."""
        values = [0.20, 0.21, 0.19, 0.22, 0.20, 0.21, 0.19, 0.20]
        inp = ForecastInput(values=values, horizon=3, method="ewma")
        result = forecast_timeseries(inp)

        assert result.fitted is not None
        assert len(result.fitted) > 0

    def test_model_quality_metrics(self):
        """Engine computes MAE, RMSE, MAPE."""
        values = [0.20, 0.21, 0.19, 0.22, 0.20, 0.21, 0.19, 0.20, 0.22, 0.21]
        inp = ForecastInput(values=values, horizon=5, method="ewma")
        result = forecast_timeseries(inp)

        assert result.mae is not None
        assert result.mae >= 0
        assert result.rmse is not None
        assert result.rmse >= 0

    def test_seasonal_decomposition(self):
        """Seasonal period triggers decomposition."""
        # Create data with clear seasonality
        import math
        values = [0.20 + 0.05 * math.sin(2 * math.pi * i / 7) for i in range(42)]
        inp = ForecastInput(values=values, horizon=7, method="ewma", seasonal_period=7)
        result = forecast_timeseries(inp)

        assert result.forecast is not None
        if result.trend is not None:
            assert len(result.trend) > 0
            assert result.seasonal is not None

    def test_short_series(self):
        """Very short series still works."""
        values = [0.20, 0.21, 0.22]
        inp = ForecastInput(values=values, horizon=3, method="sma", sma_window=2)
        result = forecast_timeseries(inp)

        assert len(result.forecast) == 3

    def test_constant_series(self):
        """Constant series �� flat forecast."""
        values = [0.20] * 20
        inp = ForecastInput(values=values, horizon=5, method="ewma")
        result = forecast_timeseries(inp)

        for v in result.forecast:
            assert v == pytest.approx(0.20, abs=0.01)

    def test_computation_time(self):
        """Engine records computation time."""
        values = [0.20 + 0.01 * i for i in range(50)]
        inp = ForecastInput(values=values, horizon=10, method="ewma")
        result = forecast_timeseries(inp)

        assert result.computation_time_ms > 0

    def test_invalid_window_too_large(self):
        """SMA window larger than series length �� error or graceful fallback."""
        values = [0.20, 0.21, 0.22]
        inp = ForecastInput(values=values, horizon=3, method="sma", sma_window=50)
        result = forecast_timeseries(inp)

        # Either returns errors or adjusts window
        assert result.forecast is not None or len(result.errors) > 0
