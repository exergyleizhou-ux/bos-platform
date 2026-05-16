import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const {
  useRemotionHealthMock,
  useRemotionTemplatesMock,
  useRemotionPresetsMock,
  useRemotionRenderMock,
  useRemotionRenderHistoryMock,
  useRemotionSuggestMock,
  useCreateRemotionPresetMock,
  useDeleteRemotionPresetMock,
  useUpdateRemotionPresetMock,
} = vi.hoisted(() => ({
  useRemotionHealthMock: vi.fn(),
  useRemotionTemplatesMock: vi.fn(),
  useRemotionPresetsMock: vi.fn(),
  useRemotionRenderMock: vi.fn(),
  useRemotionRenderHistoryMock: vi.fn(),
  useRemotionSuggestMock: vi.fn(),
  useCreateRemotionPresetMock: vi.fn(),
  useDeleteRemotionPresetMock: vi.fn(),
  useUpdateRemotionPresetMock: vi.fn(),
}));

vi.mock("@/hooks/useRemotionMedia", () => ({
  useRemotionHealth: useRemotionHealthMock,
  useRemotionTemplates: useRemotionTemplatesMock,
  useRemotionPresets: useRemotionPresetsMock,
  useRemotionRender: useRemotionRenderMock,
  useRemotionRenderHistory: useRemotionRenderHistoryMock,
  useRemotionSuggest: useRemotionSuggestMock,
  useCreateRemotionPreset: useCreateRemotionPresetMock,
  useDeleteRemotionPreset: useDeleteRemotionPresetMock,
  useUpdateRemotionPreset: useUpdateRemotionPresetMock,
}));

import BOSMediaStudioPage from "@/pages/BOSMediaStudioPage";

function idleMutation() {
  return {
    isPending: false,
    mutateAsync: vi.fn(),
    mutate: vi.fn(),
  };
}

describe("BOSMediaStudioPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    useRemotionHealthMock.mockReturnValue({
      data: {
        enabled: true,
        ready: true,
        runtime_dir: "/runtime/remotion",
        output_dir: "/output/remotion",
        node_executable: "node",
        details: ["Runtime files are present and Node is available."],
      },
      isPending: false,
      refetch: vi.fn(),
    });

    useRemotionTemplatesMock.mockReturnValue({
      data: [
        {
          id: "bos-launch-card",
          name: "BOS Launch Card",
          description: "High-contrast BOS hero card for still graphics and short kinetic loops.",
          supported_kinds: ["still", "video"],
          default_width: 1080,
          default_height: 1080,
          default_duration_in_frames: 150,
          default_fps: 30,
          fields: [],
        },
        {
          id: "bos-signal-beacon",
          name: "BOS Signal Beacon",
          description: "Portrait or landscape signal-driven visual for status recaps and release snapshots.",
          supported_kinds: ["still", "video"],
          default_width: 1920,
          default_height: 1080,
          default_duration_in_frames: 180,
          default_fps: 30,
          fields: [],
        },
      ],
      isPending: false,
    });

    useRemotionPresetsMock.mockReturnValue({
      data: [
        {
          id: "preset-1",
          name: "Weekly signal update",
          tags: ["ops", "signal"],
          snapshot_file_name: null,
          snapshot_kind: null,
          template_id: "bos-signal-beacon",
          kind: "video",
          export_recipe_id: "deck-header",
          creative_brief: "Weekly BOS signal recap for operators.",
          audience: "operators",
          brand_voice: "operations",
          title: "Signal is holding",
          subtitle: "The latest control-room recap is stable and clear.",
          caption: "OPS SIGNAL",
          accent_color: "#7CFFB2",
          background_color: "#07111F",
          width: "1920",
          height: "1080",
          fps: "30",
          duration_in_frames: "150",
          dynamic_fields: { status: "Ready" },
          created_at: "2026-04-15T00:00:00Z",
          updated_at: "2026-04-15T01:00:00Z",
        },
      ],
      isPending: false,
      refetch: vi.fn(),
    });

    useRemotionRenderHistoryMock.mockReturnValue({
      data: [
        {
          job_id: "render-1",
          kind: "still",
          template_id: "bos-launch-card",
          file_name: "render-1.png",
          mime_type: "image/png",
          width: 1080,
          height: 1080,
          fps: 30,
          duration_in_frames: 1,
          created_at: "2026-04-15T02:00:00Z",
          asset_url: "/renders/render-1.png",
          download_url: "/renders/render-1.png/download",
        },
      ],
      isPending: false,
      refetch: vi.fn(),
    });

    useRemotionRenderMock.mockReturnValue(idleMutation());
    useRemotionSuggestMock.mockReturnValue(idleMutation());
    useCreateRemotionPresetMock.mockReturnValue(idleMutation());
    useDeleteRemotionPresetMock.mockReturnValue(idleMutation());
    useUpdateRemotionPresetMock.mockReturnValue(idleMutation());
  });

  it("renders the main runtime, preset, template, and history surfaces", () => {
    const html = renderToStaticMarkup(<BOSMediaStudioPage />);

    expect(html).toContain("Campaign presets");
    expect(html).toContain("Runtime posture");
    expect(html).toContain("Ready to render");
    expect(html).toContain("Template gallery");
    expect(html).toContain("BOS Launch Card");
    expect(html).toContain("Weekly signal update");
    expect(html).toContain("Recent renders");
    expect(html).toContain("bos-launch-card");
    expect(html).toContain("still / 1080 x 1080");
    expect(html).toContain("/runtime/remotion");
    expect(html).toContain("/output/remotion");
  });
});
