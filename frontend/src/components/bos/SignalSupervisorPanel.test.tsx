import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { useSupervisorStateMock, useHandoverRecommendationMock } = vi.hoisted(() => ({
  useSupervisorStateMock: vi.fn(),
  useHandoverRecommendationMock: vi.fn(),
}));

vi.mock("@/hooks/useBos", () => ({
  useSupervisorState: useSupervisorStateMock,
  useHandoverRecommendation: useHandoverRecommendationMock,
}));

import { SignalSupervisorPanel } from "@/components/bos/SignalSupervisorPanel";

describe("SignalSupervisorPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useSupervisorStateMock.mockReturnValue({
      data: null,
      isPending: false,
      mutate: vi.fn(),
    });
    useHandoverRecommendationMock.mockReturnValue({
      data: null,
      isPending: false,
      mutate: vi.fn(),
    });
  });

  it("renders empty guidance when no signal is available", () => {
    const html = renderToStaticMarkup(<SignalSupervisorPanel signal={null} />);

    expect(html).toContain("Compile a signal first");
    expect(html).toContain("supervisor and handover recommendations");
  });

  it("renders supervisor and handover results when available", () => {
    useSupervisorStateMock.mockReturnValue({
      data: {
        id: 1,
        signal_batch_id: 1,
        c_signal_hat: 0.61,
        dc_dt_hat: 0.02,
        confidence: 0.88,
        observed_at: "2026-04-15T12:00:00Z",
        missing_channels: [],
        channels_used: ["uv254", "od280", "do", "ph"],
        information_loss: 0.12,
        observability_score: 1,
        negative_slope_streak: 0,
        trigger_reason: null,
        expected_handover: "2026-04-15T13:00:00Z",
        mechanistic_context: null,
      },
      isPending: false,
      mutate: vi.fn(),
    });
    useHandoverRecommendationMock.mockReturnValue({
      data: {
        signal_batch_id: 1,
        recommended_handover: true,
        trigger_reason: "negative_slope_persistence",
        expected_freshness_window_hours: 1.5,
        c_signal_hat: 0.48,
        dc_dt_hat: -0.06,
        confidence: 0.84,
        expected_handover: "2026-04-15T13:30:00Z",
        confidence_threshold: 0.8,
        negative_slope_persistence: 3,
        observability_required: true,
        missing_channels: [],
        channels_used: ["uv254", "od280", "do", "ph"],
        information_loss: 0.18,
        observability_score: 1,
        mechanistic_context: null,
      },
      isPending: false,
      mutate: vi.fn(),
    });

    const html = renderToStaticMarkup(
      <SignalSupervisorPanel
        signal={{
          id: 1,
          batch_id: 9,
          user_id: 1,
          tenant_id: 1,
          signal_api_version: "SIG-1.0",
          compiled_signal_id: "SIG-SUP-001",
          potency: 0.21,
          potency_unit: "SER-equivalent",
          potency_basis: "matched_boundary",
          dose_window_min: 0.1,
          dose_window_max: 0.3,
          stability_window_hours: 8,
          kernel_residence_time_hours: null,
          handover_time: null,
          freshness_state: "Fresh",
          qc_markers: null,
          notes: null,
          released_at: null,
          expires_at: null,
          created_at: "2026-04-15T10:00:00Z",
          updated_at: "2026-04-15T10:30:00Z",
        }}
      />,
    );

    expect(html).toContain("Supervisor preview");
    expect(html).toContain("SIG-SUP-001");
    expect(html).toContain("Handover advised");
    expect(html).toContain("negative_slope_persistence");
    expect(html).toContain("Observability");
  });
});
