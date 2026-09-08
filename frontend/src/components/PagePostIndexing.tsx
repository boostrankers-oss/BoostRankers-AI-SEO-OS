import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  FileText,
  Globe2,
  Loader2,
  RefreshCw,
  Send,
  Search,
  XCircle,
} from "lucide-react";
import { api } from "@/lib/api";

type Client = { id: string; business_name?: string; website?: string };

type Overview = {
  total: number;
  pages: number;
  posts: number;
  crawled: number;
  indexable: number;
  indexed: number;
  not_indexed: number;
  noindex: number;
  errors: number;
};

type Item = {
  id: string;
  wordpress_id?: number | null;
  content_type: "post" | "page" | "unknown";
  url: string;
  final_url?: string | null;
  title?: string | null;
  h1?: string | null;
  canonical_url?: string | null;
  http_status?: number | null;
  robots_meta?: string | null;
  x_robots_tag?: string | null;
  indexable?: boolean | null;
  indexability_reason?: string | null;
  crawl_status: string;
  google_index_status: string;
  google_verdict?: string | null;
  google_coverage_state?: string | null;
  google_last_crawl_time?: string | null;
  google_canonical?: string | null;
  error_message?: string | null;
  updated_at?: string | null;
};

type Run = {
  id: string;
  status: string;
  progress_message?: string | null;
  total_urls: number;
  discovered_urls: number;
  crawled_urls: number;
  indexable_urls: number;
  indexed_urls: number;
  not_indexed_urls: number;
  error_urls: number;
  sitemap_submitted: boolean;
  sitemap_url?: string | null;
  google_message?: string | null;
  created_at?: string;
  completed_at?: string | null;
};

function statusLabel(value: string) {
  return value.replace(/_/g, " ");
}

