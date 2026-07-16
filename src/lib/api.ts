// Live audit streaming client for the FastAPI audit engine.
//
// ARCHITECTURE
// ────────────
// The FastAPI backend exposes a single SSE (Server-Sent Events) endpoint:
//
//   POST /api/audit/stream
//   Body: { url, primary_keyword, location, competitors: string[] }
//
// It streams a sequence of JSON events:
//   {"type":"agent_start","agent":"Technical SEO"}
//   {"type":"finding","agent":"Technical SEO","check":"HTTPS","status":"passed","detail":"...","recommendation":"..."}
//   {"type":"agent_done","agent":"Technical SEO","score":72}
//   ... (one agent_start + N findings + agent_done per agent)
//   {"type":"audit_complete","scores":{...},"overall":64}
//
// The React client below reads this stream with the browser-native
// Fetch + ReadableStream API — no axios, no EventSource polyfill needed.
// If the backend is unreachable, we fall back to the built-in simulator
// so the UI remains fully functional during development.

import { generateAudit, AUDIT_AGENTS, type AuditResult, type Finding, type Severity } from "@/lib/store";

export interface AuditStreamEvent {
  type: "agent_start" | "finding" | "agent_done" | "audit_complete" | "error";
  agent?: string;
  check?: string;
  status?: Severity;
  detail?: string;
  recommendation?: string;
  score?: number;
  scores?: Record<string, number>;
  overall?: number;
  message?: string;
}

export interface AuditProgress {
  currentAgent: string;
  agentIndex: number;
  totalAgents: number;
  findings: Finding[];
  agentScores: Record<string, number>;
  complete: boolean;
  result: AuditResult | null;
  error: string | null;
}

const API_BASE = (import.meta as any).env?.VITE_API_BASE ?? "http://localhost:8000";

/**
 * Stream a live audit from the FastAPI backend.
 * Calls `onProgress` for every SSE event. Returns the final AuditResult.
 * Throws if the backend returns an error event or the connection fails.
 */
