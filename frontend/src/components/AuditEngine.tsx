import { useState, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CheckCircle2, Loader2, Radar, Terminal, Zap, AlertCircle, CreditCard } from "lucide-react";
import { useClaude } from "@/components/ClaudeProvider";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { useAudit } from "@/context/AuditContext";

const initialAgents = [
  { name: "Technical SEO Agent", description: "Crawlability, indexing, core web vitals", status: "pending" as const, logs: [] },
  { name: "Content SEO Agent", description: "Content quality, keyword density, headings", status: "pending" as const, logs: [] },
  { name: "Local SEO Agent", description: "GMB, citations, local rankings", status: "pending" as const, logs: [] },
  { name: "Schema Agent", description: "Structured data validation", status: "pending" as const, logs: [] },
  { name: "EEAT Agent", description: "Experience, Expertise, Authority, Trust", status: "pending" as const, logs: [] },
  { name: "Internal Linking Agent", description: "Link structure, anchor text, orphan pages", status: "pending" as const, logs: [] },
  { name: "Competitor Agent", description: "Gap analysis, competitor rankings", status: "pending" as const, logs: [] },
  { name: "Backlink Agent", description: "Backlink profile, toxic links, DA", status: "pending" as const, logs: [] },
  { name: "AI Search Agent", description: "LLM visibility, AI snippet optimization", status: "pending" as const, logs: [] },
  { name: "Reporting Agent", description: "Compile findings, generate report", status: "pending" as const, logs: [] },
];

