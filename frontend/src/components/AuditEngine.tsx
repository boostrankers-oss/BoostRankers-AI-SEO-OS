import { useRef, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AlertCircle, CheckCircle2, CreditCard, Database, FileSearch, Loader2, Radar, Terminal, Zap } from "lucide-react";
import { useClaude } from "@/components/ClaudeProvider";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { useAudit } from "@/context/AuditContext";

type SkillStatus = "pending" | "running" | "complete" | "error";
type Skill = { name: string; description: string; status: SkillStatus; logs: string[]; score?: number };

type CrawlMetrics = {
  pages_discovered: number;
  pages_crawled: number;
  pages_successful: number;
  internal_links: number;
  external_links: number;
  broken_internal_links: number;
  orphan_pages_count: number;
  sitemap_found: boolean;
  robots_found: boolean;
  schema_found: boolean;
  duplicate_pages: number;
};

const skills: Skill[] = [
  { name: "Technical SEO Agent", description: "HTTP status, crawlability, indexing, canonicals, robots and sitemap", status: "pending", logs: [] },
  { name: "Content SEO Agent", description: "Titles, meta descriptions, headings, content depth and duplicates", status: "pending", logs: [] },
  { name: "Local SEO Agent", description: "On-site local relevance and entity signals", status: "pending", logs: [] },
  { name: "Schema Agent", description: "JSON-LD and structured-data coverage", status: "pending", logs: [] },
  { name: "EEAT Agent", description: "Experience, expertise, authority and trust signals", status: "pending", logs: [] },
  { name: "Internal Linking Agent", description: "Internal graph, orphan pages, anchors and crawl depth", status: "pending", logs: [] },
  { name: "Competitor Agent", description: "Competitive opportunities without fabricated metrics", status: "pending", logs: [] },
  { name: "Backlink Agent", description: "Link acquisition readiness and crawl limitations", status: "pending", logs: [] },
  { name: "AI Search Agent", description: "Entities, answerability and machine-readable content", status: "pending", logs: [] },
  { name: "Reporting Agent", description: "Executive summary and prioritized remediation plan", status: "pending", logs: [] },
];

const blankMetrics: CrawlMetrics = {
  pages_discovered: 0, pages_crawled: 0, pages_successful: 0, internal_links: 0, external_links: 0,
  broken_internal_links: 0, orphan_pages_count: 0, sitemap_found: false, robots_found: false,
  schema_found: false, duplicate_pages: 0,
};

