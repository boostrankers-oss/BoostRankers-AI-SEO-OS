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
  if (position == null) return "â€”";
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

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [keywordData, overviewData, statusData, clientData] = await Promise.all([
        api.get<RankKeyword[]>("/api/rank-tracking/keywords"),
        api.get<Overview>("/api/rank-tracking/overview"),
        api.get<{ google_search_console_connected: boolean; selected_property: string | null }>("/api/rank-tracking/status"),
        api.get<ClientOption[]>("/api/clients/"),
      ]);
      setKeywords(keywordData || []);
      setOverview(overviewData);
      setGscConnected(Boolean(statusData.google_search_console_connected));
      setProperty(statusData.selected_property || null);
      setClients(clientData || []);
    } catch (error: any) {
      console.error("Rank tracker load failed", error);
      toast.error(error?.data?.detail || "Unable to load Rank Tracker.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return keywords.filter((item) => {
      const matchesSearch = !q || item.keyword.toLowerCase().includes(q) || (item.target_url || "").toLowerCase().includes(q);
      const matchesClient = clientFilter === "all" || item.client_id === clientFilter;
      return matchesSearch && matchesClient;
    });
  }, [keywords, search, clientFilter]);

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
    if (!form.keyword.trim()) {
      toast.error("Enter a keyword first.");
      return;
    }
    setSaving(true);
    try {
      const created = await api.post<RankKeyword>("/api/rank-tracking/keywords", {
        keyword: form.keyword,
        client_id: form.client_id === "none" ? null : form.client_id,
        target_url: form.target_url.trim() || null,
        search_engine: "google",
        country: form.country,
        location: form.location.trim() || null,
        language: form.language,
        device: form.device,
        frequency: form.frequency,
      });
      setKeywords((current) => [created, ...current]);
      setForm(emptyForm);
      setShowAdd(false);
      toast.success("Keyword added to Rank Tracker. Checking Google Search Console nowâ€¦");

      // A newly tracked keyword has no snapshot until it is checked.
      // Run the first measurement immediately so the table does not remain
      // empty until the next manual refresh.
      if (gscConnected && property) {
        try {
          const firstCheck = await api.post<{
            updated: number;
            items: RankKeyword[];
            errors?: Array<{ keyword: string; error: string }>;
          }>("/api/rank-tracking/refresh", { keyword_ids: [created.id] });

          if (firstCheck.items?.length) {
            const checked = firstCheck.items[0];
            setKeywords((current) =>
              current.map((item) => item.id === checked.id ? checked : item),
            );
            if (checked.measurement_message) {
              toast.info(checked.measurement_message);
            }
            await loadHistory(created.id);
          }

          if (firstCheck.errors?.length) {
            toast.warning(firstCheck.errors[0].error);
          } else if (!firstCheck.items?.length) {
            toast.info("Google Search Console returned no data for this keyword yet. Rankings can appear after GSC records the query.");
          }
        } catch (checkError: any) {
          toast.warning(checkError?.data?.detail || "Keyword was saved, but its first ranking check could not be completed.");
        }
      } else {
        toast.info("Keyword saved. Connect Google Search Console and select a property to measure its position.");
      }

      await load();
    } catch (error: any) {
      toast.error(error?.data?.detail || "Unable to add keyword.");
    } finally {
      setSaving(false);
    }
  };

  const handleRefresh = async (ids: string[] = []) => {
    if (!gscConnected || !property) {
      toast.error("Connect Google Search Console and select a property first.");
      return;
    }
    setRefreshing(true);
    try {
      const result = await api.post<{ updated: number; items: RankKeyword[]; errors?: Array<{ keyword: string; error: string }> }>(
        "/api/rank-tracking/refresh",
        { keyword_ids: ids },
      );
      if (result.items?.length) {
        setKeywords((current) => {
          const map = new Map(result.items.map((item) => [item.id, item]));
          return current.map((item) => map.get(item.id) || item);
        });
        const first = result.items[0];
        if (first?.measurement_message) setMeasurementMessage(first.measurement_message);
        if (ids.length === 1) await loadHistory(ids[0]);
      }
      if (result.errors?.length) {
        toast.warning(`${result.updated} updated; ${result.errors.length} could not be checked.`);
      } else {
        toast.success(`${result.updated} keyword${result.updated === 1 ? "" : "s"} updated.`);
      }
      const nextOverview = await api.get<Overview>("/api/rank-tracking/overview");
      setOverview(nextOverview);
    } catch (error: any) {
      toast.error(error?.data?.detail || "Ranking refresh failed.");
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

  if (loading) {
    return <div className="p-8 flex items-center gap-2 text-slate-500"><Loader2 className="size-4 animate-spin" /> Loading Rank Tracker...</div>;
  }

  return (
    <div className="p-6 md:p-8 space-y-6 max-w-[1600px] mx-auto">
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-emerald-600 text-sm font-medium mb-1"><Target className="size-4" /> Organic Visibility</div>
          <h1 className="font-serif text-3xl font-bold tracking-tight">Rank Tracker</h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1">Track real Google Search Console average positions for your target keywords.</p>
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
            {refreshing ? "Checking..." : "Check Rankings"}
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
          <div className="flex items-center gap-2 text-xs text-slate-500"><CheckCircle2 className="size-4 text-emerald-600" /> Measuring from <span className="font-medium text-slate-700 dark:text-slate-300">{property}</span> Â· GSC average position</div>
          {measurementMessage && (
            <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-400">
              {measurementMessage}
            </div>
          )}
        </div>
      )}

      <div className="grid grid-cols-2 xl:grid-cols-7 gap-3">
        {[
          ["Tracked", overview?.tracked_keywords ?? 0],
          ["Top 3", overview?.top_3 ?? 0],
          ["Top 10", overview?.top_10 ?? 0],
          ["Top 20", overview?.top_20 ?? 0],
          ["Improved", overview?.improved ?? 0],
          ["Declined", overview?.declined ?? 0],
          ["Avg. Position", overview?.average_position ?? "â€”"],
        ].map(([label, value]) => (
          <Card key={String(label)} className="shadow-sm">
            <CardContent className="p-4">
              <p className="text-xs text-slate-500">{label}</p>
              <p className="text-2xl font-semibold mt-1">{typeof value === "number" && label === "Avg. Position" ? value.toFixed(1) : value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="flex flex-col md:flex-row gap-3">
        <div className="relative flex-1"><Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-slate-400" /><Input className="pl-9" placeholder="Search keywords or URLs..." value={search} onChange={(e) => setSearch(e.target.value)} /></div>
        <Select value={clientFilter} onValueChange={(value) => setClientFilter(value || "all")}>
          <SelectTrigger className="w-full md:w-56"><SelectValue placeholder="All clients" /></SelectTrigger>
          <SelectContent><SelectItem value="all">All clients</SelectItem>{clients.map((client) => <SelectItem key={client.id} value={client.id}>{client.business_name || client.name || client.id}</SelectItem>)}</SelectContent>
        </Select>
      </div>

      <div className="grid xl:grid-cols-[1fr_420px] gap-6">
        <Card className="shadow-sm overflow-hidden">
          <CardHeader><CardTitle>Tracked Keywords</CardTitle><CardDescription>Current 90-day GSC average position compared with the preceding 90-day period.</CardDescription></CardHeader>
          <CardContent className="p-0">
            {filtered.length === 0 ? (
              <div className="p-10 text-center text-slate-500">No tracked keywords match your filters.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="border-y bg-slate-50/70 dark:bg-slate-900/50 dark:border-slate-800">
                    <tr className="text-left text-xs text-slate-500">
                      <th className="px-5 py-3">Keyword</th><th className="px-4 py-3">Client</th><th className="px-4 py-3">Current</th><th className="px-4 py-3">Previous</th><th className="px-4 py-3">Change</th><th className="px-4 py-3">Checked</th><th className="px-3 py-3" />
                    </tr>
                  </thead>
                  <tbody className="divide-y dark:divide-slate-800">
                    {filtered.map((item) => (
                      <tr key={item.id} className="hover:bg-slate-50 dark:hover:bg-slate-900/50 cursor-pointer" onClick={() => void loadHistory(item.id)}>
                        <td className="px-5 py-4"><div className="font-medium">{item.keyword}</div><div className="text-xs text-slate-500 truncate max-w-[320px]">{item.target_url || "No target URL specified"}</div></td>
                        <td className="px-4 py-4 text-slate-500">{item.client_name || "â€”"}</td>
                        <td className="px-4 py-4 font-semibold">{positionLabel(item.current_position)}</td>
                        <td className="px-4 py-4 text-slate-500">{positionLabel(item.previous_position)}</td>
                        <td className={`px-4 py-4 font-medium ${movementClass(item.change)}`}>
                          {item.change == null ? "â€”" : <span className="inline-flex flex-col gap-0.5"><span className="inline-flex items-center gap-1">{item.change > 0 ? <ArrowUp className="size-3.5" /> : item.change < 0 ? <ArrowDown className="size-3.5" /> : null}{Math.abs(item.change).toFixed(1)}</span><span className="text-[10px] font-normal">{movementLabel(item.change)}</span></span>}
                        </td>
                        <td className="px-4 py-4 text-xs text-slate-500">{item.last_checked_at ? new Date(item.last_checked_at).toLocaleDateString() : "Never"}</td>
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
        <div className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4" onMouseDown={(e) => { if (e.target === e.currentTarget) setShowAdd(false); }}>
          <Card className="w-full max-w-2xl shadow-2xl">
            <CardHeader><div className="flex items-center justify-between"><div><CardTitle>Add Tracked Keyword</CardTitle><CardDescription>Save the keyword first, then run a real GSC measurement.</CardDescription></div><Button variant="ghost" size="icon" onClick={() => setShowAdd(false)}><X className="size-4" /></Button></div></CardHeader>
            <CardContent className="grid md:grid-cols-2 gap-4">
              <div className="md:col-span-2 space-y-2"><Label>Keyword *</Label><Input autoFocus value={form.keyword} onChange={(e) => setForm({ ...form, keyword: e.target.value })} placeholder="commercial cleaning perth" /></div>
              <div className="space-y-2"><Label>Client</Label><Select value={form.client_id} onValueChange={(value) => setForm({ ...form, client_id: value || "none" })}><SelectTrigger><SelectValue placeholder="No client" /></SelectTrigger><SelectContent><SelectItem value="none">No client</SelectItem>{clients.map((client) => <SelectItem key={client.id} value={client.id}>{client.business_name || client.name || client.id}</SelectItem>)}</SelectContent></Select></div>
              <div className="space-y-2"><Label>Target URL</Label><Input value={form.target_url} onChange={(e) => setForm({ ...form, target_url: e.target.value })} placeholder="https://example.com/service/" /></div>
              <div className="space-y-2"><Label>Country</Label><Input value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })} placeholder="global / au / us" /></div>
              <div className="space-y-2"><Label>Location</Label><Input value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} placeholder="Perth, WA" /></div>
              <div className="space-y-2"><Label>Device</Label><Select value={form.device} onValueChange={(value) => setForm({ ...form, device: value || "all" })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="all">All</SelectItem><SelectItem value="desktop">Desktop</SelectItem><SelectItem value="mobile">Mobile</SelectItem></SelectContent></Select></div>
              <div className="space-y-2"><Label>Tracking frequency</Label><Select value={form.frequency} onValueChange={(value) => setForm({ ...form, frequency: value || "daily" })}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="daily">Daily</SelectItem><SelectItem value="weekly">Weekly</SelectItem><SelectItem value="manual">Manual</SelectItem></SelectContent></Select></div>
              <div className="md:col-span-2 flex justify-end gap-2 pt-2"><Button variant="outline" onClick={() => setShowAdd(false)}>Cancel</Button><Button onClick={() => void handleAdd()} disabled={saving} className="bg-emerald-600 hover:bg-emerald-700 text-white">{saving ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />} {saving ? "Saving..." : "Add Keyword"}</Button></div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}




