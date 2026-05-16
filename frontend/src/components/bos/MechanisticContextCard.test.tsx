import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { MechanisticContextCard } from "@/components/bos/MechanisticContextCard";
import { sampleAuditPacketView } from "@/lib/bos-read-model.fixture";

describe("MechanisticContextCard", () => {
  it("renders mechanistic summary metrics and chart labels", () => {
    const html = renderToStaticMarkup(
      <MechanisticContextCard
        context={sampleAuditPacketView.mechanisticContext}
        signalLabel={sampleAuditPacketView.signalLabel}
      />,
    );

    expect(html).toContain("Mechanistic signal snapshot");
    expect(html).toContain("SIG-BOS-DEMO-042");
    expect(html).toContain("C-DI-SER");
    expect(html).toContain("Tau star");
    expect(html).toContain("Signal geometry");
    expect(html).toContain("Handover envelope");
    expect(html).toContain("Expanded parameters");
  });

  it("falls back gracefully when the mechanistic payload is incomplete", () => {
    const html = renderToStaticMarkup(
      <MechanisticContextCard
        context={{} as never}
        signalLabel="SIG-INCOMPLETE"
      />,
    );

    expect(html).toContain("Mechanistic signal snapshot");
    expect(html).toContain("Compile a signal first");
  });
});
