import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Award, Sparkles, Loader2, CheckCircle2, AlertCircle } from "lucide-react";
import { useClaude } from "@/components/ClaudeProvider";

export function EEAT() {
  const { generateContent } = useClaude();
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState<string | null>(null);

  const handleAnalyze = async () => {
    if (!url) return;
    setLoading(true);
    setAnalysis(null);

    const prompt = `You are an expert Google E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness) analyzer.
    Analyze the concept of the website at: ${url}
    
    Provide a detailed report on:
    1. Experience: How well does the content demonstrate first-hand experience?
    2. Expertise: Is the author/site clearly an expert in the niche?
    3. Authoritativeness: Does the site have authority signals (backlinks, mentions, credentials)?
    4. Trustworthiness: Are there trust signals (HTTPS, contact info, privacy policy, transparent author bios)?
    
    Format the output cleanly with bullet points and actionable recommendations.`;

    try {
      const response = await generateContent(prompt);
      setAnalysis(response);
    } catch (error) {
      console.error("EEAT analysis failed:", error);
      setAnalysis("Failed to generate EEAT analysis. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-xl bg-emerald-50 dark:bg-emerald-500/10">
          <Award className="size-6 text-emerald-600 dark:text-emerald-400" />
        </div>
        <div>
          <h1 className="text-2xl font-serif font-bold">E-E-A-T Optimization</h1>
          <p className="text-sm text-slate-500">Enhance Experience, Expertise, Authoritativeness, and Trust.</p>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>E-E-A-T Analysis</CardTitle>
          <CardDescription>Enter your website URL to analyze its E-E-A-T signals.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-4">
            <Input 
              placeholder="https://example.com" 
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAnalyze()}
            />
            <Button onClick={handleAnalyze} disabled={loading || !url}>
              {loading ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
              Analyze
            </Button>
          </div>
        </CardContent>
      </Card>

      {loading && (
        <Card>
          <CardContent className="p-6 space-y-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-4 bg-slate-200 dark:bg-slate-800 rounded animate-pulse"></div>
            ))}
          </CardContent>
        </Card>
      )}

      {!loading && analysis && (
        <Card>
          <CardHeader>
            <CardTitle>Analysis Report</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <pre className="whitespace-pre-wrap font-sans bg-transparent p-0">{analysis}</pre>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}