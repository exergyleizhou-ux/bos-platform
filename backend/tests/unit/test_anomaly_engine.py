"""
BOS Pipeline v9.0 -Anomaly Detection Engine Unit Tests

Tests the statistical anomaly detection engine.
"""

import pytest

from app.engine.anomaly_engine import (
    AnomalyInput,
    detect_anomalies,
    ENGINE_VERSION,
)


class TestAnomalyEngine:
    """Tests for the anomaly detection engine."""

    def test_no_anomalies(self):
        """Normal data - no anomalies detected."""
        values = [
            0.20,
            0.21,
            0.19,
            0.20,
            0.21,
            0.20,
            0.19,
            0.20,
            0.21,
            0.20,
            0.19,
            0.20,
            0.21,
            0.20,
            0.19,
            0.20,
            0.21,
            0.20,
            0.19,
            0.20,
        ]
        inp = AnomalyInput(values=values, method="zscore")
        result = detect_anomalies(inp)

        assert result.anomaly_count == 0
        assert result.engine_version == ENGINE_VERSION

    def test_obvious_outlier(self):
        """Single extreme value is detected."""
        values = [
            0.20,
            0.21,
            0.19,
            0.20,
            0.21,
            0.20,
            0.19,
            0.20,
            0.21,
            0.20,
            0.19,
            0.20,
            0.21,
            0.20,
            0.19,
            0.20,
            0.21,
            0.20,
            0.19,
            5.00,
        ]  # Outlier
        inp = AnomalyInput(values=values, method="zscore")
        result = detect_anomalies(inp)

        assert result.anomaly_count >= 1
        assert result.anomaly_indices[-1] == 19  # Last element

    def test_iqr_method(self):
        """IQR method detects outliers."""
        values = [0.20] * 19 + [5.00]
        inp = AnomalyInput(values=values, method="iqr")
        result = detect_anomalies(inp)

        assert result.anomaly_count >= 1

    def test_modified_zscore(self):
        """Modified Z-score (MAD-based) method."""
        values = [0.20] * 19 + [5.00]
        inp = AnomalyInput(values=values, method="modified_zscore")
        result = detect_anomalies(inp)

        assert result.anomaly_count >= 1

    def test_isolation_forest(self):
        """Isolation forest method (if available)."""
        values = [0.20 + 0.01 * (i % 5) for i in range(30)] + [5.00]
        inp = AnomalyInput(values=values, method="isolation_forest", contamination=0.05)

        try:
            result = detect_anomalies(inp)
            assert result.anomaly_count >= 1
        except (ImportError, NotImplementedError):
            pytest.skip("Isolation forest not available (requires sklearn)")

    def test_custom_threshold(self):
        """Custom threshold changes sensitivity."""
        values = [0.20, 0.21, 0.19, 0.20, 0.28, 0.20, 0.19, 0.20, 0.21, 0.20]

        # Strict threshold - more anomalies
        result_strict = detect_anomalies(AnomalyInput(values=values, method="zscore", zscore_threshold=1.5))
        # Lenient threshold - fewer anomalies
        result_lenient = detect_anomalies(AnomalyInput(values=values, method="zscore", zscore_threshold=4.0))

        assert result_strict.anomaly_count >= result_lenient.anomaly_count

    def test_anomaly_details(self):
        """Each anomaly has index, value, and score."""
        values = [0.20] * 19 + [5.00]
        inp = AnomalyInput(values=values, method="zscore")
        result = detect_anomalies(inp)

        assert len(result.anomalies) >= 1
        anomaly = result.anomalies[0]
        assert "index" in anomaly
        assert "value" in anomaly
        assert "score" in anomaly

    def test_statistics_output(self):
        """Result includes descriptive statistics."""
        values = [0.20, 0.21, 0.19, 0.22, 0.20, 0.21, 0.19, 0.20, 0.22, 0.21]
        inp = AnomalyInput(values=values, method="zscore")
        result = detect_anomalies(inp)

        assert result.mean is not None
        assert result.std is not None
        assert result.median is not None

    def test_short_series(self):
        """Very short series handled gracefully."""
        values = [0.20, 0.21]
        inp = AnomalyInput(values=values, method="zscore")
        result = detect_anomalies(inp)

        # Should not crash; may return zero anomalies
        assert result is not None

    def test_constant_series(self):
        """Constant series - zero std - no anomalies (or special handling)."""
        values = [0.20] * 20
        inp = AnomalyInput(values=values, method="zscore")
        result = detect_anomalies(inp)

        assert result.anomaly_count == 0

    def test_trend_detection(self):
        """Gradual trend is not flagged as anomaly by default."""
        values = [0.20 + 0.005 * i for i in range(30)]
        inp = AnomalyInput(values=values, method="zscore")
        result = detect_anomalies(inp)

        # Smooth trend should not trigger anomalies
        assert result.anomaly_count == 0

    def test_deterministic(self):
        """Same input always produces same output (for deterministic methods)."""
        values = [0.20] * 19 + [5.00]
        inp = AnomalyInput(values=values, method="zscore")
        r1 = detect_anomalies(inp)
        r2 = detect_anomalies(inp)

        assert r1.anomaly_count == r2.anomaly_count
        assert r1.anomaly_indices == r2.anomaly_indices
