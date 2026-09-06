import { useMemo, useState } from "react";
import { AlertCircle, CheckCircle2, Clock3, FileText, Loader2, Send, Sparkles, X } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useClaude } from "@/components/ClaudeProvider";
import { api } from "@/lib/api";
import { generateAIInternalLinks } from "@/lib/wordpressInternalLinks";

export interface ContentWriterIdea {
  title: string;
  keyword: string;
  intent?: string;
  contentType?: string;
  outline: string[];
}

interface Props {
  open: boolean;
  onClose: () => void;
  idea: ContentWriterIdea | null;
  planId: string | null;
  dayNumber: number;
  scheduledDate: string;
  onSaved?: (article: any) => void;
}

function cleanHtml(value: string): string {
  return value.replace(/^```(?:html)?\s*/i, "").replace(/\s*```$/i, "").trim();
}

function sanitizeJsonControlCharacters(value: string): string {
  let result = "";
  let inString = false;
  let escaped = false;

  for (let i = 0; i < value.length; i += 1) {
    const char = value[i];

    if (inString) {
      if (escaped) {
        result += char;
        escaped = false;
        continue;
      }
      if (char === "\\") {
        result += char;
        escaped = true;
        continue;
      }
      if (char === '"') {
        result += char;
        inString = false;
        continue;
      }
      const code = char.charCodeAt(0);
      if (code < 0x20) {
        if (char === "\n") result += "\\n";
        else if (char === "\r") result += "\\r";
        else if (char === "\t") result += "\\t";
        else if (char === "\b") result += "\\b";
        else if (char === "\f") result += "\\f";
        else result += `\\u${code.toString(16).padStart(4, "0")}`;
      } else {
        result += char;
      }
      continue;
    }

    if (char === '"') inString = true;
    result += char;
  }
  return result;
}

function extractJsonObject(value: string): string {
  const start = value.indexOf("{");
  if (start < 0) throw new Error("Claude returned no JSON object.");

  let depth = 0;
  let inString = false;
  let escaped = false;

  for (let i = start; i < value.length; i += 1) {
    const char = value[i];
    if (inString) {
      if (escaped) escaped = false;
      else if (char === "\\") escaped = true;
      else if (char === '"') inString = false;
      continue;
    }
    if (char === '"') inString = true;
    else if (char === "{") depth += 1;
    else if (char === "}") {
      depth -= 1;
      if (depth === 0) return value.slice(start, i + 1);
    }
  }
  throw new Error("Claude returned incomplete JSON.");
}

function parseTaggedArticle(value: string): any | null {
  const cleaned = value.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  const get = (name: string): string => {
    const match = cleaned.match(new RegExp(`^${name}\\s*:\\s*(.*?)\\s*$`, "im"));
    return match?.[1]?.trim() ?? "";
  };

  const articleMatch = cleaned.match(/ARTICLE_HTML_BEGIN\s*\n?([\\s\\S]*?)\n?ARTICLE_HTML_END/i);
  if (!articleMatch) return null;

  const articleHtml = articleMatch[1].trim();
  if (!articleHtml) return null;

  return {
    meta_title: get("META_TITLE"),
    meta_description: get("META_DESCRIPTION"),
    slug: get("SLUG"),
    article_html: articleHtml,
  };
}

function parseJsonArticle(value: string): any | null {
  const cleaned = value
    .replace(/^\s*```(?:json)?\s*/i, "")
    .replace(/\s*```\s*$/i, "")
    .trim();

  const attempts = [cleaned];
  try {
    attempts.push(extractJsonObject(cleaned));
  } catch {
    // Continue to the repair attempt below.
  }

  for (const candidate of attempts) {
    try {
      return JSON.parse(candidate);
    } catch {
      try {
        return JSON.parse(sanitizeJsonControlCharacters(candidate));
      } catch {
        // Try the next representation.
      }
    }
  }
  return null;
}

