from types import SimpleNamespace

from app.services.chronos_risk_service import forecast_with_chronos_or_fallback


def test_chronos_risk_service_returns_forecast_with_fallback_contract():
    batch = SimpleNamespace(
        id=77,
        batch_id="RISK-77",
        species="BSF",
        temperature=28.0,
        moisture=66.0,
        feed_rate=1.2,
        density=3.5,
    )

    result = forecast_with_chronos_or_fallback(
        sensor_history=[0.2, 0.24, 0.25, 0.27],
        horizon=3,
        metric_name="batch_ser_risk",
        batch=batch,
    )

    assert result.model_name == "chronos_bolt"
    assert result.execution_mode in {
        "chronos_bolt_live",
        "bos_fallback_projection",
        "heuristic_exception_fallback",
    }
    assert len(result.forecast) == 3
    assert result.confidence_band[0] <= result.confidence_band[1]

