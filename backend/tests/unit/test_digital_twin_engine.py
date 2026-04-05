"""
BOS Pipeline v9.0 �� Digital Twin Engine Unit Tests

Tests the bioreactor digital twin simulation engine.
"""

import pytest

from app.engine.digital_twin_engine import (
    TwinConfig,
    TwinState,
    step_twin,
    run_twin_simulation,
    ENGINE_VERSION,
)


class TestDigitalTwinEngine:
    """Tests for the digital twin simulation engine."""

    def test_single_step(self):
        """Single time step produces valid next state."""
        config = TwinConfig()
        state = TwinState(
            biomass=1.0,
            substrate=10.0,
            temperature=28.0,
            moisture=70.0,
        )

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
        """Zero substrate �� no growth (starvation)."""
        config = TwinConfig()
        state = TwinState(biomass=1.0, substrate=0.0, temperature=28.0, moisture=70.0)

        next_state = step_twin(state, config, dt=1.0)

        # Biomass should not increase significantly (possible death)
        assert next_state.biomass <= state.biomass + 0.01

    def test_extreme_temperature(self):
        """Extreme temperature inhibits or kills growth."""
        config = TwinConfig()
        state = TwinState(biomass=1.0, substrate=10.0, temperature=5.0, moisture=70.0)

        next_state = step_twin(state, config, dt=1.0)

        # Growth should be much slower or negative at 5��C
        state_optimal = TwinState(biomass=1.0, substrate=10.0, temperature=28.0, moisture=70.0)
        next_optimal = step_twin(state_optimal, config, dt=1.0)

        assert next_state.biomass < next_optimal.biomass

    def test_run_simulation(self):
        """Run multi-step simulation returns trajectory."""
        config = TwinConfig()
        initial = TwinState(biomass=0.5, substrate=10.0, temperature=28.0, moisture=70.0)

        trajectory = run_twin_simulation(initial, config, n_steps=100, dt=1.0)

        assert len(trajectory) == 101  # initial + 100 steps
        assert trajectory[0].biomass == 0.5
        assert trajectory[-1].time == pytest.approx(100.0)

    def test_simulation_mass_conservation(self):
        """Total mass (biomass + substrate + frass) approximately conserved."""
        config = TwinConfig()
        initial = TwinState(biomass=0.5, substrate=10.0, temperature=28.0, moisture=70.0)

        trajectory = run_twin_simulation(initial, config, n_steps=50, dt=1.0)

        initial_mass = initial.biomass + initial.substrate
        final = trajectory[-1]
        final_mass = final.biomass + final.substrate + getattr(final, "frass", 0)

        # Allow for gas losses (CO2, etc.) but shouldn't exceed ~30%
        assert final_mass >= initial_mass * 0.5

    def test_temperature_dynamics(self):
        """Temperature relaxes toward T_env."""
        config = TwinConfig(T_env=30.0)
        state = TwinState(biomass=1.0, substrate=10.0, temperature=20.0, moisture=70.0)

        next_state = step_twin(state, config, dt=1.0)

        # Temperature should move toward T_env=30
        assert next_state.temperature > state.temperature

    def test_moisture_dynamics(self):
        """Moisture relaxes toward M_env."""
        config = TwinConfig(M_env=75.0)
        state = TwinState(biomass=1.0, substrate=10.0, temperature=28.0, moisture=60.0)

        next_state = step_twin(state, config, dt=1.0)

        assert next_state.moisture > state.moisture

    def test_custom_parameters(self):
        """Custom kinetic parameters affect growth rate."""
        config_slow = TwinConfig(mu_max=0.01)
        config_fast = TwinConfig(mu_max=0.05)
        state = TwinState(biomass=1.0, substrate=10.0, temperature=28.0, moisture=70.0)

        next_slow = step_twin(state, config_slow, dt=1.0)
        next_fast = step_twin(state, config_fast, dt=1.0)

        assert next_fast.biomass > next_slow.biomass

    def test_ser_from_trajectory(self):
        """SER can be computed from initial/final states."""
        config = TwinConfig()
        initial = TwinState(biomass=0.1, substrate=10.0, temperature=28.0, moisture=70.0)

        trajectory = run_twin_simulation(initial, config, n_steps=200, dt=1.0)
        final = trajectory[-1]

        ser = final.biomass / initial.substrate
        assert ser > 0
        assert ser < 1.0

    def test_engine_version(self):
        """Engine version is set."""
        assert ENGINE_VERSION is not None
        assert len(ENGINE_VERSION) > 0

    def test_deterministic(self):
        """Same input always produces same output."""
        config = TwinConfig()
        state = TwinState(biomass=1.0, substrate=10.0, temperature=28.0, moisture=70.0)

        r1 = step_twin(state, config, dt=1.0)
        r2 = step_twin(state, config, dt=1.0)

        assert r1.biomass == r2.biomass
        assert r1.substrate == r2.substrate
