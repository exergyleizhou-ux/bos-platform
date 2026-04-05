"""
BOS Pipeline v9.0 �� Scientific Engine Package

Contains 34 pure-function computation engines:

Core Bioconversion:
  - ser_engine          : System Efficiency Ratio
  - monte_carlo_engine  : Monte Carlo SER simulation
  - species_db          : Species parameters database

Environmental:
  - ghg_engine          : Greenhouse gas balance
  - water_engine        : Water footprint
  - energy_engine       : Energy balance
  - lca_engine          : Life cycle assessment

Economic:
  - tea_engine          : Techno-economic analysis

Quality & Safety:
  - risk_engine         : Contaminant risk assessment
  - flight_envelope     : Operating envelope checks
  - anomaly_engine      : Anomaly detection (Isolation Forest)

Advanced Analytics:
  - calibration_engine  : Gaussian process calibration
  - sensitivity_engine  : Sobol sensitivity analysis
  - did_engine          : Difference-in-differences
  - bayesian_engine     : Bayesian A/B testing

Digital Twin:
  - digital_twin_engine : Twin state management
  - controller_engine   : PID controller
  - ekf_engine          : Extended Kalman Filter
  - state_observer      : Luenberger observer

Machine Learning:
  - automl_engine       : Hyperparameter optimization
  - gp_engine           : Gaussian process regression
  - nn_surrogate        : Neural network surrogate model

Forecasting:
  - arima_engine        : ARIMA time series
  - prophet_engine      : Seasonal decomposition

Optimization:
  - feed_optimizer      : Feed mix LP optimization
  - scheduling_engine   : Batch scheduling optimizer
  - pareto_engine       : Multi-objective Pareto

Data Processing:
  - mass_balance        : Mass balance reconciliation
  - stoichiometry       : Stoichiometric modeling
  - kinetics_engine     : Growth kinetics (Monod, Logistic)

Validation:
  - data_validator      : Input data quality checks
  - outlier_engine      : Statistical outlier detection
  - consistency_engine  : Cross-field consistency checks
  - schema_engine       : Dynamic schema validation
"""
