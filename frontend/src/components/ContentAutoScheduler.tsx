import { useState } from "react";
import { AlertCircle, Clock3, Loader2, Play, X } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useClaude } from "@/components/ClaudeProvider";
import { api } from "@/lib/api";
import { generateAIInternalLinks } from "@/lib/wordpressInternalLinks";

interface Idea { title: string; keyword: string; intent?: string; contentType?: string; outline: string[]; }
interface Props { open: boolean; onClose: () => void; ideas: Idea[]; planId: string | null; startDate: string; }

function parseResponse(raw: string): any {
  const cleaned = raw.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/i, "").trim();
  try { return JSON.parse(cleaned); } catch {
    const a = cleaned.indexOf("{"); const b = cleaned.lastIndexOf("}");
    if (a >= 0 && b > a) return JSON.parse(cleaned.slice(a, b + 1));
    throw new Error("Claude returned invalid article JSON.");
  }
}
function toLocalIso(date: string, time: string): string {
  const value = new Date(`${date}T${time}:00`);
  const offsetMinutes = -value.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? "+" : "-";
  const absolute = Math.abs(offsetMinutes);
  const hours = String(Math.floor(absolute / 60)).padStart(2, "0");
  const minutes = String(absolute % 60).padStart(2, "0");
  return `${date}T${time}:00${sign}${hours}:${minutes}`;
}

