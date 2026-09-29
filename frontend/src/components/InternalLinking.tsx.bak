import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Link2, Sparkles, Loader2, ArrowRight, AlertCircle, Trash2, CreditCard } from "lucide-react";
import { useClaude } from "@/components/ClaudeProvider";
import { toast } from "sonner";
import { api } from "@/lib/api";

interface Suggestion {
  source: string;
  target: string;
  anchor: string;
}

interface SuggestionRecord {
  id: string;
  urls: string[];
  suggestions: Suggestion[];
  analysis: string;
  created_at: string;
}


interface AnalyzeResponse {
  id: string;
  urls: string[];
  suggestions: Suggestion[];
  analysis: string;
  created_at: string;
}
export function InternalLinking() {
  const { isConfigured, isReady, status } = useClaude();
  const [urls, setUrls] = useState("");
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [analysis, setAnalysis] = useState("");
  const [history, setHistory] = useState<SuggestionRecord[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Budget dialog state
  const [showBudgetDialog, setShowBudgetDialog] = useState(false);
  const [budgetAmount, setBudgetAmount] = useState(10);
  const [isAddingBudget, setIsAddingBudget] = useState(false);

  // Load history on mount
  useEffect(() => {
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    try {
      const data = await api.get<SuggestionRecord[]>("/api/internal-linking/");
      setHistory(data);
    } catch (err) {
      console.error("Failed to fetch history:", err);
    } finally {
    }
  };

  const handleAnalyze = async () => {
    const urlList = urls.split("\n").filter((u) => u.trim() !== "");
    if (urlList.length < 2) {
      toast.error("Please enter at least 2 URLs");
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

    setLoading(true);
    setError(null);
    setSuggestions([]);
    setAnalysis("");

    try {
      const data = await api.post<AnalyzeResponse>("/api/internal-linking/analyze", {
        urls: urlList,
      });
      setSuggestions(data.suggestions);
      setAnalysis(data.analysis);
      toast.success("Internal linking suggestions generated!");
      // Refresh history
      fetchHistory();
    } catch (err: any) {
      console.error("Failed to generate suggestions:", err);
      let message = "Failed to generate suggestions. Please try again.";

      // Extract error message from response
      if (err?.data?.detail) {
        message = err.data.detail;
      } else if (err?.message) {
        message = err.message;
      }

      // Check for credit-related errors
      if (message.toLowerCase().includes("insufficient") || message.includes("402") || message.includes("credit")) {
        message = "⚠️ Insufficient AI credits. Please add budget to continue.";
        setShowBudgetDialog(true); // Open budget dialog
      }

      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.delete(`/api/internal-linking/${id}`);
      setHistory(history.filter((h) => h.id !== id));
      toast.success("Deleted successfully");
    } catch (err) {
      console.error("Failed to delete:", err);
      toast.error("Could not delete");
    }
  };

  const addBudget = async () => {
    setIsAddingBudget(true);
    try {
      await api.post(`/api/company/add-credits?amount=${budgetAmount}`, {});
      toast.success(`Added ${budgetAmount} credits.`);
      setShowBudgetDialog(false);
      // Clear error if it was credit-related
      setError(null);
    } catch (error) {
      console.error("Failed to add credits:", error);
      toast.error("Could not add credits.");
    } finally {
      setIsAddingBudget(false);
    }
  };

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-xl bg-emerald-50 dark:bg-emerald-500/10">
          <Link2 className="size-6 text-emerald-600 dark:text-emerald-400" />
        </div>
        <div>
          <h1 className="text-2xl font-serif font-bold">Internal Linking</h1>
          <p className="text-sm text-slate-500">AI-powered internal linking strategy and suggestions.</p>
        </div>
      </div>

      {!isConfigured ? (
        <Card className="border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-900/10">
          <CardContent className="p-4 flex items-center gap-3">
            <AlertCircle className="size-5 text-amber-600" />
            <p className="text-sm text-amber-700 dark:text-amber-400">
              Claude API Key required. Please configure it in Settings to enable AI-powered internal linking.
            </p>
          </CardContent>
        </Card>
      ) : !isReady && (
        <Card className="border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-900/10">
          <CardContent className="p-4 flex items-center gap-3">
            {status === "billing_required" ? <CreditCard className="size-5 text-amber-600" /> : <AlertCircle className="size-5 text-amber-600" />}
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
          <CardTitle className="font-serif">Analyze URLs</CardTitle>
          <CardDescription>Enter your site URLs (one per line) to generate internal linking opportunities.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="urls">URLs</Label>
              <Textarea
                id="urls"
                placeholder="https://example.com/blog/post-1&#10;https://example.com/services&#10;https://example.com/about"
                className="min-h-[200px] font-mono text-sm"
                value={urls}
                onChange={(e) => setUrls(e.target.value)}
                disabled={loading}
              />
            </div>
            <Button
              onClick={handleAnalyze}
              disabled={loading || !isReady || !urls.trim()}
              className="bg-emerald-600 hover:bg-emerald-700 text-white shadow-md shadow-emerald-600/20"
            >
              {loading ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
              {loading ? "Analyzing..." : "Generate Links"}
            </Button>
            {error && (
              <div className="flex items-start gap-2 p-3 rounded-lg text-sm bg-rose-50 dark:bg-rose-500/10 border border-rose-200 dark:border-rose-800">
                <AlertCircle className="size-4 shrink-0 mt-0.5 text-rose-600 dark:text-rose-400" />
                <span className="text-rose-700 dark:text-rose-400">{error}</span>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {loading && (
        <Card className="border-slate-200 dark:border-slate-800 shadow-sm animate-pulse">
          <CardContent className="p-6 space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-12 bg-slate-200 dark:bg-slate-800 rounded"></div>
            ))}
          </CardContent>
        </Card>
      )}

      {!loading && suggestions.length > 0 && (
        <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
          <CardHeader>
            <CardTitle className="font-serif">Suggested Internal Links</CardTitle>
            <CardDescription>Improve your site architecture and page authority.</CardDescription>
          </CardHeader>
          <CardContent>
            {analysis && (
              <div className="mb-4 p-4 bg-emerald-50 dark:bg-emerald-500/10 rounded-lg border border-emerald-200 dark:border-emerald-800">
                <p className="text-sm text-emerald-700 dark:text-emerald-400 font-medium">{analysis}</p>
              </div>
            )}
            <div className="space-y-4">
              {suggestions.map((s, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between p-4 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-900 transition-colors"
                >
                  <div className="space-y-1 flex-1">
                    <div className="text-sm font-medium text-slate-700 dark:text-slate-300">{s.source}</div>
                    <div className="flex items-center gap-2 text-xs text-slate-500">
                      <ArrowRight className="size-3" />
                      <span className="text-emerald-600 dark:text-emerald-400 font-medium">{s.target}</span>
                    </div>
                  </div>
                  <Badge variant="secondary" className="ml-4">
                    {s.anchor}
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {!loading && suggestions.length === 0 && !error && (
        <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
          <CardContent className="p-12 text-center">
            <Link2 className="size-12 text-slate-300 mx-auto mb-4" />
            <p className="text-slate-500 dark:text-slate-400">
              Enter URLs and click "Generate Links" to get AI-powered internal linking suggestions.
            </p>
          </CardContent>
        </Card>
      )}

      {history.length > 0 && (
        <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
          <CardHeader>
            <CardTitle className="font-serif">History</CardTitle>
            <CardDescription>Previous internal linking analyses.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {history.slice(0, 5).map((item) => (
                <div
                  key={item.id}
                  className="flex items-center justify-between p-3 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-900"
                >
                  <div>
                    <p className="text-sm font-medium">{item.urls.length} URLs analyzed</p>
                    <p className="text-xs text-slate-500">
                      {new Date(item.created_at).toLocaleDateString()} · {item.suggestions.length} suggestions
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="text-slate-400 hover:text-rose-500"
                    onClick={() => handleDelete(item.id)}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Budget Dialog */}
      <Dialog open={showBudgetDialog} onOpenChange={setShowBudgetDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="font-serif flex items-center gap-2">
              <CreditCard className="size-5 text-amber-600" />
              Insufficient AI Credits
            </DialogTitle>
            <DialogDescription>
              You need to add budget to use the Internal Linking feature. Each analysis consumes 1 credit.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
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
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowBudgetDialog(false)}>
              Cancel
            </Button>
            <Button
              onClick={addBudget}
              disabled={isAddingBudget}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              {isAddingBudget ? <Loader2 className="size-4 animate-spin" /> : "Add Credits"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}