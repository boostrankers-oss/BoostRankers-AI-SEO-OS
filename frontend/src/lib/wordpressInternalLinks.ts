import { api } from "@/lib/api";

export interface WordPressInternalLinkCandidate {
  id: number;
  type: "page" | "post";
  title: string;
  url: string;
  slug?: string;
}

export interface AIInternalLink {
  target_url: string;
  anchor_text: string;
  reason?: string;
}

interface Credentials {
  wordpress_site: string;
  wordpress_username: string;
  wordpress_application_password: string;
}

function parseJson(value: string): any {
  const cleaned = value.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/i, "").trim();
  try {
    return JSON.parse(cleaned);
  } catch {
    const start = cleaned.indexOf("{");
    const end = cleaned.lastIndexOf("}");
    if (start >= 0 && end > start) return JSON.parse(cleaned.slice(start, end + 1));
    throw new Error("Claude returned invalid internal-link JSON.");
  }
}

function tokens(value: string): string[] {
  return value.toLowerCase().replace(/[^a-z0-9\s-]/g, " ").split(/\s+/).filter((x) => x.length >= 3);
}

function rankCandidates(candidates: WordPressInternalLinkCandidate[], title: string, keyword: string) {
  const wanted = new Set([...tokens(title), ...tokens(keyword)]);
  return [...candidates]
    .map((candidate) => {
      const haystack = tokens(`${candidate.title} ${candidate.slug || ""}`);
      const score = haystack.reduce((total, token) => total + (wanted.has(token) ? 1 : 0), 0);
      return { candidate, score };
    })
    .sort((a, b) => b.score - a.score)
    .slice(0, 80)
    .map(({ candidate }) => candidate);
}

export async function loadWordPressInternalLinkCandidates(credentials: Credentials): Promise<WordPressInternalLinkCandidate[]> {
  const response = await api.post("/api/content-automation/wordpress/internal-link-candidates", credentials) as {
    success: boolean;
    candidates?: WordPressInternalLinkCandidate[];
  };
  return response.candidates ?? [];
}

export async function generateAIInternalLinks(
  generateContent: (prompt: string) => Promise<string>,
  articleHtml: string,
  title: string,
  keyword: string,
  candidates: WordPressInternalLinkCandidate[],
): Promise<AIInternalLink[]> {
  if (!candidates.length) return [];

  const ranked = rankCandidates(candidates, title, keyword);
  const textOnly = new DOMParser().parseFromString(articleHtml, "text/html").body.textContent || "";
  const candidateBlock = ranked
    .map((candidate, index) => `${index + 1}. [${candidate.type}] ${candidate.title} | ${candidate.url}`)
    .join("\n");

  const prompt = `You are an expert technical SEO internal-linking strategist.

Article title: ${title}
Primary keyword: ${keyword}

Article text:
${textOnly.slice(0, 14000)}

Available published WordPress pages and posts:
${candidateBlock}

Choose 3 to 6 highly relevant internal-link targets from ONLY the URLs listed above.
Rules:
- Use both pages and posts when genuinely relevant; do not force either type.
- Choose links that improve topical depth, user navigation, conversion paths, and semantic relevance.
- Prefer service/category/hub pages for commercial intent and closely related posts for informational intent.
- Never choose an unrelated URL.
- Never invent, alter, shorten, or normalize a URL. Copy the URL exactly from the candidate list.
- anchor_text MUST be an exact phrase already present in the article text, copied with the same wording and capitalization.
- Prefer natural descriptive anchors over generic anchors such as "click here", "read more", or "learn more".
- Do not select the article itself or duplicate a target URL.
- Do not over-optimize with repeated exact-match keywords.
- Return JSON only in this exact structure:
{"links":[{"target_url":"exact candidate URL","anchor_text":"exact phrase from article","reason":"brief relevance reason"}]}
If there are fewer than 3 genuinely useful opportunities, return only the genuinely useful ones. Never fabricate an opportunity.`;

  const raw = await generateContent(prompt);
  const parsed = parseJson(raw);
  const rawLinks = Array.isArray(parsed?.links) ? parsed.links : [];
  const allowed = new Map(ranked.map((candidate) => [candidate.url.replace(/\/$/, "").toLowerCase(), candidate.url]));
  const seen = new Set<string>();
  const result: AIInternalLink[] = [];

  for (const item of rawLinks) {
    if (!item || typeof item !== "object") continue;
    const suppliedUrl = String(item.target_url || "").trim();
    const canonical = allowed.get(suppliedUrl.replace(/\/$/, "").toLowerCase());
    const anchor = String(item.anchor_text || "").trim();
    if (!canonical || anchor.length < 2 || anchor.length > 160) continue;
    const key = canonical.replace(/\/$/, "").toLowerCase();
    if (seen.has(key)) continue;
    if (!textOnly.toLowerCase().includes(anchor.toLowerCase())) continue;
    seen.add(key);
    result.push({ target_url: canonical, anchor_text: anchor, reason: String(item.reason || "").slice(0, 300) });
    if (result.length >= 6) break;
  }
  return result;
}

export function applyInternalLinks(articleHtml: string, links: AIInternalLink[]): { html: string; applied: AIInternalLink[] } {
  if (!links.length) return { html: articleHtml, applied: [] };
  const parser = new DOMParser();
  const document = parser.parseFromString(articleHtml, "text/html");
  const existingUrls = new Set(
    Array.from(document.querySelectorAll("a[href]"))
      .map((anchor) => (anchor.getAttribute("href") || "").replace(/\/$/, "").toLowerCase())
      .filter(Boolean),
  );
  const applied: AIInternalLink[] = [];

  for (const link of links) {
    if (existingUrls.has(link.target_url.replace(/\/$/, "").toLowerCase())) continue;
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let node: Text | null = null;
    let offset = -1;
    while (walker.nextNode()) {
      const current = walker.currentNode as Text;
      const parent = current.parentElement;
      if (!parent || parent.closest("a,code,pre,script,style,h1,h2,h3,h4,h5,h6")) continue;
      const index = current.data.toLocaleLowerCase().indexOf(link.anchor_text.toLocaleLowerCase());
      if (index >= 0) { node = current; offset = index; break; }
    }
    if (!node || offset < 0) continue;

    const matched = node.data.slice(offset, offset + link.anchor_text.length);
    const anchor = document.createElement("a");
    anchor.href = link.target_url;
    anchor.textContent = matched;
    anchor.rel = "internal";

    const fragment = document.createDocumentFragment();
    fragment.appendChild(document.createTextNode(node.data.slice(0, offset)));
    fragment.appendChild(anchor);
    fragment.appendChild(document.createTextNode(node.data.slice(offset + link.anchor_text.length)));
    node.parentNode?.replaceChild(fragment, node);

    existingUrls.add(link.target_url.replace(/\/$/, "").toLowerCase());
    applied.push(link);
  }

  return { html: document.body.innerHTML, applied };
}
