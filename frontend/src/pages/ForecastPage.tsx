import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { TrendingUp, Radar } from "lucide-react";

import { useForecast } from "@/hooks/useSimulation";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import {
  CockpitGrid,
  CockpitMetric,
  CockpitPanel,
  CockpitSectionLabel,
} from "@/components/ui/Cockpit";
import { ForecastChart } from "@/components/charts/ForecastChart";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import { translateText } from "@/lib/i18n";
import { formatNumber } from "@/lib/utils";
import type { ForecastMethod, ForecastRequest } from "@/types/simulation";
import { useRecentTimeseriesRisks } from "@/hooks/useBos";

const forecastSchema = z.object({
  values: z.string().min(1, "Enter comma-separated SER values"),
  method: z.enum(["sma", "ewma", "holt_winters"]),
  horizon: z.coerce.number().int().min(1).max(52),
  window: z.union([z.coerce.number().int().min(2).max(30), z.literal("")]).optional(),
  alpha: z.union([z.coerce.number().min(0.01).max(1), z.literal("")]).optional(),
  beta: z.union([z.coerce.number().min(0.01).max(1), z.literal("")]).optional(),
});

type ForecastFormData = z.infer<typeof forecastSchema>;

const METHOD_OPTIONS = [
  { value: "sma", label: "Simple moving average" },
  { value: "ewma", label: "Exponentially weighted moving average" },
  { value: "holt_winters", label: "Holt-Winters" },
];

const METHOD_COPY: Record<ForecastMethod, string> = {
  sma: "Stable rolling average suited to calm series with low short-term volatility.",
  ewma: "Recency-weighted smoothing for drift-sensitive monitoring.",
  holt_winters: "Trend-aware projection when directional movement is visible.",
};

