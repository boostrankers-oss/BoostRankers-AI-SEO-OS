import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sparkles, Loader2, Calendar, Target, AlertCircle } from "lucide-react";
import { useClaude } from "@/components/ClaudeProvider";
import { cn } from "@/lib/utils";

interface ContentIdea {
  title: string;
  keyword: string;
  intent: string;
  difficulty: string;
  outline: string[];
}

export function ContentPlanner() {
  const { isConfigured, generateContent } = useClaude();
  const [topic, setTopic] = useState("AI SEO strategies");
  const [loading, setLoading] = useState(false);
  const [ideas, setIdeas] = useState<ContentIdea[]>([]);
  const [error, setError] = useState<string | null>(null);

  const generatePlan = async () => {
    setLoading(true);
    setIdeas([]);
    setError(null);

    const prompt = `Generate 3 content ideas for the topic: "${topic}".
    Return as a JSON array of objects with the following structure:
    [
      {
        "title": "Content Title",
        "keyword": "Target Keyword",
        "intent": "Informational",
        "difficulty": "Medium",
        "outline": ["Point 1", "Point 2", "Point 3", "Point 4", "Point 5"]
      }
    ]
    Do not include any markdown formatting or backticks, just the raw JSON array.`;

    try {
      const response = await generateContent(prompt);
      const cleanedResponse = response.replace(/```json/g, '').replace(/```/g, '').trim();
      const parsed = JSON.parse(cleanedResponse);
      setIdeas(parsed);
    } catch (err: any) {
      setError(err.message || "Failed to generate content plan.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-8 space-y-6">
      <header>
        <h2 className="font-serif text-3xl font-bold tracking-tight">Content Planner</h2>
        <p className="text-slate-500 dark:text-slate-400 mt-1">
          Generate AI-powered content plans, outlines, and strategies.
        </p>
      </header>

      {!isConfigured && (
        <Card className="border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-900/10">
          <CardContent className="p-4 flex items-center gap-3">
            <AlertCircle className="size-5 text-amber-600" />
            <p className="text-sm text-amber-700 dark:text-amber-400">
              Claude API Key required. Please configure it in Settings to enable AI content planning.
            </p>
          </CardContent>
        </Card>
      )}

      <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
        <CardHeader>
          <CardTitle className="font-serif flex items-center gap-2">
            <Sparkles className="size-5 text-emerald-600" />
            Generate Content Plan
          </CardTitle>
          <CardDescription>Enter a topic to generate a 30-day content roadmap</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="topic">Topic / Seed Keyword</Label>
            <Input id="topic" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="e.g. Technical SEO, Local Marketing..." />
          </div>
          <Button onClick={generatePlan} disabled={loading || !isConfigured} className="bg-emerald-600 hover:bg-emerald-700 text-white shadow-md shadow-emerald-600/20">
            {loading ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
            {loading ? "Generating..." : "Generate Plan"}
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
        <div className="grid gap-4">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="border-slate-200 dark:border-slate-800 shadow-sm animate-pulse">
              <CardContent className="p-6 h-32 bg-slate-100 dark:bg-slate-800/50 rounded-xl" />
            </Card>
          ))}
        </div>
      )}

      <div className="grid gap-4">
        {ideas.map((idea, idx) => (
          <Card key={idx} className="border-slate-200 dark:border-slate-800 shadow-sm hover:shadow-md transition-shadow">
            <CardHeader>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <CardTitle className="font-serif text-lg">{idea.title}</CardTitle>
                  <div className="flex items-center gap-3 mt-2 text-xs">
                    <span className="flex items-center gap-1 text-slate-500"><Target className="size-3" /> {idea.keyword}</span>
                    <span className="text-slate-400">·</span>
                    <span className="px-2 py-0.5 rounded-md bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">{idea.intent}</span>
                    <span className={cn("px-2 py-0.5 rounded-md", idea.difficulty === "Low" ? "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10" : "bg-amber-50 text-amber-600 dark:bg-amber-500/10")}>{idea.difficulty}</span>
                  </div>
                </div>
                <Button variant="outline" size="sm">Create Draft</Button>
              </div>
            </CardHeader>
            <CardContent>
              <p className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Suggested Outline:</p>
              <ul className="space-y-1.5">
                {idea.outline.map((point, i) => (
                  <li key={i} className="text-sm text-slate-600 dark:text-slate-400 flex items-center gap-2">
                    <span className="size-1.5 rounded-full bg-emerald-500" />
                    {point}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        ))}
      </div>

      {!loading && ideas.length === 0 && !error && (
        <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
          <CardContent className="p-12 text-center">
            <Calendar className="size-10 text-slate-300 dark:text-slate-700 mx-auto mb-3" />
            <p className="text-slate-500 dark:text-slate-400">No content plans yet. Generate one to get started.</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}