function StatusBadge({ value }: { value: string }) {
  const normalized = value.toLowerCase();
  const good = normalized === "indexed" || normalized === "ok" || normalized === "completed";
  const bad = normalized === "not_indexed" || normalized === "error" || normalized === "failed";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${
        good
          ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300"
          : bad
            ? "bg-red-100 text-red-700 dark:bg-red-950/40 dark:text-red-300"
            : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
      }`}
    >
      {statusLabel(value)}
    </span>
  );
}

export function PagePostIndexing() {
  const [clients, setClients] = useState<Client[]>([]);
  const [clientId, setClientId] = useState("");
  const [overview, setOverview] = useState<Overview | null>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [filter, setFilter] = useState<"all" | "post" | "page">("all");

  const selectedClient = useMemo(
    () => clients.find((client) => client.id === clientId),
    [clients, clientId],
  );

  const loadClients = useCallback(async () => {
    const result = await api.get<Client[]>("/api/clients/");
    setClients(result || []);
    if (!clientId && result?.length) setClientId(result[0].id);
  }, [clientId]);

  const loadData = useCallback(async () => {
    if (!clientId) return;
    setLoading(true);
    setError("");
    try {
      const [overviewResult, itemResult, runResult] = await Promise.all([
        api.get<{ overview: Overview }>(`/api/page-post-indexing/overview?client_id=${encodeURIComponent(clientId)}`),
        api.get<{ items: Item[] }>(`/api/page-post-indexing/items?client_id=${encodeURIComponent(clientId)}&limit=500`),
        api.get<{ runs: Run[] }>(`/api/page-post-indexing/runs?client_id=${encodeURIComponent(clientId)}&limit=20`),
      ]);
      setOverview(overviewResult.overview);
      setItems(itemResult.items || []);
      setRuns(runResult.runs || []);
    } catch (err: any) {
      setError(err?.data?.detail || err?.message || "Unable to load Page & Post indexing data.");
    } finally {
      setLoading(false);
    }
  }, [clientId]);

  useEffect(() => {
    void loadClients();
  }, [loadClients]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const startCrawl = async () => {
    if (!clientId) return;
    setWorking(true);
    setError("");
    setMessage("");
    try {
      const result = await api.post<{ message: string }>(
        "/api/page-post-indexing/crawl",
        {
          client_id: clientId,
          include_posts: true,
          include_pages: true,
          max_urls: 500,
          verify_google_index: true,
          submit_sitemap: true,
        },
      );
      setMessage(result.message || "Crawl queued.");
      window.setTimeout(() => void loadData(), 1000);
    } catch (err: any) {
      setError(err?.data?.detail || err?.message || "Unable to start the crawl.");
    } finally {
      setWorking(false);
    }
  };

  const submitSitemap = async () => {
    if (!clientId) return;
    setWorking(true);
    setError("");
    setMessage("");
    try {
      const result = await api.post<{ message: string; submitted?: boolean }>(
        "/api/page-post-indexing/submit-sitemap",
        { client_id: clientId },
      );
      setMessage(result.message || "Sitemap submitted.");
      await loadData();
    } catch (err: any) {
      setError(err?.data?.detail || err?.message || "Unable to submit the sitemap.");
    } finally {
      setWorking(false);
    }
  };

  const visibleItems = filter === "all" ? items : items.filter((item) => item.content_type === filter);

  if (loading && !clients.length) {
    return (
      <div className="min-h-full flex items-center justify-center p-8">
        <Loader2 className="size-6 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-full bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <div className="mx-auto max-w-[1600px] space-y-6 p-6 md:p-8">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400 text-sm font-semibold">
              <Globe2 className="size-4" />
              Indexing & Crawl Intelligence
            </div>
            <h1 className="mt-1 text-3xl font-bold tracking-tight">Page & Post Indexing</h1>
            <p className="mt-2 max-w-3xl text-slate-500 dark:text-slate-400">
              Discover WordPress Pages and Posts, crawl their real indexability signals,
              submit the sitemap to Google Search Console, and verify Google index status where URL Inspection is authorized.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <select
              value={clientId}
              onChange={(event) => setClientId(event.target.value)}
              className="h-10 min-w-[230px] rounded-lg border bg-white px-3 text-sm dark:border-slate-700 dark:bg-slate-900"
            >
              <option value="">Select client</option>
              {clients.map((client) => (
                <option key={client.id} value={client.id}>
                  {client.business_name || client.website || client.id}
                </option>
              ))}
            </select>
            <button
              onClick={() => void loadData()}
              disabled={!clientId || loading}
              className="inline-flex h-10 items-center gap-2 rounded-lg border bg-white px-4 text-sm font-semibold hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900"
            >
              <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} />
              Refresh
            </button>
            <button
              onClick={() => void submitSitemap()}
              disabled={!clientId || working}
              className="inline-flex h-10 items-center gap-2 rounded-lg border bg-white px-4 text-sm font-semibold hover:bg-slate-50 disabled:opacity-50 dark:border-slate-700 dark:bg-slate-900"
            >
              <Send className="size-4" />
              Submit Sitemap
            </button>
            <button
              onClick={() => void startCrawl()}
              disabled={!clientId || working}
              className="inline-flex h-10 items-center gap-2 rounded-lg bg-emerald-600 px-4 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-50"
            >
              {working ? <Loader2 className="size-4 animate-spin" /> : <Search className="size-4" />}
              Crawl Posts & Pages
            </button>
          </div>
        </div>

        {selectedClient?.website && (
          <div className="rounded-xl border bg-white px-4 py-3 text-sm text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300">
            <span className="font-semibold">Website:</span> {selectedClient.website}
          </div>
        )}

        {message && (
          <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700 dark:border-emerald-900/40 dark:bg-emerald-950/20 dark:text-emerald-300">
            <CheckCircle2 className="size-4" />
            {message}
          </div>
        )}
        {error && (
          <div className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-950/20 dark:text-red-300">
            <AlertCircle className="size-4" />
            {error}
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-8">
          {[
            ["Total", overview?.total ?? 0],
            ["Pages", overview?.pages ?? 0],
            ["Posts", overview?.posts ?? 0],
            ["Crawled", overview?.crawled ?? 0],
            ["Indexable", overview?.indexable ?? 0],
            ["Indexed", overview?.indexed ?? 0],
            ["Not indexed", overview?.not_indexed ?? 0],
            ["Errors", overview?.errors ?? 0],
          ].map(([label, value]) => (
            <div key={String(label)} className="rounded-xl border bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</div>
              <div className="mt-2 text-2xl font-bold">{value}</div>
            </div>
          ))}
        </div>

        <div className="rounded-xl border bg-white dark:border-slate-800 dark:bg-slate-900">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b p-4 dark:border-slate-800">
            <div>
              <h2 className="font-semibold">Pages & Posts</h2>
              <p className="text-xs text-slate-500">Crawl evidence is kept separate from Google index verification.</p>
            </div>
            <div className="flex gap-2">
              {(["all", "page", "post"] as const).map((value) => (
                <button
                  key={value}
                  onClick={() => setFilter(value)}
                  className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${
                    filter === value
                      ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900"
                      : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300"
                  }`}
                >
                  {value === "all" ? "All" : value === "page" ? "Pages" : "Posts"}
                </button>
              ))}
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[1100px] text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase text-slate-500 dark:bg-slate-950/50">
                <tr>
                  <th className="px-4 py-3">URL</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">HTTP</th>
                  <th className="px-4 py-3">Crawl</th>
                  <th className="px-4 py-3">Indexability</th>
                  <th className="px-4 py-3">Google</th>
                  <th className="px-4 py-3">Canonical</th>
                </tr>
              </thead>
              <tbody className="divide-y dark:divide-slate-800">
                {visibleItems.map((item) => (
                  <tr key={item.id} className="align-top">
                    <td className="max-w-[420px] px-4 py-3">
                      <div className="flex items-start gap-2">
                        <FileText className="mt-0.5 size-4 shrink-0 text-slate-400" />
                        <div>
                          <a
                            href={item.url}
                            target="_blank"
                            rel="noreferrer"
                            className="break-all font-medium text-emerald-600 hover:underline"
                          >
                            {item.url}
                          </a>
                          {item.title && <div className="mt-1 line-clamp-2 text-xs text-slate-500">{item.title}</div>}
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 capitalize">{item.content_type}</td>
                    <td className="px-4 py-3">{item.http_status ?? "—"}</td>
                    <td className="px-4 py-3"><StatusBadge value={item.crawl_status} /></td>
                    <td className="px-4 py-3">
                      {item.indexable ? (
                        <span className="inline-flex items-center gap-1 text-emerald-600"><CheckCircle2 className="size-4" /> Indexable</span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-red-600"><XCircle className="size-4" /> {item.indexability_reason || "Not indexable"}</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge value={item.google_index_status} />
                      {item.google_coverage_state && (
                        <div className="mt-1 max-w-[260px] text-xs text-slate-500">{item.google_coverage_state}</div>
                      )}
                    </td>
                    <td className="max-w-[260px] px-4 py-3 break-all text-xs text-slate-500">
                      {item.canonical_url || "Self / not detected"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {!visibleItems.length && (
            <div className="p-10 text-center text-sm text-slate-500">
              No crawl records yet. Start a Posts & Pages crawl.
            </div>
          )}
        </div>

        <div className="rounded-xl border bg-white dark:border-slate-800 dark:bg-slate-900">
          <div className="border-b p-4 dark:border-slate-800">
            <h2 className="font-semibold">Crawl History</h2>
          </div>
          <div className="divide-y dark:divide-slate-800">
            {runs.map((run) => (
              <div key={run.id} className="flex flex-col gap-3 p-4 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <StatusBadge value={run.status} />
                    <span className="text-xs text-slate-500">{run.created_at ? new Date(run.created_at).toLocaleString() : ""}</span>
                  </div>
                  <div className="mt-1 text-sm">{run.progress_message || "—"}</div>
                  <div className="mt-1 text-xs text-slate-500">
                    {run.crawled_urls}/{run.total_urls} crawled · {run.indexable_urls} indexable · {run.indexed_urls} indexed · {run.not_indexed_urls} not indexed
                  </div>
                </div>
                {run.sitemap_submitted && (
                  <div className="text-xs font-semibold text-emerald-600">Sitemap submitted to Google</div>
                )}
              </div>
            ))}
            {!runs.length && <div className="p-8 text-center text-sm text-slate-500">No crawl history yet.</div>}
          </div>
        </div>
      </div>
    </div>
  );
}

export default PagePostIndexing;
