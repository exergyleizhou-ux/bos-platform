import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { NextBestActionsCard } from "@/components/bos/NextBestActionsCard";

describe("NextBestActionsCard", () => {
  it("renders CTA labels when actions are provided", () => {
    const html = renderToStaticMarkup(
      <NextBestActionsCard
        items={[
          {
            code: "release_blocked",
            title: "Release is currently blocked",
            message: "A blocking release condition is active.",
            recommendedAction: "Open signal lab and resolve the blocking condition.",
            severity: "critical",
            blocking: true,
            actionLabel: "Open signal lab",
          },
        ]}
        onAction={() => undefined}
      />,
    );

    expect(html).toContain("Release is currently blocked");
    expect(html).toContain("Open signal lab and resolve the blocking condition.");
    expect(html).toContain("Open signal lab");
  });

  it("renders empty-state copy without actions", () => {
    const html = renderToStaticMarkup(<NextBestActionsCard items={[]} />);

    expect(html).toContain("No additional actions are recommended right now.");
  });
});
