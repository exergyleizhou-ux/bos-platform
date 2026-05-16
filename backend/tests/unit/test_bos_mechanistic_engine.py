from app.engine.bos_mechanistic_engine import (
    analytic_handover_envelope,
    build_compile_diagnostics,
    compute_c_di_ser,
)


def test_compute_c_di_ser_penalizes_information_loss_and_adapts_balance():
    high_quality = compute_c_di_ser(d_prime=0.24, g_prime=0.5, information_loss=0.05)
    low_quality = compute_c_di_ser(d_prime=0.24, g_prime=0.5, information_loss=0.6)
    d_dominant = compute_c_di_ser(d_prime=0.8, g_prime=0.2, information_loss=0.05)

    assert high_quality.c_di_ser > low_quality.c_di_ser
    assert 0.35 <= high_quality.alpha_s <= 0.65
    assert d_dominant.alpha_s > high_quality.alpha_s
    assert round(high_quality.alpha_s + high_quality.beta_s, 4) == 1.0


def test_analytic_handover_envelope_returns_interior_peak():
    envelope = analytic_handover_envelope(
        c_max=1.4,
        alpha_c=0.035,
        k_decay=0.005,
        eta_comp=0.004,
        competition_pressure=1.2,
    )

    assert envelope.tau_star_minutes > 0
    assert 0 < envelope.c_peak <= 1.4
    assert envelope.clock_frequency_per_minute > 0
    assert envelope.decay_rate > 0


def test_build_compile_diagnostics_returns_serializable_mechanistic_context():
    diagnostics = build_compile_diagnostics(
        dm_in=10.0,
        dm_out=3.2,
        potency=0.21,
        stability_window_hours=8.0,
        metering_completeness=0.86,
        locality_shift_pct=12.0,
    )

    assert diagnostics["c_di_ser"]["score"] > 0
    assert diagnostics["handover_envelope"]["tau_star_min"] > 0
    assert diagnostics["inputs"]["mass_balance_ratio"] == 0.32
    assert diagnostics["c_di_ser"]["information_loss"] < 1.0
