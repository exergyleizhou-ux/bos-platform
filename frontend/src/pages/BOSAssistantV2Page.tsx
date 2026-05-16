/**
 * BOS Assistant V2 — LangGraph-powered agent (Phase A target).
 *
 * Stub page for Phase 0.5. Phase A will replace this with a UI that
 * drives the new ``backend/agent/`` LangGraph service over HTTP.
 *
 * Route: `/bos/v2` (opt-in).  Default `/bos` still renders V1.
 */

import { Link } from "react-router-dom";

export default function BOSAssistantV2Page() {
  return (
    <div className="mx-auto max-w-2xl px-6 py-16">
      <h1 className="text-3xl font-semibold tracking-tight">
        BOS Assistant V2
      </h1>
      <p className="mt-4 text-base text-muted-foreground">
        LangGraph-powered agent. Coming in Phase A.
      </p>
      <p className="mt-2 text-sm text-muted-foreground">
        This surface will route operator intent through the new
        independent agent service running on port 8001 and call
        BOS Core via HTTP.
      </p>
      <div className="mt-8">
        <Link
          to="/bos"
          className="inline-flex items-center text-sm font-medium text-primary hover:underline"
        >
          ← Use V1 (current)
        </Link>
      </div>
    </div>
  );
}
