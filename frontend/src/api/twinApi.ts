/**
 * BOS Pipeline v9.0 twin API client.
 *
 * Adapts the current frontend twin contract to the backend digital twin schema.
 */

import client from "@/api/client";
import {
  DEFAULT_TWIN_PARAMETERS,
  type BackendTwinCreatePayload,
  type BackendTwinState,
  type BackendTwinObservationUpdateRequest,
  type BackendTwinObservationUpdateResponse,
  type BackendTwinPredictRequest,
  type BackendTwinPredictResponse,
  type BackendTwinParameters,
  type BackendTwinResponse,
  type BackendTwinSimulationRequest,
  type BackendTwinSimulationResponse,
  type BackendTwinUpdatePayload,
  type TwinObservationUpdateRequest,
  type TwinObservationUpdateResponse,
  type TwinPredictRequest,
  type TwinPredictResponse,
  type Twin,
  type TwinCreate,
  type TwinListResponse,
  type TwinSimulateRequest,
  type TwinSimulateResponse,
  type TwinUpdate,
} from "@/types/twin";

function numberOrDefault(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function buildTwinId(payload: TwinCreate): string {
  if (payload.twin_id?.trim()) return payload.twin_id.trim();

  const slug = payload.name
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);

  return `TWIN-${slug || "UNTITLED"}-${Date.now().toString().slice(-6)}`;
}

function toBackendParameters(parameters?: Partial<Twin["parameters"]>): BackendTwinParameters | undefined {
  if (!parameters) return undefined;

  return {
    mu_max: parameters.mu_max,
    K_s: parameters.ks,
    Y: parameters.yield_coeff,
    k_death: parameters.maintenance,
    T_env: parameters.temp_opt,
    M_env: parameters.moisture_opt,
  };
}

function toBackendCreatePayload(payload: TwinCreate): BackendTwinCreatePayload {
  const config = {
    ...(payload.config ?? {}),
    ...(payload.description ? { description: payload.description } : {}),
  };

  return {
    twin_id: buildTwinId(payload),
    name: payload.name,
    species: payload.species || "BSF",
    config,
    parameters: toBackendParameters(payload.parameters),
  };
}

function toBackendUpdatePayload(payload: TwinUpdate): BackendTwinUpdatePayload {
  const config = {
    ...(payload.config ?? {}),
    ...(payload.description !== undefined ? { description: payload.description } : {}),
  };

  const backendPayload: BackendTwinUpdatePayload = {};

  if (payload.name !== undefined) backendPayload.name = payload.name;
  if (payload.is_active !== undefined) backendPayload.is_active = payload.is_active;
  if (Object.keys(config).length > 0) backendPayload.config = config;

  const parameters = toBackendParameters(payload.parameters);
  if (parameters && Object.values(parameters).some((value) => value !== undefined)) {
    backendPayload.parameters = parameters;
  }

  return backendPayload;
}

