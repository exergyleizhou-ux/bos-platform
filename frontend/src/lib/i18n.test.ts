// @ts-expect-error jsdom is installed in this workspace without a bundled type package.
import { JSDOM } from "jsdom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { applyDocumentTranslations, translateText } from "@/lib/i18n";

function installDom() {
  const dom = new JSDOM("<!doctype html><html><body></body></html>");
  vi.stubGlobal("document", dom.window.document);
  vi.stubGlobal("Node", dom.window.Node);
  vi.stubGlobal("Element", dom.window.Element);
  vi.stubGlobal("Text", dom.window.Text);
  vi.stubGlobal("NodeFilter", dom.window.NodeFilter);
  return dom.window.document;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("i18n translation", () => {
  it("translates English source copy into Chinese when requested", () => {
    expect(translateText("Compile the signal first", "zh-CN")).not.toBe(
      "Compile the signal first",
    );

    expect(
      translateText(
        "Complete one portability check first to see a clearer recommendation preview.",
        "zh-CN",
      ),
    ).not.toBe(
      "Complete one portability check first to see a clearer recommendation preview.",
    );
  });

  it("restores translated Chinese copy back to English in en-US mode", () => {
    const translatedSignal = translateText("Compile the signal first", "zh-CN");
    expect(translateText(translatedSignal, "en-US")).toBe("Compile the signal first");

    const translatedRecommendation = translateText(
      "Recommend release. There are no obvious portability blockers under the current conditions.",
      "zh-CN",
    );
    expect(
      translateText(
        translatedRecommendation,
        "en-US",
      ),
    ).toBe(
      "Recommend release. There are no obvious portability blockers under the current conditions.",
    );
  });

  it("preserves surrounding whitespace while translating", () => {
    const translated = translateText("  Signal Actions  ", "zh-CN");
    expect(translated.startsWith("  ")).toBe(true);
    expect(translated.endsWith("  ")).toBe(true);
    expect(translateText(translated, "en-US")).toBe("  Signal Actions  ");
  });

  it("keeps assistant and media exact translations readable in Chinese mode", () => {
    expect(translateText("BOS Assistant", "zh-CN")).toBe(`BOS \u52a9\u624b`);
    expect(translateText("Media Studio", "zh-CN")).toBe(`\u5a92\u4f53\u5de5\u4f5c\u53f0`);
    expect(translateText("Runtime ready", "zh-CN")).toBe(`\u8fd0\u884c\u65f6\u5df2\u5c31\u7eea`);
    expect(translateText("Campaign presets", "zh-CN")).toBe(`\u6d3b\u52a8\u9884\u8bbe`);
    expect(translateText("Recent renders", "zh-CN")).toBe(`\u6700\u8fd1\u6e32\u67d3`);
    expect(translateText("Safe generation", "zh-CN")).toBe(`\u5b89\u5168\u751f\u6210`);
    expect(translateText("Mode: Stable", "zh-CN")).toBe(`\u6a21\u5f0f: \u7a33\u5b9a`);
    expect(translateText("Route Fault", "zh-CN")).toBe(`\u8def\u7531\u6545\u969c`);
  });

  it("round-trips assistant and media exact translations back to English", () => {
    const assistantTranslated = translateText("BOS Assistant", "zh-CN");
    expect(translateText(assistantTranslated, "en-US")).toBe("BOS Assistant");

    const mediaTranslated = translateText("Media Studio", "zh-CN");
    expect(translateText(mediaTranslated, "en-US")).toBe("Media Studio");

    const safeGenerationTranslated = translateText("Safe generation", "zh-CN");
    expect(translateText(safeGenerationTranslated, "en-US")).toBe("Safe generation");
  });

  it("keeps LabSim 3D Lab Twin copy bilingual in Chinese mode", () => {
    const labSimCopy = [
      "3D Lab Twin",
      "Virtual closed-loop biowaste agent testbed",
      "Run experiment",
      "Replay seed",
      "Experiment timeline",
      "Material flow",
      "Lab assistant command",
      "Say one sentence and the bench demonstrates the operation.",
      "Demonstrate intake to reactor route",
      "Run virtual experiment and show assay bench",
      "Lab view mode",
      "Realistic Lab / Gaussian Splat",
      "Digital Twin",
      "Splat proof layer",
      "Gaussian splat renderer unavailable in this environment; Digital Twin fallback remains available.",
      "BSF on mixed food waste",
      "Runtime blocked. Hardware execution blocked. Validated defaults locked.",
      "BSF distillers grain high-moisture lane",
      "Simulation appendix is review evidence only; it does not change release decisions.",
    ];

    for (const source of labSimCopy) {
      const translated = translateText(source, "zh-CN");
      expect(translated, source).not.toBe(source);
      expect(translateText(translated, "en-US"), source).toBe(source);
    }
  });

  it("translates dynamic LabSim phrases without losing embedded values", () => {
    expect(
      translateText(
        "Experiment replay: BSF distillers grain high-moisture lane",
        "zh-CN",
      ),
    ).toContain("实验回放");
    expect(
      translateText(
        "Show whether BSF can process distillers grain while preserving review controls.",
        "zh-CN",
      ),
    ).toContain("可以处理 酒糟");
    expect(translateText("BSF on mixed food waste", "zh-CN")).toBe("黑水虻处理混合厨余");
    expect(
      translateText(
        "Moisture drift review and conversion stability; outputs remain virtual evidence.",
        "zh-CN",
      ),
    ).toContain("水分漂移复核与转化稳定性");
    expect(translateText("Cycle 3 replay", "zh-CN")).toContain("周期 3");
  });

  it("translates React-style updates to an existing text node", () => {
    const document = installDom();
    const paragraph = document.createElement("p");
    const textNode = document.createTextNode("Compile the signal first");
    paragraph.append(textNode);
    document.body.append(paragraph);

    applyDocumentTranslations(document.body, "zh-CN");
    expect(paragraph.textContent).toBe(translateText("Compile the signal first", "zh-CN"));

    textNode.nodeValue = "Signal Actions";
    applyDocumentTranslations(document.body, "zh-CN");
    expect(paragraph.textContent).toBe(translateText("Signal Actions", "zh-CN"));

    applyDocumentTranslations(document.body, "en-US");
    expect(paragraph.textContent).toBe("Signal Actions");
  });

  it("translates updated translatable attributes and restores English", () => {
    const document = installDom();
    const input = document.createElement("input");
    input.setAttribute("placeholder", "Search command center");
    input.setAttribute("title", "Open menu");
    document.body.append(input);

    applyDocumentTranslations(document.body, "zh-CN");
    expect(input.getAttribute("placeholder")).toBe(
      translateText("Search command center", "zh-CN"),
    );

    input.setAttribute("placeholder", "Search the thread");
    input.setAttribute("aria-label", "Toggle theme");
    applyDocumentTranslations(document.body, "zh-CN");
    expect(input.getAttribute("placeholder")).toBe(
      translateText("Search the thread", "zh-CN"),
    );
    expect(input.getAttribute("aria-label")).toBe(translateText("Toggle theme", "zh-CN"));

    applyDocumentTranslations(document.body, "en-US");
    expect(input.getAttribute("placeholder")).toBe("Search the thread");
    expect(input.getAttribute("title")).toBe("Open menu");
    expect(input.getAttribute("aria-label")).toBe("Toggle theme");
  });
});
