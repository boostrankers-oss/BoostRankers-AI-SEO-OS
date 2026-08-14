import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PenLine, Sparkles, Loader2, CheckCircle2, AlertCircle } from "lucide-react";
import { useClaude } from "@/components/ClaudeProvider";
import { toast } from "sonner";

export function BlogOptimizer() {
  const { isConfigured, generateContent } = useClaude();
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [optimization, setOptimization] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleOptimize = async () => {
    if (!title || !content) {
      toast.error("Please enter both a title and content.");
      return;
    }

    if (!isConfigured) {
      toast.error("Claude API key not configured. Please add it in Settings.");
      setError("Claude API key is missing. Please configure it in Settings to use this feature.");
      return;
    }

    setLoading(true);
    setError(null);
    setOptimization(null);

    const prompt = `You are an expert SEO blog optimizer. Analyze the following blog post and provide actionable recommendations to improve its SEO ranking.
    Title: "${title}"
    Content: "${content}"
    
    Provide recommendations on:
    1. Title optimization
    2. Meta description suggestion
    3. Content structure (H2, H3 tags)
    4. Keyword density and LSI keywords
    5. Readability improvements
    
    Format the output cleanly with bullet points.`;

    try {
      const response = await generateContent(prompt);
      setOptimization(response);
      toast.success("Optimization completed!");
    } catch (err: any) {
      console.error("Optimization failed:", err);
      let message = "Failed to generate optimization recommendations. Please try again.";
      if (err.message?.includes("API key")) {
        message = "Invalid or missing Claude API key. Please check your Settings.";
      } else if (err.message?.includes("credit")) {
        message = "Insufficient AI credits. Please add budget in Settings.";
      } else if (err.message) {
        message = err.message;
      }
      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center gap-3">
        <div className="p-2 rounded-xl bg-emerald-50 dark:bg-emerald-500/10">
          <PenLine className="size-6 text-emerald-600 dark:text-emerald-400" />
        </div>
        <div>
          <h1 className="text-2xl font-serif font-bold">Blog Optimizer</h1>
          <p className="text-sm text-slate-500">AI-powered recommendations to improve your blog posts.</p>
        </div>
      </div>

      {!isConfigured && (
        <Card className="border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-900/10">
          <CardContent className="p-4 flex items-center gap-3">
            <AlertCircle className="size-5 text-amber-600" />
            <p className="text-sm text-amber-700 dark:text-amber-400">
              Claude API key required. Please configure it in Settings to enable AI-powered blog optimization.
            </p>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Blog Content</CardTitle>
            <CardDescription>Input your blog post details to analyze.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Input 
              placeholder="Blog Title" 
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
            <Textarea 
              placeholder="Paste your blog content here..." 
              className="min-h-[300px]"
              value={content}
              onChange={(e) => setContent(e.target.value)}
            />
            <Button 
              onClick={handleOptimize} 
              disabled={loading || !isConfigured || !title || !content} 
              className="w-full bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              {loading ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
              {loading ? "Optimizing..." : "Optimize Blog Post"}
            </Button>
            {error && (
              <div className="flex items-start gap-2 p-3 rounded-lg text-sm text-rose-700 bg-rose-50 dark:bg-rose-500/10 dark:text-rose-400">
                <AlertCircle className="size-4 shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>AI Recommendations</CardTitle>
            <CardDescription>Actionable insights to rank higher.</CardDescription>
          </CardHeader>
          <CardContent>
            {loading && (
              <div className="space-y-3">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="h-4 bg-slate-200 dark:bg-slate-800 rounded animate-pulse"></div>
                ))}
              </div>
            )}
            {!loading && !optimization && !error && (
              <div className="flex flex-col items-center justify-center h-[300px] text-center text-slate-500">
                <CheckCircle2 className="size-12 mb-4 opacity-50" />
                <p>Your optimization recommendations will appear here.</p>
              </div>
            )}
            {!loading && optimization && (
              <div className="prose prose-sm dark:prose-invert max-w-none">
                <pre className="whitespace-pre-wrap font-sans bg-transparent p-0">{optimization}</pre>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}