function normalizeTwin(raw: BackendTwinResponse): Twin {
  const config = raw.config ?? {};
  const state = raw.state ?? {};
  const parameters = raw.parameters ?? {};

  return {
    id: raw.id,
    twin_id: raw.twin_id,
    name: raw.name,
    description:
      typeof config.description === "string" && config.description.trim().length > 0
        ? config.description
        : null,
    species: raw.species ?? null,
    is_active: raw.is_active,
    parameters: {
      mu_max: numberOrDefault(parameters.mu_max, DEFAULT_TWIN_PARAMETERS.mu_max),
      ks: numberOrDefault(parameters.K_s, DEFAULT_TWIN_PARAMETERS.ks),
      yield_coeff: numberOrDefault(parameters.Y, DEFAULT_TWIN_PARAMETERS.yield_coeff),
      maintenance: numberOrDefault(parameters.k_death, DEFAULT_TWIN_PARAMETERS.maintenance),
      temp_opt: numberOrDefault(parameters.T_env, DEFAULT_TWIN_PARAMETERS.temp_opt),
      temp_range:
        numberOrDefault(
          typeof config.temp_range === "number" ? config.temp_range : undefined,
          DEFAULT_TWIN_PARAMETERS.temp_range,
        ),
      moisture_opt: numberOrDefault(parameters.M_env, DEFAULT_TWIN_PARAMETERS.moisture_opt),
      moisture_range:
        numberOrDefault(
          typeof config.moisture_range === "number" ? config.moisture_range : undefined,
          DEFAULT_TWIN_PARAMETERS.moisture_range,
        ),
      initial_biomass: numberOrDefault(state.biomass, DEFAULT_TWIN_PARAMETERS.initial_biomass),
      initial_substrate: numberOrDefault(state.substrate, DEFAULT_TWIN_PARAMETERS.initial_substrate),
    },
    state: {
      biomass: numberOrDefault(state.biomass, DEFAULT_TWIN_PARAMETERS.initial_biomass),
      substrate: numberOrDefault(state.substrate, DEFAULT_TWIN_PARAMETERS.initial_substrate),
      temperature: numberOrDefault(state.temperature, DEFAULT_TWIN_PARAMETERS.temp_opt),
      moisture: numberOrDefault(state.moisture, DEFAULT_TWIN_PARAMETERS.moisture_opt),
      nitrogen: numberOrDefault(state.nitrogen, 50),
      timestamp_hours: numberOrDefault(state.timestamp_hours, 0),
    },
    config,
    created_at: raw.created_at ?? null,
    updated_at: raw.updated_at ?? null,
    owner_id: raw.user_id ?? null,
    tenant_id: raw.tenant_id ?? null,
    version: raw.version ?? 0,
  };
}

function normalizeTwinState(
  state: Twin["state"] | BackendTwinState | Record<string, unknown> | null | undefined,
  fallbackParameters: Twin["parameters"] = DEFAULT_TWIN_PARAMETERS,
): Twin["state"] {
  const raw = state ?? {};

  return {
    biomass: numberOrDefault(raw.biomass, fallbackParameters.initial_biomass),
    substrate: numberOrDefault(raw.substrate, fallbackParameters.initial_substrate),
    temperature: numberOrDefault(raw.temperature, fallbackParameters.temp_opt),
    moisture: numberOrDefault(raw.moisture, fallbackParameters.moisture_opt),
    nitrogen: numberOrDefault(raw.nitrogen, 50),
    timestamp_hours: numberOrDefault(raw.timestamp_hours, 0),
  };
}

function toBackendSimulationPayload(payload: TwinSimulateRequest, twin: Twin): BackendTwinSimulationRequest {
  const nSteps = Math.max(1, Math.round(payload.duration_hours / payload.time_step));
  const scheduleEntry: Record<string, number> = {
    feed_rate: payload.feed_rate ?? 0,
    ventilation: 0,
    heating: 0,
  };

  return {
    n_steps: nSteps,
    dt: payload.time_step,
    initial_biomass: twin.state.biomass ?? twin.parameters.initial_biomass,
    initial_substrate: twin.state.substrate ?? twin.parameters.initial_substrate,
    initial_temperature: payload.temperature ?? twin.state.temperature ?? twin.parameters.temp_opt,
    initial_moisture: payload.moisture ?? twin.state.moisture ?? twin.parameters.moisture_opt,
    initial_nitrogen: twin.state.nitrogen,
    inputs_schedule: [scheduleEntry],
  };
}

function normalizeSimulationResult(
  twinId: number,
  raw: BackendTwinSimulationResponse,
  request: TwinSimulateRequest,
  startedAt: number,
): TwinSimulateResponse {
  const trajectory = raw.trajectory.map((point) => ({
    time: point.t,
    biomass: point.biomass,
    substrate: point.substrate,
    growth_rate: point.growth_rate,
    temperature: point.temperature,
    moisture: point.moisture,
  }));

  const finalState = raw.final_state ?? {};
  const peakGrowthRate = trajectory.reduce(
    (max, point) => Math.max(max, point.growth_rate),
    0,
  );
  const lastTrajectoryPoint = raw.trajectory.at(-1);

  return {
    twin_id: twinId,
    trajectory,
    computed_ser: numberOrDefault(lastTrajectoryPoint?.ser_instantaneous, 0),
    final_biomass: numberOrDefault(finalState.biomass, trajectory.at(-1)?.biomass ?? 0),
    final_substrate: numberOrDefault(finalState.substrate, trajectory.at(-1)?.substrate ?? 0),
    peak_growth_rate: peakGrowthRate,
    duration_hours: request.duration_hours,
    computation_time_ms: performance.now() - startedAt,
  };
}

