/**
 * BOS Pipeline v9.0 �� Sustainability Types
 *
 * TypeScript interfaces for GHG, Water, Energy, TEA, LCA responses.
 */

// ���� GHG ����
export interface GHGResponse {
  batch_id: number;
  total_emissions: number;       // kg CO?e
  process_emissions: number;
  energy_emissions: number;
  transport_emissions: number;
  avoided_emissions: number;
  net_balance: number;
  per_kg_larvae: number;
  per_kg_protein: number;
  computation_time_ms: number;
}

// ���� Water ����
export interface WaterResponse {
  batch_id: number;
  total_footprint: number;       // litres
  blue_water: number;
  green_water: number;
  grey_water: number;
  per_kg_larvae: number;
  per_kg_protein: number;
  computation_time_ms: number;
}

// ���� Energy ����
export interface EnergyResponse {
  batch_id: number;
  total_input_energy: number;    // MJ
  total_output_energy: number;
  net_energy: number;
  eroi: number;                  // Energy Return On Investment
  fossil_energy: number;
  renewable_energy: number;
  per_kg_larvae: number;
  computation_time_ms: number;
}

// ���� TEA ����
export interface TEAResponse {
  batch_id: number;
  total_cost: number;            // USD
  total_revenue: number;
  net_profit: number;
  roi: number;                   // fraction
  profit_margin: number;         // fraction
  cost_per_kg_larvae: number;
  revenue_per_kg_larvae: number;
  break_even_kg: number;
  computation_time_ms: number;
}

// ���� LCA Summary (future) ����
export interface LCASummary {
  batch_id: number;
  global_warming_potential: number;  // kg CO?e
  water_depletion: number;           // m3
  energy_demand: number;             // MJ
  eutrophication: number;            // kg PO?e
  acidification: number;             // kg SO?e
  land_use: number;                  // m2a
  computation_time_ms: number;
}
