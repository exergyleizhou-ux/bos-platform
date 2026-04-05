/**
 * BOS Pipeline v9.0 �� Simulation API Client
 *
 * HTTP functions for Monte Carlo, Sensitivity, Bayesian A/B, and Forecast.
 */

import client from "@/api/client";
import type {
  MonteCarloRequest,
  MonteCarloResponse,
  SensitivityRequest,
  SensitivityResponse,
  BayesianABRequest,
  BayesianABResponse,
  ForecastRequest,
  ForecastResponse,
} from "@/types/simulation";

export const simulationApi = {
  // ���� Monte Carlo ����
  monteCarlo: async (
    payload: MonteCarloRequest,
  ): Promise<MonteCarloResponse> => {
    const { data } = await client.post<MonteCarloResponse>(
      "/simulation/monte-carlo",
      payload,
    );
    return data;
  },

  // ���� Sensitivity Analysis ����
  sensitivity: async (
    payload: SensitivityRequest,
  ): Promise<SensitivityResponse> => {
    const { data } = await client.post<SensitivityResponse>(
      "/simulation/sensitivity",
      payload,
    );
    return data;
  },

  // ���� Bayesian A/B ����
  bayesianAB: async (
    payload: BayesianABRequest,
  ): Promise<BayesianABResponse> => {
    const { data } = await client.post<BayesianABResponse>(
      "/simulation/bayesian-ab",
      payload,
    );
    return data;
  },

  // ���� Forecast ����
  forecast: async (payload: ForecastRequest): Promise<ForecastResponse> => {
    const { data } = await client.post<ForecastResponse>(
      "/simulation/forecast",
      payload,
    );
    return data;
  },
};