export function AuditEngine() {
  const { isConfigured, isReady, status } = useClaude();
  const { running, agents, progress, globalLogs, setRunning, setAgents, setProgress, setGlobalLogs } = useAudit();
  const [url, setUrl] = useState("https://example.com");
  const [crawlMetrics, setCrawlMetrics] = useState<CrawlMetrics>(blankMetrics);
  const [crawlComplete, setCrawlComplete] = useState(false);
  const [currentStage, setCurrentStage] = useState("Ready");
  const [showBudgetDialog, setShowBudgetDialog] = useState(false);
  const [budgetAmount, setBudgetAmount] = useState(10);
  const [isAddingBudget, setIsAddingBudget] = useState(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  const pushLog = (message: string) => setGlobalLogs((prev) => [...prev, `[${new Date().toLocaleTimeString()}] ${message}`]);

  const handleEvent = (data: any) => {
    if (data.type === "started") {
      setCurrentStage("Website Crawler");
      pushLog(data.message || "Audit started.");
      return;
    }
    if (data.type === "crawl_stage") {
      setCurrentStage(`Crawler · ${data.stage}`);
      setProgress(Number(data.progress ?? 0));
      pushLog(data.message || `Crawler stage: ${data.stage}`);
      return;
    }
    if (data.type === "crawl_progress") {
      setCurrentStage("Website Crawler");
      setProgress(Number(data.progress ?? 0));
      if (data.pages_crawled) setCrawlMetrics((m) => ({ ...m, pages_crawled: data.pages_crawled, pages_discovered: Math.max(m.pages_discovered, data.pages_discovered || 0) }));
      if (data.url) setGlobalLogs((prev) => [...prev, `  > Crawling ${data.url}`]);
      return;
    }
    if (data.type === "crawl_complete") {
      setCrawlComplete(true);
      setProgress(Number(data.progress ?? 65));
      setCurrentStage("Crawler complete · specialist skills starting");
      if (data.metrics) setCrawlMetrics((m) => ({ ...m, ...data.metrics }));
      pushLog(data.message || "Real crawl completed.");
      return;
    }
    if (data.type === "agent_start") {
      setCurrentStage(data.agent || "SEO skill");
      setProgress(Number(data.progress ?? progress));
      setAgents((prev) => prev.map((a) => a.name === data.agent ? { ...a, status: "running" } : a));
      pushLog(`Skill started: ${data.agent}`);
      return;
    }
    if (data.type === "log") {
      setAgents((prev) => prev.map((a) => a.name === data.agent ? { ...a, logs: [...a.logs, data.message] } : a));
      setGlobalLogs((prev) => [...prev, `  > ${data.message}`]);
      return;
    }
    if (data.type === "agent_complete") {
      setProgress(Number(data.progress ?? progress));
      setAgents((prev) => prev.map((a) => a.name === data.agent ? { ...a, status: "complete", score: data.score } : a));
      pushLog(`Skill completed: ${data.agent} · score ${data.score ?? "N/A"}`);
      return;
    }
    if (data.type === "agent_error") {
      setAgents((prev) => prev.map((a) => a.name === data.agent ? { ...a, status: "error", logs: [...a.logs, data.message] } : a));
      pushLog(`Skill error: ${data.agent} · ${data.message}`);
      return;
    }
    if (data.type === "provider_error" || data.type === "ai_provider_unavailable") {
      setRunning(false);
      toast.error(data.message || "AI provider error.");
      pushLog(`AI provider error: ${data.message}`);
      return;
    }
    if (data.type === "billing_required") {
      setShowBudgetDialog(true);
      setRunning(false);
      toast.error(data.message || "Insufficient AI credits.");
      return;
    }
    if (data.type === "warning") {
      pushLog(`Warning: ${data.message}`);
      toast.warning(data.message);
      return;
    }
    if (data.type === "complete") {
      setProgress(100);
      setRunning(false);
      setCurrentStage("Completed");
      if (data.crawl_metrics) setCrawlMetrics((m) => ({ ...m, ...data.crawl_metrics }));
      if (Array.isArray(data.results)) {
        setAgents((prev) => prev.map((a) => {
          const result = data.results.find((r: any) => r.agent === a.name);
          return result ? { ...a, status: "complete", score: result.score } : a;
        }));
      }
      pushLog(`Audit complete · overall score ${data.score ?? "N/A"}`);
      toast.success(`Audit complete · score ${data.score ?? "N/A"}/100`);
    }
    if (data.type === "error") {
      setRunning(false);
      toast.error(data.message || "Audit failed.");
      pushLog(`Error: ${data.message}`);
    }
  };

  const runAudit = async () => {
    if (running) return;
    const normalized = url.trim();
    if (!/^https?:\/\//i.test(normalized)) {
      toast.error("Enter a complete http:// or https:// website URL.");
      return;
    }
    if (!isConfigured) { toast.error("Claude API key not configured. Please add it in Settings."); return; }
    if (!isReady) {
      toast.error(status === "billing_required" ? "Anthropic billing is required." : status === "invalid_api_key" ? "Anthropic API key is invalid." : "Claude AI is currently unavailable.");
      return;
    }
    const token = localStorage.getItem("access_token");
    if (!token) { toast.error("Please login first."); return; }

    setRunning(true);
    setProgress(0);
    setCrawlMetrics(blankMetrics);
    setCrawlComplete(false);
    setCurrentStage("Starting real website crawl");
    setAgents(skills.map((s) => ({ ...s, status: "pending", logs: [] })));
    setGlobalLogs([`[${new Date().toLocaleTimeString()}] Starting real crawl for ${normalized}`]);

    try {
      abortControllerRef.current = new AbortController();
      const baseUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";
      const response = await fetch(`${baseUrl}/api/audits/run?url=${encodeURIComponent(normalized)}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, Accept: "text/event-stream" },
        signal: abortControllerRef.current.signal,
      });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(`Server error: ${response.status} - ${text}`);
      }
      const reader = response.body?.getReader();
      if (!reader) throw new Error("No streaming response received from audit server.");
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try { handleEvent(JSON.parse(line.slice(6))); } catch { console.warn("Invalid SSE event:", line); }
        }
      }
    } catch (error: any) {
      if (error?.name === "AbortError") { pushLog("Audit cancelled."); return; }
      console.error("Audit error:", error);
      toast.error(error?.message || "Failed to run audit.");
      pushLog(`Error: ${error?.message || "Unknown error"}`);
    } finally {
      setRunning(false);
      abortControllerRef.current = null;
    }
  };

  const addBudget = async () => {
    setIsAddingBudget(true);
    try { await api.post(`/api/company/add-credits?amount=${budgetAmount}`, {}); toast.success(`Added ${budgetAmount} credits.`); setShowBudgetDialog(false); }
    catch (error) { console.error(error); toast.error("Could not add credits."); }
    finally { setIsAddingBudget(false); }
  };

  const completedCount = agents.filter((a) => a.status === "complete").length;
  const activeSkill = agents.find((a) => a.status === "running");
  const pageProgress = crawlMetrics.pages_crawled > 0 ? Math.min(100, Math.round((crawlMetrics.pages_crawled / Math.max(crawlMetrics.pages_discovered, crawlMetrics.pages_crawled)) * 100)) : 0;

  return (
    <div className="p-8 space-y-6">
      <header>
        <h2 className="font-serif text-3xl font-bold tracking-tight">AI Audit Engine</h2>
        <p className="text-slate-500 dark:text-slate-400 mt-1">Real website crawl first, then evidence-based SEO skills executed one by one.</p>
      </header>

      {!isConfigured ? <Card className="border-amber-200 bg-amber-50 dark:bg-amber-900/10"><CardContent className="p-4 flex gap-3"><AlertCircle className="size-5 text-amber-600" /><p className="text-sm text-amber-700">Claude API Key required. Configure it in Settings.</p></CardContent></Card> : !isReady && <Card className="border-amber-200 bg-amber-50 dark:bg-amber-900/10"><CardContent className="p-4 flex gap-3"><AlertCircle className="size-5 text-amber-600" /><p className="text-sm text-amber-700">{status === "billing_required" ? "Anthropic billing is required." : "Claude AI is currently unavailable."}</p></CardContent></Card>}

      <Card className="shadow-sm">
        <CardHeader><CardTitle className="font-serif">Start New Real Audit</CardTitle><CardDescription>The server will crawl the target website, discover sitemap/robots, measure links and metadata, then run every skill sequentially.</CardDescription></CardHeader>
        <CardContent>
          <div className="flex items-end gap-4"><div className="flex-1 space-y-2"><Label htmlFor="audit-url">Target URL</Label><Input id="audit-url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://your-domain.com" disabled={running} /></div><Button onClick={runAudit} disabled={running} className="bg-emerald-600 hover:bg-emerald-700 text-white">{running ? <Loader2 className="size-4 animate-spin" /> : <Zap className="size-4" fill="white" />}{running ? "Auditing..." : "Run Real Audit"}</Button></div>
          {(running || progress > 0) && <div className="mt-6 space-y-2"><div className="flex justify-between text-sm"><span>{currentStage}</span><span className="font-bold text-emerald-600">{Math.round(progress)}%</span></div><div className="h-3 rounded-full bg-slate-200 dark:bg-slate-800 overflow-hidden"><div className="h-full bg-gradient-to-r from-emerald-500 to-teal-500 transition-all duration-300" style={{ width: `${progress}%` }} /></div></div>}
        </CardContent>
      </Card>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        {[['Pages discovered', crawlMetrics.pages_discovered], ['Pages crawled', crawlMetrics.pages_crawled], ['Internal links', crawlMetrics.internal_links], ['Broken internal', crawlMetrics.broken_internal_links], ['Orphan pages', crawlMetrics.orphan_pages_count]].map(([label, value]) => <Card key={label as string}><CardContent className="p-4"><p className="text-xs text-slate-500">{label}</p><p className="text-2xl font-bold mt-1">{value}</p></CardContent></Card>)}
      </div>

      <Card className={cn("shadow-sm", crawlComplete ? "border-emerald-200 dark:border-emerald-900" : "border-slate-200 dark:border-slate-800")}>
        <CardHeader><CardTitle className="font-serif flex items-center gap-2"><Database className="size-5 text-emerald-600" />Real Crawl Evidence</CardTitle><CardDescription>These values come from the website crawler, not placeholders.</CardDescription></CardHeader>
        <CardContent className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {[['Successful', crawlMetrics.pages_successful], ['External links', crawlMetrics.external_links], ['Sitemap', crawlMetrics.sitemap_found ? 'Found' : 'Not found'], ['Robots.txt', crawlMetrics.robots_found ? 'Found' : 'Not found'], ['Schema', crawlMetrics.schema_found ? 'Detected' : 'Not detected']].map(([label, value]) => <div key={label as string} className="rounded-xl border p-4"><p className="text-xs text-slate-500">{label}</p><p className="font-semibold mt-1">{value}</p></div>)}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-[1.25fr_.75fr] gap-6">
        <Card className="shadow-sm"><CardHeader><CardTitle className="font-serif flex items-center gap-2"><Radar className="size-5 text-emerald-600" />Sequential SEO Skills</CardTitle><CardDescription>{completedCount} / {agents.length} skills complete{activeSkill ? ` · ${activeSkill.name} running` : ""}</CardDescription></CardHeader><CardContent className="space-y-3">{agents.map((agent, index) => <div key={agent.name} className={cn("rounded-xl border p-4 transition-all", agent.status === "running" && "border-emerald-300 bg-emerald-50/60 dark:bg-emerald-500/10", agent.status === "complete" && "border-emerald-200", agent.status === "error" && "border-rose-300 bg-rose-50/50")}><div className="flex gap-3"><div className="pt-0.5">{agent.status === "complete" ? <CheckCircle2 className="size-5 text-emerald-500" /> : agent.status === "running" ? <Loader2 className="size-5 text-emerald-500 animate-spin" /> : agent.status === "error" ? <AlertCircle className="size-5 text-rose-500" /> : <span className="flex size-5 items-center justify-center rounded-full border text-[10px] text-slate-500">{index + 1}</span>}</div><div className="min-w-0 flex-1"><div className="flex items-center justify-between gap-3"><p className="font-medium text-sm">{agent.name}</p>{agent.score !== undefined && <span className="text-xs font-bold">{agent.score}/100</span>}</div><p className="text-xs text-slate-500 mt-1">{agent.description}</p>{agent.status === "running" && <div className="mt-2 h-1.5 rounded-full bg-slate-200 overflow-hidden"><div className="h-full w-2/3 bg-emerald-500 animate-pulse" /></div>}{agent.logs.length > 0 && <p className="text-xs text-slate-600 dark:text-slate-300 mt-2 line-clamp-2">{agent.logs[agent.logs.length - 1]}</p>}</div></div></div>)}</CardContent></Card>

        <Card className="shadow-sm"><CardHeader><CardTitle className="font-serif flex items-center gap-2"><FileSearch className="size-5 text-blue-600" />Crawler health</CardTitle><CardDescription>{pageProgress}% of the currently discovered queue crawled</CardDescription></CardHeader><CardContent className="space-y-4"><div className="h-2 rounded-full bg-slate-200 overflow-hidden"><div className="h-full bg-blue-500 transition-all" style={{ width: `${pageProgress}%` }} /></div><div className="grid grid-cols-2 gap-3 text-sm"><div className="rounded-lg bg-slate-50 dark:bg-slate-900 p-3"><span className="text-slate-500">Duplicate pages</span><strong className="block mt-1">{crawlMetrics.duplicate_pages}</strong></div><div className="rounded-lg bg-slate-50 dark:bg-slate-900 p-3"><span className="text-slate-500">Orphans</span><strong className="block mt-1">{crawlMetrics.orphan_pages_count}</strong></div></div><p className="text-xs text-slate-500">{crawlComplete ? "Crawl evidence is available to every specialist skill." : "Crawler is discovering pages and measuring the live HTML."}</p></CardContent></Card>
      </div>

      <Card className="shadow-sm"><CardHeader><CardTitle className="font-serif flex items-center gap-2"><Terminal className="size-5" />Live Audit Log</CardTitle><CardDescription>Every crawler and specialist event is streamed from the backend.</CardDescription></CardHeader><CardContent><div className="h-[360px] overflow-y-auto rounded-xl bg-slate-950 p-4 font-mono text-xs space-y-1">{globalLogs.length ? globalLogs.map((log, i) => <div key={`${i}-${log}`} className={cn("text-slate-300", log.includes("Skill started") && "text-emerald-400", log.includes("Skill completed") && "text-teal-400", log.includes("Error") && "text-rose-400")}>{log}</div>) : <p className="text-slate-600">Waiting for audit to start...</p>}{running && <div className="text-emerald-400 animate-pulse">▊</div>}</div></CardContent></Card>

      {showBudgetDialog && <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"><Card className="w-full max-w-md"><CardHeader><CardTitle className="flex items-center gap-2"><CreditCard className="size-5 text-amber-600" />Insufficient AI Credits</CardTitle><CardDescription>Add credits to run the real audit.</CardDescription></CardHeader><CardContent><Label htmlFor="budget-amount">Credits to Add</Label><Input id="budget-amount" type="number" min={1} value={budgetAmount} onChange={(e) => setBudgetAmount(parseInt(e.target.value) || 1)} /></CardContent><div className="flex justify-end gap-2 p-6 pt-0"><Button variant="outline" onClick={() => setShowBudgetDialog(false)}>Cancel</Button><Button onClick={addBudget} disabled={isAddingBudget} className="bg-emerald-600 text-white">{isAddingBudget ? <Loader2 className="size-4 animate-spin" /> : "Add Credits"}</Button></div></Card></div>}
    </div>
  );
}