import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  useNativeModelRuntimeStatusMock,
  useNativeModelDownloadPlanMock,
  useNativeModelDownloadMock,
  useNativeModelInferenceMock,
  useNativeModelRunsMock,
} = vi.hoisted(() => ({
  useNativeModelRuntimeStatusMock: vi.fn(),
  useNativeModelDownloadPlanMock: vi.fn(),
  useNativeModelDownloadMock: vi.fn(),
  useNativeModelInferenceMock: vi.fn(),
  useNativeModelRunsMock: vi.fn(),
}));

vi.mock("@/hooks/useBos", () => ({
  useNativeModelRuntimeStatus: useNativeModelRuntimeStatusMock,
  useNativeModelDownloadPlan: useNativeModelDownloadPlanMock,
  useNativeModelDownload: useNativeModelDownloadMock,
  useNativeModelInference: useNativeModelInferenceMock,
  useNativeModelRuns: useNativeModelRunsMock,
}));

import { NativeModelRuntimeCard } from "@/components/bos/NativeModelRuntimeCard";

describe("NativeModelRuntimeCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useNativeModelRuntimeStatusMock.mockReturnValue({
      data: {
        enabled: true,
        cache_dir: "C:/tmp/native-models",
        summary: { total_models: 5 },
        runtimes: [
          {
            key: "insecta",
            runtime_state: "live_adapter_ready",
            modality: "vision",
            adapter_status: "contract_only",
            artifact: { exists: true, configured_location: "C:/tmp/insecta" },
            dependencies: [
              { package: "onnxruntime", installed: true },
              { package: "cv2", installed: true },
            ],
          },
        ],
      },
      refetch: vi.fn(),
    });
    useNativeModelDownloadPlanMock.mockReturnValue({ data: [], isLoading: false });
    useNativeModelDownloadMock.mockReturnValue({ isPending: false, mutate: vi.fn() });
    useNativeModelRunsMock.mockReturnValue({ data: [], isLoading: false });
    useNativeModelInferenceMock.mockReturnValue({
      isPending: false,
      mutate: vi.fn(),
      data: {
        model_key: "insecta",
        execution_mode: "insecta_bootstrap_live",
        runtime_state: "live_adapter_ready",
        result: {
          detection_count: 1,
          detections: [
            {
              top_label: "鞘翅目_步甲科,Carabidae",
              confidence: 0.91,
              bbox_xyxy: [1, 2, 3, 4],
              species_candidates: [
                { label: "鞘翅目_步甲科,Carabidae" },
                { label: "鞘翅目_步甲科_麻步甲,Carabus brandti" },
              ],
            },
          ],
          artifact_path: "C:/tmp/runs/insecta.json",
        },
        warnings: [],
      },
    });
  });

  it("renders bootstrap vision controls and detection details", () => {
    const html = renderToStaticMarkup(<NativeModelRuntimeCard batchId={42} />);

    expect(html).toContain("Run Insecta bootstrap");
    expect(html).toContain("Vision image URL");
    expect(html).toContain("Bootstrap public vision");
    expect(html).toContain("Detection 1");
    expect(html).toContain("鞘翅目_步甲科,Carabidae");
    expect(html).toContain("bbox: 1, 2, 3, 4");
  });
});