export default function ForecastPage() {
  const forecast = useForecast();
  const recentRisks = useRecentTimeseriesRisks(1, 6);
  const [historicalValues, setHistoricalValues] = useState<number[]>([]);

  const form = useForm<ForecastFormData>({
    resolver: zodResolver(forecastSchema),
    defaultValues: {
      values: "",
      method: "sma",
      horizon: 5,
      window: 3,
      alpha: 0.3,
      beta: 0.1,
    },
  });

  const selectedMethod = form.watch("method");
  const result = forecast.data;
  const modelRisk = recentRisks.data?.items[0] ?? null;
  const forecastErrorMessage = getForecastErrorMessage(forecast.error);

  const onSubmit = (data: ForecastFormData) => {
    const parsed = data.values
      .split(",")
      .map((value) => Number.parseFloat(value.trim()))
      .filter((value) => !Number.isNaN(value));

    if (parsed.length < 3) {
      form.setError("values", { message: "Need at least 3 values" });
      return;
    }

    setHistoricalValues(parsed);

    const payload: ForecastRequest = {
      values: parsed,
      method: data.method,
      horizon: data.horizon,
    };

    if (data.method === "sma" && data.window !== "" && data.window != null) {
      payload.window = Number(data.window);
    }
    if (data.method !== "sma" && data.alpha !== "" && data.alpha != null) {
      payload.alpha = Number(data.alpha);
    }
    if (data.method === "holt_winters" && data.beta !== "" && data.beta != null) {
      payload.beta = Number(data.beta);
    }

    forecast.mutate(payload);
  };

  return (
    <div className="assistant-ambient-shell space-y-6">
      <div className="assistant-ambient-backdrop" aria-hidden="true">
        <span className="assistant-ambient-orb assistant-ambient-orb-cyan" />
        <span className="assistant-ambient-orb assistant-ambient-orb-violet" />
        <span className="assistant-ambient-orb assistant-ambient-orb-white" />
        <span className="assistant-ambient-grid" />
        <span className="assistant-ambient-scan assistant-ambient-scan-a" />
        <span className="assistant-ambient-scan assistant-ambient-scan-b" />
      </div>

      <CockpitPanel tone="hero" className="p-6 lg:p-7">
        <div className="flex flex-col gap-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <CockpitSectionLabel>{translateText("Forecast")}</CockpitSectionLabel>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight text-white sm:text-[2.65rem]">
                {translateText("Signal drift and forecast studio")}
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-surface-300">
                {translateText(
                  "Project likely SER movement from recent values and inspect uncertainty bands without overstating model confidence.",
                )}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Badge variant="info">{`${translateText("Method")}: ${selectedMethod.toUpperCase()}`}</Badge>
              <Badge variant="brand">{translateText("Scenario-ready")}</Badge>
            </div>
          </div>

          {result ? (
            <CockpitGrid className="sm:grid-cols-2 xl:grid-cols-4">
              <CockpitMetric label={translateText("Method")} value={result.method.toUpperCase()} hint={translateText("Projection mode")} accent="cyan" />
              <CockpitMetric label={translateText("Horizon")} value={String(result.horizon)} hint={translateText("Forecast steps")} accent="violet" />
              <CockpitMetric label="MAPE" value={result.mape != null ? formatNumber(result.mape * 100, 1) : translateText("N/A")} hint="%" accent="amber" />
              <CockpitMetric label="RMSE" value={result.rmse != null ? formatNumber(result.rmse, 4) : translateText("N/A")} hint={translateText("Error scale")} accent="neutral" />
            </CockpitGrid>
          ) : null}
        </div>
      </CockpitPanel>

      <div className="grid gap-6 xl:grid-cols-[1fr_1.1fr]">
        <CockpitPanel className="p-5 lg:p-6">
          <div>
            <CockpitSectionLabel>{translateText("Forecast contract")}</CockpitSectionLabel>
            <p className="mt-3 text-sm leading-7 text-surface-300">
              {translateText("Paste historical SER observations, select a method, and tune only the parameters supported by the chosen model.")}
            </p>
          </div>
          <div className="mt-5">
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
              <Textarea
                label={translateText("Historical SER values")}
                placeholder={translateText("0.15, 0.14, 0.16, 0.13, 0.17, 0.12")}
                helperText={translateText("Comma-separated, chronological order.")}
                required
                rows={4}
                error={form.formState.errors.values?.message}
                {...form.register("values")}
              />

              <div className="grid gap-4 md:grid-cols-2">
                <Select label={translateText("Method")} options={METHOD_OPTIONS} {...form.register("method")} />
                <Input
                  label={translateText("Forecast horizon")}
                  type="number"
                  helperText={translateText("1 to 52 future steps")}
                  error={form.formState.errors.horizon?.message}
                  {...form.register("horizon")}
                />
              </div>

              {selectedMethod === "sma" ? (
                <Input
                  label={translateText("Window size")}
                  type="number"
                  helperText={translateText("Rolling average window")}
                  error={form.formState.errors.window?.message}
                  {...form.register("window")}
                />
              ) : (
                <div className="grid gap-4 md:grid-cols-2">
                  <Input
                    label={translateText("Alpha")}
                    type="number"
                    step="0.01"
                    helperText={translateText("Level smoothing")}
                    error={form.formState.errors.alpha?.message}
                    {...form.register("alpha")}
                  />

                  {selectedMethod === "holt_winters" ? (
                    <Input
                      label={translateText("Beta")}
                      type="number"
                      step="0.01"
                      helperText={translateText("Trend smoothing")}
                      error={form.formState.errors.beta?.message}
                      {...form.register("beta")}
                    />
                  ) : null}
                </div>
              )}

              <div className="assistant-thread-shell rounded-2xl border border-white/8 px-4 py-3">
                <div className="flex items-center gap-2">
                  <Radar className="h-4 w-4 text-sky-200" />
                  <p className="text-sm font-medium text-white">{translateText("Method interpretation")}</p>
                </div>
                <p className="mt-2 text-sm leading-6 text-surface-300">
                  {translateText(METHOD_COPY[selectedMethod])}
                </p>
              </div>

              {forecastErrorMessage ? (
                <div className="rounded-2xl border border-red-400/24 bg-red-500/10 px-4 py-3 text-sm text-red-100">
                  <p className="font-medium">{translateText("Forecast failed")}</p>
                  <p className="mt-1 text-red-100/80">{forecastErrorMessage}</p>
                </div>
              ) : null}

              <Button
                type="submit"
                fullWidth
                loading={forecast.isPending}
                leftIcon={<TrendingUp className="h-4 w-4" />}
              >
                {translateText("Generate forecast")}
              </Button>
            </form>
          </div>
        </CockpitPanel>

        <div className="space-y-6">
          <CockpitPanel tone="emphasis" className="p-5 lg:p-6">
            <div>
              <CockpitSectionLabel>{translateText("Forecast envelope")}</CockpitSectionLabel>
              <p className="mt-3 text-sm leading-7 text-surface-300">
                {translateText("Historical path, projected path, and uncertainty band in one decision view.")}
              </p>
            </div>

            {result ? (
              <>
                <div className="assistant-thread-console mt-5 px-2 py-2">
                  <ForecastChart historical={historicalValues} forecast={result} />
                </div>
              </>
            ) : (
              <div className="flex flex-col items-center justify-center py-20 text-surface-400">
                <TrendingUp className="mb-3 h-10 w-10 text-surface-500" />
                <p className="text-sm">{translateText("Generate a forecast to populate the projection surface.")}</p>
              </div>
            )}
          </CockpitPanel>

          <CockpitPanel className="p-5 lg:p-6">
            <div>
              <CockpitSectionLabel>{translateText("Projected steps")}</CockpitSectionLabel>
              <p className="mt-3 text-sm leading-7 text-surface-300">
                {translateText("Per-step values with confidence interval when the backend provides one.")}
              </p>
            </div>
            <div className="mt-5">
              {result?.forecast?.length ? (
                <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
                  {result.forecast.map((value, index) => (
                    <div
                      key={`${value}-${index}`}
                      className="assistant-side-panel-chip rounded-2xl px-4 py-3"
                    >
                      <p className="metric-kicker">{`${translateText("Step")} ${index + 1}`}</p>
                      <p className="mt-2 text-lg font-semibold text-white">{formatNumber(value, 4)}</p>
                      {result.ci_lower?.[index] != null ? (
                        <p className="mt-2 text-xs text-surface-500">
                          CI [{formatNumber(result.ci_lower[index], 3)}, {formatNumber(result.ci_upper[index], 3)}]
                        </p>
                      ) : null}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3 text-sm text-surface-400">
                  {translateText("No projected steps yet.")}
                </div>
              )}
            </div>
          </CockpitPanel>

          <CockpitPanel className="p-5 lg:p-6">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <CockpitSectionLabel>{translateText("Heuristic vs model")}</CockpitSectionLabel>
                <p className="mt-3 text-sm leading-7 text-surface-300">
                  {translateText("Current page forecast remains heuristic; BOS model-backed risk is read separately and falls back honestly when Chronos is unavailable.")}
                </p>
              </div>
              {modelRisk ? (
                <Badge variant={modelRisk.fallback_used ? "warning" : "success"}>
                  {translateText(modelRisk.fallback_used ? "Fallback preserved" : "Chronos-backed")}
                </Badge>
              ) : null}
            </div>
            {modelRisk ? (
              <div className="mt-5 grid gap-3 md:grid-cols-3">
                <div className="assistant-side-panel-chip rounded-2xl px-4 py-3">
                  <p className="metric-kicker">{translateText("Future risk")}</p>
                  <p className="mt-2 text-lg font-semibold text-white">
                    {formatNumber(modelRisk.future_risk_score * 100, 1)}%
                  </p>
                </div>
                <div className="assistant-side-panel-chip rounded-2xl px-4 py-3">
                  <p className="metric-kicker">{translateText("Freshness drift")}</p>
                  <p className="mt-2 text-lg font-semibold text-white">
                    {formatNumber(modelRisk.freshness_drift_score * 100, 1)}%
                  </p>
                </div>
                <div className="assistant-side-panel-chip rounded-2xl px-4 py-3">
                  <p className="metric-kicker">{translateText("Release warning")}</p>
                  <p className="mt-2 text-lg font-semibold text-white">
                    {formatNumber(modelRisk.release_warning_score * 100, 1)}%
                  </p>
                </div>
                <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3 text-sm leading-6 text-surface-300 md:col-span-3">
                  {translateText(modelRisk.explanation)}
                  <span className="ml-2 text-surface-500">
                    {modelRisk.batch_label} · {modelRisk.forecast_window}
                  </span>
                </div>
              </div>
            ) : (
              <div className="mt-5 rounded-2xl border border-white/8 bg-white/5 px-4 py-3 text-sm text-surface-400">
                {translateText(recentRisks.isLoading ? "Loading model-backed risk comparison." : "No recent batch risk comparison is available yet.")}
              </div>
            )}
          </CockpitPanel>
        </div>
      </div>
    </div>
  );
}

function getForecastErrorMessage(error: unknown) {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail) && detail.length) return detail.join("; ");
  if (typeof detail === "object" && detail && "errors" in detail) {
    const errors = (detail as { errors?: string[] }).errors;
    if (Array.isArray(errors) && errors.length) return errors.join("; ");
  }

  const message = (error as { message?: string })?.message;
  return message && message !== "Network Error"
    ? message
    : translateText("Check the input values and make sure your session is still signed in.");
}