export function AuditEngine() {
  const { isConfigured } = useClaude();
  const [url, setUrl] = useState("https://example.com");
  const [showBudgetDialog, setShowBudgetDialog] = useState(false);
  const [budgetAmount, setBudgetAmount] = useState(10);
  const [isAddingBudget, setIsAddingBudget] = useState(false);

  const {
    running,
    agents,
    progress,
    globalLogs,
    setRunning,
    setAgents,
    setProgress,
    setGlobalLogs,
  } = useAudit();

  const abortControllerRef = useRef<AbortController | null>(null);

  const handleEvent = (data: any) => {
    if (data.type === "agent_start") {
      setAgents((prev) =>
        prev.map((a) =>
          a.name === data.agent ? { ...a, status: "running" } : a
        )
      );
      setGlobalLogs((prev) => [...prev, `[${new Date().toLocaleTimeString()}] Agent started: ${data.agent}`]);
    } else if (data.type === "log") {
      setAgents((prev) =>
        prev.map((a) =>
          a.name === data.agent ? { ...a, logs: [...a.logs, data.message] } : a
        )
      );
      setGlobalLogs((prev) => [...prev, `  > ${data.message}`]);
    } else if (data.type === "error") {
      if (data.message.includes("Insufficient AI credits")) {
        setShowBudgetDialog(true);
        setRunning(false);
        toast.error("Insufficient AI credits. Please add budget.");
        return;
      }
      toast.error(data.message || "Agent error");
      setAgents((prev) =>
        prev.map((a) =>
          a.name === data.agent ? { ...a, status: "error", logs: [...a.logs, data.message] } : a
        )
      );
    } else if (data.type === "complete") {
      setRunning(false);
      setProgress(100);
      setGlobalLogs((prev) => [...prev, `[${new Date().toLocaleTimeString()}] Audit complete. Score: ${data.score?.toFixed(1) || "N/A"}`]);
      toast.success(`Audit complete! Overall score: ${data.score?.toFixed(1) || "N/A"}`);
      if (data.results) {
        data.results.forEach((r: any) => {
          setAgents((prev) =>
            prev.map((a) =>
              a.name === r.agent ? { ...a, status: "complete", score: r.score } : a
            )
          );
        });
      }
    }
  };

  const runAudit = async () => {
    if (running) return;
    if (!isConfigured) {
      toast.error("Claude API key not configured. Please add it in Settings.");
      return;
    }

    setRunning(true);
    setProgress(0);
    setGlobalLogs([`[${new Date().toLocaleTimeString()}] Starting audit for ${url}...`]);
    setAgents(initialAgents.map((a) => ({ ...a, status: "pending", logs: [] })));

    try {
      const token = localStorage.getItem("access_token");
      if (!token) {
        toast.error("Please login first.");
        setRunning(false);
        return;
      }

      abortControllerRef.current = new AbortController();
      const baseUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";
      const response = await fetch(`${baseUrl}/api/audits/run?url=${encodeURIComponent(url)}`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Accept": "text/event-stream",
        },
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(`Server error: ${response.status} - ${text}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("No reader available");
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              handleEvent(data);
            } catch (e) {
              console.warn("Failed to parse SSE data:", line);
            }
          }
        }
      }

      if (progress < 100) {
        setProgress(100);
        setRunning(false);
      }

    } catch (error: any) {
      if (error.name === "AbortError") {
        setGlobalLogs((prev) => [...prev, `[${new Date().toLocaleTimeString()}] Audit cancelled.`]);
        setRunning(false);
        return;
      }
      console.error("Audit error:", error);
      toast.error(error.message || "Failed to run audit.");
      setRunning(false);
      setGlobalLogs((prev) => [...prev, `[${new Date().toLocaleTimeString()}] Error: ${error.message}`]);
    }
  };

  const addBudget = async () => {
    setIsAddingBudget(true);
    try {
      await api.post(`/api/company/add-credits?amount=${budgetAmount}`, {});
      toast.success(`Added ${budgetAmount} credits.`);
      setShowBudgetDialog(false);
    } catch (error) {
      console.error("Failed to add credits:", error);
      toast.error("Could not add credits.");
    } finally {
      setIsAddingBudget(false);
    }
  };

  const completedCount = agents.filter((a) => a.status === "complete").length;

  return (
    <div className="p-8 space-y-6">
      <header>
        <h2 className="font-serif text-3xl font-bold tracking-tight">AI Audit Engine</h2>
        <p className="text-slate-500 dark:text-slate-400 mt-1">
          Multi-agent autonomous SEO analysis with live streaming progress.
        </p>
      </header>

      {!isConfigured && (
        <Card className="border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-900/10">
          <CardContent className="p-4 flex items-center gap-3">
            <AlertCircle className="size-5 text-amber-600" />
            <p className="text-sm text-amber-700 dark:text-amber-400">
              Claude API Key required. Please configure it in Settings to enable AI-powered audit insights.
            </p>
          </CardContent>
        </Card>
      )}

      <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
        <CardHeader>
          <CardTitle className="font-serif">Start New Audit</CardTitle>
          <CardDescription>Enter the URL to analyze. All 10 agents will execute sequentially.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-end gap-4">
            <div className="flex-1 space-y-2">
              <Label htmlFor="url">Target URL</Label>
              <Input
                id="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://your-domain.com"
                disabled={running}
              />
            </div>
            <Button
              onClick={runAudit}
              disabled={running}
              className="bg-emerald-600 hover:bg-emerald-700 text-white shadow-md shadow-emerald-600/20"
            >
              {running ? <Loader2 className="size-4 animate-spin" /> : <Zap className="size-4" fill="white" />}
              {running ? "Running..." : "Run Audit"}
            </Button>
          </div>

          {(running || progress > 0) && (
            <div className="mt-6 space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-slate-500 dark:text-slate-400">
                  {completedCount} / {agents.length} agents complete
                </span>
                <span className="font-semibold text-emerald-600 dark:text-emerald-400">
                  {Math.round(progress)}%
                </span>
              </div>
              <div className="h-2.5 w-full rounded-full bg-slate-200 dark:bg-slate-800 overflow-hidden">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-500 transition-all duration-500"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
          <CardHeader>
            <CardTitle className="font-serif flex items-center gap-2">
              <Radar className="size-5 text-emerald-600" />
              Agent Status
            </CardTitle>
            <CardDescription>Real-time agent execution pipeline</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {agents.map((agent) => (
              <div
                key={agent.name}
                className={cn(
                  "flex items-center gap-3 p-3 rounded-lg border transition-all",
                  agent.status === "running"
                    ? "border-emerald-300 dark:border-emerald-700 bg-emerald-50 dark:bg-emerald-500/10"
                    : agent.status === "error"
                    ? "border-rose-300 dark:border-rose-700 bg-rose-50 dark:bg-rose-500/10"
                    : "border-slate-200 dark:border-slate-800"
                )}
              >
                <div className="shrink-0">
                  {agent.status === "complete" ? (
                    <CheckCircle2 className="size-5 text-emerald-500" />
                  ) : agent.status === "running" ? (
                    <Loader2 className="size-5 text-emerald-500 animate-spin" />
                  ) : agent.status === "error" ? (
                    <AlertCircle className="size-5 text-rose-500" />
                  ) : (
                    <div className="size-5 rounded-full border-2 border-slate-300 dark:border-slate-700" />
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{agent.name}</p>
                  <p className="text-xs text-slate-500 dark:text-slate-400 truncate">
                    {agent.status === "running" && agent.logs.length > 0
                      ? agent.logs[agent.logs.length - 1]
                      : agent.status === "complete" && agent.score !== undefined
                      ? `Score: ${agent.score}`
                      : agent.description}
                  </p>
                </div>
                {agent.status === "running" && (
                  <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 animate-pulse">
                    LIVE
                  </span>
                )}
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
          <CardHeader>
            <CardTitle className="font-serif flex items-center gap-2">
              <Terminal className="size-5 text-slate-600 dark:text-slate-400" />
              Live Logs
            </CardTitle>
            <CardDescription>Streaming audit output</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[420px] overflow-y-auto rounded-lg bg-slate-950 dark:bg-black p-4 font-mono text-xs space-y-1 border border-slate-800">
              {globalLogs.length === 0 ? (
                <p className="text-slate-600 italic">Waiting for audit to start...</p>
              ) : (
                globalLogs.map((log, i) => (
                  <div
                    key={i}
                    className={cn(
                      "text-slate-300",
                      log.includes("started") && "text-emerald-400 font-semibold",
                      log.includes("completed") && "text-teal-400 font-semibold",
                      log.includes("complete") && "text-teal-400 font-semibold",
                      log.startsWith("  >") && "text-slate-400 pl-2"
                    )}
                  >
                    {log}
                  </div>
                ))
              )}
              {running && (
                <div className="text-emerald-400 animate-pulse">▊</div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {showBudgetDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <Card className="w-full max-w-md border-slate-200 dark:border-slate-800 shadow-xl">
            <CardHeader>
              <CardTitle className="font-serif flex items-center gap-2">
                <CreditCard className="size-5 text-amber-600" />
                Insufficient AI Credits
              </CardTitle>
              <CardDescription>
                You need to add budget to run the audit. Each audit consumes 1 credit.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="budget-amount">Credits to Add</Label>
                <Input
                  id="budget-amount"
                  type="number"
                  min={1}
                  value={budgetAmount}
                  onChange={(e) => setBudgetAmount(parseInt(e.target.value) || 1)}
                />
              </div>
            </CardContent>
            <div className="flex justify-end gap-2 p-6 pt-0">
              <Button variant="outline" onClick={() => setShowBudgetDialog(false)}>
                Cancel
              </Button>
              <Button onClick={addBudget} disabled={isAddingBudget} className="bg-emerald-600 hover:bg-emerald-700 text-white">
                {isAddingBudget ? <Loader2 className="size-4 animate-spin" /> : "Add Credits"}
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}