"""
BOS Pipeline v9.0 �� Test Suite

Package root for all backend tests.

Structure:
  tests/
  ������ __init__.py
  ������ conftest.py          �� Shared fixtures (DB, client, auth)
  ������ unit/
  ��   ������ __init__.py
  ��   ������ test_ser_engine.py
  ��   ������ test_monte_carlo_engine.py
  ��   ������ test_ghg_engine.py
  ��   ������ test_water_engine.py
  ��   ������ test_energy_engine.py
  ��   ������ test_tea_engine.py
  ��   ������ test_lca_engine.py
  ��   ������ test_risk_engine.py
  ��   ������ test_flight_envelope.py
  ��   ������ test_bayesian_engine.py
  ��   ������ test_arima_engine.py
  ��   ������ test_mass_balance.py
  ��   ������ test_sensitivity_engine.py
  ��   ������ test_anomaly_engine.py
  ��   ������ test_digital_twin_engine.py
  ��   ������ test_species_db.py
  ������ integration/
  ��   ������ __init__.py
  ��   ������ test_auth_router.py
  ��   ������ test_batch_router.py
  ��   ������ test_ser_router.py
  ��   ������ test_simulation_router.py
  ��   ������ test_twin_router.py
  ��   ������ test_dashboard_router.py
  ������ e2e/
      ������ __init__.py
      ������ test_full_workflow.py
"""
