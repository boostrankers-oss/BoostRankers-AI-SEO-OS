import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Network, Sparkles, Search, Loader2, AlertCircle } from "lucide-react";
import { useClaude } from "@/components/ClaudeProvider";

interface Cluster {
  id: string;
  name: string;
  keywords: string[];
  intent: string;
}

export function KeywordClusters() {
  const { isConfigured, isReady, status, generateContent } = useClaude();
  const [seedKeyword, setSeedKeyword] = useState("");
  const [loading, setLoading] = useState(false);
  const [clusters, setClusters] = useState<Cluster[]>([]);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async () => {
    if (!seedKeyword) return;

    if (!isConfigured) {
      setError("Claude API key required. Please configure it in Settings.");
      return;
    }

    if (!isReady) {
      setError(
        status === "billing_required"
          ? "Anthropic billing is required. Add credits or upgrade your plan, then try again."
          : "Claude AI is currently unavailable. Please check Settings."
      );
      return;
    }

    setLoading(true);
    setClusters([]);
    setError(null);

    const prompt = `Generate 3 distinct SEO keyword clusters for the seed keyword: "${seedKeyword}".
    Return as a JSON array of objects with the following structure:
    [
      { "name": "Cluster Name", "keywords": ["kw1", "kw2", "kw3", "kw4"], "intent": "Informational" }
    ]
    Do not include any markdown formatting or backticks, just the raw JSON array.`;

    try {
      const response = await generateContent(prompt);
      const cleanedResponse = response.replace(/```json/g, '').replace(/```/g, '').trim();
      const parsed = JSON.parse(cleanedResponse);
      setClusters(parsed);
    } catch (error: any) {
      console.error("Failed to generate clusters:", error);
      setError(
        error?.message ||
          "Failed to generate keyword clusters."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-xl bg-emerald-50 dark:bg-emerald-500/10">
          <Network className="size-6 text-emerald-600 dark:text-emerald-400" />
        </div>
        <div>
          <h1 className="text-2xl font-serif font-bold">Keyword Clusters</h1>
          <p className="text-sm text-slate-500">Group related keywords to build topical authority.</p>
        </div>
      </div>

      {!isConfigured ? (
        <Card className="border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-900/10">
          <CardContent className="p-4 flex items-center gap-3">
            <AlertCircle className="size-5 text-amber-600" />
            <p className="text-sm text-amber-700 dark:text-amber-400">
              Claude API Key required. Please configure it in Settings to enable AI keyword clustering.
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

      {error && (
        <Card className="border-rose-200 dark:border-rose-900/50 bg-rose-50 dark:bg-rose-900/10">
          <CardContent className="p-4 flex items-center gap-3">
            <AlertCircle className="size-5 text-rose-600" />
            <p className="text-sm text-rose-700 dark:text-rose-400">{error}</p>
          </CardContent>
        </Card>
      )}
      <Card>
        <CardHeader>
          <CardTitle>Generate Clusters</CardTitle>
          <CardDescription>Enter a seed keyword to generate AI-powered keyword clusters.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-4">
            <Input 
              placeholder="e.g. digital marketing" 
              value={seedKeyword}
              onChange={(e) => setSeedKeyword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleGenerate()}
            />
            <Button onClick={handleGenerate} disabled={loading || !isReady || !seedKeyword}>
              {loading ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
              Generate
            </Button>
          </div>
        </CardContent>
      </Card>

      {loading && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="animate-pulse">
              <CardHeader>
                <div className="h-4 bg-slate-200 dark:bg-slate-800 rounded w-1/2"></div>
              </CardHeader>
              <CardContent className="space-y-2">
                <div className="h-3 bg-slate-200 dark:bg-slate-800 rounded"></div>
                <div className="h-3 bg-slate-200 dark:bg-slate-800 rounded w-5/6"></div>
                <div className="h-3 bg-slate-200 dark:bg-slate-800 rounded w-4/6"></div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {!loading && clusters.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {clusters.map((cluster, idx) => (
            <Card key={idx} className="hover:shadow-md transition-shadow">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg">{cluster.name}</CardTitle>
                  <Badge variant="secondary">{cluster.intent}</Badge>
                </div>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {cluster.keywords.map((kw, i) => (
                    <li key={i} className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400">
                      <Search className="size-3 text-slate-400" />
                      {kw}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}