/**
 * BOS Pipeline v9.0 simulation API client.
 *
 * HTTP helpers for Monte Carlo, sensitivity, Bayesian A/B, and forecast endpoints.
 */

import client from "@/api/client";
import type {
  BayesianABRequest,
  BayesianABResponse,
  ForecastRequest,
  ForecastResponse,
  MonteCarloRequest,
  MonteCarloResponse,
  SensitivityRequest,
  SensitivityResponse,
} from "@/types/simulation";

export const simulationApi = {
  // Monte Carlo
  monteCarlo: async (payload: MonteCarloRequest): Promise<MonteCarloResponse> => {
    const { data } = await client.post<MonteCarloResponse>(
      "/simulation/monte-carlo",
      payload,
    );
    return data;
  },

  // Sensitivity analysis
  sensitivity: async (
    payload: SensitivityRequest,
  ): Promise<SensitivityResponse> => {
    const { data } = await client.post<SensitivityResponse>(
      "/simulation/sensitivity",
      payload,
    );
    return data;
  },

  // Bayesian A/B
  bayesianAB: async (payload: BayesianABRequest): Promise<BayesianABResponse> => {
    const { data } = await client.post<BayesianABResponse>(
      "/simulation/bayesian-ab",
      payload,
    );
    return data;
  },

  // Forecast
  forecast: async (payload: ForecastRequest): Promise<ForecastResponse> => {
    const { data } = await client.post<ForecastResponse>(
      "/simulation/forecast",
      payload,
    );
    return data;
  },
};
