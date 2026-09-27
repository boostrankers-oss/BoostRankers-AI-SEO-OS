import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  ArrowDown,
  ArrowUp,
  BarChart3,
  CheckCircle2,
  ChevronRight,
  Clock3,
  ExternalLink,
  Globe2,
  Loader2,
  Plus,
  RefreshCw,
  Search,
  Target,
  Trash2,
  X,
} from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";

interface ClientOption {
  id: string;
  business_name?: string;
  name?: string;
}

interface RankKeyword {
  id: string;
  client_id: string | null;
  client_name?: string | null;
  keyword: string;
  target_url: string | null;
  search_engine: string;
  country: string;
  location: string | null;
  language: string;
  device: string;
  frequency: string;
  is_active: boolean;
  current_position: number | null;
  previous_position: number | null;
  change: number | null;
  ranking_url: string | null;
  last_checked_at: string | null;
  status: string;
  last_error?: string | null;
  measurement_property?: string;
  measurement_message?: string;
  date_range?: { start: string; end: string };
  comparison_date_range?: { start: string; end: string };
  latest_gsc_date?: string | null;
  clicks?: number;
  impressions?: number;
  ctr?: number;
  measurement_start_date?: string | null;
  measurement_end_date?: string | null;
  snapshot_period?: string | null;
}

interface Overview {
  tracked_keywords: number;
  top_3: number;
  top_10: number;
  top_20: number;
  improved: number;
  declined: number;
  not_ranking: number;
  average_position: number | null;
}

interface HistoryPoint {
  checked_at: string;
  position: number | null;
  ranking_url: string | null;
  clicks?: number;
  impressions?: number;
  ctr?: number;
  measurement_start_date?: string | null;
  measurement_end_date?: string | null;
  comparison_start_date?: string | null;
  comparison_end_date?: string | null;
}

const emptyForm = {
  keyword: "",
  client_id: "none",
  target_url: "",
  country: "global",
  location: "",
  device: "all",
  language: "en",
  frequency: "daily",
};

function positionLabel(position: number | null): string {
  if (position == null) return "—";
  return position.toFixed(1);
}

function movementClass(change: number | null): string {
  if (change == null || change === 0) return "text-slate-500";
  return change > 0 ? "text-emerald-600" : "text-rose-600";
}

function movementLabel(change: number | null): string {
  if (change == null) return "No comparison";
  if (change > 0) return "Improved";
  if (change < 0) return "Declined";
  return "Unchanged";
}

