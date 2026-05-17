/**
 * BOS Assistant V2 — LangGraph-powered chat surface (Phase A6).
 *
 * Sends operator messages to the BOS Agent service (default
 * http://localhost:8001 via Vite's `/agent` proxy) and renders the
 * returned markdown report + audit-trail summary.
 *
 * Lives at `/bos/v2` (opt-in). The V1 surface remains the default at
 * `/bos`, unchanged since Phase 0.5.
 */

import { useState } from "react";
import { Link } from "react-router-dom";

import {
  createAgentRun,
  type AgentRunResponse,
  type AgentToolCallRecord,
} from "@/api/agentApi";

interface ConversationTurn {
  id: number;
  role: "user" | "agent";
  text: string;
  /** Populated only on agent turns. */
  response?: AgentRunResponse;
  /** Populated on agent turns when the request failed. */
  error?: string;
}

function ToolCallList({ records }: { records: AgentToolCallRecord[] }) {
  if (!records.length) return null;
  return (
    <details className="mt-3 text-xs text-muted-foreground">
      <summary className="cursor-pointer select-none">
        Tool calls ({records.length})
      </summary>
      <ul className="mt-2 space-y-1">
        {records.map((r, i) => (
          <li
            key={i}
            className={r.status === "error" ? "text-red-500" : ""}
          >
            <span className="font-mono">{r.tool}</span>
            {" "}— {r.status ?? "?"}
            {typeof r.duration_ms === "number" ? ` (${r.duration_ms} ms)` : ""}
            {r.error ? `: ${r.error}` : ""}
          </li>
        ))}
      </ul>
    </details>
  );
}

function AgentTurnView({ turn }: { turn: ConversationTurn }) {
  if (turn.error) {
    return (
      <div className="rounded-md border border-red-300 bg-red-50 p-3 text-sm text-red-700">
        Agent error: {turn.error}
      </div>
    );
  }
  const resp = turn.response;
  if (!resp) return null;
  return (
    <div className="rounded-md border border-border bg-card p-3 text-sm">
      <div className="mb-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
        <span>
          intent: <span className="font-mono">{resp.intent ?? "—"}</span>
        </span>
        {resp.evidence_level ? (
          <span>
            evidence: <span className="font-mono">{resp.evidence_level}</span>
          </span>
        ) : null}
        {typeof resp.ser === "number" ? (
          <span>
            SER: <span className="font-mono">{resp.ser.toFixed(4)}</span>
          </span>
        ) : null}
        {resp.sfi_zone ? (
          <span>
            SFI: <span className="font-mono">{resp.sfi_zone}</span>
          </span>
        ) : null}
      </div>
      <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-relaxed">
        {resp.report ?? "(no report)"}
      </pre>
      <ToolCallList records={resp.tool_calls ?? []} />
    </div>
  );
}

export default function BOSAssistantV2Page() {
  const [input, setInput] = useState("");
  const [turns, setTurns] = useState<ConversationTurn[]>([]);
  const [pending, setPending] = useState(false);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || pending) return;
    setError(null);

    const userTurn: ConversationTurn = {
      id: Date.now(),
      role: "user",
      text,
    };
    setTurns((t) => [...t, userTurn]);
    setInput("");
    setPending(true);

    try {
      const resp = await createAgentRun({
        message: text,
        thread_id: threadId ?? undefined,
      });
      setThreadId(resp.thread_id);
      setTurns((t) => [
        ...t,
        {
          id: Date.now() + 1,
          role: "agent",
          text: resp.report ?? "",
          response: resp,
        },
      ]);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      setTurns((t) => [
        ...t,
        {
          id: Date.now() + 1,
          role: "agent",
          text: "",
          error: msg,
        },
      ]);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col px-6 py-10">
      <header className="mb-6">
        <h1 className="text-3xl font-semibold tracking-tight">
          BOS Assistant V2
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          LangGraph-powered agent. Routes operator messages through the
          independent agent service (port 8001) and calls BOS Core
          (port 8000) over HTTP.
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          Thread:{" "}
          <span className="font-mono">{threadId ?? "(new on first send)"}</span>
          {" · "}
          <Link to="/bos" className="text-primary hover:underline">
            ← Switch to V1
          </Link>
        </p>
      </header>

      <section
        className="mb-6 flex-1 space-y-3"
        data-testid="bos-v2-conversation"
      >
        {turns.length === 0 ? (
          <div className="rounded-md border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
            Send a message to start. Phase A demo prompts:
            <ul className="mt-2 list-disc text-left text-xs sm:pl-8">
              <li><code>hello</code> — smalltalk path (no Core call)</li>
              <li><code>compute SER</code> — needs state fields filled by Phase B</li>
              <li><code>compare scenarios</code> — cyber-lab placeholder</li>
            </ul>
          </div>
        ) : (
          turns.map((turn) =>
            turn.role === "user" ? (
              <div key={turn.id} className="flex justify-end">
                <div className="max-w-[80%] rounded-md bg-primary px-3 py-2 text-sm text-primary-foreground">
                  {turn.text}
                </div>
              </div>
            ) : (
              <AgentTurnView key={turn.id} turn={turn} />
            ),
          )
        )}
        {pending ? (
          <div className="text-xs text-muted-foreground">Agent thinking…</div>
        ) : null}
        {error ? (
          <div className="text-xs text-red-500" role="alert">
            {error}
          </div>
        ) : null}
      </section>

      <form
        onSubmit={handleSubmit}
        className="flex gap-2 border-t border-border pt-4"
        aria-label="bos-v2-message-form"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask the BOS Agent…"
          aria-label="Message"
          className="flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm"
          disabled={pending}
        />
        <button
          type="submit"
          disabled={pending || !input.trim()}
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </div>
  );
}
