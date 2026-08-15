import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Sparkles, Loader2, Search, AlertCircle } from "lucide-react";
import { useClaude } from "@/components/ClaudeProvider";
import { cn } from "@/lib/utils";

interface Keyword {
  keyword: string;
  volume: number;
  difficulty: number;
  intent: string;
}

export function KeywordResearch() {
  const { isConfigured, isReady, status, generateContent } = useClaude();
  const [seed, setSeed] = useState("AI SEO");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<Keyword[]>([]);
  const [error, setError] = useState<string | null>(null);

  const generate = async () => {
    if (!isConfigured) {
      setError("Claude API key required. Please configure it in Settings.");
      return;
    }

    if (!isReady) {
      setError(
        status === "billing_required"
          ? "Anthropic billing is required. Your API key is valid, but your credit balance is too low. Please add credits or upgrade your plan, then try again."
          : status === "invalid_api_key"
            ? "Anthropic API key is invalid. Please update it in Settings."
            : "Claude AI is currently unavailable. Please check Settings."
      );
      return;
    }

    setLoading(true);
    setError(null);
    setResults([]);

    const prompt = `Generate 6 highly relevant SEO keywords for the seed: "${seed}".
    Return as a JSON array of objects with the following structure:
    [
      { "keyword": "example keyword", "volume": 5000, "difficulty": 45, "intent": "Commercial" }
    ]
    Do not include any markdown formatting or backticks, just the raw JSON array.`;

    try {
      const response = await generateContent(prompt);
      const cleanedResponse = response.replace(/```json/g, '').replace(/```/g, '').trim();
      const parsed = JSON.parse(cleanedResponse);
      setResults(parsed);
    } catch (err: any) {
      setError(err.message || "Failed to generate keywords.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-8 space-y-6">
      <header>
        <h2 className="font-serif text-3xl font-bold tracking-tight">Keyword Research</h2>
        <p className="text-slate-500 dark:text-slate-400 mt-1">
          Discover high-impact keywords powered by Claude AI.
        </p>
      </header>

      {!isConfigured ? (
        <Card className="border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-900/10">
          <CardContent className="p-4 flex items-center gap-3">
            <AlertCircle className="size-5 text-amber-600" />
            <p className="text-sm text-amber-700 dark:text-amber-400">
              Claude API Key required. Please configure it in Settings to enable AI keyword research.
            </p>
          </CardContent>
        </Card>
      ) : !isReady && (
        <Card className="border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-900/10">
          <CardContent className="p-4 flex items-center gap-3">
            <AlertCircle className="size-5 text-amber-600" />
            <p className="text-sm text-amber-700 dark:text-amber-400">
              {status === "billing_required"
                ? "Anthropic billing is required. Your API key is valid, but your credit balance is too low. Please add credits or upgrade your plan, then try again."
                : "Claude AI is currently unavailable. Please check Settings."}
            </p>
          </CardContent>
        </Card>
      )}

      <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
        <CardHeader>
          <CardTitle className="font-serif flex items-center gap-2">
            <Sparkles className="size-5 text-emerald-600" />
            AI Keyword Generator
          </CardTitle>
          <CardDescription>Generate keyword clusters with semantic intent</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="seed">Seed Keyword</Label>
            <Input id="seed" value={seed} onChange={(e) => setSeed(e.target.value)} placeholder="e.g. Technical SEO, Local Marketing..." />
          </div>
          <Button onClick={generate} disabled={loading || !isReady} className="bg-emerald-600 hover:bg-emerald-700 text-white shadow-md shadow-emerald-600/20">
            {loading ? <Loader2 className="size-4 animate-spin" /> : <Search className="size-4" />}
            {loading ? "Researching..." : "Generate Keywords"}
          </Button>
        </CardContent>
      </Card>

      {error && (
        <Card className="border-rose-200 dark:border-rose-900/50 bg-rose-50 dark:bg-rose-900/10">
          <CardContent className="p-4 flex items-center gap-3">
            <AlertCircle className="size-5 text-rose-600" />
            <p className="text-sm text-rose-700 dark:text-rose-400">{error}</p>
          </CardContent>
        </Card>
      )}

      {loading && (
        <div className="grid gap-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <Card key={i} className="border-slate-200 dark:border-slate-800 shadow-sm animate-pulse">
              <CardContent className="p-4 h-16 bg-slate-100 dark:bg-slate-800/50 rounded-xl" />
            </Card>
          ))}
        </div>
      )}

      <div className="grid gap-3">
        {results.map((kw) => (
          <Card key={kw.keyword} className="border-slate-200 dark:border-slate-800 shadow-sm hover:shadow-md transition-shadow">
            <CardContent className="p-4 flex items-center justify-between flex-wrap gap-4">
              <div>
                <p className="font-medium">{kw.keyword}</p>
                <div className="flex items-center gap-2 mt-1">
                  <Badge variant="outline" className="border-slate-200 dark:border-slate-700">{kw.intent}</Badge>
                </div>
              </div>
              <div className="flex items-center gap-6">
                <div>
                  <p className="text-xs text-slate-500">Volume</p>
                  <p className="font-serif text-lg font-bold">{kw.volume.toLocaleString()}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Difficulty</p>
                  <p className={cn("font-serif text-lg font-bold", kw.difficulty > 70 ? "text-rose-500" : kw.difficulty > 40 ? "text-amber-500" : "text-emerald-500")}>
                    {kw.difficulty}
                  </p>
                </div>
                <Button variant="outline" size="sm">Track</Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}