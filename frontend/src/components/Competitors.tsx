import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Target, TrendingUp, Globe, Link2, Search, Sparkles, Loader2, AlertCircle, Trash2 } from "lucide-react";
import { useClaude } from "@/components/ClaudeProvider";
import { toast } from "sonner";
import { api } from "@/lib/api";

interface Competitor {
  id: string;
  domain: string;
  traffic: string;
  keywords: number;
  backlinks: number;
  da: number;
  gap: number;
  analysis: string;
}

export function Competitors() {
  const { isConfigured, isReady, status } = useClaude();
  const [competitors, setCompetitors] = useState<Competitor[]>([]);
  const [loading, setLoading] = useState(true);
  const [newDomain, setNewDomain] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchCompetitors();
  }, []);

  const fetchCompetitors = async () => {
    try {
      const data = await api.get<Competitor[]>("/api/competitors");
      setCompetitors(data);
    } catch (err) {
      console.error("Failed to fetch competitors:", err);
      toast.error("Could not load competitors");
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyze = async () => {
    if (!newDomain) {
      toast.error("Please enter a competitor domain");
      return;
    }

    if (!isConfigured) {
      toast.error("Claude API key not configured. Please add it in Settings.");
      setError("Claude API key is missing. Please configure it in Settings.");
      return;
    }

    if (!isReady) {
      const message =
        status === "billing_required"
          ? "Anthropic billing is required. Your API key is valid, but your credit balance is too low. Please add credits or upgrade your plan, then try again."
          : status === "invalid_api_key"
            ? "Anthropic API key is invalid. Please update it in Settings."
            : "Claude AI is currently unavailable. Please check Settings.";
      toast.error(message);
      setError(message);
      return;
    }

    setAnalyzing(true);
    setError(null);

    try {
      const data = await api.post<Competitor>(`/api/competitors?domain=${encodeURIComponent(newDomain)}`, {});
      setCompetitors([data, ...competitors]);
      setNewDomain("");
      toast.success("Competitor analyzed successfully");
    } catch (err: any) {
      console.error("Failed to analyze competitor:", err);
      let message = "Failed to analyze competitor. Please try again.";
      if (err?.data?.detail) {
        message = err.data.detail;
      } else if (err?.message) {
        message = err.message;
      }
      setError(message);
      toast.error(message);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.delete(`/api/competitors/${id}`);
      setCompetitors(competitors.filter((c) => c.id !== id));
      toast.success("Competitor deleted");
    } catch (err) {
      console.error("Failed to delete competitor:", err);
      toast.error("Could not delete competitor");
    }
  };

  if (loading) {
    return <div className="p-8 flex justify-center items-center">Loading competitors...</div>;
  }

  return (
    <div className="p-8 space-y-6">
      <header>
        <h2 className="font-serif text-3xl font-bold tracking-tight">Competitor Analysis</h2>
        <p className="text-slate-500 dark:text-slate-400 mt-1">
          Track competitors, discover content gaps, and analyze backlink profiles.
        </p>
      </header>

      {!isConfigured ? (
        <Card className="border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-900/10">
          <CardContent className="p-4 flex items-center gap-3">
            <AlertCircle className="size-5 text-amber-600" />
            <p className="text-sm text-amber-700 dark:text-amber-400">
              Claude API Key required. Please configure it in Settings to enable AI-powered competitor analysis.
            </p>
          </CardContent>
        </Card>
      ) : !isReady && (
        <Card className="border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-900/10">
          <CardContent className="p-4 flex items-center gap-3">
            <AlertCircle className="size-5 text-amber-600" />
            <p className="text-sm text-amber-700 dark:text-amber-400">
              {status === "billing_required"
                ? "Anthropic billing is required. Add credits or upgrade your plan, then try again."
                : "Claude AI is currently unavailable. Please check Settings."}
            </p>
          </CardContent>
        </Card>
      )}

      <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
        <CardHeader>
          <CardTitle className="font-serif">Add Competitor</CardTitle>
          <CardDescription>Monitor a new competitor domain</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-end gap-4">
            <div className="flex-1 space-y-2">
              <Label htmlFor="domain">Competitor Domain</Label>
              <Input
                id="domain"
                placeholder="competitor.com"
                value={newDomain}
                onChange={(e) => setNewDomain(e.target.value)}
                disabled={analyzing}
              />
            </div>
            <Button
              onClick={handleAnalyze}
              disabled={analyzing || !isReady}
              className="bg-emerald-600 hover:bg-emerald-700 text-white shadow-md shadow-emerald-600/20"
            >
              {analyzing ? <Loader2 className="size-4 animate-spin" /> : <Search className="size-4" />}
              {analyzing ? "Analyzing..." : "Analyze"}
            </Button>
          </div>
          {error && (
            <div className="mt-4 flex items-start gap-2 p-3 rounded-lg text-sm text-rose-700 bg-rose-50 dark:bg-rose-500/10 dark:text-rose-400">
              <AlertCircle className="size-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4">
        {competitors.length === 0 ? (
          <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
            <CardContent className="p-12 text-center">
              <Target className="size-12 text-slate-300 mx-auto mb-4" />
              <p className="text-slate-500 dark:text-slate-400">No competitors added yet. Enter a domain to analyze.</p>
            </CardContent>
          </Card>
        ) : (
          competitors.map((comp) => (
            <Card key={comp.id} className="border-slate-200 dark:border-slate-800 shadow-sm hover:shadow-md transition-shadow">
              <CardContent className="p-6">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-4">
                    <div className="size-12 rounded-xl bg-gradient-to-br from-rose-400 to-orange-500 flex items-center justify-center text-white font-bold text-lg">
                      {comp.domain.charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <h3 className="font-semibold text-lg">{comp.domain}</h3>
                      <p className="text-sm text-slate-500 dark:text-slate-400 flex items-center gap-1">
                        <Globe className="size-3" /> Domain Authority: {comp.da}
                      </p>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="text-slate-400 hover:text-rose-500"
                    onClick={() => handleDelete(comp.id)}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>

                <div className="grid grid-cols-4 gap-6 mt-4">
                  <Metric icon={TrendingUp} label="Traffic" value={comp.traffic} color="text-emerald-600" />
                  <Metric icon={Search} label="Keywords" value={comp.keywords.toLocaleString()} color="text-indigo-600" />
                  <Metric icon={Link2} label="Backlinks" value={comp.backlinks.toLocaleString()} color="text-amber-600" />
                  <Metric icon={Target} label="Gap" value={`+${comp.gap}`} color="text-rose-600" />
                </div>

                {comp.analysis && (
                  <div className="mt-6 pt-6 border-t border-slate-100 dark:border-slate-800">
                    <div className="flex items-center gap-2">
                      <Sparkles className="size-4 text-emerald-600" />
                      <span className="text-sm font-semibold text-emerald-700 dark:text-emerald-400">AI Competitive Strategy</span>
                    </div>
                    <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed mt-2">{comp.analysis}</p>
                  </div>
                )}
              </CardContent>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}

function Metric({ icon: Icon, label, value, color }: { icon: any; label: string; value: string; color: string }) {
  return (
    <div>
      <p className="text-xs text-slate-500 dark:text-slate-400 flex items-center gap-1"><Icon className="size-3" /> {label}</p>
      <p className={`font-serif text-xl font-bold ${color}`}>{value}</p>
    </div>
  );
}