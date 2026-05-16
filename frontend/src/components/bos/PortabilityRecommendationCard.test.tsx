import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { PortabilityRecommendationCard } from "@/components/bos/PortabilityRecommendationCard";

describe("PortabilityRecommendationCard", () => {
  it("renders explicit retuning guidance", () => {
    const html = renderToStaticMarkup(
      <PortabilityRecommendationCard
        recommendation={{
          signal_batch_id: 11,
          executor_profile_id: 7,
          locality_profile_id: 8,
          recommended_outcome: "PASS_WITH_RETUNING",
          rationale: "The signal can transfer, but portability risk remains elevated around HAL.",
          recommended_action: "Retune HAL before formal release.",
          requires_requalification: false,
          retuning_axes: ["HAL"],
          retuning_magnitude: 0.12,
          override_outcome: null,
          portability_score: 0.82,
        }}
      />,
    );

    expect(html).toContain("Release with retuning");
    expect(html).toContain("portability risk remains elevated around HAL");
    expect(html).toContain("Retune HAL before formal release.");
    expect(html).toContain("HAL");
  });

  it("renders explicit requalification guidance", () => {
    const html = renderToStaticMarkup(
      <PortabilityRecommendationCard
        recommendation={{
          signal_batch_id: 11,
          executor_profile_id: 7,
          locality_profile_id: 8,
          recommended_outcome: "FAIL",
          rationale: "The current signal and portability context remain outside the safe transfer envelope.",
          recommended_action: "Requalify the signal under a different executor or locality before release.",
          requires_requalification: true,
          retuning_axes: ["executor_hal"],
          retuning_magnitude: 0.33,
          override_outcome: null,
          portability_score: 0.22,
        }}
      />,
    );

    expect(html).toContain("Do not release");
    expect(html).toContain("Requalification required");
    expect(html).toContain("outside the safe transfer envelope");
    expect(html).toContain("Requalify the signal under a different executor or locality before release.");
  });
});
