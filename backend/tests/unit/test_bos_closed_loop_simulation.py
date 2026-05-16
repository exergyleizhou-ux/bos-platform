from app.engine.bos_closed_loop_simulation import (
    ClosedLoopSimulationConfig,
    build_closed_loop_table_rows,
    run_closed_loop_simulation,
)


def test_closed_loop_simulation_returns_expected_shape():
    result = run_closed_loop_simulation(
        batch_code="BATCH-001",
        species="BSF",
        substrate="food_waste",
        dm_in=12.0,
        dm_out=3.4,
        temperature=27.5,
        moisture=68.0,
        density=1.05,
        mechanistic_context={"c_di_ser": {"information_loss": 0.11}},
        config=ClosedLoopSimulationConfig(num_cycles=4, seed=11),
    )

    assert result["mode"] == "simulation"
    assert result["summary"]["cycle_count"] == 4
    assert len(result["cycles"]) == 4
    assert result["summary"]["avg_response_time_ms"] <= 48.0
    assert result["summary"]["ser_min"] > 0
    assert result["cycles"][0]["phy_execution"]["protocol_trace"][-1] == "ENVIRONMENT.md refreshed"
    assert result["disclaimer"].startswith("This endpoint returns in-memory simulation evidence")


def test_closed_loop_simulation_is_seed_reproducible():
    config = ClosedLoopSimulationConfig(num_cycles=3, seed=19, feed_amount_g=22.5)
    first = run_closed_loop_simulation(
        batch_code="BATCH-002",
        species="BSF",
        dm_in=10.0,
        dm_out=2.5,
        temperature=28.0,
        moisture=70.0,
        density=0.95,
        config=config,
    )
    second = run_closed_loop_simulation(
        batch_code="BATCH-002",
        species="BSF",
        dm_in=10.0,
        dm_out=2.5,
        temperature=28.0,
        moisture=70.0,
        density=0.95,
        config=config,
    )

    assert first["summary"] == second["summary"]
    assert first["cycles"][0]["vision"] == second["cycles"][0]["vision"]
    assert first["cycles"][1]["prediction"] == second["cycles"][1]["prediction"]


def test_closed_loop_table_rows_are_flattened_for_supplementary_table_use():
    simulation = run_closed_loop_simulation(
        batch_code="BATCH-003",
        species="BSF",
        substrate="okara",
        dm_in=9.5,
        dm_out=2.9,
        temperature=27.0,
        moisture=66.5,
        density=1.1,
        config=ClosedLoopSimulationConfig(num_cycles=2, seed=5),
    )

    rows = build_closed_loop_table_rows(simulation)

    assert len(rows) == 2
    assert rows[0]["batch_id"] == "BATCH-003"
    assert rows[0]["species"] == "BSF"
    assert "ser_score" in rows[0]
    assert "response_time_ms" in rows[0]
    assert "watchdog_triggered" in rows[0]
    assert "audit_recorded_at" in rows[0]
