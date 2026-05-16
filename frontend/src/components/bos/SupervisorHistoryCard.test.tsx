import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { SupervisorHistoryCard } from "@/components/bos/SupervisorHistoryCard";
import { sampleAuditPacketView } from "@/lib/bos-read-model.fixture";

describe("SupervisorHistoryCard", () => {
  it("renders supervisor history when snapshots are available", () => {
    const html = renderToStaticMarkup(
      <SupervisorHistoryCard history={[sampleAuditPacketView.supervisorSnapshot!]} />,
    );

    expect(html).toContain("Supervisor history");
    expect(html).toContain("1 observations");
    expect(html).toContain("Latest mode handover");
  });
});