function parseArticleResponse(value: string): any {
  // Preferred protocol: plain-text delimiters. This avoids JSON escaping
  // entirely for large multiline WordPress HTML documents.
  const tagged = parseTaggedArticle(value);
  if (tagged) return tagged;

  // Backward-compatible JSON support for older Claude responses.
  const json = parseJsonArticle(value);
  if (json) return json;

  throw new Error(
    "Claude returned an invalid article response. The response was neither the required tagged format nor valid JSON."
  );
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

export function ContentWriter({ open, onClose, idea, planId, dayNumber, scheduledDate, onSaved }: Props) {
  const { isReady, status, generateContent } = useClaude();
  const [loading, setLoading] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [article, setArticle] = useState<any>(null);
  const [site, setSite] = useState("");
  const [username, setUsername] = useState("");
  const [appPassword, setAppPassword] = useState("");
  const [publishMode, setPublishMode] = useState<"draft" | "future" | "publish">("future");
  const [publishDate, setPublishDate] = useState(scheduledDate);
  const [publishTime, setPublishTime] = useState("10:00");
  const [publishInfo, setPublishInfo] = useState<{ featuredImageUrl?: string; seoMetadataApplied?: boolean; internalLinksApplied?: Array<{ target_url: string; anchor_text: string }> } | null>(null);

  const readyMessage = useMemo(() => {
    if (status === "billing_required") return "Anthropic billing is required.";
    if (status === "invalid_api_key") return "Anthropic API key is invalid.";
    return "Claude AI is currently unavailable.";
  }, [status]);

  if (!open || !idea) return null;

  const writeArticle = async () => {
    if (!isReady) { setError(readyMessage); return; }
    setLoading(true); setError(null);
    try {
      const prompt = `Write a production-ready SEO article for this planned content item.
Title: ${idea.title}
Primary keyword: ${idea.keyword}
Search intent: ${idea.intent || "Informational"}
Content type: ${idea.contentType || "Blog"}
Outline:
${idea.outline.map((x) => `- ${x}`).join("\n")}

Requirements:
- Write original, useful, human-sounding content; do not mention AI.
- Satisfy the search intent and the exact topic.
- Use the primary keyword naturally, never keyword-stuff it.
- Add useful secondary terminology only where genuinely relevant.
- Use semantic H2/H3 headings, short paragraphs, bullets where useful, and a concise FAQ when appropriate.
- Do not invent statistics, search volume, rankings, customer results, credentials, citations, or claims that cannot be supported by the topic.
- Do not add fake sources or fake links.
- Do NOT return JSON. JSON escaping is intentionally not used for article HTML.
- Return ONLY this exact tagged format, with no commentary and no code fences:
META_TITLE: a concise SEO title
META_DESCRIPTION: a useful meta description
SLUG: a clean URL slug
ARTICLE_HTML_BEGIN
<article HTML here>
ARTICLE_HTML_END
- article_html must contain semantic HTML suitable for WordPress post content, without html/head/body wrappers.
- Never put ARTICLE_HTML_END inside the article itself.
- Do not use markdown outside the HTML.
- Aim for approximately 1200-1800 words unless the topic genuinely requires less.
`;
      const recoveryPrompt = `${prompt}

CRITICAL RECOVERY RULE: Output the tagged format exactly. Do not output JSON, markdown fences, explanations, or introductory text.`;
      let raw = await generateContent(prompt);
      let parsed: any | null = null;
      let firstParseError: unknown = null;

      try {
        parsed = parseArticleResponse(raw);
      } catch (parseError) {
        firstParseError = parseError;
      }

      // If Claude ignored the output protocol or the response was truncated,
      // make one recovery request instead of surfacing the parser error immediately.
      if (!parsed?.article_html || String(parsed.article_html).length < 500) {
        raw = await generateContent(recoveryPrompt);
        try {
          parsed = parseArticleResponse(raw);
        } catch (recoveryError) {
          const firstMessage = firstParseError instanceof Error ? firstParseError.message : "";
          const recoveryMessage = recoveryError instanceof Error ? recoveryError.message : "";
          throw new Error(recoveryMessage || firstMessage || "Claude did not return a readable article.");
        }
      }

      if (!parsed?.article_html || String(parsed.article_html).length < 500) {
        throw new Error("Claude did not return enough article content after the recovery attempt.");
      }
      const payload = {
        plan_id: planId,
        day_number: dayNumber,
        title: idea.title,
        keyword: idea.keyword,
        article_html: cleanHtml(String(parsed.article_html)),
        meta_title: String(parsed.meta_title || idea.title).slice(0, 500),
        meta_description: String(parsed.meta_description || "").slice(0, 1000),
        slug: String(parsed.slug || "").slice(0, 500),
      };
      const saved = await api.post("/api/content-automation/articles", payload);
      setArticle((saved as any).article);
      onSaved?.((saved as any).article);
    } catch (err: any) {
      setError(err?.data?.detail || err?.message || "Failed to write the article.");
    } finally { setLoading(false); }
  };

  const publish = async () => {
    if (!article) { setError("Write the article first."); return; }
    if (!site.trim() || !username.trim() || !appPassword.trim()) { setError("WordPress site, username and Application Password are required."); return; }
    if (publishMode === "future" && (!publishDate || !publishTime)) { setError("Choose a publishing date and time."); return; }
    setPublishing(true); setError(null); setPublishInfo(null);
    try {
      const scheduledAt = publishMode === "future" ? toLocalIso(publishDate, publishTime) : null;
      const credentials = {
        wordpress_site: site.trim(),
        wordpress_username: username.trim(),
        wordpress_application_password: appPassword.trim(),
      };

      // Discover the site's real published pages/posts, then let Claude choose
      // only semantically useful targets and exact anchor phrases from the article.
      setError(null);
      const candidateResponse = await api.post(`/api/content-automation/articles/${article.id}/internal-link-candidates`, credentials) as { candidates?: any[] };
      const candidates = candidateResponse.candidates ?? [];
      let internalLinks: Array<{ target_url: string; anchor_text: string; reason?: string }> = [];
      if (candidates.length > 0) {
        internalLinks = await generateAIInternalLinks(
          generateContent,
          article.article_html,
          article.title,
          article.keyword,
          candidates,
        );
      }

      const result = await api.post(`/api/content-automation/articles/${article.id}/publish/wordpress`, {
        ...credentials,
        status: publishMode,
        scheduled_at: scheduledAt,
        internal_links: internalLinks,
      });
      setArticle((result as any).article);
      setPublishInfo({
        featuredImageUrl: (result as any).wordpress?.featured_image_url,
        seoMetadataApplied: (result as any).wordpress?.seo_metadata_applied,
        internalLinksApplied: (result as any).wordpress?.internal_links_applied ?? [],
      });
      onSaved?.((result as any).article);
    } catch (err: any) {
      setError(err?.data?.detail || err?.message || "WordPress publication failed.");
    } finally { setPublishing(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <Card className="max-h-[92vh] w-full max-w-6xl overflow-hidden border-slate-200 shadow-2xl dark:border-slate-800">
        <CardHeader className="flex flex-row items-center justify-between border-b">
          <div>
            <CardTitle className="flex items-center gap-2 font-serif"><FileText className="size-5 text-emerald-600" />Content Writer · Day {dayNumber}</CardTitle>
            <p className="mt-1 text-sm text-slate-500">{idea.title} · {idea.keyword}</p>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose}><X className="size-5" /></Button>
        </CardHeader>
        <CardContent className="max-h-[calc(92vh-90px)] overflow-y-auto p-5">
          <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
            <div className="space-y-4">
              <div className="rounded-lg border bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-900/50">
                <p className="text-sm font-semibold">Planned outline</p>
                <ul className="mt-2 space-y-1 text-sm text-slate-600 dark:text-slate-400">{idea.outline.map((x, i) => <li key={i}>• {x}</li>)}</ul>
              </div>
              {!article ? (
                <Button onClick={writeArticle} disabled={loading || !isReady} className="bg-emerald-600 text-white hover:bg-emerald-700">
                  {loading ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />} {loading ? "Writing article..." : "Write SEO Article"}
                </Button>
              ) : (
                <div className="space-y-3">
                  <div className="flex flex-wrap gap-2">
                    <Button variant="outline" onClick={writeArticle} disabled={loading}><Sparkles className="size-4" /> Regenerate</Button>
                    <Button variant="outline" onClick={() => setArticle({ ...article, article_html: article.article_html })}><CheckCircle2 className="size-4" /> Saved</Button>
                  </div>
                  <div className="rounded-lg border p-5 dark:border-slate-800">
                    <div className="mb-4 space-y-1"><h2 className="text-xl font-bold">{article.meta_title}</h2><p className="text-sm text-slate-500">{article.meta_description}</p></div>
                    <div className="prose prose-slate max-w-none dark:prose-invert" dangerouslySetInnerHTML={{ __html: article.article_html }} />
                  </div>
                </div>
              )}
            </div>

            <div className="space-y-4 rounded-lg border p-4 dark:border-slate-800">
              <div><p className="font-semibold">WordPress Publishing</p><p className="mt-1 text-xs text-slate-500">Credentials are used for this request and are not saved by this feature.</p></div>
              <div className="space-y-2"><Label>WordPress Site</Label><Input value={site} onChange={e => setSite(e.target.value)} placeholder="https://example.com" /></div>
              <div className="space-y-2"><Label>Username</Label><Input value={username} onChange={e => setUsername(e.target.value)} placeholder="WordPress username" /></div>
              <div className="space-y-2"><Label>Application Password</Label><Input type="password" value={appPassword} onChange={e => setAppPassword(e.target.value)} placeholder="Application Password" /></div>
              <div className="grid grid-cols-3 gap-2">
                <Button variant={publishMode === "draft" ? "default" : "outline"} onClick={() => setPublishMode("draft")} className="text-xs">Draft</Button>
                <Button variant={publishMode === "future" ? "default" : "outline"} onClick={() => setPublishMode("future")} className="text-xs"><Clock3 className="size-3" /> Schedule</Button>
                <Button variant={publishMode === "publish" ? "default" : "outline"} onClick={() => setPublishMode("publish")} className="text-xs">Publish</Button>
              </div>
              {publishMode === "future" && <><div className="mb-2 rounded-md bg-slate-50 p-2 text-[11px] text-slate-500 dark:bg-slate-900/50">Schedule time uses your browser's local timezone ({Intl.DateTimeFormat().resolvedOptions().timeZone || "local time"}).</div><div className="grid grid-cols-2 gap-2"><div className="space-y-2"><Label>Date</Label><Input type="date" value={publishDate} onChange={e => setPublishDate(e.target.value)} /></div><div className="space-y-2"><Label>Time</Label><Input type="time" value={publishTime} onChange={e => setPublishTime(e.target.value)} /></div></div></>}
              <Button onClick={publish} disabled={!article || publishing} className="w-full bg-indigo-600 text-white hover:bg-indigo-700"><Send className="size-4" />{publishing ? "Sending to WordPress..." : publishMode === "future" ? "Schedule on WordPress" : publishMode === "publish" ? "Publish Now" : "Create WordPress Draft"}</Button>
              <div className="rounded-md border bg-slate-50 p-3 text-xs text-slate-600 dark:border-slate-800 dark:bg-slate-900/50 dark:text-slate-300">
                <strong>Automatic publishing package:</strong> featured image, SEO title, meta description, focus keyphrase and AI-selected internal links are applied to WordPress.
              </div>
              {article?.status && <div className="rounded-md bg-emerald-50 p-3 text-xs text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400">Status: <strong>{article.status}</strong>{publishInfo?.seoMetadataApplied ? " · Yoast SEO saved" : null}{publishInfo?.featuredImageUrl ? <> · Featured image uploaded</> : null}{publishInfo?.internalLinksApplied?.length ? <> · {publishInfo.internalLinksApplied.length} internal links added</> : null}{article.wordpress_url ? <> · <a className="underline" href={article.wordpress_url} target="_blank" rel="noreferrer">Open post</a></> : null}</div>}
            </div>
          </div>
          {error && <div className="mt-4 flex items-start gap-2 rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700 dark:border-rose-900/50 dark:bg-rose-900/10 dark:text-rose-400"><AlertCircle className="mt-0.5 size-4 shrink-0" />{error}</div>}
        </CardContent>
      </Card>
    </div>
  );
}
