/**
 * BOS Pipeline v9.0 �� Simulation Hooks
 *
 * React Query mutation hooks for Monte Carlo, Sensitivity, Bayesian A/B, and Forecast.
 */

import { useMutation } from "@tanstack/react-query";
import toast from "react-hot-toast";

import { simulationApi } from "@/api/simulationApi";
import type {
  MonteCarloRequest,
  SensitivityRequest,
  BayesianABRequest,
  ForecastRequest,
} from "@/types/simulation";

// ���� Monte Carlo ����
export function useMonteCarloSimulation() {
  return useMutation({
    mutationFn: (payload: MonteCarloRequest) =>
      simulationApi.monteCarlo(payload),
    onSuccess: (data) => {
      toast.success(
        `Simulation complete �� Mean SER: ${data.ser_mean.toFixed(4)}`,
      );
    },
    onError: () => {
      toast.error("Monte Carlo simulation failed");
    },
  });
}

// ���� Sensitivity Analysis ����
export function useSensitivityAnalysis() {
  return useMutation({
    mutationFn: (payload: SensitivityRequest) =>
      simulationApi.sensitivity(payload),
    onSuccess: () => {
      toast.success("Sensitivity analysis complete");
    },
    onError: () => {
      toast.error("Sensitivity analysis failed");
    },
  });
}

// ���� Bayesian A/B ����
export function useBayesianAB() {
  return useMutation({
    mutationFn: (payload: BayesianABRequest) =>
      simulationApi.bayesianAB(payload),
    onSuccess: (data) => {
      toast.success(`A/B test complete �� ${data.decision}`);
    },
    onError: () => {
      toast.error("Bayesian A/B test failed");
    },
  });
}

// ���� Forecast ����
export function useForecast() {
  return useMutation({
    mutationFn: (payload: ForecastRequest) =>
      simulationApi.forecast(payload),
    onSuccess: (data) => {
      toast.success(
        `Forecast complete �� ${data.forecast.length} steps (${data.method.toUpperCase()})`,
      );
    },
    onError: () => {
      toast.error("Forecast failed");
    },
  });
}