export function RankTracker() {
  const [keywords, setKeywords] = useState<RankKeyword[]>([]);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [clients, setClients] = useState<ClientOption[]>([]);
  const [gscConnected, setGscConnected] = useState(false);
  const [property, setProperty] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState("");
  const [clientFilter, setClientFilter] = useState("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [measurementMessage, setMeasurementMessage] = useState("");
  const [period, setPeriod] = useState<"daily" | "weekly" | "monthly" | "yearly">("daily");
  const [compare, setCompare] = useState<"previous_period" | "previous_week" | "previous_month" | "previous_year" | "custom">("previous_period");
  const [customCompareStart, setCustomCompareStart] = useState("");
  const [customCompareEnd, setCustomCompareEnd] = useState("");
  const [latestGscDate, setLatestGscDate] = useState<string | null>(null);
  const [activeKpi, setActiveKpi] = useState<"tracked" | "top_3" | "top_10" | "top_20" | "improved" | "declined" | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [keywordData, overviewData, statusData, clientData] = await Promise.all([
        api.get<RankKeyword[]>(`/api/rank-tracking/keywords?period=${period}`),
        api.get<Overview>(`/api/rank-tracking/overview?period=${period}`),
        api.get<{ google_search_console_connected: boolean; selected_property: string | null }>("/api/rank-tracking/status"),
        api.get<ClientOption[]>("/api/clients/"),
      ]);
      setKeywords(keywordData || []);
      setOverview(overviewData);
      setGscConnected(Boolean(statusData.google_search_console_connected));
      setProperty(statusData.selected_property || null);
      setClients(clientData || []);
      const availableDates = (keywordData || [])
        .map((item) => item.latest_gsc_date || item.measurement_end_date)
        .filter(Boolean)
        .sort();
      setLatestGscDate(availableDates.length ? availableDates[availableDates.length - 1] as string : null);
    } catch (error: any) {
      console.error("Rank tracker load failed", error);
      toast.error(error?.data?.detail || "Unable to load Rank Tracker.");
    } finally {
      setLoading(false);
    }
  }, [period]);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return keywords.filter((item) => {
      const matchesSearch = !q || item.keyword.toLowerCase().includes(q) || (item.target_url || "").toLowerCase().includes(q);
      const matchesClient = clientFilter === "all" || item.client_id === clientFilter;

      const position = item.current_position;
      const matchesKpi =
        activeKpi === null ||
        activeKpi === "tracked" ||
        (activeKpi === "top_3" && position != null && position >= 1 && position <= 3) ||
        (activeKpi === "top_10" && position != null && position >= 1 && position <= 10) ||
        (activeKpi === "top_20" && position != null && position >= 1 && position <= 20) ||
        (activeKpi === "improved" && item.change != null && item.change > 0) ||
        (activeKpi === "declined" && item.change != null && item.change < 0);

      return matchesSearch && matchesClient && matchesKpi;
    });
  }, [keywords, search, clientFilter, activeKpi]);

  const loadHistory = useCallback(async (id: string) => {
    setSelectedId(id);
    setHistoryLoading(true);
    try {
      const result = await api.get<{ history: HistoryPoint[] }>(`/api/rank-tracking/keywords/${id}/history?limit=90`);
      setHistory(result.history || []);
    } catch (error: any) {
      toast.error(error?.data?.detail || "Unable to load ranking history.");
      setHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  const handleAdd = async () => {
    const entries = Array.from(
      new Set(
        form.keyword
          .split(/\r?\n/)
          .map((value) => value.replace(/\s+/g, " ").trim())
          .filter(Boolean),
      ),
    );
    if (!entries.length) {
      toast.error("Enter at least one keyword.");
      return;
    }

    if (compare === "custom" && (!customCompareStart || !customCompareEnd)) {
      toast.error("Select both custom comparison dates.");
      return;
    }
    if (compare === "custom" && customCompareEnd < customCompareStart) {
      toast.error("Custom comparison end date must be on or after the start date.");
      return;
    }

    setSaving(true);
    const addPeriod = form.frequency as "daily" | "weekly" | "monthly" | "yearly";
    const createdIds: string[] = [];
    const errors: string[] = [];
    try {
      for (const keyword of entries) {
        try {
          const created = await api.post<RankKeyword>("/api/rank-tracking/keywords", {
            keyword,
            client_id: form.client_id === "none" ? null : form.client_id,
            target_url: null,
            search_engine: "google",
            country: "global",
            location: null,
            language: "en",
            device: "all",
            frequency: form.frequency,
          });
          createdIds.push(created.id);
          setKeywords((current) => [created, ...current.filter((item) => item.id !== created.id)]);
        } catch (error: any) {
          const message = error?.data?.detail || `Unable to add "${keyword}".`;
          errors.push(`${keyword}: ${message}`);
        }
      }

      setForm(emptyForm);
      setShowAdd(false);

      if (createdIds.length) {
        toast.success(`${createdIds.length} keyword${createdIds.length === 1 ? "" : "s"} added. Syncing latest GSC data...`);
        if (gscConnected && property) {
          const result = await api.post<{ updated: number; items: RankKeyword[]; errors?: Array<{ keyword: string; error: string }> }>(
            "/api/rank-tracking/refresh",
            { keyword_ids: createdIds, period: addPeriod, compare, custom_compare_start: compare === "custom" ? customCompareStart || null : null, custom_compare_end: compare === "custom" ? customCompareEnd || null : null },
          );
          if (result.items?.length) {
            setKeywords((current) => {
              const map = new Map(result.items.map((item) => [item.id, item]));
              return current.map((item) => map.get(item.id) || item);
            });
          }
          if (result.errors?.length) {
            errors.push(...result.errors.map((item) => `${item.keyword}: ${item.error}`));
          }
        }
      }

      if (errors.length) {
        toast.warning(errors.slice(0, 2).join(" • "));
      }
      setPeriod(addPeriod);
      const freshKeywords = await api.get<RankKeyword[]>(`/api/rank-tracking/keywords?period=${addPeriod}`);
      setKeywords(freshKeywords || []);
      const freshOverview = await api.get<Overview>(`/api/rank-tracking/overview?period=${addPeriod}`);
      setOverview(freshOverview);
      const freshDates = (freshKeywords || []).map((item) => item.latest_gsc_date || item.measurement_end_date).filter(Boolean).sort();
      setLatestGscDate(freshDates.length ? freshDates[freshDates.length - 1] as string : null);
    } catch (error: any) {
      toast.error(error?.data?.detail || "Unable to add keywords.");
    } finally {
      setSaving(false);
    }
  };

  const handleRefresh = async (ids: string[] = []) => {
    if (!gscConnected || !property) {
      toast.error("Connect Google Search Console and select a property first.");
      return;
    }
    if (compare === "custom" && (!customCompareStart || !customCompareEnd)) {
      toast.error("Select both custom comparison dates.");
      return;
    }
    if (compare === "custom" && customCompareEnd < customCompareStart) {
      toast.error("Custom comparison end date must be on or after the start date.");
      return;
    }
    setRefreshing(true);
    try {
      const result = await api.post<{ updated: number; items: RankKeyword[]; errors?: Array<{ keyword: string; error: string }> }>(
        "/api/rank-tracking/refresh",
        { keyword_ids: ids, period, compare, custom_compare_start: compare === "custom" ? customCompareStart || null : null, custom_compare_end: compare === "custom" ? customCompareEnd || null : null },
      );
      if (result.items?.length) {
        setKeywords((current) => {
          const map = new Map(result.items.map((item) => [item.id, item]));
          return current.map((item) => map.get(item.id) || item);
        });
        const dates = result.items.map((item) => item.latest_gsc_date || item.measurement_end_date).filter(Boolean).sort();
        if (dates.length) setLatestGscDate(dates[dates.length - 1] as string);
        const first = result.items[0];
        if (first?.measurement_message) setMeasurementMessage(first.measurement_message);
        if (ids.length === 1) await loadHistory(ids[0]);
      }
      if (result.errors?.length) {
        toast.warning(`${result.updated} updated; ${result.errors.length} could not be checked.`);
      } else {
        toast.success(`${result.updated} keyword${result.updated === 1 ? "" : "s"} synced from Google Search Console.`);
      }
      const nextOverview = await api.get<Overview>(`/api/rank-tracking/overview?period=${period}`);
      setOverview(nextOverview);
      await load();
    } catch (error: any) {
      toast.error(error?.data?.detail || "Google Search Console sync failed.");
    } finally {
      setRefreshing(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm("Stop tracking this keyword? Historical snapshots will remain available.")) return;
    try {
      await api.delete(`/api/rank-tracking/keywords/${id}`);
      setKeywords((current) => current.filter((item) => item.id !== id));
      if (selectedId === id) {
        setSelectedId(null);
        setHistory([]);
      }
      toast.success("Keyword removed from tracking.");
      const nextOverview = await api.get<Overview>("/api/rank-tracking/overview");
      setOverview(nextOverview);
    } catch (error: any) {
      toast.error(error?.data?.detail || "Unable to remove keyword.");
    }
  };

  const chartData = history.map((point, index) => {
    const checkedAt = new Date(point.checked_at);
    return {
      // Include time (and seconds) so multiple snapshots taken on the same day
      // remain distinct on the X axis instead of collapsing into one "Sep 6" label.
      date: checkedAt.toLocaleString(undefined, {
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
        second: "2-digit",
      }),
      position: point.position,
      snapshot: index + 1,
      checkedAt: point.checked_at,
    };
  });

  const chartPositions = chartData
    .map((point) => point.position)
    .filter((position): position is number => typeof position === "number" && Number.isFinite(position));
  const chartMin = chartPositions.length ? Math.min(...chartPositions) : 1;
  const chartMax = chartPositions.length ? Math.max(...chartPositions) : 1;
  // Keep a small amount of breathing room around a flat series (e.g. 21, 21, 21, 21)
  // so the line and snapshot points are clearly visible.
  const chartPadding = Math.max(1, Math.ceil((chartMax - chartMin) * 0.2));
  const chartDomain: [number, number] = [
    Math.max(1, chartMin - chartPadding),
    chartMax + chartPadding,
  ];

  const kpiCards = [
    ["tracked", "Tracked", overview?.tracked_keywords ?? 0],
    ["top_3", "Top 3", overview?.top_3 ?? 0],
    ["top_10", "Top 10", overview?.top_10 ?? 0],
    ["top_20", "Top 20", overview?.top_20 ?? 0],
    ["improved", "Improved", overview?.improved ?? 0],
    ["declined", "Declined", overview?.declined ?? 0],
    ["average", "Avg. Position", overview?.average_position ?? "—"],
  ] as const;

  const handleKpiClick = (key: typeof kpiCards[number][0]) => {
    if (key === "average") return;
    setActiveKpi((current) => current === key ? null : key);
  };

  const activeKpiLabel = kpiCards.find(([key]) => key === activeKpi)?.[1];

  if (loading) {
    return <div className="p-8 flex items-center gap-2 text-slate-500"><Loader2 className="size-4 animate-spin" /> Loading Rank Tracker...</div>;
  }

  return (
    <div className="p-6 md:p-8 space-y-6 max-w-[1600px] mx-auto">
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-emerald-600 text-sm font-medium mb-1"><Target className="size-4" /> Organic Visibility</div>
          <h1 className="font-serif text-3xl font-bold tracking-tight">Rank Tracker</h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1">Track the latest available Google Search Console average position with flexible period comparison.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => void load()} disabled={loading}>
            <RefreshCw className="size-4" /> Refresh Data
          </Button>
          <Button onClick={() => setShowAdd(true)} className="bg-emerald-600 hover:bg-emerald-700 text-white">
            <Plus className="size-4" /> Add Keyword
          </Button>
          <Button onClick={() => void handleRefresh()} disabled={refreshing || keywords.length === 0} className="bg-slate-900 hover:bg-slate-800 text-white dark:bg-white dark:text-slate-900">
            {refreshing ? <Loader2 className="size-4 animate-spin" /> : <Activity className="size-4" />}
            {refreshing ? "Syncing..." : "Sync GSC Data"}
          </Button>
        </div>
      </div>

      {!gscConnected || !property ? (
        <Card className="border-amber-200 dark:border-amber-800 bg-amber-50/60 dark:bg-amber-500/5">
          <CardContent className="p-4 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
            <div className="flex gap-3">
              <Globe2 className="size-5 text-amber-600 mt-0.5" />
              <div>
                <p className="font-medium">Google Search Console connection required</p>
                <p className="text-sm text-slate-600 dark:text-slate-400">Connect GSC and select the website property in Google Integration before checking positions.</p>
              </div>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-xs text-slate-500"><CheckCircle2 className="size-4 text-emerald-600" /> Measuring from <span className="font-medium text-slate-700 dark:text-slate-300">{property}</span> · GSC average position</div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
            <span className="rounded-full border px-2 py-1">Period: <strong>{period}</strong></span>
            <span className="rounded-full border px-2 py-1">Compare: <strong>{compare === "previous_period" ? "Previous period" : compare.replace("previous_", "Previous ")}</strong></span>
            {latestGscDate && <span className="rounded-full border px-2 py-1">Latest GSC data: <strong>{new Date(`${latestGscDate}T00:00:00`).toLocaleDateString()}</strong></span>}
          </div>
          {measurementMessage && (
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-400">
              {measurementMessage}
            </div>
          )}
        </div>
      )}

      <div className="grid grid-cols-2 xl:grid-cols-7 gap-3">
        {kpiCards.map(([key, label, value]) => {
          const clickable = key !== "average";
          const active = activeKpi === key;

          return (
            <Card
              key={key}
              role={clickable ? "button" : undefined}
              tabIndex={clickable ? 0 : undefined}
              aria-pressed={clickable ? active : undefined}
              onClick={clickable ? () => handleKpiClick(key) : undefined}
              onKeyDown={clickable ? (event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  handleKpiClick(key);
                }
              } : undefined}
              className={`shadow-sm transition-all ${
                clickable
                  ? "cursor-pointer hover:-translate-y-0.5 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
                  : ""
              } ${active ? "ring-2 ring-emerald-500 bg-emerald-50/60 dark:bg-emerald-500/10" : ""}`}
              title={clickable ? `Show ${label.toLowerCase()} keywords` : "Overall average position"}
            >
              <CardContent className="p-4">
                <p className="text-xs text-slate-500">{label}</p>
                <p className="text-2xl font-semibold mt-1">
                  {typeof value === "number" && label === "Avg. Position" ? value.toFixed(1) : value}
                </p>
                {clickable && (
                  <p className={`text-[10px] mt-1 ${active ? "text-emerald-600 font-medium" : "text-slate-400"}`}>
                    {active ? "Showing keywords" : "Click to filter"}
                  </p>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {activeKpi && (
        <div className="flex items-center justify-between gap-3 rounded-lg border border-emerald-200 bg-emerald-50/70 px-3 py-2 text-xs text-emerald-800 dark:border-emerald-900/60 dark:bg-emerald-500/10 dark:text-emerald-300">
          <span>Showing <strong>{activeKpiLabel}</strong> keywords · {filtered.length} result{filtered.length === 1 ? "" : "s"}</span>
          <Button variant="ghost" size="sm" className="h-7 text-xs" onClick={() => setActiveKpi(null)}>
            Clear filter
            <X className="size-3.5" />
          </Button>
        </div>
      )}

      <div className="flex flex-col md:flex-row gap-3">
        <div className="relative flex-1"><Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-slate-400" /><Input className="pl-9" placeholder="Search keywords or URLs..." value={search} onChange={(e) => setSearch(e.target.value)} /></div>
        <Select value={clientFilter} onValueChange={(value) => setClientFilter(value || "all")}>
          <SelectTrigger className="w-full md:w-56"><SelectValue placeholder="All clients" /></SelectTrigger>
          <SelectContent className="bg-white dark:bg-slate-950 border-slate-200 dark:border-slate-800 opacity-100"><SelectItem value="all">All clients</SelectItem>{clients.map((client) => <SelectItem key={client.id} value={client.id}>{client.business_name || client.name || client.id}</SelectItem>)}</SelectContent>
        </Select>
      </div>

      <Card className="shadow-sm">
        <CardContent className="p-3 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
          <div className="flex items-center gap-2 text-sm font-medium"><Clock3 className="size-4 text-emerald-600" /> Reporting period</div>
          <div className="flex flex-wrap gap-2">
            {(["daily", "weekly", "monthly", "yearly"] as const).map((value) => (
              <Button key={value} variant={period === value ? "default" : "outline"} size="sm"
                onClick={() => setPeriod(value)} className={period === value ? "bg-emerald-600 hover:bg-emerald-700 text-white" : ""}>
                {value.charAt(0).toUpperCase() + value.slice(1)}
              </Button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">Compare</span>
            <Select value={compare} onValueChange={(value) => setCompare(value as typeof compare)}>
              <SelectTrigger className="w-44 h-9 bg-white dark:bg-slate-950 opacity-100"><SelectValue /></SelectTrigger>
              <SelectContent className="bg-white dark:bg-slate-950 border-slate-200 dark:border-slate-800 opacity-100">
                <SelectItem value="previous_period">Previous period</SelectItem>
                <SelectItem value="previous_week">Previous week</SelectItem>
                <SelectItem value="previous_month">Previous month</SelectItem>
                <SelectItem value="previous_year">Previous year</SelectItem>
                <SelectItem value="custom">Custom dates</SelectItem>
              </SelectContent>
            </Select>
          </div>
          {compare === "custom" && (
            <div className="w-full lg:w-auto flex flex-col sm:flex-row items-start sm:items-center gap-2 pt-2 lg:pt-0">
              <div className="flex items-center gap-2">
                <Label htmlFor="custom-compare-start" className="text-xs text-slate-500 whitespace-nowrap">From</Label>
                <Input id="custom-compare-start" type="date" value={customCompareStart} onChange={(e) => setCustomCompareStart(e.target.value)} className="h-9 w-40 bg-white dark:bg-slate-950" />
              </div>
              <div className="flex items-center gap-2">
                <Label htmlFor="custom-compare-end" className="text-xs text-slate-500 whitespace-nowrap">To</Label>
                <Input id="custom-compare-end" type="date" value={customCompareEnd} onChange={(e) => setCustomCompareEnd(e.target.value)} className="h-9 w-40 bg-white dark:bg-slate-950" />
              </div>
              <Button size="sm" onClick={() => void handleRefresh()} disabled={refreshing || !customCompareStart || !customCompareEnd}>Apply</Button>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid xl:grid-cols-[1fr_420px] gap-6">
        <Card className="shadow-sm overflow-hidden">
          <CardHeader>
            <CardTitle>{activeKpiLabel ? `${activeKpiLabel} Keywords` : "Tracked Keywords"}</CardTitle>
            <CardDescription>{period.charAt(0).toUpperCase() + period.slice(1)} GSC average position compared with the selected comparison period.</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            {filtered.length === 0 ? (
              <div className="p-10 text-center text-slate-500">No tracked keywords match your filters.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="border-y bg-slate-50/70 dark:bg-slate-900/50 dark:border-slate-800">
                    <tr className="text-left text-xs text-slate-500">
                      <th className="px-5 py-3">Keyword</th><th className="px-4 py-3">Latest</th><th className="px-4 py-3">Previous</th><th className="px-4 py-3">Change</th><th className="px-4 py-3">Clicks</th><th className="px-4 py-3">Impressions</th><th className="px-4 py-3">CTR</th><th className="px-4 py-3">GSC Date</th><th className="px-3 py-3" />
                    </tr>
                  </thead>
                  <tbody className="divide-y dark:divide-slate-800">
                    {filtered.map((item) => (
                      <tr key={item.id} className="hover:bg-slate-50 dark:hover:bg-slate-900/50 cursor-pointer" onClick={() => void loadHistory(item.id)}>
                        <td className="px-5 py-4"><div className="font-medium">{item.keyword}</div><div className="text-xs text-slate-500">{item.status === "ok" ? "Google Search Console" : item.status}</div></td>
                        <td className="px-4 py-4 font-semibold">{positionLabel(item.current_position)}</td>
                        <td className="px-4 py-4 text-slate-500">{positionLabel(item.previous_position)}</td>
                        <td className={`px-4 py-4 font-medium ${movementClass(item.change)}`}>
                          {item.change == null ? "—" : <span className="inline-flex flex-col gap-0.5"><span className="inline-flex items-center gap-1">{item.change > 0 ? <ArrowUp className="size-3.5" /> : item.change < 0 ? <ArrowDown className="size-3.5" /> : null}{Math.abs(item.change).toFixed(1)}</span><span className="text-[10px] font-normal">{movementLabel(item.change)}</span></span>}
                        </td>
                        <td className="px-4 py-4 text-xs">{Math.round(item.clicks || 0).toLocaleString()}</td>
                        <td className="px-4 py-4 text-xs">{Math.round(item.impressions || 0).toLocaleString()}</td>
                        <td className="px-4 py-4 text-xs">{((item.ctr || 0) * 100).toFixed(2)}%</td>
                        <td className="px-4 py-4 text-xs text-slate-500">{item.measurement_end_date ? new Date(`${item.measurement_end_date}T00:00:00`).toLocaleDateString() : "Not synced"}</td>
                        <td className="px-3 py-4">
                          <div className="flex items-center gap-1">
                            <Button variant="ghost" size="sm" title="Check this keyword now" onClick={(e) => { e.stopPropagation(); void handleRefresh([item.id]); }} disabled={refreshing}>
                              <RefreshCw className={`size-3.5 ${refreshing ? "animate-spin" : ""}`} />
                            </Button>
                            <Button variant="ghost" size="icon" onClick={(e) => { e.stopPropagation(); void handleDelete(item.id); }}>
                              <Trash2 className="size-4 text-slate-400 hover:text-rose-500" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardHeader><CardTitle className="flex items-center gap-2"><BarChart3 className="size-5 text-emerald-600" /> Position History</CardTitle><CardDescription>{selectedId ? keywords.find((item) => item.id === selectedId)?.keyword : "Select a keyword"}</CardDescription></CardHeader>
          <CardContent>
            {!selectedId ? <div className="py-16 text-center text-slate-500"><ChevronRight className="size-6 mx-auto mb-2" />Select a keyword to view history.</div> : historyLoading ? <div className="py-16 flex justify-center"><Loader2 className="size-5 animate-spin" /></div> : chartData.length === 0 ? (
                <div className="py-16 text-center text-slate-500">
                  {keywords.find((item) => item.id === selectedId)?.last_error ||
                    "No ranking position was returned by Google Search Console for this keyword in the selected period."}
                </div>
              ) : (
              <div className="h-[320px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 12, right: 12, left: 4, bottom: 38 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 10 }}
                      interval={0}
                      angle={-28}
                      textAnchor="end"
                      height={58}
                      tickMargin={8}
                    />
                    <YAxis
                      reversed
                      domain={chartDomain}
                      allowDecimals
                      tick={{ fontSize: 11 }}
                      width={34}
                      tickFormatter={(value) => Number(value).toFixed(0)}
                    />
                    <Tooltip
                      labelFormatter={(_, payload) => {
                        const checkedAt = payload?.[0]?.payload?.checkedAt;
                        return checkedAt
                          ? new Date(checkedAt).toLocaleString(undefined, {
                              dateStyle: "medium",
                              timeStyle: "medium",
                            })
                          : "Snapshot";
                      }}
                      formatter={(value) => [
                        value == null ? "Not ranking" : Number(value).toFixed(1),
                        "Position",
                      ]}
                    />
                    <Line
                      type="monotone"
                      dataKey="position"
                      connectNulls={false}
                      strokeWidth={3}
                      dot={{ r: 4, strokeWidth: 2 }}
                      activeDot={{ r: 6 }}
                      isAnimationActive={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
            {selectedId && history.length > 0 && <div className="mt-4 pt-4 border-t dark:border-slate-800 text-xs text-slate-500 flex items-center gap-2"><Clock3 className="size-3.5" /> {history.length} stored snapshot{history.length === 1 ? "" : "s"}</div>}
            {selectedId && keywords.find((item) => item.id === selectedId)?.ranking_url && <a className="mt-3 text-xs inline-flex items-center gap-1 text-emerald-600 hover:underline" href={keywords.find((item) => item.id === selectedId)?.ranking_url || "#"} target="_blank" rel="noreferrer">Open ranking URL <ExternalLink className="size-3" /></a>}
          </CardContent>
        </Card>
      </div>

      {showAdd && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4" onMouseDown={(e) => { if (e.target === e.currentTarget) setShowAdd(false); }}>
          <Card className="w-full max-w-2xl max-h-[90vh] overflow-y-auto shadow-2xl bg-white dark:bg-slate-950 border-slate-200 dark:border-slate-800 opacity-100">
            <CardHeader><div className="flex items-center justify-between"><div><CardTitle>Add Keywords</CardTitle><CardDescription>Enter one keyword per line. The connected Google Search Console property supplies the ranking data; no page URL is required.</CardDescription></div><Button variant="ghost" size="icon" onClick={() => setShowAdd(false)}><X className="size-4" /></Button></div></CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Keywords *</Label>
                <textarea autoFocus value={form.keyword} onChange={(e) => setForm({ ...form, keyword: e.target.value })} placeholder={"commercial cleaning perth\noffice cleaning perth\nschool cleaning perth"} className="min-h-40 w-full rounded-md border border-slate-300 bg-white px-3 py-3 text-sm text-slate-900 outline-none focus:ring-2 focus:ring-emerald-500 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100" />
                <p className="text-xs text-slate-500">One keyword per line. Duplicate lines are automatically removed.</p>
              </div>
              <div className="grid md:grid-cols-2 gap-4">
                <div className="space-y-2"><Label>Reporting frequency</Label><Select value={form.frequency} onValueChange={(value) => setForm({ ...form, frequency: value || "daily" })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent className="bg-white dark:bg-slate-950 border-slate-200 dark:border-slate-800 opacity-100"><SelectItem value="daily">Daily</SelectItem><SelectItem value="weekly">Weekly</SelectItem><SelectItem value="monthly">Monthly</SelectItem><SelectItem value="yearly">Yearly</SelectItem></SelectContent></Select></div>
                <div className="space-y-2"><Label>Comparison</Label><Select value={compare} onValueChange={(value) => setCompare(value as typeof compare)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent className="bg-white dark:bg-slate-950 border-slate-200 dark:border-slate-800 opacity-100"><SelectItem value="previous_period">Previous period</SelectItem><SelectItem value="previous_week">Previous week</SelectItem><SelectItem value="previous_month">Previous month</SelectItem><SelectItem value="previous_year">Previous year</SelectItem><SelectItem value="custom">Custom dates</SelectItem></SelectContent></Select></div>
              </div>
              {compare === "custom" && (
                <div className="grid sm:grid-cols-2 gap-4">
                  <div className="space-y-2"><Label htmlFor="modal-custom-start">Compare from</Label><Input id="modal-custom-start" type="date" value={customCompareStart} onChange={(e) => setCustomCompareStart(e.target.value)} className="bg-white text-slate-900 dark:bg-slate-900 dark:text-slate-100" /></div>
                  <div className="space-y-2"><Label htmlFor="modal-custom-end">Compare to</Label><Input id="modal-custom-end" type="date" value={customCompareEnd} onChange={(e) => setCustomCompareEnd(e.target.value)} className="bg-white text-slate-900 dark:bg-slate-900 dark:text-slate-100" /></div>
                </div>
              )}
              <div className="rounded-lg border border-slate-200 bg-slate-100 p-3 text-xs text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300">
                <strong>GSC property:</strong> {property || "Connect Google Search Console first."}
              </div>
              <div className="flex justify-end gap-2 pt-2"><Button variant="outline" onClick={() => setShowAdd(false)}>Cancel</Button><Button onClick={() => void handleAdd()} disabled={saving} className="bg-emerald-600 hover:bg-emerald-700 text-white">{saving ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />} {saving ? "Adding..." : "Add Keywords"}</Button></div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}




