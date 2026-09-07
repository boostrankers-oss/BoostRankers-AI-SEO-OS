import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  FileSearch,
  Loader2,
  RefreshCw,
  Search,
  ShieldAlert,
  Sparkles,
  Target,
} from "lucide-react";
import { api } from "@/lib/api";

type Risk = "high" | "medium" | "low";
type ConflictStatus = "open" | "reviewed" | "resolved" | "ignored";

type Client = { id: string; business_name?: string; website?: string };

type Scan = {
  id: string;
  client_id: string;
  status: string;
  pages_scanned: number;
  focus_keywords_found: number;
  conflicts_found: number;
  repeated_focus_keywords: number;
  stuffing_warnings: number;
  gsc_connected: boolean;
  measurement_property?: string | null;
  date_start?: string | null;
  date_end?: string | null;
  error_message?: string | null;
  progress_message?: string | null;
  pages_discovered?: number;
  last_activity_at?: string | null;
  gsc_status_message?: string | null;
  focus_status_message?: string | null;
  gsc_rows_measured?: number;
  gsc_shared_queries?: number;
  gsc_candidate_pairs?: number;
  wordpress_posts_found?: number;
  wordpress_pages_found?: number;
  wordpress_content_scanned?: number;
  wordpress_status_message?: string | null;
};

type Conflict = {
  id: string;
  scan_id: string;
  keyword: string;
  primary_url: string;
  competing_url: string;
  conflict_score: number;
  risk_level: Risk;
  intent_similarity: number;
  content_similarity: number;
  gsc_overlap: number;
  ranking_displacement: number;
  status: ConflictStatus;
  recommendation: string;
  evidence: {
    evidence_class?: string;
    exact_focus_keyword?: boolean;
    focus_keyword_primary?: string | null;
    focus_keyword_competing?: string | null;
    title_similarity?: number;
    keyword_similarity?: number;
    canonical_conflict?: boolean;
    url_switch_signal?: boolean;
    shared_queries?: Array<{
      query: string;
      primary: { clicks?: number; impressions?: number; position?: number | null };
      competing: { clicks?: number; impressions?: number; position?: number | null };
    }>;
    ai_analysis?: string;
    interpretation?: string;
    primary_content_type?: string;
    competing_content_type?: string;
    primary_wordpress_id?: number | null;
    competing_wordpress_id?: number | null;
    primary_wordpress_source?: boolean;
    competing_wordpress_source?: boolean;
    website_resolution?: {
      status?: string;
      action?: string;
      target_url?: string;
      new_title?: string;
      replacements_applied?: number;
      reason?: string;
      applied_at?: string;
    };
  };
};

type Page = {
  id: string;
  url: string;
  title?: string;
  h1?: string;
  canonical?: string;
  word_count: number;
  focus_keyword?: string | null;
  keyword_frequency: number;
  stuffing_risk: number;
  gsc_primary_query?: string | null;
  gsc_query_impressions?: number;
  gsc_query_clicks?: number;
  gsc_query_position?: number | null;
  page_type: string;
};

const riskClass: Record<Risk, string> = {
  high: "bg-red-50 text-red-700 dark:bg-red-500/10 dark:text-red-300",
  medium: "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300",
  low: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
};

function pct(value: number | undefined) {
  return `${Math.round((value || 0) * 100)}%`;
}

function number(value: number | undefined) {
  return new Intl.NumberFormat().format(Math.round(value || 0));
}

function contentTypeLabel(value?: string, wordpress = false) {
  if (value === "post") return wordpress ? "WordPress Post" : "Post-like URL";
  if (value === "page") return wordpress ? "WordPress Page" : "Page-like URL";
  return "URL";
}

