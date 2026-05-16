/**
 * BOS Pipeline v9.0 -Simulation Types
 *
 * Type definitions for Monte Carlo, Sensitivity, Bayesian A/B, and Forecast.
 */

// Monte Carlo 

export interface MonteCarloRequest {
 dm_in_mean: number;
 dm_in_std: number;
 dm_out_mean: number;
 dm_out_std: number;
 n_simulations: number;
 n_in_mean?: number;
 n_in_std?: number;
 seed?: number;
}

export interface MonteCarloResponse {
 ser_mean: number;
 ser_std: number;
 ser_median: number;
 ser_p5: number;
 ser_p95: number;
 pass_probability: number;
 histogram_bins: number[];
 histogram_counts: number[];
 n_simulations: number;
 computation_time_ms: number;
}

// Sensitivity 

export interface SensitivityRequest {
 dm_in: number;
 dm_out: number;
 n_in?: number;
 n_larvae?: number;
 n_frass?: number;
 variation_pct: number;
 n_steps: number;
}

export interface SensitivityResponse {
 base_ser: number;
 parameter_ranking: string[];
 impact_scores: Record<string, number>;
 sweep_results: Record<string, SensitivitySweepPoint[]>;
}

export interface SensitivitySweepPoint {
 parameter_value: number;
 ser_value: number;
 variation_pct: number;
}

// Bayesian A/B 

export interface BayesianABRequest {
 group_a: number[];
 group_b: number[];
 n_samples: number;
 prior_alpha?: number;
 prior_beta?: number;
}

export interface BayesianABResponse {
 mean_a: number;
 mean_b: number;
 std_a: number;
 std_b: number;
 prob_b_better: number;
 effect_size: number;
 ci_effect_lower: number;
 ci_effect_upper: number;
 decision: string;
 confidence: number;
 posterior_a: number[];
 posterior_b: number[];
}

// Forecast 

export type ForecastMethod = "sma" | "ewma" | "holt_winters";

export interface ForecastRequest {
 values: number[];
 method: ForecastMethod;
 horizon: number;
 window?: number;
 alpha?: number;
 beta?: number;
 gamma?: number;
}

export interface ForecastResponse {
 forecast: number[];
 ci_lower: number[];
 ci_upper: number[];
 method: ForecastMethod;
 horizon: number;
 mape: number | null;
 rmse: number | null;
}
