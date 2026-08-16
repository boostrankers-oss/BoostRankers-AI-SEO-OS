import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BarChart3,
  CheckCircle2,
  ExternalLink,
  FileSearch,
  Loader2,
  LogOut,
  RefreshCw,
  Search,
  Unplug,
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
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";


type Provider = "search_console" | "analytics";

type ConnectionStatus = {
  connected: boolean;
  account_email: string | null;
  selected_property: string | null;
  updated_at: string | null;
};

type GoogleStatusResponse = {
  search_console: ConnectionStatus;
  analytics: ConnectionStatus;
};

type Property = {
  id: string;
  name: string;
  permission_level?: string;
  property_type?: string;
};

type SearchConsolePoint = {
  date: string;
  clicks: number;
  impressions: number;
  ctr: number;
  position: number;
};

type AnalyticsPoint = {
  date: string;
  users: number;
  sessions: number;
  pageviews: number;
  conversions: number;
};

type GoogleMetricResponse<T> = {
  items: T[];
  totals: Record<string, number>;
};

const providerLabels: Record<Provider, string> = {
  search_console: "Google Search Console",
  analytics: "Google Analytics 4",
};

function dateValue(daysAgo: number): string {
  const date = new Date();
  date.setUTCDate(date.getUTCDate() - daysAgo);
  return date.toISOString().slice(0, 10);
}

