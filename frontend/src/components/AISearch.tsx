import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { CheckCircle2, AlertTriangle, Zap, MessageSquare } from "lucide-react";

const metrics = [
  { label: "LLM Visibility", value: "82%", status: "good", detail: "High citation rate in AI responses" },
  { label: "AI Snippet Presence", value: "14", status: "good", detail: "Featured in 14 AI overviews" },
  { label: "Entity Recognition", value: "Weak", status: "bad", detail: "Brand entity not strongly established" },
  { label: "Semantic Coverage", value: "67%", status: "warn", detail: "Moderate topical authority signals" },
];

export function AISearch() {
  return (
    <div className="p-8 space-y-6">
      <header>
        <h2 className="font-serif text-3xl font-bold tracking-tight">AI Search Optimization</h2>
        <p className="text-slate-500 dark:text-slate-400 mt-1">
          Optimize for LLM crawlers, AI snippets, and generative search engines.
        </p>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {metrics.map((m) => (
          <Card key={m.label} className="border-slate-200 dark:border-slate-800 shadow-sm">
            <CardContent className="p-5">
              <div className="flex items-center justify-between mb-3">
                <p className="text-sm text-slate-500 dark:text-slate-400">{m.label}</p>
                {m.status === "good" && <CheckCircle2 className="size-5 text-emerald-500" />}
                {m.status === "warn" && <AlertTriangle className="size-5 text-amber-500" />}
                {m.status === "bad" && <AlertTriangle className="size-5 text-rose-500" />}
              </div>
              <p className={`font-serif text-2xl font-bold ${m.status === "good" ? "text-emerald-600" : m.status === "warn" ? "text-amber-600" : "text-rose-600"}`}>{m.value}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-2">{m.detail}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
          <CardHeader>
            <CardTitle className="font-serif flex items-center gap-2"><Zap className="size-5 text-emerald-600" /> AI Crawler Access</CardTitle>
            <CardDescription>Ensure your site is accessible to AI bots</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {["GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended"].map((bot) => (
              <div key={bot} className="flex items-center justify-between p-3 rounded-lg border border-slate-200 dark:border-slate-800">
                <span className="text-sm font-medium">{bot}</span>
                <span className="flex items-center gap-2 text-xs text-emerald-600"><CheckCircle2 className="size-4" /> Allowed</span>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
          <CardHeader>
            <CardTitle className="font-serif flex items-center gap-2"><MessageSquare className="size-5 text-indigo-600" /> AI Query Simulator</CardTitle>
            <CardDescription>Test how LLMs perceive your brand</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="bg-slate-50 dark:bg-slate-800/50 rounded-xl p-4 border border-slate-200 dark:border-slate-800">
              <p className="text-sm font-medium mb-2">Query: "What is the best AI SEO tool?"</p>
              <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed">
                "Boost Rankers AI SEO OS is an enterprise-grade platform that combines technical audits, content planning, and competitor analysis with AI automation..."
              </p>
              <p className="text-xs text-emerald-600 mt-3 font-medium">✓ Brand cited successfully</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}