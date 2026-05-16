/**
 * BOS Pipeline v9.0 digital twin types.
 *
 * Frontend-facing twin shapes plus backend contract types used by the API adapter.
 */

// Normalized twin model consumed by the current frontend pages.
export interface Twin {
  id: number;
  twin_id: string;
  name: string;
  description: string | null;
  species: string | null;
  is_active: boolean;
  parameters: TwinParameters;
  state: TwinState;
  config: Record<string, unknown>;
  created_at: string | null;
  updated_at: string | null;
  owner_id: number | null;
  tenant_id: number | null;
  version: number;
}

export interface TwinState {
  biomass: number;
  substrate: number;
  temperature: number;
  moisture: number;
  nitrogen: number;
  timestamp_hours: number;
}

export interface TwinParameters {
  mu_max: number;
  ks: number;
  yield_coeff: number;
  maintenance: number;
  temp_opt: number;
  temp_range: number;
  moisture_opt: number;
  moisture_range: number;
  initial_biomass: number;
  initial_substrate: number;
}

export const DEFAULT_TWIN_PARAMETERS: TwinParameters = {
  mu_max: 0.025,
  ks: 5.0,
  yield_coeff: 0.22,
  maintenance: 0.001,
  temp_opt: 25,
  temp_range: 5,
  moisture_opt: 60,
  moisture_range: 10,
  initial_biomass: 0.5,
  initial_substrate: 10.0,
};

// Frontend create / update payloads.
export interface TwinCreate {
  twin_id?: string;
  name: string;
  description?: string;
  species?: string;
  config?: Record<string, unknown>;
  parameters?: Partial<TwinParameters>;
}

export interface TwinUpdate {
  name?: string;
  description?: string;
  species?: string;
  is_active?: boolean;
  config?: Record<string, unknown>;
  parameters?: Partial<TwinParameters>;
}

// Shared list response.
export interface TwinListResponse {
  items: Twin[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// Frontend-friendly simulation payload consumed by the current page.
export interface TwinSimulateRequest {
  duration_hours: number;
  time_step: number;
  temperature?: number;
  moisture?: number;
  feed_rate?: number;
}

export interface TwinSimulateResponse {
  twin_id: number;
  trajectory: TwinTrajectoryPoint[];
  computed_ser: number;
  final_biomass: number;
  final_substrate: number;
  peak_growth_rate: number;
  duration_hours: number;
  computation_time_ms: number;
}

export interface TwinTrajectoryPoint {
  time: number;
  biomass: number;
  substrate: number;
  growth_rate: number;
  temperature: number;
  moisture: number;
}

export interface TwinPredictRequest {
  dt?: number;
  feed_rate?: number;
  ventilation?: number;
  heating?: number;
}

export interface TwinPredictResponse {
  state: TwinState;
  growth_rate: number;
  ser_instantaneous: number;
  timestamp_hours: number;
  version: number;
}

export interface TwinObservationUpdateRequest {
  weight?: number;
  temperature?: number;
  moisture?: number;
}

export interface TwinObservationUpdateResponse {
  state: TwinState;
  innovation: number[];
  version: number;
}

// Backend contract types used only by the adapter layer.
export interface BackendTwinState {
  biomass?: number;
  substrate?: number;
  temperature?: number;
  moisture?: number;
  nitrogen?: number;
  timestamp_hours?: number;
}

export interface BackendTwinParameters {
  mu_max?: number;
  K_s?: number;
  Y?: number;
  k_death?: number;
  tau_T?: number;
  tau_M?: number;
  T_env?: number;
  M_env?: number;
  k_n?: number;
  c_p?: number;
  Q_met_coeff?: number;
  evap_rate?: number;
  Q_heat_coeff?: number;
}

export interface BackendTwinResponse {
  id: number;
  twin_id: string;
  name: string;
  species: string;
  is_active: boolean;
  state?: BackendTwinState | null;
  parameters?: BackendTwinParameters | null;
  config?: Record<string, unknown> | null;
  version: number;
  user_id?: number | null;
  tenant_id?: number | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface BackendTwinCreatePayload {
  twin_id: string;
  name: string;
  species?: string;
  config?: Record<string, unknown>;
  parameters?: BackendTwinParameters;
}

export interface BackendTwinUpdatePayload {
  name?: string;
  is_active?: boolean;
  config?: Record<string, unknown>;
  parameters?: BackendTwinParameters;
}

export interface BackendTwinSimulationRequest {
  inputs_schedule?: Array<Record<string, number>>;
  initial_biomass?: number;
  initial_substrate?: number;
  initial_temperature?: number;
  initial_moisture?: number;
  initial_nitrogen?: number;
  n_steps: number;
  dt: number;
}

export interface BackendTwinSimulationTrajectoryPoint {
  t: number;
  biomass: number;
  substrate: number;
  temperature: number;
  moisture: number;
  nitrogen: number;
  growth_rate: number;
  ser_instantaneous: number;
}

export interface BackendTwinSimulationResponse {
  n_steps: number;
  trajectory: BackendTwinSimulationTrajectoryPoint[];
  final_state: BackendTwinState;
}

export interface BackendTwinPredictRequest {
  inputs: {
    feed_rate?: number;
    ventilation?: number;
    heating?: number;
  };
  dt?: number;
}

export interface BackendTwinPredictResponse {
  state: BackendTwinState;
  growth_rate: number;
  ser_instantaneous: number;
  timestamp_hours: number;
  version: number;
}

export interface BackendTwinObservationUpdateRequest {
  observations: {
    weight?: number;
    temperature?: number;
    moisture?: number;
  };
}

export interface BackendTwinObservationUpdateResponse {
  state: BackendTwinState;
  innovation: number[];
  version: number;
}
