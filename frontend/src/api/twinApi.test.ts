import { beforeEach, describe, expect, it, vi } from "vitest";

const { mockClient } = vi.hoisted(() => ({
  mockClient: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock("@/api/client", () => ({
  default: mockClient,
}));

import { twinApi } from "@/api/twinApi";

describe("twinApi adapter", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("translates create payload into backend contract and normalizes the response", async () => {
    mockClient.post.mockResolvedValueOnce({
      data: {
        id: 42,
        twin_id: "TWIN-ALPHA-123456",
        name: "Alpha",
        species: "BSF",
        is_active: true,
        state: {
          biomass: 0.5,
          substrate: 10,
          temperature: 28,
          moisture: 70,
          nitrogen: 50,
          timestamp_hours: 0,
        },
        parameters: {
          mu_max: 0.03,
          K_s: 5.5,
          Y: 0.25,
          k_death: 0.0015,
          T_env: 27,
          M_env: 66,
        },
        config: {
          description: "alpha description",
        },
        version: 1,
        user_id: 7,
        tenant_id: 3,
        created_at: "2026-04-14T03:00:00",
        updated_at: "2026-04-14T03:00:00",
      },
    });

    const result = await twinApi.create({
      name: "Alpha",
      species: "BSF",
      description: "alpha description",
      parameters: {
        mu_max: 0.03,
        ks: 5.5,
        yield_coeff: 0.25,
        maintenance: 0.0015,
        temp_opt: 27,
        moisture_opt: 66,
      },
    });

    expect(mockClient.post).toHaveBeenCalledWith(
      "/twins",
      expect.objectContaining({
        twin_id: expect.stringMatching(/^TWIN-ALPHA-\d{6}$/),
        name: "Alpha",
        species: "BSF",
        config: {
          description: "alpha description",
        },
        parameters: {
          mu_max: 0.03,
          K_s: 5.5,
          Y: 0.25,
          k_death: 0.0015,
          T_env: 27,
          M_env: 66,
        },
      }),
    );

    expect(result).toMatchObject({
      id: 42,
      twin_id: "TWIN-ALPHA-123456",
      name: "Alpha",
      description: "alpha description",
      species: "BSF",
      parameters: {
        mu_max: 0.03,
        ks: 5.5,
        yield_coeff: 0.25,
        maintenance: 0.0015,
        temp_opt: 27,
        moisture_opt: 66,
      },
      state: {
        biomass: 0.5,
        substrate: 10,
        temperature: 28,
        moisture: 70,
        nitrogen: 50,
        timestamp_hours: 0,
      },
      owner_id: 7,
      tenant_id: 3,
    });
  });

  it("normalizes list responses and backfills description from config", async () => {
    mockClient.get.mockResolvedValueOnce({
      data: {
        items: [
          {
            id: 1,
            twin_id: "TWIN-1",
            name: "Twin One",
            species: "BSF",
            is_active: true,
            state: null,
            parameters: null,
            config: {
              description: "stored in config",
            },
            version: 2,
            user_id: 9,
            tenant_id: 1,
            created_at: "2026-04-14T03:00:00",
            updated_at: "2026-04-14T03:05:00",
          },
        ],
        total: 1,
        page: 1,
        page_size: 12,
        total_pages: 1,
      },
    });

    const result = await twinApi.list(1, 12, true);

    expect(mockClient.get).toHaveBeenCalledWith("/twins", {
      params: { page: 1, page_size: 12, is_active: true },
    });
    expect(result.items[0]).toMatchObject({
      id: 1,
      twin_id: "TWIN-1",
      description: "stored in config",
      parameters: {
        ks: 5,
        temp_range: 5,
        moisture_range: 10,
      },
      state: {
        biomass: 0.5,
        substrate: 10,
        temperature: 25,
        moisture: 60,
      },
    });
  });

  it("adapts simulate request and response through the normalized twin shape", async () => {
    mockClient.get.mockResolvedValueOnce({
      data: {
        id: 5,
        twin_id: "TWIN-5",
        name: "Sim Twin",
        species: "BSF",
        is_active: true,
        state: {
          biomass: 0.7,
          substrate: 11,
          temperature: 29,
          moisture: 68,
          nitrogen: 52,
          timestamp_hours: 3,
        },
        parameters: {
          mu_max: 0.031,
          K_s: 5.2,
          Y: 0.24,
          k_death: 0.0012,
          T_env: 27.5,
          M_env: 66,
        },
        config: {
          description: "simulation ready",
        },
        version: 1,
        user_id: 2,
        tenant_id: 1,
        created_at: "2026-04-14T03:19:13",
        updated_at: "2026-04-14T03:19:13",
      },
    });

    mockClient.post.mockResolvedValueOnce({
      data: {
        n_steps: 12,
        trajectory: [
          {
            t: 4,
            biomass: 0.72,
            substrate: 11.1,
            temperature: 27.5,
            moisture: 66,
            nitrogen: 51.9,
            growth_rate: 0.012,
            ser_instantaneous: 0.11,
          },
          {
            t: 15,
            biomass: 0.84,
            substrate: 12.2,
            temperature: 27.6,
            moisture: 66,
            nitrogen: 51.7,
            growth_rate: 0.017,
            ser_instantaneous: 0.14,
          },
        ],
        final_state: {
          biomass: 0.84,
          substrate: 12.2,
          temperature: 27.6,
          moisture: 66,
          nitrogen: 51.7,
          timestamp_hours: 15,
        },
      },
    });

    const result = await twinApi.simulate(5, {
      duration_hours: 12,
      time_step: 1,
      temperature: 27.5,
      moisture: 66,
      feed_rate: 0.15,
    });

    expect(mockClient.post).toHaveBeenCalledWith("/twins/5/simulate", {
      n_steps: 12,
      dt: 1,
      initial_biomass: 0.7,
      initial_substrate: 11,
      initial_temperature: 27.5,
      initial_moisture: 66,
      initial_nitrogen: 52,
      inputs_schedule: [
        {
          feed_rate: 0.15,
          ventilation: 0,
          heating: 0,
        },
      ],
    });

    expect(result).toMatchObject({
      twin_id: 5,
      duration_hours: 12,
      computed_ser: 0.14,
      final_biomass: 0.84,
      final_substrate: 12.2,
      peak_growth_rate: 0.017,
      trajectory: [
        {
          time: 4,
          biomass: 0.72,
          substrate: 11.1,
          growth_rate: 0.012,
          temperature: 27.5,
          moisture: 66,
        },
        {
          time: 15,
          biomass: 0.84,
          substrate: 12.2,
          growth_rate: 0.017,
          temperature: 27.6,
          moisture: 66,
        },
      ],
    });
    expect(result.computation_time_ms).toBeGreaterThanOrEqual(0);
  });

  it("translates update payload status and description into backend fields", async () => {
    mockClient.patch.mockResolvedValueOnce({
      data: {
        id: 8,
        twin_id: "TWIN-UPDATE-008",
        name: "Updated Twin",
        species: "BSF",
        is_active: false,
        state: {
          biomass: 0.5,
          substrate: 10,
          temperature: 28,
          moisture: 70,
          nitrogen: 50,
          timestamp_hours: 0,
        },
        parameters: {
          mu_max: 0.041,
          K_s: 6.1,
          Y: 0.28,
          k_death: 0.0018,
          T_env: 26.5,
          M_env: 64,
        },
        config: {
          description: "updated config description",
        },
        version: 3,
        user_id: 2,
        tenant_id: 1,
        created_at: "2026-04-14T03:19:13",
        updated_at: "2026-04-14T03:29:13",
      },
    });

    const result = await twinApi.update(8, {
      name: "Updated Twin",
      is_active: false,
      description: "updated config description",
      parameters: {
        mu_max: 0.041,
        ks: 6.1,
        yield_coeff: 0.28,
        maintenance: 0.0018,
        temp_opt: 26.5,
        moisture_opt: 64,
      },
    });

    expect(mockClient.patch).toHaveBeenCalledWith("/twins/8", {
      name: "Updated Twin",
      is_active: false,
      config: {
        description: "updated config description",
      },
      parameters: {
        mu_max: 0.041,
        K_s: 6.1,
        Y: 0.28,
        k_death: 0.0018,
        T_env: 26.5,
        M_env: 64,
      },
    });

    expect(result).toMatchObject({
      id: 8,
      twin_id: "TWIN-UPDATE-008",
      name: "Updated Twin",
      description: "updated config description",
      is_active: false,
      parameters: {
        mu_max: 0.041,
        ks: 6.1,
        yield_coeff: 0.28,
        maintenance: 0.0018,
        temp_opt: 26.5,
        moisture_opt: 64,
      },
    });
  });

  it("adapts predict requests and normalizes runtime state", async () => {
    mockClient.post.mockResolvedValueOnce({
      data: {
        state: {
          biomass: 0.91,
          substrate: 9.7,
          temperature: 27.4,
          moisture: 65.5,
          nitrogen: 49.2,
          timestamp_hours: 14,
        },
        growth_rate: 0.014,
        ser_instantaneous: 0.18,
        timestamp_hours: 14,
        version: 4,
      },
    });

    const result = await twinApi.predict(9, {
      dt: 2,
      feed_rate: 0.12,
      ventilation: 0.4,
      heating: 0.1,
    });

    expect(mockClient.post).toHaveBeenCalledWith("/twins/9/predict", {
      dt: 2,
      inputs: {
        feed_rate: 0.12,
        ventilation: 0.4,
        heating: 0.1,
      },
    });

    expect(result).toMatchObject({
      state: {
        biomass: 0.91,
        substrate: 9.7,
        temperature: 27.4,
        moisture: 65.5,
        nitrogen: 49.2,
        timestamp_hours: 14,
      },
      growth_rate: 0.014,
      ser_instantaneous: 0.18,
      timestamp_hours: 14,
      version: 4,
    });
  });

  it("adapts observation updates and normalizes innovation/state payloads", async () => {
    mockClient.post.mockResolvedValueOnce({
      data: {
        state: {
          biomass: 0.88,
          substrate: 9.4,
          temperature: 27.1,
          moisture: 64.8,
          nitrogen: 48.9,
          timestamp_hours: 14,
        },
        innovation: [0.4, -0.2, 1.1],
        version: 5,
      },
    });

    const result = await twinApi.updateObservations(9, {
      weight: 10.2,
      temperature: 27.1,
      moisture: 64.8,
    });

    expect(mockClient.post).toHaveBeenCalledWith("/twins/9/update", {
      observations: {
        weight: 10.2,
        temperature: 27.1,
        moisture: 64.8,
      },
    });

    expect(result).toMatchObject({
      state: {
        biomass: 0.88,
        substrate: 9.4,
        temperature: 27.1,
        moisture: 64.8,
        nitrogen: 48.9,
        timestamp_hours: 14,
      },
      innovation: [0.4, -0.2, 1.1],
      version: 5,
    });
  });
});