function addDays(date: string, days: number) {
  const d = new Date(`${date}T12:00:00`); d.setDate(d.getDate() + days);
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`;
}

export function ContentAutoScheduler({ open, onClose, ideas, planId, startDate }: Props) {
  const { isReady, generateContent } = useClaude();
  const [site, setSite] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [time, setTime] = useState("10:00");
  const [running, setRunning] = useState(false);
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const run = async () => {
    if (!isReady) { setError("Claude AI is not ready. Check your API settings and billing."); return; }
    if (ideas.length !== 90) { setError("A complete 90-day plan with exactly 90 items is required."); return; }
    if (!site.trim() || !username.trim() || !password.trim()) { setError("WordPress site, username and Application Password are required."); return; }
    setRunning(true); setProgress(0); setError(null); setMessage("Starting 90-day publishing queue...");
    let completed = 0;
    let internalLinkCandidates: any[] | null = null;
    for (let i = 0; i < ideas.length; i += 1) {
      const idea = ideas[i];
      try {
        setMessage(`Writing Day ${i + 1}/90: ${idea.title}`);
        const raw = await generateContent(`Write a production-ready SEO article for this planned item. Return ONLY JSON with meta_title, meta_description, slug, article_html.\nTitle: ${idea.title}\nPrimary keyword: ${idea.keyword}\nSearch intent: ${idea.intent || "Informational"}\nContent type: ${idea.contentType || "Blog"}\nOutline:\n${idea.outline.map(x => `- ${x}`).join("\n")}\nRequirements: original human-sounding content; satisfy search intent; natural keyword use; semantic H2/H3 HTML; useful bullets/FAQ where appropriate; no fabricated statistics, rankings, backlinks, credentials, sources or claims; no markdown; WordPress-ready HTML; approximately 1200-1800 words.`);
        const article = parseResponse(raw);
        if (!article.article_html || String(article.article_html).length < 500) throw new Error("Article content was too short.");
        const saved = await api.post("/api/content-automation/articles", {
          plan_id: planId, day_number: i + 1, title: idea.title, keyword: idea.keyword,
          article_html: String(article.article_html), meta_title: String(article.meta_title || idea.title),
          meta_description: String(article.meta_description || ""), slug: String(article.slug || "")
        }) as any;
        if (internalLinkCandidates === null) {
          setMessage("Analyzing WordPress pages and posts for internal links...");
          const candidateResponse = await api.post(`/api/content-automation/articles/${saved.article.id}/internal-link-candidates`, {
            wordpress_site: site.trim(),
            wordpress_username: username.trim(),
            wordpress_application_password: password.trim(),
          }) as { candidates?: any[] };
          internalLinkCandidates = candidateResponse.candidates ?? [];
        }

        let internalLinks: Array<{ target_url: string; anchor_text: string; reason?: string }> = [];
        if (internalLinkCandidates.length > 0) {
          internalLinks = await generateAIInternalLinks(
            generateContent,
            String(article.article_html),
            idea.title,
            idea.keyword,
            internalLinkCandidates,
          );
        }

        const scheduledDate = addDays(startDate, i);
        setMessage(`Scheduling Day ${i + 1}/90 on WordPress with ${internalLinks.length} AI internal links...`);
        await api.post(`/api/content-automation/articles/${saved.article.id}/publish/wordpress`, {
          wordpress_site: site.trim(), wordpress_username: username.trim(), wordpress_application_password: password.trim(),
          status: "future", scheduled_at: toLocalIso(scheduledDate, time),
          internal_links: internalLinks,
        });
        completed += 1; setProgress(completed);
      } catch (err: any) {
        // Continue the queue so one failed article does not cancel the remaining 90 days.
        setError(`Day ${i + 1} failed: ${err?.data?.detail || err?.message || "Unknown error"}. Completed ${completed}/90; the remaining queue will continue.`);
      }
    }
    setMessage(`Automation finished: ${completed}/90 articles scheduled.`);
    setRunning(false);
  };

  return <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
    <Card className="w-full max-w-2xl border-slate-200 shadow-2xl dark:border-slate-800">
      <CardHeader className="flex flex-row items-center justify-between border-b"><div><CardTitle className="font-serif">90-Day WordPress Automation</CardTitle><p className="mt-1 text-sm text-slate-500">AI-write each planned article and schedule it on WordPress.</p></div><Button variant="ghost" size="icon" onClick={onClose} disabled={running}><X className="size-5" /></Button></CardHeader>
      <CardContent className="space-y-4 p-5">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-2 sm:col-span-2"><Label>WordPress Site</Label><Input value={site} onChange={e=>setSite(e.target.value)} placeholder="https://example.com" /></div>
          <div className="space-y-2"><Label>Username</Label><Input value={username} onChange={e=>setUsername(e.target.value)} /></div>
          <div className="space-y-2"><Label>Application Password</Label><Input type="password" value={password} onChange={e=>setPassword(e.target.value)} /></div>
          <div className="space-y-2"><Label>Daily Publishing Time</Label><Input type="time" value={time} onChange={e=>setTime(e.target.value)} /></div>
        </div>
        <div className="rounded-lg border bg-slate-50 p-4 text-sm dark:border-slate-800 dark:bg-slate-900/50"><strong>90 scheduled posts</strong><div className="mt-1 text-slate-500">Day 1: {startDate} at {time} · Day 90: {addDays(startDate,89)} at {time}</div><div className="mt-1 text-xs text-slate-500">Articles are generated one at a time and sent to WordPress as native future posts.</div></div>
        {running && <div className="space-y-2"><div className="flex justify-between text-xs"><span>{message}</span><span>{progress}/90</span></div><div className="h-2 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800"><div className="h-full bg-emerald-600 transition-all" style={{width:`${(progress/90)*100}%`}} /></div></div>}
        {error && <div className="flex gap-2 rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 dark:border-rose-900/50 dark:bg-rose-900/10 dark:text-rose-400"><AlertCircle className="size-4 shrink-0" />{error}</div>}
        {!running && message && <div className="rounded-md bg-emerald-50 p-3 text-sm text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400">{message}</div>}
        <Button className="w-full bg-indigo-600 text-white hover:bg-indigo-700" onClick={run} disabled={running || ideas.length !== 90}><Play className="size-4" />{running ? <><Loader2 className="size-4 animate-spin" /> Processing {progress}/90</> : <><Clock3 className="size-4" /> Generate & Schedule All 90 Days</>}</Button>
      </CardContent>
    </Card>
  </div>;
}
