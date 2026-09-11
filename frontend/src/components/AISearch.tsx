import { useMemo, useState } from "react";
import {
  AlertCircle,
  ArrowRight,
  Bot,
  CheckCircle2,
  FileSearch,
  Loader2,
  RefreshCw,
  Rocket,
  Sparkles,
  Target,
  Wand2,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";

import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface CheckItem {
  key: string;
  label: string;
  score: number;
  detail: string;
}

interface MeasuredPage {
  url: string;
  title: string;
  meta_title: string;
  meta_description: string;
  canonical: string;
  h1s: string[];
  headings: { level: number; text: string }[];
  word_count: number;
  schema_types: string[];
  internal_links: number;
  external_links: number;
  focus_keyword: string;
  focus_keyword_occurrences: number;
  checks: CheckItem[];
  measured_score: number;
  content_html: string;
  content_text_excerpt: string;
  answer_headings: string[];
  author_present: boolean;
  date_present: boolean;
}

interface AIAnalysis {
  ai_search_score: number;
  content_quality: number;
  answer_engine_readiness: number;
  entity_readiness: number;
  semantic_coverage: number;
  suggested_focus_keyword: string;
  focus_keyword_auto_selected?: boolean;
  focus_keyword_conflict?: boolean;
  summary: string;
  critical_issues: string[];
  high_priority_actions: string[];
  quick_wins: string[];
  rewrite_recommended: boolean;
  rewrite_reason: string;
  suggested_focus_keyword: string;
  suggested_title: string;
  suggested_meta_title: string;
  suggested_meta_description: string;
}

interface RewriteResult {
  title: string;
  focus_keyword: string;
  meta_title: string;
  meta_description: string;
  article_html: string;
  change_summary: string[];
  focus_keyword_usage: Record<string, boolean>;
  internal_links_applied?: number;
  internal_link_targets?: string[];
}

interface WPItem {
  id: number;
  type: "post" | "page";
  title: string;
  url: string;
  status: string;
  modified: string;
  content_html: string;
  excerpt: string;
  focus_keyword?: string;
}

function scoreClass(score: number) {
  if (score >= 80) return "text-emerald-500";
  if (score >= 60) return "text-amber-500";
  return "text-rose-500";
}

function scoreBarClass(score: number) {
  if (score >= 80) return "bg-emerald-500";
  if (score >= 60) return "bg-amber-500";
  return "bg-rose-500";
}

function getErrorMessage(error: any, fallback: string) {
  return error?.data?.detail || error?.response?.data?.detail || error?.message || fallback;
}

function normalizePhrase(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim().replace(/\s+/g, " ");
}

export function AISearch() {
  const [url, setUrl] = useState("");
  const [focusKeyword, setFocusKeyword] = useState("");
  const [loading, setLoading] = useState(false);
  const [rewriting, setRewriting] = useState(false);
  const [analysis, setAnalysis] = useState<{ measured: MeasuredPage; ai_analysis: AIAnalysis } | null>(null);
  const [rewrite, setRewrite] = useState<RewriteResult | null>(null);
  const [showOriginal, setShowOriginal] = useState(false);
  const [error, setError] = useState("");

  const [wpSite, setWpSite] = useState("");
  const [wpUsername, setWpUsername] = useState("");
  const [wpPassword, setWpPassword] = useState("");
  const [wpItems, setWpItems] = useState<WPItem[]>([]);
  const [selectedPostId, setSelectedPostId] = useState("");
  const [loadingWp, setLoadingWp] = useState(false);
  const [applying, setApplying] = useState(false);
  const [wpStatus, setWpStatus] = useState<"draft" | "publish">("draft");

  const activeTitle = rewrite?.title || analysis?.measured.title || "";
  const activeKeyword = rewrite?.focus_keyword || focusKeyword;
  const activeMetaTitle = rewrite?.meta_title || analysis?.measured.meta_title || "";
  const activeMetaDescription = rewrite?.meta_description || analysis?.measured.meta_description || "";
  const activeHtml = rewrite?.article_html || analysis?.measured.content_html || "";

  const readinessCards = useMemo(() => {
    if (!analysis) {
      return [
        { label: "AI Search Readiness", value: "—", detail: "Analyze a real page to measure it" },
        { label: "Content Quality", value: "—", detail: "Measured from the page content" },
        { label: "Answer Engine", value: "—", detail: "Question and answer structure" },
        { label: "Entity Readiness", value: "—", detail: "Schema, author and date signals" },
      ];
    }
    return [
      { label: "AI Search Readiness", value: `${analysis.ai_analysis.ai_search_score}%`, detail: "Evidence-based AI-search assessment" },
      { label: "Content Quality", value: `${analysis.ai_analysis.content_quality}%`, detail: "Depth, clarity and usefulness" },
      { label: "Answer Engine", value: `${analysis.ai_analysis.answer_engine_readiness}%`, detail: "Passage-level answer readiness" },
      { label: "Entity Readiness", value: `${analysis.ai_analysis.entity_readiness}%`, detail: "Entity and trust signals" },
    ];
  }, [analysis]);

  const analyze = async () => {
    if (!url.trim()) {
      toast.error("Enter the post URL first.");
      return;
    }
    setLoading(true);
    setError("");
    setAnalysis(null);
    setRewrite(null);
    try {
      const usedFocusKeywords = wpItems
        .filter((item) => String(item.id) !== String(selectedPostId))
        .map((item) => item.focus_keyword?.trim() || "")
        .filter(Boolean);
      const result = await api.post<{ success: boolean; measured: MeasuredPage; ai_analysis: AIAnalysis }>(
        "/api/ai-search-optimization/analyze",
        {
          url: url.trim(),
          focus_keyword: focusKeyword.trim(),
          used_focus_keywords: usedFocusKeywords,
        },
      );
      setAnalysis({ measured: result.measured, ai_analysis: result.ai_analysis });
      setFocusKeyword(result.measured.focus_keyword || result.ai_analysis.suggested_focus_keyword || focusKeyword.trim());
      if (result.ai_analysis.focus_keyword_conflict) {
        toast.warning(`That focus keyword was already used. Boost Rankers selected an unused keyword: ${result.measured.focus_keyword}`);
      } else if (result.ai_analysis.focus_keyword_auto_selected) {
        toast.success(`Focus keyword selected automatically: ${result.measured.focus_keyword}`);
      } else {
        toast.success("Post analyzed using real page evidence.");
      }
    } catch (err: any) {
      const message = getErrorMessage(err, "Could not analyze the post.");
      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  const rewritePost = async () => {
    if (!analysis || !focusKeyword.trim()) {
      toast.error("Analyze the post and provide a focus keyword first.");
      return;
    }
    setRewriting(true);
    setError("");
    try {
      const internalLinkCandidates = wpItems
        .filter((item) => String(item.id) !== String(selectedPostId) && item.status === "publish" && item.url && item.title)
        .map((item) => ({ id: String(item.id), type: item.type, title: item.title, url: item.url }));
      const result = await api.post<{ success: boolean; rewrite: RewriteResult }>(
        "/api/ai-search-optimization/rewrite",
        {
          url: analysis.measured.url,
          focus_keyword: focusKeyword.trim(),
          title: analysis.measured.title || "Optimized article",
          content_html: analysis.measured.content_html,
          meta_title: analysis.measured.meta_title,
          meta_description: analysis.measured.meta_description,
          analysis: analysis.ai_analysis,
          internal_link_candidates: internalLinkCandidates,
        },
      );
      setRewrite(result.rewrite);
      toast.success("The article has been rewritten and optimized for review.");
    } catch (err: any) {
      const message = getErrorMessage(err, "Could not rewrite the post.");
      setError(message);
      toast.error(message);
    } finally {
      setRewriting(false);
    }
  };

  const loadWordPressContent = async () => {
    if (!wpSite || !wpUsername || !wpPassword) {
      toast.error("Enter the WordPress site, username and Application Password.");
      return;
    }
    setLoadingWp(true);
    try {
      const result = await api.post<{ success: boolean; items: WPItem[] }>(
        "/api/ai-search-optimization/wordpress/content",
        {
          wordpress_site: wpSite.trim(),
          wordpress_username: wpUsername.trim(),
          wordpress_application_password: wpPassword.trim(),
        },
      );
      setWpItems(result.items || []);
      toast.success(`${result.items?.length || 0} WordPress items loaded.`);
    } catch (err: any) {
      toast.error(getErrorMessage(err, "Could not load WordPress content."));
    } finally {
      setLoadingWp(false);
    }
  };

  const useWordPressItem = (id: string) => {
    setSelectedPostId(id);
    const item = wpItems.find((entry) => String(entry.id) === id);
    if (!item) return;
    setUrl(item.url);
    setRewrite(null);
    setAnalysis(null);
    const otherUsed = new Set(
      wpItems
        .filter((entry) => String(entry.id) !== id)
        .map((entry) => normalizePhrase(entry.focus_keyword || ""))
        .filter(Boolean),
    );
    const existingKeyword = item.focus_keyword?.trim() || "";
    setFocusKeyword(existingKeyword && !otherUsed.has(normalizePhrase(existingKeyword)) ? existingKeyword : "");
    toast.success(
      existingKeyword && !otherUsed.has(normalizePhrase(existingKeyword))
        ? `${item.type === "post" ? "Post" : "Page"} selected. Existing unique focus keyword loaded automatically.`
        : `${item.type === "post" ? "Post" : "Page"} selected. The focus keyword will be selected automatically from the title/content if needed.`,
    );
  };

  const applyToWordPress = async () => {
    if (!rewrite) {
      toast.error("Rewrite the article first so the optimized version can be reviewed.");
      return;
    }
    if (!wpSite || !wpUsername || !wpPassword || !selectedPostId) {
      toast.error("Load WordPress content and select a post or page first.");
      return;
    }
    setApplying(true);
    try {
      const result = await api.post<any>("/api/ai-search-optimization/wordpress/apply", {
        wordpress_site: wpSite.trim(),
        wordpress_username: wpUsername.trim(),
        wordpress_application_password: wpPassword.trim(),
        post_id: Number(selectedPostId),
        title: activeTitle,
        content_html: activeHtml,
        meta_title: activeMetaTitle,
        meta_description: activeMetaDescription,
        focus_keyphrase: activeKeyword,
        status: wpStatus,
      });
      toast.success(result.message || "Optimized content applied to WordPress.");
      if (result.wordpress?.url) window.open(result.wordpress.url, "_blank", "noopener,noreferrer");
    } catch (err: any) {
      toast.error(getErrorMessage(err, "Could not apply the optimized content to WordPress."));
    } finally {
      setApplying(false);
    }
  };

  return (
    <div className="p-8 space-y-6">
      <header>
        <div className="flex items-center gap-3">
          <div className="size-11 rounded-xl bg-indigo-500/10 flex items-center justify-center">
            <Bot className="size-6 text-indigo-500" />
          </div>
          <div>
            <h2 className="font-serif text-3xl font-bold tracking-tight">AI Search Optimization</h2>
            <p className="text-slate-500 dark:text-slate-400 mt-1">
              Analyze real pages, identify answer-engine gaps, rewrite weak content, and apply SEO metadata safely.
            </p>
          </div>
        </div>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {readinessCards.map((card) => {
          const numeric = Number.parseInt(card.value, 10);
          return (
            <Card key={card.label} className="border-slate-200 dark:border-slate-800 shadow-sm">
              <CardContent className="p-5">
                <p className="text-sm text-slate-500 dark:text-slate-400">{card.label}</p>
                <p className={cn("font-serif text-3xl font-bold mt-2", Number.isFinite(numeric) ? scoreClass(numeric) : "text-slate-300")}>{card.value}</p>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-2">{card.detail}</p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <Card className="xl:col-span-2 border-slate-200 dark:border-slate-800 shadow-sm">
          <CardHeader>
            <CardTitle className="font-serif flex items-center gap-2">
              <FileSearch className="size-5 text-emerald-500" /> Analyze a real post
            </CardTitle>
            <CardDescription>Use a public article URL. The analyzer measures the HTML first, then Claude interprets the evidence.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="ai-url">Post URL</Label>
                <Input id="ai-url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com/blog/your-post/" />
              </div>
              <div className="space-y-2 md:col-span-2">
                <Label htmlFor="ai-focus">Focus keyword</Label>
                <Input id="ai-focus" value={focusKeyword} onChange={(e) => setFocusKeyword(e.target.value)} placeholder="Leave blank for automatic unused keyword selection" />
                <p className="text-xs text-slate-500">If the keyword is already used by another loaded WordPress post/page, Boost Rankers automatically selects an unused title-derived keyword.</p>
              </div>
            </div>
            <div className="flex flex-wrap gap-3">
              <Button onClick={analyze} disabled={loading || !url.trim()} className="bg-emerald-600 hover:bg-emerald-700 text-white">
                {loading ? <Loader2 className="size-4 animate-spin" /> : <FileSearch className="size-4" />}
                {loading ? "Analyzing..." : "Analyze Post"}
              </Button>
              {analysis && (
                <Button variant="outline" onClick={rewritePost} disabled={rewriting}>
                  {rewriting ? <Loader2 className="size-4 animate-spin" /> : <Wand2 className="size-4" />}
                  {rewriting ? "Rewriting..." : "Rewrite & Optimize"}
                </Button>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
          <CardHeader>
            <CardTitle className="font-serif flex items-center gap-2"><Target className="size-5 text-indigo-500" /> What this checks</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-slate-600 dark:text-slate-300">
            {[
              "Content depth and structure",
              "Focus-keyword placement",
              "Answer-engine / passage readiness",
              "Entity and trust signals",
              "Title, H1 and meta quality",
              "Internal linking and schema evidence",
            ].map((item) => <div key={item} className="flex items-center gap-2"><CheckCircle2 className="size-4 text-emerald-500" />{item}</div>)}
          </CardContent>
        </Card>
      </div>

      {error && (
        <Card className="border-rose-200 dark:border-rose-900/50 bg-rose-50 dark:bg-rose-900/10">
          <CardContent className="p-4 flex items-center gap-3 text-sm text-rose-700 dark:text-rose-400"><AlertCircle className="size-5" />{error}</CardContent>
        </Card>
      )}

      {analysis && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
            <CardHeader>
              <div className="flex items-center justify-between gap-4">
                <div>
                  <CardTitle className="font-serif">Measured page evidence</CardTitle>
                  <CardDescription>Facts extracted from the page. These are not fabricated rankings or AI citations.</CardDescription>
                </div>
                <Badge variant="outline">{analysis.measured.measured_score}/100</Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {analysis.measured.checks.map((check) => (
                <div key={check.key}>
                  <div className="flex justify-between text-sm mb-1"><span>{check.label}</span><span className={cn("font-semibold", scoreClass(check.score))}>{check.score}</span></div>
                  <div className="h-2 rounded-full bg-slate-100 dark:bg-slate-800 overflow-hidden"><div className={cn("h-full rounded-full", scoreBarClass(check.score))} style={{ width: `${check.score}%` }} /></div>
                  <p className="text-xs text-slate-500 mt-1">{check.detail}</p>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
            <CardHeader>
              <div className="flex items-center justify-between gap-4">
                <div><CardTitle className="font-serif">AI Search interpretation</CardTitle><CardDescription>Claude recommendations grounded in the measured page.</CardDescription></div>
                {analysis.ai_analysis.rewrite_recommended ? <Badge className="bg-rose-500">Rewrite recommended</Badge> : <Badge className="bg-emerald-500">Content usable</Badge>}
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm leading-6 text-slate-600 dark:text-slate-300">{analysis.ai_analysis.summary}</p>
              {analysis.ai_analysis.rewrite_reason && <div className="rounded-lg bg-amber-50 dark:bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-300"><strong>Why:</strong> {analysis.ai_analysis.rewrite_reason}</div>}
              <div className="grid grid-cols-2 gap-3">
                {["answer_engine_readiness", "semantic_coverage"].map((key) => {
                  const value = analysis.ai_analysis[key as "answer_engine_readiness" | "semantic_coverage"];
                  return <div key={key} className="rounded-lg border border-slate-200 dark:border-slate-800 p-3"><p className="text-xs text-slate-500">{key === "answer_engine_readiness" ? "Answer Engine" : "Semantic Coverage"}</p><p className={cn("text-xl font-bold mt-1", scoreClass(value))}>{value}%</p></div>;
                })}
              </div>
              <IssueList title="Critical issues" items={analysis.ai_analysis.critical_issues} tone="bad" />
              <IssueList title="High-priority actions" items={analysis.ai_analysis.high_priority_actions} tone="warn" />
              <IssueList title="Quick wins" items={analysis.ai_analysis.quick_wins} tone="good" />
            </CardContent>
          </Card>
        </div>
      )}

      {rewrite && (
        <Card className="border-indigo-200 dark:border-indigo-900/50 shadow-sm">
          <CardHeader>
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
              <div>
                <CardTitle className="font-serif flex items-center gap-2"><Sparkles className="size-5 text-indigo-500" /> Optimized article preview</CardTitle>
                <CardDescription>Review the generated content before applying it to WordPress.</CardDescription>
              </div>
              <div className="flex gap-2">
                <Button variant={showOriginal ? "outline" : "default"} size="sm" onClick={() => setShowOriginal(false)}>Optimized</Button>
                <Button variant={showOriginal ? "default" : "outline"} size="sm" onClick={() => setShowOriginal(true)}>Original</Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <MetaField label="Title" value={showOriginal ? analysis?.measured.title || "" : rewrite.title} />
              <MetaField label="Meta title" value={showOriginal ? analysis?.measured.meta_title || "" : rewrite.meta_title} />
              <MetaField label="Focus keyword" value={rewrite.focus_keyword} />
              <MetaField label="Internal links" value={String(rewrite.internal_links_applied ?? 0)} />
            </div>
            <div><p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">Meta description</p><div className="rounded-lg border border-slate-200 dark:border-slate-800 p-3 text-sm">{showOriginal ? analysis?.measured.meta_description : rewrite.meta_description}</div></div>
            <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/60 p-5 max-h-[520px] overflow-auto">
              {showOriginal ? <div className="prose prose-sm dark:prose-invert max-w-none" dangerouslySetInnerHTML={{ __html: analysis?.measured.content_html || "" }} /> : <div className="prose prose-sm dark:prose-invert max-w-none" dangerouslySetInnerHTML={{ __html: rewrite.article_html }} />}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card className="bg-emerald-50/60 dark:bg-emerald-500/5 border-emerald-200 dark:border-emerald-900/40">
                <CardContent className="p-4"><p className="text-sm font-semibold mb-2">What changed</p><ul className="space-y-2 text-sm text-slate-600 dark:text-slate-300">{rewrite.change_summary.map((item, i) => <li key={i} className="flex gap-2"><ArrowRight className="size-4 text-emerald-500 shrink-0 mt-0.5" />{item}</li>)}</ul></CardContent>
              </Card>
              <Card className="bg-indigo-50/60 dark:bg-indigo-500/5 border-indigo-200 dark:border-indigo-900/40">
                <CardContent className="p-4"><p className="text-sm font-semibold mb-2">Focus keyword checks</p><div className="space-y-2">{Object.entries(rewrite.focus_keyword_usage).map(([key, ok]) => <div key={key} className="flex justify-between text-sm"><span className="capitalize">{key.replace(/_/g, " ")}</span>{ok ? <CheckCircle2 className="size-4 text-emerald-500" /> : <XCircle className="size-4 text-rose-500" />}</div>)}</div></CardContent>
              </Card>
            </div>
          </CardContent>
        </Card>
      )}

      <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
        <CardHeader>
          <CardTitle className="font-serif flex items-center gap-2"><Rocket className="size-5 text-emerald-500" /> Apply to WordPress</CardTitle>
          <CardDescription>Credentials are used only for this request. Use a WordPress Application Password, not the account password.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2"><Label>WordPress site</Label><Input value={wpSite} onChange={(e) => setWpSite(e.target.value)} placeholder="https://clientsite.com" /></div>
            <div className="space-y-2"><Label>Username</Label><Input value={wpUsername} onChange={(e) => setWpUsername(e.target.value)} placeholder="wordpress-admin" /></div>
            <div className="space-y-2"><Label>Application Password</Label><Input type="password" value={wpPassword} onChange={(e) => setWpPassword(e.target.value)} placeholder="xxxx xxxx xxxx xxxx" /></div>
          </div>
          <div className="flex flex-wrap gap-3 items-center">
            <Button variant="outline" onClick={loadWordPressContent} disabled={loadingWp}>
              {loadingWp ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
              {loadingWp ? "Loading..." : "Load Posts & Pages"}
            </Button>
            <select value={selectedPostId} onChange={(e) => useWordPressItem(e.target.value)} className="h-10 min-w-[280px] rounded-md border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 px-3 text-sm">
              <option value="">Select a WordPress item</option>
              {wpItems.map((item) => <option key={`${item.type}-${item.id}`} value={item.id}>{item.type.toUpperCase()} · {item.title}</option>)}
            </select>
            <select value={wpStatus} onChange={(e) => setWpStatus(e.target.value as "draft" | "publish")} className="h-10 rounded-md border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 px-3 text-sm">
              <option value="draft">Save as Draft</option>
              <option value="publish">Publish</option>
            </select>
          </div>
          <div className="rounded-lg bg-slate-50 dark:bg-slate-900/70 p-3 text-xs text-slate-500 dark:text-slate-400">
            The apply step updates the selected WordPress post/page content. If the existing Boost Rankers SEO Bridge + Yoast integration is available, it also saves the optimized SEO title, meta description and focus keyphrase.
          </div>
          <Button onClick={applyToWordPress} disabled={applying || !rewrite || !selectedPostId} className="bg-indigo-600 hover:bg-indigo-700 text-white">
            {applying ? <Loader2 className="size-4 animate-spin" /> : <Rocket className="size-4" />}
            {applying ? "Applying..." : "Apply Optimized Post"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

function IssueList({ title, items, tone }: { title: string; items: string[]; tone: "bad" | "warn" | "good" }) {
  if (!items?.length) return null;
  const icon = tone === "bad" ? <XCircle className="size-4 text-rose-500 shrink-0" /> : tone === "warn" ? <AlertCircle className="size-4 text-amber-500 shrink-0" /> : <CheckCircle2 className="size-4 text-emerald-500 shrink-0" />;
  return <div><p className="text-sm font-semibold mb-2">{title}</p><ul className="space-y-2 text-sm text-slate-600 dark:text-slate-300">{items.map((item, i) => <li key={i} className="flex gap-2">{icon}<span>{item}</span></li>)}</ul></div>;
}

function MetaField({ label, value }: { label: string; value: string }) {
  return <div><p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-2">{label}</p><div className="min-h-10 rounded-lg border border-slate-200 dark:border-slate-800 p-2.5 text-sm bg-white/50 dark:bg-slate-950/40">{value || "—"}</div></div>;
}
