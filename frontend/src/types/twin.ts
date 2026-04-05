/**
 * BOS Pipeline v9.0 �� Digital Twin Types
 *
 * Type definitions for digital twin models, parameters, and simulation.
 */

// �T�T�T�T�T�T�T�T�T�T�T Twin Model �T�T�T�T�T�T�T�T�T�T�T

export interface Twin {
  id: number;
  name: string;
  description: string | null;
  species: string | null;
  parameters: TwinParameters;
  created_at: string;
  updated_at: string;
  owner_id: number;
}

export interface TwinParameters {
  mu_max: number;         // Maximum specific growth rate (1/h)
  ks: number;             // Half-saturation constant (kg)
  yield_coeff: number;    // Yield coefficient (kg biomass / kg substrate)
  maintenance: number;    // Maintenance coefficient (1/h)
  temp_opt: number;       // Optimal temperature (��C)
  temp_range: number;     // Temperature tolerance (��C)
  moisture_opt: number;   // Optimal moisture (%)
  moisture_range: number; // Moisture tolerance (%)
  initial_biomass: number; // Starting biomass (kg)
  initial_substrate: number; // Starting substrate (kg)
}

export const DEFAULT_TWIN_PARAMETERS: TwinParameters = {
  mu_max: 0.15,
  ks: 0.5,
  yield_coeff: 0.35,
  maintenance: 0.01,
  temp_opt: 28,
  temp_range: 5,
  moisture_opt: 65,
  moisture_range: 10,
  initial_biomass: 0.1,
  initial_substrate: 10.0,
};

// �T�T�T�T�T�T�T�T�T�T�T Twin Create / Update �T�T�T�T�T�T�T�T�T�T�T

export interface TwinCreate {
  name: string;
  description?: string;
  species?: string;
  parameters?: Partial<TwinParameters>;
}

export interface TwinUpdate extends Partial<TwinCreate> {}

// �T�T�T�T�T�T�T�T�T�T�T Twin List Response �T�T�T�T�T�T�T�T�T�T�T

export interface TwinListResponse {
  items: Twin[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// �T�T�T�T�T�T�T�T�T�T�T Simulation �T�T�T�T�T�T�T�T�T�T�T

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
  time: number;       // hours
  biomass: number;    // kg
  substrate: number;  // kg
  growth_rate: number; // 1/h
  temperature: number; // ��C
  moisture: number;    // %
}
