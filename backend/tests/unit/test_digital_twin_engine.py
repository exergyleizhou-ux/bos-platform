"""
BOS Pipeline v9.0 digital twin engine unit tests.
"""

import pytest

from app.engine.digital_twin_engine import ENGINE_VERSION, TwinConfig, TwinState, run_twin_simulation, step_twin


class TestDigitalTwinEngine:
    """Tests for the digital twin simulation engine."""

    def test_single_step(self):
        """Single time step produces a valid next state."""
        config = TwinConfig()
        state = TwinState(biomass=1.0, substrate=10.0, temperature=28.0, moisture=70.0)

        next_state = step_twin(state, config, dt=1.0)

        assert next_state.biomass >= 0
        assert next_state.substrate >= 0
        assert next_state.temperature > 0
        assert next_state.moisture >= 0
        assert next_state.time == state.time + 1.0

    def test_biomass_growth(self):
        """Biomass should increase when substrate is available and conditions are good."""
        config = TwinConfig()
        state = TwinState(biomass=1.0, substrate=10.0, temperature=28.0, moisture=70.0)

        next_state = step_twin(state, config, dt=1.0)
        assert next_state.biomass > state.biomass

    def test_substrate_consumption(self):
        """Substrate should decrease as biomass grows."""
        config = TwinConfig()
        state = TwinState(biomass=1.0, substrate=10.0, temperature=28.0, moisture=70.0)

        next_state = step_twin(state, config, dt=1.0)
        assert next_state.substrate < state.substrate

    def test_zero_substrate(self):
        """Zero substrate leads to negligible or negative growth."""
        config = TwinConfig()
        state = TwinState(biomass=1.0, substrate=0.0, temperature=28.0, moisture=70.0)

        next_state = step_twin(state, config, dt=1.0)
        assert next_state.biomass <= state.biomass + 0.01

    def test_extreme_temperature(self):
        """Extreme temperature should inhibit growth relative to optimal conditions."""
        config = TwinConfig()
        cold_state = TwinState(biomass=1.0, substrate=10.0, temperature=5.0, moisture=70.0)
        optimal_state = TwinState(biomass=1.0, substrate=10.0, temperature=28.0, moisture=70.0)

        next_cold = step_twin(cold_state, config, dt=1.0)
        next_optimal = step_twin(optimal_state, config, dt=1.0)

        assert next_cold.biomass < next_optimal.biomass

    def test_run_simulation(self):
        """Run multi-step simulation and return the full trajectory."""
        config = TwinConfig()
        initial = TwinState(biomass=0.5, substrate=10.0, temperature=28.0, moisture=70.0)

        trajectory = run_twin_simulation(initial, config, n_steps=100, dt=1.0)

        assert len(trajectory) == 101
        assert trajectory[0].biomass == 0.5
        assert trajectory[-1].time == pytest.approx(100.0)

    def test_simulation_mass_conservation(self):
        """Total mass should remain within a reasonable physical range."""
        config = TwinConfig()
        initial = TwinState(biomass=0.5, substrate=10.0, temperature=28.0, moisture=70.0)

        trajectory = run_twin_simulation(initial, config, n_steps=50, dt=1.0)

        initial_mass = initial.biomass + initial.substrate
        final = trajectory[-1]
        final_mass = final.biomass + final.substrate + getattr(final, "frass", 0)

        assert final_mass >= initial_mass * 0.5

    def test_temperature_dynamics(self):
        """Temperature should relax toward the environment temperature."""
        config = TwinConfig(T_env=30.0)
        state = TwinState(biomass=1.0, substrate=10.0, temperature=20.0, moisture=70.0)

        next_state = step_twin(state, config, dt=1.0)
        assert next_state.temperature > state.temperature

    def test_moisture_dynamics(self):
        """Moisture should relax toward the environment moisture."""
        config = TwinConfig(M_env=75.0)
        state = TwinState(biomass=1.0, substrate=10.0, temperature=28.0, moisture=60.0)

        next_state = step_twin(state, config, dt=1.0)
        assert next_state.moisture > state.moisture
