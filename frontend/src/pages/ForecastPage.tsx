import { useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { TrendingUp, Radar } from "lucide-react";

import { useForecast } from "@/hooks/useSimulation";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader, StatCard } from "@/components/ui/Card";
import { ForecastChart } from "@/components/charts/ForecastChart";
import { PageHeader } from "@/components/ui/PageHeader";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import { formatNumber } from "@/lib/utils";
import type { ForecastMethod, ForecastRequest } from "@/types/simulation";

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

  const parsedInput = useMemo(
    () =>
      form
        .watch("values")
        .split(",")
        .map((value) => Number.parseFloat(value.trim()))
        .filter((value) => !Number.isNaN(value)),
    [form.watch("values")],
  );

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
    <div className="space-y-6">
      <PageHeader
        eyebrow="Forecast"
        title="Signal drift and forecast studio"
        description="Project likely SER movement from recent values and inspect uncertainty bands without overstating model confidence."
        badges={[
          { label: `Method: ${selectedMethod.toUpperCase()}`, variant: "info" },
          { label: "Scenario-ready", variant: "brand" },
        ]}
        stats={[
          {
            label: "Input points",
            value: parsedInput.length || "0",
            hint: "Chronological values in the current draft",
          },
          {
            label: "Horizon",
            value: form.watch("horizon"),
            hint: "Future steps requested",
          },
          {
            label: "Latest forecast",
            value: result?.forecast?.[0] != null ? formatNumber(result.forecast[0], 4) : "Pending",
            hint: "First projected value",
          },
          {
            label: "Model note",
            value: selectedMethod.toUpperCase(),
            hint: METHOD_COPY[selectedMethod],
          },
        ]}
      />

      <div className="grid gap-6 xl:grid-cols-[1fr_1.1fr]">
        <Card tone="strong">
          <CardHeader
            title="Forecast contract"
            description="Paste historical SER observations, select a method, and tune only the parameters supported by the chosen model."
          />
          <CardBody>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4" noValidate>
              <Textarea
                label="Historical SER values"
                placeholder="0.15, 0.14, 0.16, 0.13, 0.17, 0.12"
                helperText="Comma-separated, chronological order."
                required
                rows={4}
                error={form.formState.errors.values?.message}
                {...form.register("values")}
              />

              <div className="grid gap-4 md:grid-cols-2">
                <Select label="Method" options={METHOD_OPTIONS} {...form.register("method")} />
                <Input
                  label="Forecast horizon"
                  type="number"
                  helperText="1 to 52 future steps"
                  error={form.formState.errors.horizon?.message}
                  {...form.register("horizon")}
                />
              </div>

              {selectedMethod === "sma" ? (
                <Input
                  label="Window size"
                  type="number"
                  helperText="Rolling average window"
                  error={form.formState.errors.window?.message}
                  {...form.register("window")}
                />
              ) : (
                <div className="grid gap-4 md:grid-cols-2">
                  <Input
                    label="Alpha"
                    type="number"
                    step="0.01"
                    helperText="Level smoothing"
                    error={form.formState.errors.alpha?.message}
                    {...form.register("alpha")}
                  />

                  {selectedMethod === "holt_winters" ? (
                    <Input
                      label="Beta"
                      type="number"
                      step="0.01"
                      helperText="Trend smoothing"
                      error={form.formState.errors.beta?.message}
                      {...form.register("beta")}
                    />
                  ) : null}
                </div>
              )}

              <div className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3">
                <div className="flex items-center gap-2">
                  <Radar className="h-4 w-4 text-sky-200" />
                  <p className="text-sm font-medium text-white">Method interpretation</p>
                </div>
                <p className="mt-2 text-sm leading-6 text-surface-300">
                  {METHOD_COPY[selectedMethod]}
                </p>
              </div>

              <Button
                type="submit"
                fullWidth
                loading={forecast.isPending}
                leftIcon={<TrendingUp className="h-4 w-4" />}
              >
                Generate forecast
              </Button>
            </form>
          </CardBody>
        </Card>

        <div className="space-y-6">
          <Card tone="strong" noPadding>
            <div className="border-b border-white/8 px-6 py-5">
              <CardHeader
                title="Forecast envelope"
                description="Historical path, projected path, and uncertainty band in one decision view."
              />
            </div>

            {result ? (
              <>
                <div className="grid grid-cols-2 gap-4 px-5 py-5 sm:grid-cols-4">
                  <StatCard label="Method" value={result.method.toUpperCase()} color="blue" />
                  <StatCard label="Horizon" value={result.horizon} unit="steps" color="neutral" />
                  <StatCard
                    label="MAPE"
                    value={result.mape != null ? formatNumber(result.mape * 100, 1) : "N/A"}
                    unit="%"
                    color={result.mape != null && result.mape < 0.1 ? "green" : "amber"}
                  />
                  <StatCard
                    label="RMSE"
                    value={result.rmse != null ? formatNumber(result.rmse, 4) : "N/A"}
                    color="neutral"
                  />
                </div>

                <div className="px-2 pb-5">
                  <ForecastChart historical={historicalValues} forecast={result} />
                </div>
              </>
            ) : (
              <div className="flex flex-col items-center justify-center py-20 text-surface-400">
                <TrendingUp className="mb-3 h-10 w-10 text-surface-500" />
                <p className="text-sm">Generate a forecast to populate the projection surface.</p>
              </div>
            )}
          </Card>

          <Card>
            <CardHeader
              title="Projected steps"
              description="Per-step values with confidence interval when the backend provides one."
            />
            <CardBody>
              {result?.forecast?.length ? (
                <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
                  {result.forecast.map((value, index) => (
                    <div
                      key={`${value}-${index}`}
                      className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3"
                    >
                      <p className="metric-kicker">Step {index + 1}</p>
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
                  No projected steps yet.
                </div>
              )}
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  );
}