function toBackendPredictPayload(payload: TwinPredictRequest): BackendTwinPredictRequest {
  return {
    dt: payload.dt,
    inputs: {
      feed_rate: payload.feed_rate,
      ventilation: payload.ventilation,
      heating: payload.heating,
    },
  };
}

function normalizePredictResult(raw: BackendTwinPredictResponse): TwinPredictResponse {
  return {
    state: normalizeTwinState(raw.state),
    growth_rate: raw.growth_rate,
    ser_instantaneous: raw.ser_instantaneous,
    timestamp_hours: raw.timestamp_hours,
    version: raw.version,
  };
}

function toBackendObservationPayload(
  payload: TwinObservationUpdateRequest,
): BackendTwinObservationUpdateRequest {
  return {
    observations: {
      weight: payload.weight,
      temperature: payload.temperature,
      moisture: payload.moisture,
    },
  };
}

function normalizeObservationUpdateResult(
  raw: BackendTwinObservationUpdateResponse,
): TwinObservationUpdateResponse {
  return {
    state: normalizeTwinState(raw.state),
    innovation: raw.innovation,
    version: raw.version,
  };
}

export const twinApi = {
  list: async (
    page: number,
    pageSize: number,
    isActive?: boolean,
  ): Promise<TwinListResponse> => {
    const { data } = await client.get<{
      items: BackendTwinResponse[];
      total: number;
      page: number;
      page_size: number;
      total_pages: number;
    }>("/twins", {
      params: {
        page,
        page_size: pageSize,
        is_active: isActive,
      },
    });

    return {
      ...data,
      items: data.items.map(normalizeTwin),
    };
  },

  get: async (id: number): Promise<Twin> => {
    const { data } = await client.get<BackendTwinResponse>(`/twins/${id}`);
    return normalizeTwin(data);
  },

  create: async (payload: TwinCreate): Promise<Twin> => {
    const { data } = await client.post<BackendTwinResponse>(
      "/twins",
      toBackendCreatePayload(payload),
    );
    return normalizeTwin(data);
  },

  update: async (id: number, payload: TwinUpdate): Promise<Twin> => {
    const { data } = await client.patch<BackendTwinResponse>(
      `/twins/${id}`,
      toBackendUpdatePayload(payload),
    );
    return normalizeTwin(data);
  },

  delete: async (id: number): Promise<void> => {
    await client.delete(`/twins/${id}`);
  },

  simulate: async (
    id: number,
    payload: TwinSimulateRequest,
  ): Promise<TwinSimulateResponse> => {
    const twin = await twinApi.get(id);
    const startedAt = performance.now();
    const { data } = await client.post<BackendTwinSimulationResponse>(
      `/twins/${id}/simulate`,
      toBackendSimulationPayload(payload, twin),
    );

    return normalizeSimulationResult(id, data, payload, startedAt);
  },

  predict: async (id: number, payload: TwinPredictRequest): Promise<TwinPredictResponse> => {
    const { data } = await client.post<BackendTwinPredictResponse>(
      `/twins/${id}/predict`,
      toBackendPredictPayload(payload),
    );
    return normalizePredictResult(data);
  },

  updateObservations: async (
    id: number,
    payload: TwinObservationUpdateRequest,
  ): Promise<TwinObservationUpdateResponse> => {
    const { data } = await client.post<BackendTwinObservationUpdateResponse>(
      `/twins/${id}/update`,
      toBackendObservationPayload(payload),
    );
    return normalizeObservationUpdateResult(data);
  },
};
