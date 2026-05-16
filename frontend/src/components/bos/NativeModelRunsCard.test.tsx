import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

const { useNativeModelRunsMock } = vi.hoisted(() => ({
  useNativeModelRunsMock: vi.fn(),
}));

vi.mock("@/hooks/useBos", () => ({
  useNativeModelRuns: useNativeModelRunsMock,
}));

import { NativeModelRunsCard } from "@/components/bos/NativeModelRunsCard";

describe("NativeModelRunsCard", () => {
  it("renders visual and timeseries evidence badges from provided runs", () => {
    useNativeModelRunsMock.mockReturnValue({
      data: [],
      isLoading: false,
    });

    const html = renderToStaticMarkup(
      <NativeModelRunsCard
        batchId={42}
        runs={[
          {
            model_key: "insecta",
            execution_mode: "insecta_bootstrap_live",
            recorded_at: "2026-04-16T02:00:00Z",
            artifact_path: "C:/tmp/runs/insecta.json",
            payload_echo: {},
            result: { detection_count: 3 },
            warnings: [],
          },
          {
            model_key: "chronos_bolt",
            execution_mode: "chronos_bolt_live",
            recorded_at: "2026-04-16T01:00:00Z",
            artifact_path: "C:/tmp/runs/chronos.json",
            payload_echo: {},
            result: { forecast: [1, 2, 3] },
            warnings: [],
          },
        ]}
        isLoading={false}
      />,
    );

    expect(html).toContain("Native inference history");
    expect(html).toContain("Bootstrap public vision");
    expect(html).toContain("Time-series evidence");
    expect(html).toContain("batch 42");
  });

  it("renders empty state when no runs exist", () => {
    useNativeModelRunsMock.mockReturnValue({
      data: [],
      isLoading: false,
    });

    const html = renderToStaticMarkup(
      <NativeModelRunsCard batchId={42} runs={[]} isLoading={false} />,
    );

    expect(html).toContain("No native inference artifacts are attached to this batch yet.");
  });
});
