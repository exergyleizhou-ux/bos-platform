import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { SupervisorSnapshotCard } from "@/components/bos/SupervisorSnapshotCard";
import { sampleAuditPacketView } from "@/lib/bos-read-model.fixture";

describe("SupervisorSnapshotCard", () => {
  it("renders persisted supervisor details", () => {
    const html = renderToStaticMarkup(
      <SupervisorSnapshotCard snapshot={sampleAuditPacketView.supervisorSnapshot} />,
    );

    expect(html).toContain("Latest supervisor snapshot");
    expect(html).toContain("handover");
    expect(html).toContain("Handover advised");
    expect(html).toContain("negative_slope_persistence");
    expect(html).toContain("Expanded decision");
  });
});
