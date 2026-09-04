import { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sparkles, Loader2, Calendar, Target, AlertCircle, ChevronLeft, ChevronRight, CheckCircle2, Clock3, RefreshCw } from "lucide-react";
import { useClaude } from "@/components/ClaudeProvider";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { ContentWriter, type ContentWriterIdea } from "@/components/ContentWriter";
import { ContentAutoScheduler } from "@/components/ContentAutoScheduler";

interface ContentIdea {
  title: string;
  keyword: string;
  intent: string;
  difficulty: string;
  outline: string[];
  contentType?: string;
  status?: string;
}

interface CalendarDay {
  date: string;
  idea: ContentIdea;
}

interface SavedPlanSummary {
  id: string;
  topic: string;
  start_date: string;
  item_count: number;
  created_at: string | null;
}

interface SavedPlanResponse {
  success: boolean;
  plan: {
    id: string;
    topic: string;
    start_date: string;
    item_count: number;
    items: ContentIdea[];
  };
}

interface ContentArticleStatus {
  id: string;
  plan_id: string | null;
  day_number: number;
  status: string;
  scheduled_at: string | null;
  wordpress_url: string | null;
  published_at: string | null;
}

function formatDateKey(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function addDays(date: Date, days: number): Date {
  const result = new Date(date);
  result.setHours(12, 0, 0, 0);
  result.setDate(result.getDate() + days);
  return result;
}

function parseDateInput(value: string): Date {
  const [year, month, day] = value.split("-").map(Number);
  const date = new Date(year, month - 1, day, 12, 0, 0, 0);
  return Number.isNaN(date.getTime()) ? new Date() : date;
}

function parseContentBatch(response: string, expectedCount: number): ContentIdea[] {
  const cleaned = response
    .replace(/^\s*```(?:json)?\s*/i, "")
    .replace(/\s*```\s*$/i, "")
    .trim();

  let parsed: unknown;

  try {
    parsed = JSON.parse(cleaned);
  } catch {
    const start = cleaned.indexOf("[");
    const end = cleaned.lastIndexOf("]");
    if (start === -1 || end <= start) {
      throw new Error("Claude returned an invalid content plan response.");
    }

    try {
      parsed = JSON.parse(cleaned.slice(start, end + 1));
    } catch {
      throw new Error("Claude returned an invalid content plan response.");
    }
  }

  let items: unknown = parsed;
  if (!Array.isArray(items) && items && typeof items === "object") {
    const object = items as Record<string, unknown>;
    items = object.items ?? object.plan ?? object.content_plan ?? object.contentPlan ?? object.calendar ?? object.ideas;
  }

  if (!Array.isArray(items)) {
    throw new Error("Claude returned an unexpected content plan structure.");
  }

  const normalized = items
    .map((item): ContentIdea | null => {
      if (!item || typeof item !== "object") return null;
      const value = item as Record<string, unknown>;
      const title = String(value.title ?? value.topic ?? value.content_title ?? "").trim();
      const keyword = String(value.keyword ?? value.primary_keyword ?? value.primaryKeyword ?? "").trim();
      if (!title || !keyword) return null;

      const rawOutline = value.outline ?? value.outline_points ?? [];
      const outline = Array.isArray(rawOutline)
        ? rawOutline.map((point) => String(point).trim()).filter(Boolean).slice(0, 5)
        : [];

      return {
        title,
        keyword,
        intent: String(value.intent ?? value.search_intent ?? "Informational").trim() || "Informational",
        difficulty: String(value.difficulty ?? "Not measured").trim() || "Not measured",
        outline,
        contentType: String(value.contentType ?? value.content_type ?? value.type ?? "Blog").trim() || "Blog",
        status: String(value.status ?? "Planned").trim() || "Planned",
      };
    })
    .filter((item): item is ContentIdea => item !== null);

  if (normalized.length !== expectedCount) {
    throw new Error(`Claude returned ${normalized.length} items; ${expectedCount} were required for this batch.`);
  }

  return normalized;
}

function hasDuplicateContent(items: ContentIdea[]): boolean {
  const titles = new Set<string>();
  const keywords = new Set<string>();

  for (const item of items) {
    const title = item.title.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
    const keyword = item.keyword.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
    if (!title || !keyword || titles.has(title) || keywords.has(keyword)) return true;
    titles.add(title);
    keywords.add(keyword);
  }

  return false;
}

function validateAgainstExisting(batch: ContentIdea[], existing: ContentIdea[]): ContentIdea[] {
  const existingTitles = new Set(existing.map((item) => item.title.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim()));
  const existingKeywords = new Set(existing.map((item) => item.keyword.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim()));

  if (hasDuplicateContent(batch)) {
    throw new Error("Claude returned duplicate content items in this batch.");
  }

  for (const item of batch) {
    const title = item.title.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
    const keyword = item.keyword.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
    if (existingTitles.has(title) || existingKeywords.has(keyword)) {
      throw new Error("Claude returned a duplicate title or keyword across batches.");
    }
  }

  return batch;
}

function monthKey(date: Date): string {
  return `${date.getFullYear()}-${date.getMonth()}`;
}

function monthLabel(date: Date): string {
  return date.toLocaleDateString(undefined, { month: "long", year: "numeric" });
}

function buildMonthDates(date: Date): Date[] {
  const first = new Date(date.getFullYear(), date.getMonth(), 1, 12, 0, 0, 0);
  const last = new Date(date.getFullYear(), date.getMonth() + 1, 0, 12, 0, 0, 0);
  const cells: Date[] = [];

  for (let i = 0; i < first.getDay(); i += 1) {
    cells.push(addDays(first, i - first.getDay()));
  }
  for (let day = 1; day <= last.getDate(); day += 1) {
    cells.push(new Date(date.getFullYear(), date.getMonth(), day, 12, 0, 0, 0));
  }
  while (cells.length % 7 !== 0) cells.push(addDays(cells[cells.length - 1], 1));
  return cells;
}

export function ContentPlanner() {
  const { isConfigured, isReady, status, generateContent } = useClaude();
  const [topic, setTopic] = useState("AI SEO strategies");
  const [startDate, setStartDate] = useState(() => formatDateKey(new Date()));
  const [loading, setLoading] = useState(false);
  const [ideas, setIdeas] = useState<ContentIdea[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selectedMonth, setSelectedMonth] = useState<string | null>(null);
  const [savedPlans, setSavedPlans] = useState<SavedPlanSummary[]>([]);
  const [loadingSavedPlans, setLoadingSavedPlans] = useState(true);
  const [savingPlan, setSavingPlan] = useState(false);
  const [openingPlanId, setOpeningPlanId] = useState<string | null>(null);
  const [currentPlanId, setCurrentPlanId] = useState<string | null>(null);
  const [writerOpen, setWriterOpen] = useState(false);
  const [writerIdea, setWriterIdea] = useState<ContentWriterIdea | null>(null);
  const [writerDay, setWriterDay] = useState(1);
  const [writerDate, setWriterDate] = useState(startDate);
  const [autoSchedulerOpen, setAutoSchedulerOpen] = useState(false);

  const calendarDays = useMemo<CalendarDay[]>(() => {
    const start = parseDateInput(startDate);
    return ideas.map((idea, index) => ({ date: formatDateKey(addDays(start, index)), idea }));
  }, [ideas, startDate]);

  const ideasByDate = useMemo(() => {
    const map = new Map<string, ContentIdea>();
    calendarDays.forEach(({ date, idea }) => map.set(date, idea));
    return map;
  }, [calendarDays]);

  const months = useMemo(() => {
    const unique = new Map<string, Date>();
    calendarDays.forEach(({ date }) => {
      const parsed = parseDateInput(date);
      const key = monthKey(parsed);
      if (!unique.has(key)) unique.set(key, new Date(parsed.getFullYear(), parsed.getMonth(), 1, 12, 0, 0, 0));
    });
    return Array.from(unique.values());
  }, [calendarDays]);

  const visibleMonths = useMemo(
    () => selectedMonth ? months.filter((month) => monthKey(month) === selectedMonth) : months,
    [months, selectedMonth]
  );

  const loadSavedPlans = async () => {
    try {
      setLoadingSavedPlans(true);
      const response = (await api.get("/api/content-plans")) as {
        success: boolean;
        plans: SavedPlanSummary[];
      };
      setSavedPlans(response.plans ?? []);
    } catch (err) {
      console.error("Failed to load saved content plans:", err);
    } finally {
      setLoadingSavedPlans(false);
    }
  };

  useEffect(() => {
    void loadSavedPlans();
  }, []);

  const refreshArticleStatuses = async () => {
    if (!currentPlanId) return;

    try {
      const response = (await api.get("/api/content-automation/articles")) as {
        success: boolean;
        articles: ContentArticleStatus[];
      };

      let relevant = (response.articles ?? []).filter((article) => article.plan_id === currentPlanId);
      const now = Date.now();
      const dueScheduled = relevant.filter((article) => {
        if (article.status !== "scheduled" || !article.scheduled_at) return false;
        const time = new Date(article.scheduled_at).getTime();
        return Number.isFinite(time) && time <= now;
      });

      if (dueScheduled.length > 0) {
        const synced = await Promise.all(
          dueScheduled.map(async (article) => {
            try {
              const result = (await api.post(`/api/content-automation/articles/${article.id}/sync-wordpress`)) as {
                success: boolean;
                article?: ContentArticleStatus;
              };
              return result.article ?? article;
            } catch {
              return article;
            }
          })
        );

        const syncedById = new Map(synced.map((article) => [article.id, article]));
        relevant = relevant.map((article) => syncedById.get(article.id) ?? article);
      }

      const byDay = new Map<number, ContentArticleStatus>();
      relevant.forEach((article) => {
        const existing = byDay.get(article.day_number);
        if (!existing || article.status === "published" || article.id === existing.id) {
          byDay.set(article.day_number, article);
        }
      });

      setIdeas((current) => current.map((idea, index) => {
        const article = byDay.get(index + 1);
        return article ? { ...idea, status: article.status } : idea;
      }));
    } catch (err) {
      console.debug("Content publication status refresh skipped:", err);
    }
  };

  useEffect(() => {
    if (!currentPlanId) return;

    void refreshArticleStatuses();
    const interval = window.setInterval(() => {
      void refreshArticleStatuses();
    }, 30000);

    return () => window.clearInterval(interval);
  }, [currentPlanId, ideas.length]);

  const openSavedPlan = async (planId: string) => {
    try {
      setOpeningPlanId(planId);
      setError(null);
      const response = (await api.get(`/api/content-plans/${planId}`)) as SavedPlanResponse;
      if (!response.plan?.items?.length) {
        throw new Error("This saved content plan has no content items.");
      }
      setCurrentPlanId(response.plan.id);
      setTopic(response.plan.topic);
      setStartDate(response.plan.start_date);
      setIdeas(response.plan.items);
      setSelectedMonth(null);
    } catch (err: any) {
      setError(err?.data?.detail || err?.message || "Failed to open saved content plan.");
    } finally {
      setOpeningPlanId(null);
    }
  };

  const deleteSavedPlan = async (planId: string) => {
    if (!window.confirm("Delete this saved content plan?")) return;
    try {
      await api.delete(`/api/content-plans/${planId}`);
      setSavedPlans((current) => current.filter((plan) => plan.id !== planId));
    } catch (err: any) {
      setError(err?.data?.detail || err?.message || "Failed to delete saved content plan.");
    }
  };

  const saveGeneratedPlan = async (generated: ContentIdea[]) => {
    setSavingPlan(true);
    try {
      const response = (await api.post("/api/content-plans", {
        topic: topic.trim(),
        start_date: startDate,
        items: generated,
      })) as {
        success: boolean;
        plan: SavedPlanSummary;
      };

      if (response.plan) {
        setCurrentPlanId(response.plan.id);
        setSavedPlans((current) => [
          response.plan,
          ...current.filter((plan) => plan.id !== response.plan.id),
        ]);
      }
    } finally {
      setSavingPlan(false);
    }
  };

  const generatePlan = async () => {
    if (!topic.trim()) {
      setError("Please enter a topic or seed keyword.");
      return;
    }
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
    setIdeas([]);
    setSelectedMonth(null);
    setError(null);

    const batchSize = 5;
    const totalDays = 90;
    const totalBatches = Math.ceil(totalDays / batchSize);
    const generated: ContentIdea[] = [];

    const phaseForBatch = (batchNumber: number): string => {
      if (batchNumber <= 3) return "topical foundations, pillar topics, definitions, beginner guides, and core entities";
      if (batchNumber <= 6) return "supporting clusters, problem-solving guides, how-to content, FAQs, and long-tail topics";
      if (batchNumber <= 9) return "commercial investigation, comparisons, alternatives, service-focused topics, and buyer questions";
      if (batchNumber <= 12) return "advanced strategies, implementation guides, workflows, checklists, and expert-level topics";
      if (batchNumber <= 15) return "case-study angles, trust content, common mistakes, audits, templates, and authority-building topics";
      return "refresh/support topics, emerging angles, decision-stage content, FAQs, and final topical-authority gaps";
    };

    const buildBatchPrompt = (batchNumber: number, retry = false): string => {
      const startDay = (batchNumber - 1) * batchSize + 1;
      const endDay = Math.min(batchNumber * batchSize, totalDays);
      const existing = generated
        .map((item, index) => `${index + 1}. ${item.title} | ${item.keyword}`)
        .join("\n");

      return `Create SEO content calendar items for Days ${startDay}-${endDay} of a 90-day plan about the topic/seed keyword: "${topic.trim()}".

This is batch ${batchNumber} of ${totalBatches}. Generate EXACTLY ${endDay - startDay + 1} items.
Strategic focus for this batch: ${phaseForBatch(batchNumber)}.

Requirements:
- Every item must be genuinely useful, specific, and distinct.
- Do not duplicate or closely repeat any existing title or keyword listed below.
- Vary search intent and content type naturally.
- Use realistic types such as Blog, Pillar, Guide, Comparison, Case Study, Checklist, FAQ, or Commercial.
- Keep each outline to exactly 3 concise section points.
- Do not invent search volume, traffic, rankings, backlink metrics, or numerical keyword difficulty.
- Use difficulty only as a qualitative label: Easy, Medium, Hard, or Not measured.
- Do not use placeholders.
- Return ONLY valid JSON. No markdown, explanation, or code fences.

Return exactly this structure:
[
  {
    "title": "Content title",
    "keyword": "Primary keyword",
    "intent": "Informational",
    "difficulty": "Not measured",
    "contentType": "Blog",
    "status": "Planned",
    "outline": ["Section 1", "Section 2", "Section 3"]
  }
]

Existing items that MUST NOT be repeated:
${existing || "None — this is the first batch."}

${retry ? "IMPORTANT: Your previous response failed validation. Return the exact required number of valid, unique JSON objects now. Do not add commentary." : ""}`;
    };

    try {
      for (let batchNumber = 1; batchNumber <= totalBatches; batchNumber += 1) {
        let batch: ContentIdea[] | null = null;
        let lastError: unknown = null;

        for (let attempt = 1; attempt <= 2; attempt += 1) {
          try {
            const response = await generateContent(buildBatchPrompt(batchNumber, attempt === 2));
            const parsed = parseContentBatch(response, Math.min(batchSize, totalDays - generated.length));
            batch = validateAgainstExisting(parsed, generated);
            break;
          } catch (err) {
            lastError = err;
          }
        }

        if (!batch) {
          throw new Error(
            lastError instanceof Error
              ? `Unable to generate Days ${(batchNumber - 1) * batchSize + 1}-${Math.min(batchNumber * batchSize, totalDays)}. ${lastError.message}`
              : "Claude could not generate a valid content batch. Please try again."
          );
        }

        generated.push(...batch);
        setIdeas([...generated]);
      }

      if (generated.length !== totalDays) {
        throw new Error(`The content planner generated ${generated.length} items instead of exactly ${totalDays}.`);
      }

      try {
        await saveGeneratedPlan(generated);
      } catch (saveError: any) {
        // The generated plan remains visible for this session, but the user
        // must be told that persistence failed instead of silently losing it.
        setError(
          saveError?.data?.detail ||
            saveError?.message ||
            "The 90-day plan was generated, but could not be saved. Please try again."
        );
      }
    } catch (err: any) {
      setIdeas([]);
      setError(err?.message || "Failed to generate the 90-day content plan.");
    } finally {
      setLoading(false);
    }
  };

  const goToPreviousMonth = () => {
    if (!months.length) return;
    const currentIndex = selectedMonth ? months.findIndex((month) => monthKey(month) === selectedMonth) : 0;
    setSelectedMonth(monthKey(months[Math.max(0, currentIndex - 1)]));
  };

  const goToNextMonth = () => {
    if (!months.length) return;
    const currentIndex = selectedMonth ? months.findIndex((month) => monthKey(month) === selectedMonth) : 0;
    setSelectedMonth(monthKey(months[Math.min(months.length - 1, currentIndex + 1)]));
  };

  return (
    <div className="p-8 space-y-6">
      <header>
        <h2 className="font-serif text-3xl font-bold tracking-tight">Content Planner</h2>
        <p className="text-slate-500 dark:text-slate-400 mt-1">
          Generate AI-powered 90-day content plans, outlines, and strategies.
        </p>
      </header>

      {!isConfigured ? (
        <Card className="border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-900/10">
          <CardContent className="p-4 flex items-center gap-3">
            <AlertCircle className="size-5 text-amber-600" />
            <p className="text-sm text-amber-700 dark:text-amber-400">Claude API Key required. Please configure it in Settings to enable AI content planning.</p>
          </CardContent>
        </Card>
      ) : !isReady && (
        <Card className="border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-900/10">
          <CardContent className="p-4 flex items-center gap-3">
            <AlertCircle className="size-5 text-amber-600" />
            <p className="text-sm text-amber-700 dark:text-amber-400">
              {status === "billing_required"
                ? "Anthropic billing is required. Your API key is valid, but your credit balance is too low. Please add credits or upgrade your plan, then try again."
                : status === "invalid_api_key"
                  ? "Anthropic API key is invalid. Please update it in Settings."
                  : "Claude AI is currently unavailable. Please check Settings."}
            </p>
          </CardContent>
        </Card>
      )}

      <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
        <CardHeader>
          <CardTitle className="font-serif flex items-center gap-2">
            <Calendar className="size-5 text-emerald-600" />
            Saved Content Plans
          </CardTitle>
          <CardDescription>
            Your generated calendars are saved to your account and remain available after refresh or login.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loadingSavedPlans ? (
            <div className="text-sm text-slate-500 dark:text-slate-400">Loading saved plans...</div>
          ) : savedPlans.length === 0 ? (
            <div className="text-sm text-slate-500 dark:text-slate-400">
              No saved content plans yet. Generate your first 90-day plan below.
            </div>
          ) : (
            <div className="space-y-2">
              {savedPlans.map((plan) => (
                <div
                  key={plan.id}
                  className="flex flex-col gap-3 rounded-lg border border-slate-200 p-3 dark:border-slate-800 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-slate-800 dark:text-slate-100">{plan.topic}</p>
                    <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                      {plan.item_count} days · starts {parseDateInput(plan.start_date).toLocaleDateString()}
                      {plan.created_at ? ` · saved ${new Date(plan.created_at).toLocaleDateString()}` : ""}
                    </p>
                  </div>
                  <div className="flex shrink-0 gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => void openSavedPlan(plan.id)}
                      disabled={openingPlanId !== null}
                    >
                      {openingPlanId === plan.id ? <Loader2 className="size-4 animate-spin" /> : "Open Plan"}
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => void deleteSavedPlan(plan.id)}
                      disabled={openingPlanId !== null}
                    >
                      Delete
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
        <CardHeader>
          <CardTitle className="font-serif flex items-center gap-2"><Sparkles className="size-5 text-emerald-600" />Generate 90-Day Content Plan</CardTitle>
          <CardDescription>Enter a topic and choose the first publishing date to generate a complete 90-day calendar.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="topic">Topic / Seed Keyword</Label>
            <Input id="topic" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="e.g. Technical SEO, Local Marketing..." />
          </div>
          <div className="space-y-2">
            <Label htmlFor="start-date">Calendar Start Date</Label>
            <Input id="start-date" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
            <p className="text-xs text-slate-500 dark:text-slate-400">Day 1 starts on this date and Day 90 is automatically scheduled 89 days later.</p>
          </div>
          <div className="flex flex-wrap gap-2">
          <Button onClick={generatePlan} disabled={loading || savingPlan || !isReady} className="bg-emerald-600 hover:bg-emerald-700 text-white shadow-md shadow-emerald-600/20">
            {loading ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
            {loading ? `Generating ${ideas.length}/90...` : savingPlan ? "Saving Plan..." : "Generate 90-Day Plan"}
          </Button>
          {ideas.length === 90 && <Button type="button" variant="outline" onClick={() => setAutoSchedulerOpen(true)} disabled={loading || savingPlan}>Auto Schedule 90 Days</Button>}
          </div>
        </CardContent>
      </Card>

      {error && (
        <Card className="border-rose-200 dark:border-rose-900/50 bg-rose-50 dark:bg-rose-900/10">
          <CardContent className="p-4 flex items-center gap-3"><AlertCircle className="size-5 text-rose-600" /><p className="text-sm text-rose-700 dark:text-rose-400">{error}</p></CardContent>
        </Card>
      )}

      {loading && (
        <div className="grid gap-4">
          {[1, 2, 3].map((i) => <Card key={i} className="border-slate-200 dark:border-slate-800 shadow-sm animate-pulse"><CardContent className="p-6 h-32 bg-slate-100 dark:bg-slate-800/50 rounded-xl" /></Card>)}
        </div>
      )}

      {!loading && ideas.length > 0 && (
        <>
          <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
            <CardHeader className="pb-4">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <CardTitle className="font-serif flex items-center gap-2"><Calendar className="size-5 text-emerald-600" />90-Day Content Calendar</CardTitle>
                  <CardDescription>
                    {calendarDays.length} scheduled publishing days from {parseDateInput(calendarDays[0]?.date || startDate).toLocaleDateString()} to {parseDateInput(calendarDays[calendarDays.length - 1]?.date || startDate).toLocaleDateString()}
                  </CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  <Button type="button" variant="outline" size="sm" onClick={() => setSelectedMonth(null)} disabled={selectedMonth === null}>All 90 Days</Button>
                  <Button type="button" variant="outline" size="icon" onClick={goToPreviousMonth} disabled={!selectedMonth || selectedMonth === monthKey(months[0])} aria-label="Previous month"><ChevronLeft className="size-4" /></Button>
                  <Button type="button" variant="outline" size="icon" onClick={goToNextMonth} disabled={!selectedMonth || selectedMonth === monthKey(months[months.length - 1])} aria-label="Next month"><ChevronRight className="size-4" /></Button>
                </div>
              </div>
              {months.length > 1 && (
                <div className="flex flex-wrap gap-2 pt-2">
                  {months.map((month) => {
                    const key = monthKey(month);
                    return <Button key={key} type="button" variant={selectedMonth === key ? "default" : "outline"} size="sm" onClick={() => setSelectedMonth(key)} className={selectedMonth === key ? "bg-emerald-600 hover:bg-emerald-700" : ""}>{monthLabel(month)}</Button>;
                  })}
                </div>
              )}
            </CardHeader>
          </Card>

          <div className="space-y-6">
            {visibleMonths.map((month) => {
              const cells = buildMonthDates(month);
              const planStart = parseDateInput(startDate);
              const planEnd = addDays(planStart, 89);

              return (
                <Card key={monthKey(month)} className="border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                  <CardHeader className="border-b border-slate-200 dark:border-slate-800"><CardTitle className="font-serif text-xl">{monthLabel(month)}</CardTitle></CardHeader>
                  <CardContent className="p-0">
                    <div className="grid grid-cols-7 border-b border-slate-200 dark:border-slate-800">
                      {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day) => <div key={day} className="p-2 text-center text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">{day}</div>)}
                    </div>
                    <div className="grid grid-cols-7">
                      {cells.map((cell) => {
                        const key = formatDateKey(cell);
                        const idea = ideasByDate.get(key);
                        const inMonth = cell.getMonth() === month.getMonth();
                        const inPlan = cell >= planStart && cell <= planEnd;
                        const dayNumber = calendarDays.findIndex((d) => d.date === key) + 1;

                        return (
                          <div key={key} className={cn("min-h-[150px] border-r border-b border-slate-200 dark:border-slate-800 p-2 align-top", !inMonth && "bg-slate-50/70 dark:bg-slate-950/40", inMonth && "bg-white dark:bg-slate-950/20")}>
                            <div className={cn("mb-2 flex items-center justify-between", !inMonth && "opacity-40")}>
                              <span className={cn("text-xs font-semibold", key === formatDateKey(new Date()) && "rounded-full bg-emerald-600 px-2 py-0.5 text-white")}>{cell.getDate()}</span>
                              {idea && <span className="text-[10px] font-medium text-emerald-600 dark:text-emerald-400">Day {dayNumber}</span>}
                            </div>
                            {idea && inPlan ? (
                              <div className="rounded-lg border border-emerald-200 bg-emerald-50/70 p-2 dark:border-emerald-900/50 dark:bg-emerald-950/20">
                                <p className="line-clamp-3 text-xs font-semibold leading-4 text-slate-800 dark:text-slate-100">{idea.title}</p>
                                <div className="mt-2 flex items-start gap-1 text-[10px] text-slate-500 dark:text-slate-400"><Target className="mt-0.5 size-3 shrink-0" /><span className="line-clamp-2">{idea.keyword}</span></div>
                                <div className="mt-2 flex flex-wrap items-center gap-1">
                                  <span className="rounded bg-indigo-100 px-1.5 py-0.5 text-[9px] text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-300">{idea.intent}</span>
                                  <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[9px] text-slate-600 dark:bg-slate-800 dark:text-slate-300">{idea.contentType || "Blog"}</span>
                                  {idea.status === "published" ? (
                                    <span className="inline-flex items-center gap-1 rounded bg-emerald-100 px-1.5 py-0.5 text-[9px] font-semibold text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300"><CheckCircle2 className="size-2.5" />Published</span>
                                  ) : idea.status === "scheduled" ? (
                                    <span className="inline-flex items-center gap-1 rounded bg-amber-100 px-1.5 py-0.5 text-[9px] font-semibold text-amber-700 dark:bg-amber-500/10 dark:text-amber-300"><Clock3 className="size-2.5" />Scheduled</span>
                                  ) : null}
                                </div>
                              </div>
                            ) : inMonth && inPlan ? <div className="rounded-lg border border-dashed border-slate-200 p-3 text-center text-[10px] text-slate-400 dark:border-slate-800">No content scheduled</div> : null}
                          </div>
                        );
                      })}
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>

          <div className="grid gap-4">
            {ideas.map((idea, idx) => {
              const date = addDays(parseDateInput(startDate), idx);
              return (
                <Card key={`${formatDateKey(date)}-${idx}`} className="border-slate-200 dark:border-slate-800 shadow-sm hover:shadow-md transition-shadow">
                  <CardHeader>
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <div className="mb-2 inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400"><Calendar className="size-3" />Day {idx + 1} · {date.toLocaleDateString()}</div>
                        <CardTitle className="font-serif text-lg">{idea.title}</CardTitle>
                        <div className="flex flex-wrap items-center gap-3 mt-2 text-xs">
                          <span className="flex items-center gap-1 text-slate-500"><Target className="size-3" /> {idea.keyword}</span>
                          <span className="text-slate-400">·</span>
                          <span className="px-2 py-0.5 rounded-md bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">{idea.intent}</span>
                          <span className={cn("px-2 py-0.5 rounded-md", idea.difficulty.toLowerCase() === "low" ? "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/10" : "bg-amber-50 text-amber-600 dark:bg-amber-500/10")}>{idea.difficulty}</span>
                          <span className="px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300">{idea.contentType || "Blog"}</span>
                        </div>
                      </div>
                      <Button
                        variant={idea.status === "published" ? "default" : "outline"}
                        size="sm"
                        disabled={idea.status === "published" || idea.status === "scheduled"}
                        onClick={() => { setWriterIdea(idea); setWriterDay(idx + 1); setWriterDate(formatDateKey(date)); setWriterOpen(true); }}
                        className={idea.status === "published" ? "bg-emerald-600 text-white hover:bg-emerald-700" : ""}
                      >
                        {idea.status === "published" ? <><CheckCircle2 className="size-3.5" /> Published</> : idea.status === "scheduled" ? <><Clock3 className="size-3.5" /> Scheduled</> : <><RefreshCw className="size-3.5" /> Write Content</>}
                      </Button>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Suggested Outline:</p>
                    <ul className="space-y-1.5">
                      {idea.outline.map((point, i) => <li key={i} className="text-sm text-slate-600 dark:text-slate-400 flex items-center gap-2"><span className="size-1.5 rounded-full bg-emerald-500" />{point}</li>)}
                    </ul>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </>
      )}

      {!loading && ideas.length === 0 && !error && (
        <Card className="border-slate-200 dark:border-slate-800 shadow-sm"><CardContent className="p-12 text-center"><Calendar className="size-10 text-slate-300 dark:text-slate-700 mx-auto mb-3" /><p className="text-slate-500 dark:text-slate-400">No 90-day content plan yet. Generate one to get started.</p></CardContent></Card>
      )}

      <ContentAutoScheduler
        open={autoSchedulerOpen}
        onClose={() => setAutoSchedulerOpen(false)}
        ideas={ideas}
        planId={currentPlanId}
        startDate={startDate}
        onArticleUpdated={(dayNumber, article) => {
          setIdeas((current) => current.map((item, index) =>
            index === dayNumber - 1 ? { ...item, status: article?.status || item.status } : item
          ));
        }}
      />

      <ContentWriter
        open={writerOpen}
        onClose={() => setWriterOpen(false)}
        idea={writerIdea}
        planId={currentPlanId}
        dayNumber={writerDay}
        scheduledDate={writerDate}
        onSaved={(article) => {
          setIdeas((current) => current.map((item, index) =>
            index === writerDay - 1 ? { ...item, status: article?.status || item.status } : item
          ));
        }}
      />
    </div>
  );
}