export function GoogleIntegration() {
  const [status, setStatus] = useState<GoogleStatusResponse | null>(null);
  const [gscProperties, setGscProperties] = useState<Property[]>([]);
  const [gaProperties, setGaProperties] = useState<Property[]>([]);
  const [gscProperty, setGscProperty] = useState("");
  const [gaProperty, setGaProperty] = useState("");
  const [gscData, setGscData] = useState<SearchConsolePoint[]>([]);
  const [gaData, setGaData] = useState<AnalyticsPoint[]>([]);
  const [startDate, setStartDate] = useState(dateValue(28));
  const [endDate, setEndDate] = useState(dateValue(1));
  const [loading, setLoading] = useState(true);
  const [loadingData, setLoadingData] = useState<Provider | null>(null);
  const [connecting, setConnecting] = useState<Provider | null>(null);
  const [disconnecting, setDisconnecting] = useState<Provider | null>(null);
  const [message, setMessage] = useState<string>("");
  const [error, setError] = useState<string>("");

  const loadStatus = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const result = await api.get<GoogleStatusResponse>("/api/google/status");
      setStatus(result);

      if (result.search_console.connected) {
        const properties = await api.get<{ items: Property[] }>(
          "/api/google/properties/search-console",
        );
        setGscProperties(properties.items || []);

        const stored = result.search_console.selected_property;
        const first = stored || properties.items?.[0]?.id || "";
        setGscProperty(first);

        if (first) {
          await api.post("/api/google/select-property/search_console", {
            property: first,
          });
        }
      } else {
        setGscProperties([]);
        setGscProperty("");
        setGscData([]);
      }

      if (result.analytics.connected) {
        const properties = await api.get<{ items: Property[] }>(
          "/api/google/properties/analytics",
        );
        setGaProperties(properties.items || []);

        const stored = result.analytics.selected_property;
        const first = stored || properties.items?.[0]?.id || "";
        setGaProperty(first);

        if (first) {
          await api.post("/api/google/select-property/analytics", {
            property: first,
          });
        }
      } else {
        setGaProperties([]);
        setGaProperty("");
        setGaData([]);
      }
    } catch (err: any) {
      const detail = err?.data?.detail || "Unable to load Google integration status.";
      setError(detail);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const googleStatus = params.get("google");
    const provider = params.get("provider");
    const errorMessage = params.get("error");

    if (googleStatus === "connected") {
      setMessage(
        provider === "search_console"
          ? "Google Search Console connected successfully."
          : provider === "analytics"
            ? "Google Analytics connected successfully."
            : "Google integration connected successfully.",
      );
      void loadStatus();
    } else if (googleStatus === "error") {
      setError(errorMessage || "Google authorization failed.");
    } else {
      void loadStatus();
    }

    if (googleStatus || provider || errorMessage) {
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, [loadStatus]);

  const connect = useCallback(async (provider: Provider) => {
    setConnecting(provider);
    setError("");
    setMessage("");

    try {
      const result = await api.get<{ authorization_url: string }>(
        `/api/google/connect/${provider}`,
      );

      window.location.assign(result.authorization_url);
    } catch (err: any) {
      setError(
        err?.data?.detail ||
          `Unable to start ${providerLabels[provider]} authorization.`,
      );
      setConnecting(null);
    }
  }, []);

  const disconnect = useCallback(async (provider: Provider) => {
    setDisconnecting(provider);
    setError("");
    setMessage("");

    try {
      await api.delete(`/api/google/disconnect/${provider}`);
      setMessage(`${providerLabels[provider]} disconnected.`);
      await loadStatus();
    } catch (err: any) {
      setError(
        err?.data?.detail || `Unable to disconnect ${providerLabels[provider]}.`,
      );
    } finally {
      setDisconnecting(null);
    }
  }, [loadStatus]);

  const selectProperty = useCallback(
    async (provider: Provider, property: string) => {
      if (!property) return;

      try {
        await api.post(`/api/google/select-property/${provider}`, {
          property,
        });

        if (provider === "search_console") {
          setGscProperty(property);
          setGscData([]);
        } else {
          setGaProperty(property);
          setGaData([]);
        }

        setMessage(`${providerLabels[provider]} property selected.`);
      } catch (err: any) {
        setError(err?.data?.detail || "Unable to save the selected property.");
      }
    },
    [],
  );

  const loadSearchConsoleData = useCallback(async () => {
    if (!gscProperty) return;
    setLoadingData("search_console");
    setError("");

    try {
      const result = await api.get<GoogleMetricResponse<SearchConsolePoint>>(
        `/api/google/search-console/performance?site_url=${encodeURIComponent(gscProperty)}&start_date=${startDate}&end_date=${endDate}`,
      );
      setGscData(result.items || []);
    } catch (err: any) {
      setError(err?.data?.detail || "Unable to load Search Console performance data.");
    } finally {
      setLoadingData(null);
    }
  }, [endDate, gscProperty, startDate]);

  const loadAnalyticsData = useCallback(async () => {
    if (!gaProperty) return;
    setLoadingData("analytics");
    setError("");

    try {
      const result = await api.get<GoogleMetricResponse<AnalyticsPoint>>(
        `/api/google/analytics/performance?property_id=${encodeURIComponent(gaProperty)}&start_date=${startDate}&end_date=${endDate}`,
      );
      setGaData(result.items || []);
    } catch (err: any) {
      setError(err?.data?.detail || "Unable to load Google Analytics data.");
    } finally {
      setLoadingData(null);
    }
  }, [endDate, gaProperty, startDate]);

  const gscTotals = useMemo(
    () => ({
      clicks: gscData.reduce((sum, row) => sum + row.clicks, 0),
      impressions: gscData.reduce((sum, row) => sum + row.impressions, 0),
    }),
    [gscData],
  );

  const gaTotals = useMemo(
    () => ({
      users: gaData.reduce((sum, row) => sum + row.users, 0),
      sessions: gaData.reduce((sum, row) => sum + row.sessions, 0),
    }),
    [gaData],
  );

  const formatDate = (value: string | null) => {
    if (!value) return "Never";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
  };

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-[420px]">
        <div className="flex items-center gap-3 text-slate-500">
          <Loader2 className="size-5 animate-spin" />
          Loading Google integrations...
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-6">
      <header>
        <h2 className="font-serif text-3xl font-bold tracking-tight">Google Integration</h2>
        <p className="text-slate-500 dark:text-slate-400 mt-1">
          Connect Google services through OAuth and use live account data. No sample or seeded metrics are used.
        </p>
      </header>

      {message && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800 dark:border-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-300">
          {message}
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:border-rose-800 dark:bg-rose-500/10 dark:text-rose-300">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
          <CardHeader>
            <CardTitle className="font-serif flex items-center gap-2">
              <Search className="size-5 text-emerald-600" />
              Google Search Console
            </CardTitle>
            <CardDescription>
              Pull verified properties and Search Analytics directly from Google.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            {status?.search_console.connected ? (
              <>
                <div className="flex items-center justify-between gap-4 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 dark:border-emerald-800 dark:bg-emerald-500/10">
                  <div>
                    <div className="flex items-center gap-2 text-sm font-medium text-emerald-800 dark:text-emerald-300">
                      <CheckCircle2 className="size-4" /> Connected
                    </div>
                    <p className="text-xs text-slate-500 mt-1">
                      {status.search_console.account_email || "Google account"}
                    </p>
                    <p className="text-xs text-slate-400 mt-1">
                      Last updated: {formatDate(status.search_console.updated_at)}
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => void disconnect("search_console")}
                    disabled={disconnecting === "search_console"}
                  >
                    {disconnecting === "search_console" ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : (
                      <Unplug className="size-4" />
                    )}
                    Disconnect
                  </Button>
                </div>

                {gscProperty ? (
					  <div className="space-y-3">
						<label className="text-sm font-semibold">
						  Search Console property
						</label>

						<div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 px-4 py-3">
						  <div className="flex items-center gap-2 text-sm font-medium text-emerald-400">
							<CheckCircle2 className="size-4" />
							Selected property
						  </div>

						  <p className="mt-1 break-all text-sm text-slate-300">
							{gscProperty}
						  </p>
						</div>
					  </div>
					) : (
					  <div className="space-y-2">
						<label className="text-sm font-semibold">
						  Search Console property
						</label>

						<select
						  value={gscProperty}
						  onChange={(event) =>
							void selectProperty(
							  "search_console",
							  event.target.value
							)
						  }
						  className="w-full h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm dark:border-slate-700 dark:bg-slate-900"
						>
						  <option value="">Select a property</option>

						  {gscProperties.map((property) => (
							<option key={property.id} value={property.id}>
							  {property.name}
							</option>
						  ))}
						</select>

						{gscProperties.length === 0 && (
						  <p className="text-xs text-slate-500">
							No Search Console properties are available to this Google account.
						  </p>
						)}
					  </div>
					)}

                <Button
                  onClick={() => void loadSearchConsoleData()}
                  disabled={!gscProperty || loadingData === "search_console"}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white"
                >
                  {loadingData === "search_console" ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <RefreshCw className="size-4" />
                  )}
                  Refresh live data
                </Button>
              </>
            ) : (
              <div className="space-y-4">
                <p className="text-sm text-slate-600 dark:text-slate-300">
                  Connect a Google account with access to Search Console. The backend will handle OAuth and securely store refresh tokens.
                </p>
                <Button
                  onClick={() => void connect("search_console")}
                  disabled={connecting === "search_console"}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white"
                >
                  {connecting === "search_console" ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <ExternalLink className="size-4" />
                  )}
                  Connect Search Console
                </Button>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
          <CardHeader>
            <CardTitle className="font-serif flex items-center gap-2">
              <BarChart3 className="size-5 text-indigo-600" />
              Google Analytics 4
            </CardTitle>
            <CardDescription>
              Discover accessible GA4 properties and load live Analytics Data API reports.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            {status?.analytics.connected ? (
              <>
                <div className="flex items-center justify-between gap-4 rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-3 dark:border-indigo-800 dark:bg-indigo-500/10">
                  <div>
                    <div className="flex items-center gap-2 text-sm font-medium text-indigo-800 dark:text-indigo-300">
                      <CheckCircle2 className="size-4" /> Connected
                    </div>
                    <p className="text-xs text-slate-500 mt-1">
                      {status.analytics.account_email || "Google account"}
                    </p>
                    <p className="text-xs text-slate-400 mt-1">
                      Last updated: {formatDate(status.analytics.updated_at)}
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => void disconnect("analytics")}
                    disabled={disconnecting === "analytics"}
                  >
                    {disconnecting === "analytics" ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : (
                      <Unplug className="size-4" />
                    )}
                    Disconnect
                  </Button>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium">GA4 property</label>
                  <select
                    value={gaProperty}
                    onChange={(event) => void selectProperty("analytics", event.target.value)}
                    className="w-full h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm dark:border-slate-700 dark:bg-slate-900"
                  >
                    <option value="">Select a property</option>
                    {gaProperties.map((property) => (
                      <option key={property.id} value={property.id}>
                        {property.name}
                      </option>
                    ))}
                  </select>
                  {gaProperties.length === 0 && (
                    <p className="text-xs text-slate-500">No GA4 properties are available to this Google account.</p>
                  )}
                </div>

                <Button
                  onClick={() => void loadAnalyticsData()}
                  disabled={!gaProperty || loadingData === "analytics"}
                  className="bg-indigo-600 hover:bg-indigo-700 text-white"
                >
                  {loadingData === "analytics" ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <RefreshCw className="size-4" />
                  )}
                  Refresh live data
                </Button>
              </>
            ) : (
              <div className="space-y-4">
                <p className="text-sm text-slate-600 dark:text-slate-300">
                  Connect a Google account with access to one or more GA4 properties. Only read-only reporting scopes are requested.
                </p>
                <Button
                  onClick={() => void connect("analytics")}
                  disabled={connecting === "analytics"}
                  className="bg-indigo-600 hover:bg-indigo-700 text-white"
                >
                  {connecting === "analytics" ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <ExternalLink className="size-4" />
                  )}
                  Connect Google Analytics
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
        <CardHeader>
          <CardTitle className="font-serif flex items-center gap-2">
            <FileSearch className="size-5 text-slate-600" />
            Live reporting window
          </CardTitle>
          <CardDescription>
            Choose the period used for the Search Console and GA4 charts below.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
            <div className="space-y-2">
              <label className="text-sm font-medium">Start date</label>
              <input
                type="date"
                value={startDate}
                onChange={(event) => setStartDate(event.target.value)}
                className="w-full h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm dark:border-slate-700 dark:bg-slate-900"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">End date</label>
              <input
                type="date"
                value={endDate}
                onChange={(event) => setEndDate(event.target.value)}
                className="w-full h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm dark:border-slate-700 dark:bg-slate-900"
              />
            </div>
            <Button
              variant="outline"
              onClick={() => {
                setStartDate(dateValue(28));
                setEndDate(dateValue(1));
              }}
            >
              Reset to last 28 days
            </Button>
          </div>
        </CardContent>
      </Card>

      {status?.search_console.connected && gscProperty && (
        <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
          <CardHeader>
            <div className="flex items-center justify-between gap-4">
              <div>
                <CardTitle className="font-serif">Search Console Performance</CardTitle>
                <CardDescription>Live clicks and impressions by date.</CardDescription>
              </div>
              <div className="text-right text-xs text-slate-500">
                <div>{gscTotals.clicks.toLocaleString()} clicks</div>
                <div>{gscTotals.impressions.toLocaleString()} impressions</div>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {gscData.length === 0 ? (
              <div className="py-16 text-center text-sm text-slate-500">
                Load live data to display Search Console performance.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={320}>
                <LineChart data={gscData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" strokeOpacity={0.3} />
                  <XAxis dataKey="date" stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis yAxisId="left" stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis yAxisId="right" orientation="right" stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                  <Tooltip />
                  <Line yAxisId="left" type="monotone" dataKey="clicks" stroke="#10b981" strokeWidth={2} dot={false} />
                  <Line yAxisId="right" type="monotone" dataKey="impressions" stroke="#6366f1" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      )}

      {status?.analytics.connected && gaProperty && (
        <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
          <CardHeader>
            <div className="flex items-center justify-between gap-4">
              <div>
                <CardTitle className="font-serif">Google Analytics 4 Performance</CardTitle>
                <CardDescription>Live users and sessions by date.</CardDescription>
              </div>
              <div className="text-right text-xs text-slate-500">
                <div>{gaTotals.users.toLocaleString()} users</div>
                <div>{gaTotals.sessions.toLocaleString()} sessions</div>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {gaData.length === 0 ? (
              <div className="py-16 text-center text-sm text-slate-500">
                Load live data to display Google Analytics performance.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={320}>
                <LineChart data={gaData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" strokeOpacity={0.3} />
                  <XAxis dataKey="date" stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                  <Tooltip />
                  <Line type="monotone" dataKey="users" stroke="#6366f1" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="sessions" stroke="#f59e0b" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      )}

      <div className="flex items-start gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600 dark:border-slate-800 dark:bg-slate-900/40 dark:text-slate-300">
        <LogOut className="size-4 mt-0.5 shrink-0" />
        Google tokens stay on the backend. The browser receives only connection status and report data.
      </div>
    </div>
  );
}