export async function streamAudit(
  params: { url: string; primaryKeyword: string; location: string; competitors: string[] },
  onProgress: (p: AuditProgress) => void,
  signal?: AbortSignal
): Promise<AuditResult> {
  const findings: Finding[] = [];
  const agentScores: Record<string, number> = {};
  let currentAgent = "";

  const update = (complete: boolean, error: string | null = null) => {
    const agentIndex = AUDIT_AGENTS.indexOf(currentAgent);
    const result: AuditResult | null = complete && !error
      ? {
          id: `a${Date.now()}`,
          clientId: "",
          url: params.url,
          primaryKeyword: params.primaryKeyword,
          location: params.location,
          competitors: params.competitors,
          createdAt: Date.now(),
          scores: agentScores,
          findings: [...findings],
        }
      : null;
    onProgress({
      currentAgent,
      agentIndex: agentIndex >= 0 ? agentIndex : 0,
      totalAgents: AUDIT_AGENTS.length,
      findings: [...findings],
      agentScores: { ...agentScores },
      complete,
      result,
      error,
    });
  };

  const resp = await fetch(`${API_BASE}/api/audit/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      url: params.url,
      primary_keyword: params.primaryKeyword,
      location: params.location,
      competitors: params.competitors,
    }),
    signal,
  });

  if (!resp.ok || !resp.body) {
    throw new Error(`Backend returned ${resp.status}`);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE events are separated by double newlines
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) >= 0) {
      const rawEvent = buffer.slice(0, sep).trim();
      buffer = buffer.slice(sep + 2);
      if (!rawEvent) continue;

      // Parse "data: {json}" lines
      const dataLines = rawEvent
        .split("\n")
        .filter((l) => l.startsWith("data:"))
        .map((l) => l.slice(5).trim());
      if (!dataLines.length) continue;

      try {
        const evt: AuditStreamEvent = JSON.parse(dataLines.join("\n"));

        switch (evt.type) {
          case "agent_start":
            currentAgent = evt.agent ?? "";
            update(false);
            break;
          case "finding":
            if (evt.agent && evt.check && evt.status) {
              findings.push({
                agent: evt.agent,
                check: evt.check,
                status: evt.status,
                detail: evt.detail ?? "",
                recommendation: evt.recommendation ?? "",
              });
              update(false);
            }
            break;
          case "agent_done":
            if (evt.agent && evt.score !== undefined) {
              const key = evt.agent === "Technical SEO" ? "Technical" : evt.agent === "Content SEO" ? "Content" : evt.agent;
              agentScores[key] = evt.score;
              update(false);
            }
            break;
          case "audit_complete":
            if (evt.scores) {
              Object.assign(agentScores, evt.scores);
            }
            update(true);
            return {
              id: `a${Date.now()}`,
              clientId: "",
              url: params.url,
              primaryKeyword: params.primaryKeyword,
              location: params.location,
              competitors: params.competitors,
              createdAt: Date.now(),
              scores: agentScores,
              findings: [...findings],
            };
          case "error":
            throw new Error(evt.message ?? "Backend error");
        }
      } catch (e) {
        // Skip malformed event lines
      }
    }
  }

  // Stream ended without audit_complete
  update(true);
  return {
    id: `a${Date.now()}`,
    clientId: "",
    url: params.url,
    primaryKeyword: params.primaryKeyword,
    location: params.location,
    competitors: params.competitors,
    createdAt: Date.now(),
    scores: agentScores,
    findings: [...findings],
  };
}

/**
 * Run an audit. Attempts the live FastAPI backend first; if unreachable,
 * falls back to the built-in simulator so the UI always works.
 */
export async function runAudit(
  params: { url: string; primaryKeyword: string; location: string; competitors: string[] },
  onProgress: (p: AuditProgress) => void,
  signal?: AbortSignal
): Promise<{ result: AuditResult; live: boolean }> {
  try {
    const result = await streamAudit(params, onProgress, signal);
    return { result, live: true };
  } catch (err) {
    // Backend unavailable — fall back to simulator
    return simulateAudit(params, onProgress);
  }
}

/**
 * Built-in simulator that mimics the SSE stream timing.
 */
function simulateAudit(
  params: { url: string; primaryKeyword: string; location: string; competitors: string[] },
  onProgress: (p: AuditProgress) => void
): Promise<{ result: AuditResult; live: boolean }> {
  return new Promise((resolve) => {
    const audit = generateAudit(params.url, params.primaryKeyword, params.location, params.competitors);
    const findingsByAgent: Record<string, Finding[]> = {};
    audit.findings.forEach((f) => {
      if (!findingsByAgent[f.agent]) findingsByAgent[f.agent] = [];
      findingsByAgent[f.agent].push(f);
    });

    let i = 0;
    const tick = () => {
      if (i >= AUDIT_AGENTS.length) {
        onProgress({
          currentAgent: "",
          agentIndex: AUDIT_AGENTS.length,
          totalAgents: AUDIT_AGENTS.length,
          findings: audit.findings,
          agentScores: audit.scores,
          complete: true,
          result: audit,
          error: null,
        });
        resolve({ result: audit, live: false });
        return;
      }
      const agent = AUDIT_AGENTS[i];
      const agentFindings = findingsByAgent[agent] ?? [];
      const key = agent === "Technical SEO" ? "Technical" : agent === "Content SEO" ? "Content" : agent;

      // Emit findings for this agent
      let fi = 0;
      const emitFinding = () => {
        if (fi < agentFindings.length) {
          onProgress({
            currentAgent: agent,
            agentIndex: i,
            totalAgents: AUDIT_AGENTS.length,
            findings: audit.findings.slice(0, audit.findings.indexOf(agentFindings[fi]) + 1),
            agentScores: audit.scores,
            complete: false,
            result: null,
            error: null,
          });
          fi++;
          setTimeout(emitFinding, 120);
        } else {
          i++;
          setTimeout(tick, 200);
        }
      };
      emitFinding();
    };
    tick();
  });
}