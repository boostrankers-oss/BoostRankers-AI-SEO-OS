import { useMemo, useState, type ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { useClaude } from "@/components/ClaudeProvider";
import { toast } from "sonner";
import {
  AlertCircle, ArrowUpRight, CheckCircle2, ChevronDown, ChevronUp,
  Clock, ExternalLink, Globe2, Loader2, MapPin, Search,
  Sparkles, Star, Target, XCircle, Zap,
} from "lucide-react";

type Profile = {
  name: string; website: string; phone: string; address: string;
  category: string; serviceArea: string; description: string; hours: string;
};
type Priority = "critical" | "high" | "medium" | "low";
type Finding = { title: string; detail: string; priority: Priority; passed: boolean; recommendation?: string };
type AgentResult = { agent?: string; score?: number; findings?: unknown; [key: string]: unknown };
type AuditEvent = { type?: string; score?: number; results?: AgentResult[]; audit_id?: string; message?: string };

const initialProfile: Profile = { name: "", website: "", phone: "", address: "", category: "", serviceArea: "", description: "", hours: "" };
const priorityStyle: Record<Priority, string> = {
  critical: "border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/20 dark:text-rose-300",
  high: "border-orange-200 bg-orange-50 text-orange-700 dark:border-orange-900/50 dark:bg-orange-950/20 dark:text-orange-300",
  medium: "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/50 dark:bg-amber-950/20 dark:text-amber-300",
  low: "border-slate-200 bg-slate-50 text-slate-600 dark:border-slate-800 dark:bg-slate-900/40 dark:text-slate-300",
};

const normalizeUrl = (value: string) => {
  const v = value.trim();
  if (!v) return "";
  return /^https?:\/\//i.test(v) ? v : `https://${v}`;
};
const scoreLabel = (score: number) => score >= 85 ? "Excellent" : score >= 70 ? "Good" : score >= 50 ? "Needs work" : "At risk";
const clamp = (n: number) => Math.max(0, Math.min(100, Math.round(n)));

function parseFindings(value: unknown): Finding[] {
  if (!value) return [];
  let parsed: unknown = value;
  if (typeof value === "string") {
    try { parsed = JSON.parse(value); } catch { return [{ title: "Claude Local SEO finding", detail: value, priority: "medium", passed: false }]; }
  }
  if (!Array.isArray(parsed)) {
    const objectValue = parsed as Record<string, unknown> | null;
    if (objectValue && Array.isArray(objectValue.findings)) return parseFindings(objectValue.findings);
    return [];
  }
  return parsed.map((item, index) => {
    if (typeof item === "string") return { title: `Local SEO finding ${index + 1}`, detail: item, priority: "medium" as Priority, passed: false };
    const f = (item || {}) as Record<string, unknown>;
    const raw = String(f.priority ?? f.severity ?? "medium").toLowerCase();
    const priority: Priority = ["critical", "high", "medium", "low"].includes(raw) ? raw as Priority : "medium";
    const passed = typeof f.passed === "boolean" ? f.passed : String(f.status ?? "").toLowerCase() === "pass";
    return {
      title: String(f.title ?? f.name ?? f.issue ?? `Local SEO finding ${index + 1}`),
      detail: String(f.detail ?? f.description ?? f.message ?? f.finding ?? "No additional detail was returned."),
      priority,
      passed,
      recommendation: typeof f.recommendation === "string" ? f.recommendation : typeof f.action === "string" ? f.action : undefined,
    };
  });
}

function Metric({ icon, title, value, detail, tone }: { icon: ReactNode; title: string; value: string; detail: string; tone: string }) {
  return <Card className="border-slate-200 shadow-sm dark:border-slate-800"><CardHeader className="pb-2"><CardTitle className="flex items-center gap-2 text-sm font-semibold">{icon}{title}</CardTitle></CardHeader><CardContent><p className={`font-serif text-4xl font-bold ${tone}`}>{value}</p><p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{detail}</p></CardContent></Card>;
}

export function LocalSEO() {
  const { isConfigured, isReady, status } = useClaude();
  const [profile, setProfile] = useState<Profile>(initialProfile);
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [overallScore, setOverallScore] = useState<number | null>(null);
  const [localScore, setLocalScore] = useState<number | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [auditId, setAuditId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [section, setSection] = useState<"overview" | "findings" | "ai" | "checklist">("overview");
  const [expanded, setExpanded] = useState<number | null>(null);

  const completeness = useMemo(() => Math.round(Object.values(profile).filter(v => v.trim()).length / Object.values(profile).length * 100), [profile]);
  const setField = (field: keyof Profile, value: string) => setProfile(p => ({ ...p, [field]: value }));
  const critical = findings.filter(f => !f.passed && f.priority === "critical").length;
  const high = findings.filter(f => !f.passed && f.priority === "high").length;

  const clientChecks = useMemo<Finding[]>(() => [
    { title: "Business name supplied", detail: profile.name ? "Business name is available." : "Add the exact public-facing business name.", priority: profile.name ? "low" : "high", passed: !!profile.name, recommendation: "Use the same factual business name used on the website and business profile." },
    { title: "Website supplied", detail: profile.website ? normalizeUrl(profile.website) : "A canonical website URL is required.", priority: profile.website ? "low" : "critical", passed: !!profile.website, recommendation: "Enter the canonical HTTPS URL to audit." },
    { title: "Business category supplied", detail: profile.category ? profile.category : "No primary category supplied.", priority: profile.category ? "low" : "medium", passed: !!profile.category, recommendation: "Use the most specific accurate primary category." },
    { title: "Location signal supplied", detail: profile.address || profile.serviceArea ? "Address/service area supplied." : "No address or service area supplied.", priority: profile.address || profile.serviceArea ? "low" : "high", passed: !!(profile.address || profile.serviceArea), recommendation: "Add the primary location or service area used for local targeting." },
    { title: "Phone supplied", detail: profile.phone ? "Business phone supplied." : "No business phone supplied.", priority: profile.phone ? "low" : "medium", passed: !!profile.phone, recommendation: "Use the main customer-facing number consistently across local listings." },
  ], [profile]);

  const runAudit = async () => {
    setError(null); setSection("overview");
    const website = normalizeUrl(profile.website);
    if (!profile.name || !profile.category || !website) {
      const message = "Business name, category, and website are required."; setError(message); toast.error(message); return;
    }
    if (!isConfigured) { const message = "Claude API key is not configured. Add it in Settings."; setError(message); toast.error(message); return; }
    if (!isReady) {
      const message = status === "billing_required" ? "Anthropic billing is required. Add credits or upgrade your plan." : status === "invalid_api_key" ? "Anthropic API key is invalid. Update it in Settings." : "Claude AI is currently unavailable. Check Settings.";
      setError(message); toast.error(message); return;
    }
    const token = localStorage.getItem("access_token");
    if (!token) { const message = "Please login first."; setError(message); toast.error(message); return; }

    setRunning(true); setProgress(10); setOverallScore(null); setLocalScore(null); setFindings([]); setAuditId(null);
    try {
      const baseUrl = import.meta.env.VITE_API_URL || "http://localhost:8000";
      const response = await fetch(`${baseUrl}/api/audits/run?url=${encodeURIComponent(website)}`, { method: "POST", headers: { Authorization: `Bearer ${token}`, Accept: "text/event-stream" } });
      if (!response.ok) throw new Error(`Server error: ${response.status} - ${await response.text()}`);
      const reader = response.body?.getReader();
      if (!reader) throw new Error("The audit server did not return a stream.");
      const decoder = new TextDecoder(); let buffer = ""; let completed: AuditEvent | null = null; let streamError: string | null = null;
      while (true) {
        const { done, value } = await reader.read(); if (done) break;
        buffer += decoder.decode(value, { stream: true }); const lines = buffer.split("\n"); buffer = lines.pop() || "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(line.slice(6)) as AuditEvent;
            if (data.type === "agent_start") setProgress(p => Math.max(p, 35));
            if (data.type === "log") setProgress(p => Math.min(90, p + 2));
            if (data.type === "error") streamError = String(data.message || "Audit failed.");
            if (data.type === "complete") { completed = data; setProgress(100); }
          } catch { console.warn("Could not parse audit SSE event:", line); }
        }
      }
      if (streamError) throw new Error(streamError);
      if (!completed) throw new Error("The audit stream ended without a completed result. Please try again.");
      setAuditId(completed.audit_id ? String(completed.audit_id) : null);
      setOverallScore(typeof completed.score === "number" ? clamp(completed.score) : null);
      const local = (completed.results || []).find(r => String(r.agent || "").toLowerCase().includes("local seo"));
      if (local) {
        setLocalScore(typeof local.score === "number" ? clamp(local.score) : null);
        setFindings(parseFindings(local.findings));
      }
      toast.success("Local SEO audit completed successfully."); setSection("findings");
    } catch (e) {
      const message = e instanceof Error ? e.message : "Failed to run Local SEO audit.";
      console.error("Local SEO audit error:", e); setError(message); setProgress(0); toast.error(message);
    } finally { setRunning(false); }
  };

  const allChecks = [...clientChecks, ...findings];
  const passedChecks = allChecks.filter(c => c.passed).length;

  return <div className="min-h-full space-y-6 p-6 lg:p-8">
    <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div><div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-emerald-600 dark:text-emerald-400"><MapPin className="size-4" />Local Search Intelligence</div><h2 className="font-serif text-3xl font-bold tracking-tight text-slate-900 dark:text-white">Local SEO</h2><p className="mt-1 max-w-3xl text-sm text-slate-500 dark:text-slate-400">Audit local search visibility, NAP signals, local pages, reviews, schema and targeting using the existing Claude SEO audit engine.</p></div>
      {auditId && <div className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs shadow-sm dark:border-slate-800 dark:bg-slate-950"><span className="text-slate-500">Audit ID:</span> <span className="font-mono text-slate-700 dark:text-slate-300">{auditId}</span></div>}
    </header>

    {(!isConfigured || !isReady) && <Card className="border-amber-200 bg-amber-50 dark:border-amber-900/50 dark:bg-amber-950/20"><CardContent className="flex items-start gap-3 p-4"><AlertCircle className="mt-0.5 size-5 shrink-0 text-amber-600" /><div><p className="font-semibold text-amber-800 dark:text-amber-300">Claude AI is not ready</p><p className="mt-1 text-sm text-amber-700 dark:text-amber-400">{!isConfigured ? "Configure your Anthropic API key in Settings to enable AI-powered Local SEO recommendations." : status === "billing_required" ? "Anthropic billing is required before AI credits can be consumed." : "Claude is currently unavailable. Check Settings."}</p></div></CardContent></Card>}

    <Card className="overflow-hidden border-slate-200 shadow-sm dark:border-slate-800">
      <CardHeader className="border-b border-slate-100 bg-slate-50/70 dark:border-slate-800 dark:bg-slate-950/40"><div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between"><div><CardTitle className="font-serif">Business Profile</CardTitle><CardDescription>Enter real business details. Dashboard metrics stay blank until a real audit returns.</CardDescription></div><span className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-950/20 dark:text-emerald-300">{completeness}% complete</span></div></CardHeader>
      <CardContent className="space-y-5 p-5">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {([ ["name","Business Name *","e.g. Sparkle Cleaning Services Perth"], ["category","Primary Category *","e.g. Commercial Cleaning Service"], ["phone","Phone Number","+61 ..."], ["address","Business Address","Street, suburb, state, postcode"], ["serviceArea","Service Area","e.g. Perth metro, WA"], ["hours","Opening Hours","e.g. Mon–Fri 8:00–17:00"] ] as [keyof Profile,string,string][]).map(([field,label,placeholder]) => <div key={field} className="space-y-2"><Label htmlFor={`local-${field}`}>{label}</Label><Input id={`local-${field}`} value={profile[field]} onChange={e => setField(field,e.target.value)} placeholder={placeholder} disabled={running} /></div>)}
          <div className="space-y-2 md:col-span-2"><Label htmlFor="local-website">Website URL *</Label><div className="flex gap-2"><div className="relative flex-1"><Globe2 className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" /><Input id="local-website" className="pl-9" value={profile.website} onChange={e => setField("website",e.target.value)} placeholder="https://yourbusiness.com.au" disabled={running} /></div>{profile.website && <Button type="button" variant="outline" onClick={() => window.open(normalizeUrl(profile.website),"_blank","noopener,noreferrer")} disabled={running}><ExternalLink className="size-4" /></Button>}</div></div>
          <div className="space-y-2 md:col-span-2"><Label htmlFor="local-description">Business Description</Label><textarea id="local-description" value={profile.description} onChange={e => setField("description",e.target.value)} placeholder="Short, factual description of the business and services." disabled={running} className="min-h-24 w-full rounded-md border border-slate-200 bg-transparent px-3 py-2 text-sm outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-500/20 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-800" /></div>
        </div>
        <div><div className="mb-1 flex justify-between text-xs"><span className="text-slate-500">Profile completeness</span><span className="font-semibold text-emerald-600">{completeness}%</span></div><div className="h-2 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800"><div className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-500 transition-all" style={{width:`${completeness}%`}} /></div></div>
        {error && <div className="flex items-start gap-3 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/20 dark:text-rose-300"><AlertCircle className="mt-0.5 size-4 shrink-0" />{error}</div>}
        <Button onClick={runAudit} disabled={running} className="h-11 w-full bg-emerald-600 text-white shadow-md shadow-emerald-600/20 hover:bg-emerald-700">{running ? <Loader2 className="size-4 animate-spin" /> : <Zap className="size-4" />}{running ? "Running Local SEO Audit..." : "Run Local SEO Audit"}</Button>
        {running && <div className="space-y-2"><div className="flex justify-between text-xs"><span className="text-slate-500">Claude audit engine is processing the website</span><span className="font-semibold text-emerald-600">{progress}%</span></div><div className="h-2 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800"><div className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-teal-500 transition-all" style={{width:`${progress}%`}} /></div></div>}
      </CardContent>
    </Card>

    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Card className="border-slate-200 shadow-sm dark:border-slate-800"><CardContent className="flex items-center justify-between p-5"><div><p className="text-xs font-medium uppercase tracking-wider text-slate-500">Local SEO Score</p><p className="mt-1 font-serif text-4xl font-bold text-emerald-600">{localScore === null ? "—" : localScore}</p><p className="mt-1 text-xs text-slate-500">{localScore === null ? "Run an audit to measure" : scoreLabel(localScore)}</p></div><Target className="size-7 text-emerald-500" /></CardContent></Card>
      <Card className="border-slate-200 shadow-sm dark:border-slate-800"><CardContent className="flex items-center justify-between p-5"><div><p className="text-xs font-medium uppercase tracking-wider text-slate-500">Overall SEO Score</p><p className="mt-1 font-serif text-4xl font-bold text-indigo-600">{overallScore === null ? "—" : overallScore}</p><p className="mt-1 text-xs text-slate-500">From completed audit</p></div><Search className="size-7 text-indigo-500" /></CardContent></Card>
      <Metric icon={<AlertCircle className="size-4 text-rose-500" />} title="Critical Issues" value={String(critical)} detail={`${high} high-priority issue${high === 1 ? "" : "s"}`} tone="text-rose-500" />
      <Metric icon={<CheckCircle2 className="size-4 text-emerald-500" />} title="Checks Completed" value={allChecks.length ? `${passedChecks}/${allChecks.length}` : "—"} detail="Profile checks + audit findings" tone="text-emerald-600" />
    </div>

    <div className="flex flex-wrap gap-2 rounded-xl border border-slate-200 bg-white p-2 shadow-sm dark:border-slate-800 dark:bg-slate-950">{([["overview","Overview"],["findings","Findings"],["ai","Claude Recommendations"],["checklist","Checklist"]] as const).map(([key,label]) => <button key={key} type="button" onClick={() => setSection(key)} className={`rounded-lg px-4 py-2 text-sm font-medium transition ${section === key ? "bg-emerald-600 text-white shadow-sm" : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-900"}`}>{label}</button>)}</div>

    {section === "overview" && <div className="grid grid-cols-1 gap-6 xl:grid-cols-3"><Card className="xl:col-span-2 border-slate-200 shadow-sm dark:border-slate-800"><CardHeader><CardTitle className="font-serif">Local SEO Health</CardTitle><CardDescription>Evidence from the latest completed audit.</CardDescription></CardHeader><CardContent>{localScore === null ? <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center dark:border-slate-700"><MapPin className="mx-auto size-9 text-slate-400" /><p className="mt-3 font-medium">No Local SEO audit has been completed yet.</p><p className="mx-auto mt-1 max-w-md text-sm text-slate-500">Add your real business details above and run the audit to populate this dashboard.</p></div> : <div className="space-y-5"><div className="flex flex-col gap-4 rounded-xl border border-slate-200 p-5 sm:flex-row sm:items-center dark:border-slate-800"><div className="flex size-28 shrink-0 items-center justify-center rounded-full border-8 border-emerald-100 bg-white text-center dark:border-emerald-950 dark:bg-slate-950"><div><div className="font-serif text-3xl font-bold text-emerald-600">{localScore}</div><div className="text-[10px] uppercase text-slate-500">/ 100</div></div></div><div><p className="text-lg font-semibold">{scoreLabel(localScore)}</p><p className="mt-1 text-sm text-slate-500">Claude's Local SEO Agent evaluated the website and returned a local score.</p></div></div><div className="grid gap-3 sm:grid-cols-2"><div className="rounded-lg border border-slate-200 p-4 dark:border-slate-800"><p className="text-xs uppercase tracking-wider text-slate-500">Business</p><p className="mt-1 font-medium">{profile.name}</p></div><div className="rounded-lg border border-slate-200 p-4 dark:border-slate-800"><p className="text-xs uppercase tracking-wider text-slate-500">Location</p><p className="mt-1 font-medium">{profile.address || profile.serviceArea || "Not supplied"}</p></div></div></div>}</CardContent></Card><Card className="border-slate-200 shadow-sm dark:border-slate-800"><CardHeader><CardTitle className="font-serif">Quick Signals</CardTitle><CardDescription>Input completeness, not invented third-party metrics.</CardDescription></CardHeader><CardContent className="space-y-3">{[["Business identity",!!profile.name],["Location signal",!!(profile.address||profile.serviceArea)],["Primary category",!!profile.category],["Phone",!!profile.phone],["Website",!!profile.website]].map(([label,passed]) => <div key={String(label)} className="flex items-center justify-between rounded-lg border border-slate-200 p-3 dark:border-slate-800"><p className="text-sm font-medium">{label}</p>{passed ? <CheckCircle2 className="size-5 text-emerald-500" /> : <XCircle className="size-5 text-slate-300" />}</div>)}</CardContent></Card></div>}

    {section === "findings" && <Card className="border-slate-200 shadow-sm dark:border-slate-800"><CardHeader><CardTitle className="font-serif">Local SEO Findings</CardTitle><CardDescription>Findings returned by the existing Claude Local SEO Agent.</CardDescription></CardHeader><CardContent className="space-y-3">{findings.length === 0 ? <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center dark:border-slate-700"><Search className="mx-auto size-8 text-slate-400" /><p className="mt-3 font-medium">No Local SEO findings available.</p><p className="mt-1 text-sm text-slate-500">Run the audit to load real findings.</p></div> : findings.map((f,i) => { const open=expanded===i; return <div key={`${f.title}-${i}`} className="rounded-xl border border-slate-200 dark:border-slate-800"><button type="button" className="flex w-full items-center gap-3 p-4 text-left" onClick={() => setExpanded(open ? null : i)}>{f.passed ? <CheckCircle2 className="size-5 shrink-0 text-emerald-500" /> : <AlertCircle className="size-5 shrink-0 text-orange-500" />}<div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><p className="font-medium">{f.title}</p><span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase ${priorityStyle[f.priority]}`}>{f.priority}</span></div><p className="mt-1 line-clamp-2 text-sm text-slate-500">{f.detail}</p></div>{open ? <ChevronUp className="size-4 text-slate-400" /> : <ChevronDown className="size-4 text-slate-400" />}</button>{open && <div className="border-t border-slate-200 px-4 pb-4 pt-4 dark:border-slate-800"><div className="rounded-lg bg-slate-50 p-4 dark:bg-slate-900/50"><p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Finding</p><p className="mt-2 text-sm leading-6 text-slate-700 dark:text-slate-300">{f.detail}</p></div>{f.recommendation && <div className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 p-4 dark:border-emerald-900/50 dark:bg-emerald-950/20"><p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-emerald-700 dark:text-emerald-300"><Sparkles className="size-4" />Recommended action</p><p className="mt-2 text-sm leading-6 text-emerald-800 dark:text-emerald-200">{f.recommendation}</p></div>}</div>}</div>})}</CardContent></Card>}

    {section === "ai" && <Card className="overflow-hidden border-emerald-200 shadow-sm dark:border-emerald-900/50"><CardHeader className="bg-gradient-to-r from-emerald-50 to-teal-50 dark:from-emerald-950/30 dark:to-teal-950/20"><div className="flex items-center gap-3"><div className="flex size-10 items-center justify-center rounded-xl bg-emerald-600 text-white"><Sparkles className="size-5" /></div><div><CardTitle className="font-serif">Claude Recommendations</CardTitle><CardDescription>Actionable recommendations from the Local SEO Agent.</CardDescription></div></div></CardHeader><CardContent className="space-y-4 p-5">{findings.filter(f=>f.recommendation).length === 0 ? <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center dark:border-slate-700"><Sparkles className="mx-auto size-8 text-slate-400" /><p className="mt-3 font-medium">Claude recommendations will appear here.</p><p className="mt-1 text-sm text-slate-500">Run a Local SEO audit first.</p></div> : findings.filter(f=>f.recommendation).map((f,i) => <div key={`${f.title}-ai-${i}`} className="rounded-xl border border-slate-200 p-4 dark:border-slate-800"><div className="flex items-start gap-3"><div className="mt-0.5 rounded-lg bg-emerald-100 p-2 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300"><ArrowUpRight className="size-4" /></div><div className="flex-1"><div className="flex flex-wrap items-center gap-2"><h3 className="font-semibold">{f.title}</h3><span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase ${priorityStyle[f.priority]}`}>{f.priority}</span></div><p className="mt-2 text-sm leading-6 text-slate-600 dark:text-slate-300">{f.recommendation}</p></div></div></div>)}</CardContent></Card>}

    {section === "checklist" && <Card className="border-slate-200 shadow-sm dark:border-slate-800"><CardHeader><CardTitle className="font-serif">Local SEO Checklist</CardTitle><CardDescription>Input validation plus real findings from the audit.</CardDescription></CardHeader><CardContent className="space-y-3">{allChecks.map((f,i) => <div key={`${f.title}-${i}`} className="flex items-start gap-3 rounded-lg border border-slate-200 p-4 dark:border-slate-800">{f.passed ? <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-emerald-500" /> : <AlertCircle className="mt-0.5 size-5 shrink-0 text-orange-500" />}<div className="flex-1"><div className="flex flex-wrap items-center gap-2"><p className="text-sm font-semibold">{f.title}</p><span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase ${priorityStyle[f.priority]}`}>{f.priority}</span></div><p className="mt-1 text-sm text-slate-500">{f.detail}</p>{f.recommendation && !f.passed && <p className="mt-2 text-xs font-medium text-emerald-700 dark:text-emerald-300">Action: {f.recommendation}</p>}</div></div>)}</CardContent></Card>}

    <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
      <Metric icon={<Star className="size-5 text-amber-500" />} title="Reviews" value="—" detail="Connect real review data to measure rating and velocity." tone="text-amber-500" />
      <Metric icon={<MapPin className="size-5 text-emerald-500" />} title="Citations" value="—" detail="Connect a citation source before showing directory counts." tone="text-emerald-600" />
      <Metric icon={<Clock className="size-5 text-indigo-500" />} title="Review Response" value="—" detail="Response rate requires real review/reply data." tone="text-indigo-600" />
    </div>
  </div>;
}