export function KeywordConflicts() {
  const [clients, setClients] = useState<Client[]>([]);
  const [clientId, setClientId] = useState("");
  const [scan, setScan] = useState<Scan | null>(null);
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [pages, setPages] = useState<Page[]>([]);
  const [selected, setSelected] = useState<Conflict | null>(null);
  const [tab, setTab] = useState<"conflicts" | "focus" | "stuffing">("conflicts");
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState("");
  const [risk, setRisk] = useState<"all" | Risk>("all");
  const [search, setSearch] = useState("");
  const [includeGsc, setIncludeGsc] = useState(true);
  const [maxPages, setMaxPages] = useState(150);
  const [wpSite, setWpSite] = useState("");
  const [wpUsername, setWpUsername] = useState("");
  const [wpPassword, setWpPassword] = useState("");
  const [aiLoading, setAiLoading] = useState(false);

  const loadClients = useCallback(async () => {
    const data = await api.get<Client[]>('/api/clients/');
    setClients(data || []);
    if (!clientId && data?.length) setClientId(data[0].id);
  }, [clientId]);

  const loadData = useCallback(async () => {
    if (!clientId) return;
    setLoading(true);
    setError("");
    try {
      const [overview, conflictData, pageData] = await Promise.all([
        api.get<{ scan?: Scan; metrics?: Record<string, number> }>(`/api/keyword-conflicts/overview?client_id=${encodeURIComponent(clientId)}`),
        api.get<{ conflicts: Conflict[] }>(`/api/keyword-conflicts?client_id=${encodeURIComponent(clientId)}`),
        api.get<{ pages: Page[] }>(`/api/keyword-conflicts/pages?client_id=${encodeURIComponent(clientId)}`),
      ]);
      setScan(overview?.scan || null);
      setConflicts(conflictData?.conflicts || []);
      setPages(pageData?.pages || []);
    } catch (err: any) {
      setError(err?.data?.detail || err?.message || "Unable to load Keyword Conflicts.");
    } finally {
      setLoading(false);
    }
  }, [clientId]);

  useEffect(() => {
    void loadClients().catch((err: any) => setError(err?.data?.detail || "Unable to load clients."));
  }, [loadClients]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  useEffect(() => {
    if (!scanning || !scan?.id) return;
    if (scan.status === "completed" || scan.status === "failed") {
      setScanning(false);
      void loadData();
      return;
    }
    const timer = window.setInterval(async () => {
      try {
        const data = await api.get<{ scans: Scan[] }>(`/api/keyword-conflicts/scans?client_id=${encodeURIComponent(clientId)}`);
        const current = data.scans?.find((x) => x.id === scan.id);
        if (current) setScan(current);
      } catch {
        // Keep the scan running; the next poll can recover from a transient error.
      }
    }, 2000);
    return () => window.clearInterval(timer);
  }, [scanning, scan?.id, scan?.status, clientId, loadData]);

  const filteredConflicts = useMemo(() => {
    const q = search.trim().toLowerCase();
    return conflicts.filter((item) => {
      const matchesRisk = risk === "all" || item.risk_level === risk;
      const matchesSearch = !q || `${item.keyword} ${item.primary_url} ${item.competing_url} ${item.evidence.primary_content_type || ""} ${item.evidence.competing_content_type || ""}`.toLowerCase().includes(q);
      return matchesRisk && matchesSearch;
    });
  }, [conflicts, risk, search]);

  const repeatedFocus = useMemo(() => {
    const groups = new Map<string, Page[]>();
    for (const page of pages) {
      const key = page.focus_keyword?.trim().toLowerCase();
      if (!key) continue;
      const group = groups.get(key) || [];
      group.push(page);
      groups.set(key, group);
    }
    return [...groups.entries()].filter(([, group]) => group.length > 1).sort((a, b) => b[1].length - a[1].length);
  }, [pages]);

  const stuffingPages = useMemo(() => pages.filter((page) => page.stuffing_risk >= 55), [pages]);

  const highRisk = conflicts.filter((x) => x.risk_level === "high").length;

  const startScan = async () => {
    if (!clientId) {
      setError("Select a client first.");
      return;
    }
    // Do not let the polling effect attach to an older scan while the new
    // scan request is being created/recovered by the backend.
    setScanning(true);
    setError("");
    setScan(null);
    try {
      const response = await api.post<{ scan: Scan }>("/api/keyword-conflicts/scan", {
        client_id: clientId,
        days: 90,
        max_pages: maxPages,
        include_gsc: includeGsc,
        wordpress_site: wpSite.trim() || null,
        wordpress_username: wpUsername.trim() || null,
        wordpress_application_password: wpPassword || null,
      });
      setScan(response.scan);
    } catch (err: any) {
      setScanning(false);
      setError(err?.data?.detail || err?.message || "Unable to start the scan.");
    }
  };

  const updateStatus = async (id: string, next: ConflictStatus) => {
    try {
      const response = await api.patch<{ conflict: Conflict }>(`/api/keyword-conflicts/${id}/status`, { status: next });
      setConflicts((items) => items.map((item) => item.id === id ? response.conflict : item));
      if (selected?.id === id) setSelected(response.conflict);
    } catch (err: any) {
      setError(err?.data?.detail || err?.message || "Unable to update status.");
    }
  };

  const resolveWithClaude = async () => {
    if (!selected) return;
    const site = wpSite.trim() || clients.find((client) => client.id === clientId)?.website || "";
    if (!site || !wpUsername.trim() || !wpPassword) {
      setError("To resolve this conflict directly on WordPress, enter the WordPress site, username, and Application Password in Scan configuration. Credentials are sent only for this request.");
      return;
    }
    setAiLoading(true);
    setError("");
    try {
      const response = await api.post<{ success: boolean; applied: boolean; message: string; conflict: Conflict }>(
        `/api/keyword-conflicts/${selected.id}/resolve`,
        {
          wordpress_site: site,
          wordpress_username: wpUsername.trim(),
          wordpress_application_password: wpPassword,
        },
      );
      setSelected(response.conflict);
      setConflicts((items) => items.map((item) => item.id === selected.id ? response.conflict : item));
      if (!response.applied) {
        setError(response.message || "Claude determined that this conflict requires manual review.");
      }
    } catch (err: any) {
      setError(err?.data?.detail || err?.message || "Claude could not resolve this conflict on WordPress.");
    } finally {
      setAiLoading(false);
    }
  };

  const analyzeWithClaude = async () => {
    if (!selected) return;
    setAiLoading(true);
    try {
      const response = await api.post<{ analysis: string; conflict: Conflict }>(`/api/keyword-conflicts/${selected.id}/analyze`, {});
      setSelected(response.conflict);
      setConflicts((items) => items.map((item) => item.id === selected.id ? response.conflict : item));
    } catch (err: any) {
      setError(err?.data?.detail || err?.message || "Claude analysis is unavailable.");
    } finally {
      setAiLoading(false);
    }
  };

  if (loading && !clients.length) {
    return <div className="min-h-full p-8 flex items-center justify-center"><Loader2 className="size-6 animate-spin" /></div>;
  }

  return (
    <div className="min-h-full bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100">
      <div className="max-w-[1500px] mx-auto p-6 md:p-8 space-y-6">
        <div className="flex flex-col xl:flex-row xl:items-center xl:justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400 text-sm font-semibold"><ShieldAlert className="size-4" /> Content Risk Intelligence</div>
            <h1 className="text-3xl font-bold tracking-tight mt-1">Keyword Conflicts &amp; Cannibalization</h1>
            <p className="text-slate-500 dark:text-slate-400 mt-2 max-w-3xl">Find repeated focus keywords, possible search-intent conflicts, GSC query-to-URL overlap and page-level keyword over-optimization using measured evidence.</p>
          </div>
          <div className="flex flex-wrap gap-2 items-center">
            <select value={clientId} onChange={(e) => setClientId(e.target.value)} className="h-10 rounded-lg border bg-white dark:bg-slate-900 px-3 text-sm min-w-[220px]">
              <option value="">Select client</option>
              {clients.map((client) => <option key={client.id} value={client.id}>{client.business_name || client.website || client.id}</option>)}
            </select>
            <button onClick={() => void loadData()} className="h-10 px-3 rounded-lg border bg-white dark:bg-slate-900 hover:bg-slate-100 dark:hover:bg-slate-800" title="Refresh">
              <RefreshCw className="size-4" />
            </button>
            <button onClick={startScan} disabled={scanning || !clientId} className="h-10 px-4 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-semibold inline-flex items-center gap-2 disabled:opacity-50">
              {scanning ? <Loader2 className="size-4 animate-spin" /> : <FileSearch className="size-4" />}
              {scanning ? "Scanning…" : "Run Conflict Scan"}
            </button>
          </div>
        </div>

        {error && <div className="rounded-xl border border-red-200 bg-red-50 dark:bg-red-500/10 dark:border-red-900 p-4 text-sm text-red-700 dark:text-red-300">{error}</div>}

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <Kpi title="Potential Conflicts" value={conflicts.length} icon={<AlertTriangle className="size-5" />} />
          <Kpi title="High Risk" value={highRisk} icon={<ShieldAlert className="size-5" />} />
          <Kpi title="Repeated Focus Keywords" value={repeatedFocus.length} icon={<Target className="size-5" />} />
          <Kpi title="Stuffing Warnings" value={stuffingPages.length} icon={<Search className="size-5" />} />
        </div>

        <div className="rounded-2xl border bg-white dark:bg-slate-900 dark:border-slate-800 p-4">
          <div className="flex flex-col lg:flex-row gap-3 lg:items-center lg:justify-between">
            <div className="flex flex-wrap gap-2">
              {(["conflicts", "focus", "stuffing"] as const).map((value) => (
                <button key={value} onClick={() => setTab(value)} className={`px-4 py-2 rounded-lg text-sm font-semibold ${tab === value ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900" : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300"}`}>
                  {value === "conflicts" ? "Potential Ranking Conflicts" : value === "focus" ? "Repeated Focus Keywords" : "Keyword Over-Optimization"}
                </button>
              ))}
            </div>
            {tab === "conflicts" && <div className="flex flex-wrap gap-2">
              <div className="relative"><Search className="absolute left-3 top-2.5 size-4 text-slate-400" /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search URL or keyword" className="h-9 pl-9 pr-3 rounded-lg border bg-white dark:bg-slate-950 text-sm" /></div>
              <select value={risk} onChange={(e) => setRisk(e.target.value as any)} className="h-9 rounded-lg border bg-white dark:bg-slate-950 px-3 text-sm"><option value="all">All risk</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select>
            </div>}
          </div>
        </div>

        {tab === "conflicts" && <div className="grid xl:grid-cols-[1fr_390px] gap-5">
          <div className="rounded-2xl border bg-white dark:bg-slate-900 dark:border-slate-800 overflow-hidden">
            {filteredConflicts.length === 0 ? <Empty text="No measured keyword conflicts were found in the latest scan." /> : <div className="divide-y dark:divide-slate-800">
              {filteredConflicts.map((item) => <button key={item.id} onClick={() => setSelected(item)} className="w-full text-left p-5 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><span className={`px-2 py-1 rounded-md text-xs font-bold uppercase ${riskClass[item.risk_level]}`}>{item.risk_level}</span><span className="text-xs text-slate-400">Score {Math.round(item.conflict_score)}/100</span><span className="text-xs text-slate-400">{item.status}</span></div><h3 className="font-semibold mt-2 truncate">{item.keyword || "Query overlap"}</h3><div className="flex flex-wrap gap-1.5 mt-2"><span className="px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 text-[11px] font-semibold">{contentTypeLabel(item.evidence.primary_content_type, item.evidence.primary_wordpress_source)}</span><span className="text-[11px] text-slate-400">↔</span><span className="px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 text-[11px] font-semibold">{contentTypeLabel(item.evidence.competing_content_type, item.evidence.competing_wordpress_source)}</span></div><p className="text-xs text-slate-500 mt-1 truncate">Primary: {item.primary_url}</p><p className="text-xs text-slate-500 truncate">Competing: {item.competing_url}</p></div>
                  <ChevronRight className="size-5 text-slate-400 shrink-0 mt-5" />
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4 text-xs"><Metric label="GSC overlap" value={pct(item.gsc_overlap)} /><Metric label="Content similarity" value={pct(item.content_similarity)} /><Metric label="Intent/title" value={pct(item.intent_similarity)} /><Metric label="Displacement signal" value={pct(item.ranking_displacement)} /></div>
              </button>)}
            </div>}
          </div>

          {selected ? <ConflictDrawer conflict={selected} onClose={() => setSelected(null)} onStatus={updateStatus} onResolve={resolveWithClaude} onAnalyze={analyzeWithClaude} aiLoading={aiLoading} /> : <div className="rounded-2xl border border-dashed bg-white dark:bg-slate-900 dark:border-slate-700 p-6 text-sm text-slate-500 flex items-center justify-center min-h-[320px]">Select a conflict to view the evidence drawer.</div>}
        </div>}

        {tab === "focus" && <div className="rounded-2xl border bg-white dark:bg-slate-900 dark:border-slate-800 overflow-hidden">
          {repeatedFocus.length === 0 ? <Empty text="No repeated WordPress/Yoast focus keywords were measured." /> : <div className="divide-y dark:divide-slate-800">{repeatedFocus.map(([keyword, group]) => <div key={keyword} className="p-5"><div className="flex items-center justify-between gap-3"><div><h3 className="font-semibold">{group[0].focus_keyword}</h3><p className="text-xs text-slate-500 mt-1">Used as a focus keyword on {group.length} WordPress URLs.</p></div><span className="rounded-full bg-amber-50 text-amber-700 px-3 py-1 text-xs font-bold">{group.length} URLs</span></div><div className="mt-3 space-y-2">{group.map((page) => <div key={page.id} className="rounded-lg bg-slate-50 dark:bg-slate-800/70 p-3 text-xs"><div className="font-medium break-all">{page.url}</div><div className="text-slate-500 mt-1">{page.title || page.h1 || "Untitled"}</div></div>)}</div></div>)}</div>}
        </div>}

        {tab === "stuffing" && <div className="rounded-2xl border bg-white dark:bg-slate-900 dark:border-slate-800 overflow-hidden">
          <div className="p-5 border-b dark:border-slate-800"><h2 className="font-semibold">Keyword over-optimization signals</h2><p className="text-sm text-slate-500 mt-1">Heuristic page-level signals. These do not mean Google has penalized the page.</p></div>
          {stuffingPages.length === 0 ? <Empty text="No pages crossed the current heuristic warning threshold." /> : <div className="divide-y dark:divide-slate-800">{stuffingPages.map((page) => <div key={page.id} className="p-5 flex flex-col md:flex-row md:items-center md:justify-between gap-3"><div className="min-w-0"><div className="font-medium break-all">{page.url}</div><div className="text-xs text-slate-500 mt-1">{page.focus_keyword ? `Focus: ${page.focus_keyword}` : page.gsc_primary_query ? `GSC query: ${page.gsc_primary_query}` : "No measured target query"} · {page.word_count} words · {page.keyword_frequency.toFixed(2)}% exact-phrase frequency</div></div><span className={`px-3 py-1 rounded-full text-xs font-bold ${page.stuffing_risk >= 80 ? riskClass.high : riskClass.medium}`}>Risk {Math.round(page.stuffing_risk)}/100</span></div>)}</div>}
        </div>}

        <div className="rounded-2xl border bg-white dark:bg-slate-900 dark:border-slate-800 p-5">
          <div className="flex items-center gap-2 font-semibold"><FileSearch className="size-5 text-emerald-600" /> Scan configuration</div>
          <div className="grid md:grid-cols-3 gap-4 mt-4">
            <label className="text-sm">Pages to inspect<input type="number" min={10} max={300} value={maxPages} onChange={(e) => setMaxPages(Math.max(10, Math.min(300, Number(e.target.value) || 150)))} className="mt-1 w-full h-10 rounded-lg border px-3 bg-white dark:bg-slate-950" /></label>
            <label className="flex items-center gap-3 text-sm md:pt-7"><input type="checkbox" checked={includeGsc} onChange={(e) => setIncludeGsc(e.target.checked)} /> Include Google Search Console query/page evidence</label>
            <div className="text-sm md:pt-7">{scan?.gsc_connected ? <span className="inline-flex items-center gap-2 text-emerald-600"><CheckCircle2 className="size-4" /> GSC connected{scan.measurement_property ? ` · ${scan.measurement_property}` : ""}</span> : <span className="text-slate-500">GSC evidence unavailable for this scan</span>}</div>
          </div>
          <details className="mt-5"><summary className="cursor-pointer text-sm font-medium">WordPress / Yoast focus-keyword access</summary><p className="text-xs text-slate-500 mt-2">The scanner separately inventories published WordPress Posts and Pages, independent of the sitemap crawl limit, and uses the Boost Rankers SEO Bridge for verified focus-keyword metadata. Credentials are sent only with this scan request and are never stored by this feature. If you provide credentials, the scan first verifies the account with WordPress and then uses the same authenticated connection for WordPress/Yoast requests.</p><div className="grid md:grid-cols-3 gap-3 mt-3"><input value={wpSite} onChange={(e) => setWpSite(e.target.value)} placeholder="https://your-wordpress-site.com" autoComplete="url" className="h-10 rounded-lg border px-3 bg-white dark:bg-slate-950 text-sm" /><input value={wpUsername} onChange={(e) => setWpUsername(e.target.value)} placeholder="WordPress username" autoComplete="username" className="h-10 rounded-lg border px-3 bg-white dark:bg-slate-950 text-sm" /><input value={wpPassword} onChange={(e) => setWpPassword(e.target.value)} type="password" placeholder="Application Password" autoComplete="current-password" className="h-10 rounded-lg border px-3 bg-white dark:bg-slate-950 text-sm" /></div><p className="text-[11px] text-slate-500 mt-2">For authenticated WordPress access, provide all three fields. The Application Password is used for this scan only.</p></details>
          {scan && <div className="mt-5 rounded-xl bg-slate-50 dark:bg-slate-800/70 p-4 space-y-4"><div className="grid grid-cols-2 md:grid-cols-6 gap-3"><Metric label="Scan status" value={scan.status} /><Metric label="URLs scanned" value={`${number(scan.pages_scanned)} / ${number(scan.pages_discovered || maxPages)}`} /><Metric label="WP Posts" value={number(scan.wordpress_posts_found)} /><Metric label="WP Pages" value={number(scan.wordpress_pages_found)} /><Metric label="Focus keywords" value={number(scan.focus_keywords_found)} /><Metric label="Conflicts" value={number(scan.conflicts_found)} /></div>{scan.gsc_connected && <div className="grid grid-cols-2 md:grid-cols-3 gap-3"><Metric label="GSC query/page rows" value={number(scan.gsc_rows_measured)} /><Metric label="Shared GSC queries" value={number(scan.gsc_shared_queries)} /><Metric label="GSC candidate groups" value={number(scan.gsc_candidate_pairs)} /></div>}{scan.progress_message && <div className="text-xs text-slate-500 dark:text-slate-400">{scan.progress_message}</div>}{scan.wordpress_status_message && <div className="text-xs text-slate-600 dark:text-slate-300"><strong>WordPress:</strong> {scan.wordpress_status_message}</div>}{scan.gsc_status_message && <div className={`text-xs ${scan.gsc_connected ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400"}`}><strong>GSC:</strong> {scan.gsc_status_message}</div>}{scan.focus_status_message && <div className="text-xs text-slate-500 dark:text-slate-400"><strong>Focus keywords:</strong> {scan.focus_status_message}</div>}{scan.error_message && <div className="text-xs text-red-600 dark:text-red-400"><strong>Error:</strong> {scan.error_message}</div>}</div>}
        </div>
      </div>
    </div>
  );
}

function ConflictDrawer({ conflict, onClose, onStatus, onResolve, onAnalyze, aiLoading }: { conflict: Conflict; onClose: () => void; onStatus: (id: string, status: ConflictStatus) => void; onResolve: () => void; onAnalyze: () => void; aiLoading: boolean }) {
  const queries = conflict.evidence.shared_queries || [];
  return <aside className="rounded-2xl border bg-white dark:bg-slate-900 dark:border-slate-800 p-5 xl:sticky xl:top-5 h-fit max-h-[calc(100vh-40px)] overflow-y-auto">
    <div className="flex items-start justify-between gap-3"><div><span className={`px-2 py-1 rounded-md text-xs font-bold uppercase ${riskClass[conflict.risk_level]}`}>{conflict.risk_level} risk</span><h2 className="text-xl font-bold mt-2">{conflict.keyword || "Query conflict"}</h2></div><button onClick={onClose} className="text-slate-400 hover:text-slate-700">×</button></div>
    <p className="text-xs text-slate-500 mt-2">Potential ranking conflict. This evidence does not prove that one URL caused another URL to lose rankings.</p>
    <div className="mt-5 space-y-4"><Evidence label="Primary URL" value={conflict.primary_url} /><Evidence label="Competing URL" value={conflict.competing_url} /><Evidence label="Recommendation" value={conflict.recommendation} /></div>
    <div className="grid grid-cols-2 gap-3 mt-5"><Metric label="Conflict score" value={`${Math.round(conflict.conflict_score)}/100`} /><Metric label="Content similarity" value={pct(conflict.content_similarity)} /><Metric label="GSC query overlap" value={pct(conflict.gsc_overlap)} /><Metric label="Displacement signal" value={pct(conflict.ranking_displacement)} /></div>
    <div className="mt-5 rounded-xl border dark:border-slate-800 p-4"><h3 className="font-semibold text-sm">Measured signals</h3><ul className="mt-3 text-xs space-y-2 text-slate-500"><li>Exact focus keyword: {conflict.evidence.exact_focus_keyword ? "Yes" : "No"}</li><li>Primary type: {contentTypeLabel(conflict.evidence.primary_content_type, conflict.evidence.primary_wordpress_source)}</li><li>Competing type: {contentTypeLabel(conflict.evidence.competing_content_type, conflict.evidence.competing_wordpress_source)}</li><li>Primary focus: {conflict.evidence.focus_keyword_primary || "Not verified"}</li><li>Competing focus: {conflict.evidence.focus_keyword_competing || "Not verified"}</li><li>Title similarity: {pct(conflict.evidence.title_similarity)}</li><li>Keyword similarity: {pct(conflict.evidence.keyword_similarity)}</li><li>Canonical relationship: {conflict.evidence.canonical_conflict ? "Detected" : "Not detected"}</li></ul></div>
    <div className="mt-5"><h3 className="font-semibold text-sm">GSC query evidence</h3>{queries.length ? <div className="mt-2 overflow-x-auto"><table className="w-full text-xs"><thead><tr className="text-left text-slate-400"><th className="py-2 pr-2">Query</th><th className="py-2 pr-2">Primary</th><th className="py-2">Competing</th></tr></thead><tbody>{queries.map((q) => <tr key={q.query} className="border-t dark:border-slate-800"><td className="py-2 pr-2 max-w-[150px] break-words">{q.query}</td><td className="py-2 pr-2">{number(q.primary.impressions)} imp · {q.primary.position ? q.primary.position.toFixed(1) : "—"}</td><td className="py-2">{number(q.competing.impressions)} imp · {q.competing.position ? q.competing.position.toFixed(1) : "—"}</td></tr>)}</tbody></table></div> : <p className="text-xs text-slate-500 mt-2">No shared GSC query rows were measured.</p>}</div>
    {conflict.evidence.ai_analysis && <div className="mt-5 rounded-xl bg-emerald-50 dark:bg-emerald-500/10 p-4"><div className="flex items-center gap-2 font-semibold text-sm"><Sparkles className="size-4" /> Claude interpretation</div><p className="text-xs text-slate-600 dark:text-slate-300 mt-2 whitespace-pre-wrap">{conflict.evidence.ai_analysis}</p></div>}
    {conflict.evidence.website_resolution?.status === "applied" && <div className="mt-5 rounded-xl border border-emerald-200 dark:border-emerald-900/60 bg-emerald-50 dark:bg-emerald-500/10 p-4"><div className="flex items-center gap-2 font-semibold text-sm text-emerald-700 dark:text-emerald-300"><CheckCircle2 className="size-4" /> Website fix applied by Claude</div><p className="text-xs text-slate-600 dark:text-slate-300 mt-2">{conflict.evidence.website_resolution.replacements_applied || 0} targeted content change(s) were published on the competing WordPress page.</p><p className="text-[11px] text-slate-500 mt-1 break-all">Target: {conflict.evidence.website_resolution.target_url || conflict.competing_url}</p></div>}
    {conflict.evidence.website_resolution?.status === "manual_review_required" && <div className="mt-5 rounded-xl border border-amber-200 dark:border-amber-900/60 bg-amber-50 dark:bg-amber-500/10 p-4"><div className="font-semibold text-sm text-amber-700 dark:text-amber-300">Claude recommends manual review</div><p className="text-xs text-slate-600 dark:text-slate-300 mt-2">{conflict.evidence.website_resolution.reason}</p></div>}
    <div className="mt-5 flex flex-wrap gap-2"><button onClick={onAnalyze} disabled={aiLoading} className="px-3 py-2 rounded-lg bg-slate-900 text-white dark:bg-white dark:text-slate-900 text-xs font-semibold inline-flex items-center gap-2 disabled:opacity-50">{aiLoading ? <Loader2 className="size-3 animate-spin" /> : <Sparkles className="size-3" />} Analyze with Claude</button><button onClick={onResolve} disabled={aiLoading || conflict.status === "resolved"} className="px-3 py-2 rounded-lg bg-emerald-600 text-white text-xs font-semibold inline-flex items-center gap-2 disabled:opacity-50"><CheckCircle2 className="size-3" /> {conflict.status === "resolved" ? "Resolved on website" : "Resolved"}</button>{(["reviewed", "ignored"] as ConflictStatus[]).map((value) => <button key={value} onClick={() => onStatus(conflict.id, value)} className={`px-3 py-2 rounded-lg border text-xs font-semibold ${conflict.status === value ? "bg-slate-100 dark:bg-slate-800" : ""}`}>{value}</button>)}</div>
  </aside>;
}

function Kpi({ title, value, icon }: { title: string; value: number; icon: ReactNode }) { return <div className="rounded-2xl border bg-white dark:bg-slate-900 dark:border-slate-800 p-5"><div className="flex items-center justify-between"><span className="text-sm text-slate-500">{title}</span><span className="text-emerald-600">{icon}</span></div><div className="text-3xl font-bold mt-2">{value}</div></div>; }
function Metric({ label, value }: { label: string; value: string | number }) { return <div className="rounded-lg bg-slate-50 dark:bg-slate-800/70 p-3"><div className="text-[11px] uppercase tracking-wide text-slate-400">{label}</div><div className="font-semibold mt-1 truncate">{value}</div></div>; }
function Evidence({ label, value }: { label: string; value: string }) { return <div><div className="text-[11px] uppercase tracking-wide text-slate-400">{label}</div><div className="text-xs break-all mt-1">{value}</div></div>; }
function Empty({ text }: { text: string }) { return <div className="p-10 text-center text-sm text-slate-500">{text}</div>; }

export default KeywordConflicts;
