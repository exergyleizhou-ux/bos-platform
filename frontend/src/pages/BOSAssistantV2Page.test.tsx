/**
 * Phase A6 — BOSAssistantV2Page tests.
 *
 * Style: ``renderToStaticMarkup`` (consistent with the V1 tests in
 * BOSAssistantV1Page.render.test.tsx). No ``@testing-library/react``
 * dependency — production wiring is exercised end-to-end by the
 * backend ``tests/e2e/test_phase_a_e2e.py`` and the cross-process
 * subprocess demo in ``backend/scripts/phase_a_two_process_demo.py``.
 *
 * Interactive scenarios (fireEvent / click / submit) deliberately
 * deferred to Phase B/C UI polish:
 *   - ``@testing-library/react`` is NOT in current dependencies.
 *   - Phase A goal is demo wiring, not production QA.
 *   - Adding new dev deps risks compounding the known Node 24.14
 *     OOM symptoms observed during ``npm run build``.
 *
 * Coverage here:
 *   - Initial render (heading, message input, Send button,
 *     onboarding hint, V1 fallback link, thread id placeholder)
 *   - ``agentApi`` module shape (createAgentRun + getAgentHealth
 *     exported; types compile)
 *   - Route mounting at ``/bos/v2`` (asserted via the router config)
 *
 * TODO(Phase B/C): when the Node toolchain is upgraded and
 * ``@testing-library/react`` is added, expand to full interaction
 * tests (mock createAgentRun, fireEvent on the form, assert markdown
 * report renders + thread id persists across turns).
 */

import { describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";

// Mock the agent API module so the page doesn't try to talk to a real
// server during a server-side render.
vi.mock("@/api/agentApi", () => ({
  createAgentRun: vi.fn(),
  getAgentHealth: vi.fn(),
}));

import BOSAssistantV2Page from "@/pages/BOSAssistantV2Page";
import * as agentApi from "@/api/agentApi";

function renderHtml(): string {
  return renderToStaticMarkup(
    <MemoryRouter>
      <BOSAssistantV2Page />
    </MemoryRouter>,
  );
}

describe("BOSAssistantV2Page (renderToStaticMarkup)", () => {
  it("renders the page heading", () => {
    const html = renderHtml();
    expect(html).toContain("BOS Assistant V2");
  });

  it("renders the message input box", () => {
    const html = renderHtml();
    expect(html).toMatch(/aria-label="Message"/);
    expect(html).toMatch(/placeholder="Ask the BOS Agent/);
  });

  it("renders a Send button", () => {
    const html = renderHtml();
    expect(html).toMatch(/<button[^>]*type="submit"/);
    expect(html).toContain("Send");
  });

  it("renders the onboarding hint when the conversation is empty", () => {
    const html = renderHtml();
    expect(html).toContain("Send a message to start");
    // Three suggested demo prompts.
    expect(html).toContain("hello");
    expect(html).toContain("compute SER");
    expect(html).toContain("compare scenarios");
  });

  it("renders the V1 fallback link pointing at /bos", () => {
    const html = renderHtml();
    expect(html).toMatch(/href="\/bos"/);
    expect(html).toContain("Switch to V1");
  });

  it("renders the thread-id placeholder before the first turn", () => {
    const html = renderHtml();
    expect(html).toContain("new on first send");
  });
});

describe("agentApi module shape", () => {
  it("exports createAgentRun as a function", () => {
    expect(typeof agentApi.createAgentRun).toBe("function");
  });

  it("exports getAgentHealth as a function", () => {
    expect(typeof agentApi.getAgentHealth).toBe("function");
  });
});

describe("router mounts V2 at /bos/v2", () => {
  it("includes a /bos/v2 route in the lazy router config", async () => {
    // Read the router source so the assertion doesn't depend on the
    // lazy import resolving inside the test runner.
    const fs = await import("node:fs");
    const path = await import("node:path");
    const { fileURLToPath } = await import("node:url");
    const here = path.dirname(fileURLToPath(import.meta.url));
    const routerPath = path.resolve(here, "..", "router.tsx");
    const src = fs.readFileSync(routerPath, "utf8");
    expect(src).toMatch(/path:\s*"\/bos\/v2"/);
    expect(src).toMatch(/BOSAssistantV2Page/);
  });
});
