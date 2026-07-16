import { useSyncExternalStore } from "use-sync-external-store";

// ─── Types ──────────────────────────────────────────────────────────

export type Severity = "critical" | "warning" | "passed" | "info";

export interface Finding {
  agent: string;
  check: string;
  status: Severity;
  detail: string;
  recommendation: string;
}

export interface AuditResult {
  id: string;
  clientId: string;
  url: string;
  primaryKeyword: string;
  location: string;
  competitors: string[];
  createdAt: number;
  scores: Record<string, number>;
  findings: Finding[];
}

export interface Client {
  id: string;
  businessName: string;
  website: string;
  industry: string;
  country: string;
  city: string;
  primaryKeywords: string[];
  secondaryKeywords: string[];
  competitors: string[];
  monthlyGoals: string;
  createdAt: number;
}

export interface Task {
  id: string;
  title: string;
  priority: "high" | "medium" | "low";
  category: string;
  done: boolean;
}

export type View =
  | "dashboard"
  | "clients"
  | "new-audit"
  | "reports"
  | "content-planner"
  | "keyword-research"
  | "keyword-clusters"
  | "competitors"
  | "internal-linking"
  | "backlinks"
  | "local-seo"
  | "schema"
  | "eeat"
  | "ai-search"
  | "search-console"
  | "analytics"
  | "settings"
  | "documentation";

// ─── Audit Agents List ──────────────────────────────────────────────

export const AUDIT_AGENTS = [
  "Technical SEO",
  "Content SEO",
  "Local SEO",
  "Schema",
  "EEAT",
  "Internal Linking",
  "Competitor",
  "Backlink",
  "AI Search",
  "Claude AI Deep Analysis",
];

// ─── Store Implementation ───────────────────────────────────────────

interface State {
  view: View;
  clients: Client[];
  audits: AuditResult[];
  tasks: Task[];
  apiKey: string;
}

const STORAGE_KEY = "boost-rankers-seo-os-v1";

function loadState(): State {
  if (typeof window === "undefined") {
    return defaultState();
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      return { ...defaultState(), ...parsed };
    }
  } catch (e) {
    // ignore
  }
  return defaultState();
}

function defaultState(): State {
  return {
    view: "dashboard",
    clients: seedClients(),
    audits: seedAudits(),
    tasks: seedTasks(),
    apiKey: "",
  };
}

function saveState(state: State) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch (e) {
    // ignore
  }
}

let state: State = loadState();
const listeners = new Set<() => void>();

function emitChange() {
  saveState(state);
  listeners.forEach((l) => l());
}

function setState(next: Partial<State>) {
  state = { ...state, ...next };
  emitChange();
}

export function useStore() {
  const subscribe = (listener: () => void) => {
    listeners.add(listener);
    return () => listeners.delete(listener);
  };
  const getSnapshot = () => state;

  const snap = useSyncExternalStore(subscribe, getSnapshot, getSnapshot);

  return {
    ...snap,
    setView: (view: View) => setState({ view }),
    addClient: (client: Omit<Client, "id" | "createdAt">) => {
      const newClient: Client = {
        ...client,
        id: `c${Date.now()}`,
        createdAt: Date.now(),
      };
      setState({ clients: [newClient, ...state.clients] });
    },
    addAudit: (audit: AuditResult) => {
      if (state.audits.find((a) => a.id === audit.id)) return;
      setState({ audits: [audit, ...state.audits] });
    },
    toggleTask: (id: string) => {
      setState({
        tasks: state.tasks.map((t) => (t.id === id ? { ...t, done: !t.done } : t)),
      });
    },
    setApiKey: (apiKey: string) => setState({ apiKey }),
  };
}

// ─── Seed Data ──────────────────────────────────────────────────────

function seedClients(): Client[] {
  return [
    {
      id: "c1",
      businessName: "Apex Roofing Co.",
      website: "https://apexroofing.com",
      industry: "Construction",
      country: "USA",
      city: "Denver, CO",
      primaryKeywords: ["roof repair denver", "roofing contractor"],
      secondaryKeywords: ["roof replacement", "gutter installation"],
      competitors: ["https://competitor1.com", "https://competitor2.com"],
      monthlyGoals: "Increase organic traffic by 20% and rank top 3 for primary keywords.",
      createdAt: Date.now() - 86400000 * 5,
    },
    {
      id: "c2",
      businessName: "Bright Smile Dental",
      website: "https://brightsmiledental.com",
      industry: "Healthcare",
      country: "USA",
      city: "Austin, TX",
      primaryKeywords: ["dentist austin", "teeth whitening"],
      secondaryKeywords: ["dental implants", "emergency dentist"],
      competitors: ["https://dentalcomp1.com"],
      monthlyGoals: "Generate 30 new patient leads via organic search.",
      createdAt: Date.now() - 86400000 * 12,
    },
  ];
}

function seedAudits(): AuditResult[] {
  return [
    {
      id: "a1",
      clientId: "c1",
      url: "https://apexroofing.com",
      primaryKeyword: "roof repair denver",
      location: "Denver, CO",
      competitors: ["https://competitor1.com"],
      createdAt: Date.now() - 86400000 * 2,
      scores: {
        Technical: 72,
        Content: 64,
        Local: 81,
        Schema: 45,
        EEAT: 58,
        "Internal Linking": 67,
        Competitor: 70,
        Backlink: 55,
        "AI Search": 62,
        "Claude AI Deep Analysis": 68,
      },
      findings: [
        { agent: "Technical SEO", check: "HTTPS", status: "passed", detail: "Valid SSL certificate", recommendation: "No action needed" },
        { agent: "Technical SEO", check: "Sitemap", status: "warning", detail: "Sitemap missing last modified dates", recommendation: "Add lastmod tags to sitemap entries" },
        { agent: "Content SEO", check: "Content Depth", status: "warning", detail: "Homepage has 412 words", recommendation: "Expand to 800+ words with service details" },
        { agent: "Local SEO", check: "NAP Consistency", status: "passed", detail: "Name, address, phone consistent", recommendation: "No action needed" },
        { agent: "Schema", check: "LocalBusiness Schema", status: "critical", detail: "Missing LocalBusiness JSON-LD", recommendation: "Add LocalBusiness schema with NAP details" },
        { agent: "EEAT", check: "Author Info", status: "critical", detail: "No author bios on blog posts", recommendation: "Add author bylines with credentials" },
      ],
    },
  ];
}

function seedTasks(): Task[] {
  return [
    { id: "t1", title: "Fix missing LocalBusiness schema on Apex Roofing", priority: "high", category: "Schema", done: false },
    { id: "t2", title: "Add 500 words to Bright Smile homepage", priority: "medium", category: "Content", done: false },
    { id: "t3", title: "Submit XML sitemap to Google Search Console", priority: "high", category: "Technical", done: false },
    { id: "t4", title: "Build 5 citation links for Apex Roofing", priority: "medium", category: "Local SEO", done: false },
    { id: "t5", title: "Write author bio pages for blog authors", priority: "low", category: "EEAT", done: true },
  ];
}

// ─── Audit Simulator (Fallback) ──────────────────────────────────────

export function generateAudit(url: string, keyword: string, location: string, competitors: string[]): AuditResult {
  const scores: Record<string, number> = {};
  const findings: Finding[] = [];

  AUDIT_AGENTS.forEach((agent) => {
    const agentFindings = generateAgentFindings(agent, url, keyword, location, competitors);
    findings.push(...agentFindings);
    const key = agent === "Technical SEO" ? "Technical" : agent === "Content SEO" ? "Content" : agent;
    scores[key] = computeScore(agentFindings);
  });

  return {
    id: `a${Date.now()}`,
    clientId: "",
    url,
    primaryKeyword: keyword,
    location,
    competitors,
    createdAt: Date.now(),
    scores,
    findings,
  };
}

function generateAgentFindings(agent: string, url: string, keyword: string, location: string, competitors: string[]): Finding[] {
  const findings: Finding[] = [];

  if (agent === "Technical SEO") {
    findings.push({ agent, check: "HTTP Status", status: "passed", detail: "Site returns 200 OK", recommendation: "No action needed" });
    findings.push({ agent, check: "HTTPS", status: url.startsWith("https") ? "passed" : "critical", detail: url.startsWith("https") ? "Valid SSL" : "No SSL detected", recommendation: url.startsWith("https") ? "No action needed" : "Install SSL certificate" });
    findings.push({ agent, check: "XML Sitemap", status: "warning", detail: "Sitemap found but missing lastmod", recommendation: "Add lastmod dates to sitemap" });
    findings.push({ agent, check: "Core Web Vitals", status: "warning", detail: "LCP 2.8s (needs improvement)", recommendation: "Optimize images and reduce JS" });
  } else if (agent === "Content SEO") {
    findings.push({ agent, check: "Content Depth", status: "warning", detail: "Page has 450 words", recommendation: "Expand to 800+ words" });
    findings.push({ agent, check: "Keyword in Title", status: keyword ? "passed" : "critical", detail: keyword ? `Title contains '${keyword}'` : "No keyword specified", recommendation: keyword ? "No action needed" : "Specify a primary keyword" });
    findings.push({ agent, check: "Heading Structure", status: "warning", detail: "Multiple H1s detected", recommendation: "Use only one H1 per page" });
  } else if (agent === "Local SEO") {
    findings.push({ agent, check: "NAP Consistency", status: "passed", detail: "Name, address, phone consistent", recommendation: "No action needed" });
    findings.push({ agent, check: "Location in Content", status: location ? "passed" : "warning", detail: location ? `'${location}' found in content` : "No location specified", recommendation: location ? "No action needed" : "Add location to content" });
    findings.push({ agent, check: "Google Maps", status: "warning", detail: "No map embed found", recommendation: "Embed Google Map on contact page" });
  } else if (agent === "Schema") {
    findings.push({ agent, check: "Organization Schema", status: "passed", detail: "Organization JSON-LD found", recommendation: "No action needed" });
    findings.push({ agent, check: "LocalBusiness Schema", status: "critical", detail: "Missing LocalBusiness schema", recommendation: "Add LocalBusiness JSON-LD" });
    findings.push({ agent, check: "FAQ Schema", status: "warning", detail: "No FAQ schema found", recommendation: "Add FAQPage schema" });
  } else if (agent === "EEAT") {
    findings.push({ agent, check: "About Page", status: "passed", detail: "About page found", recommendation: "No action needed" });
    findings.push({ agent, check: "Author Info", status: "critical", detail: "No author bios", recommendation: "Add author bylines and bios" });
    findings.push({ agent, check: "Trust Signals", status: "warning", detail: "No testimonials visible", recommendation: "Add customer testimonials" });
  } else if (agent === "Internal Linking") {
    findings.push({ agent, check: "Anchor Text", status: "warning", detail: "Generic 'click here' anchors found", recommendation: "Use descriptive anchor text" });
    findings.push({ agent, check: "Breadcrumbs", status: "passed", detail: "Breadcrumb navigation present", recommendation: "No action needed" });
  } else if (agent === "Competitor") {
    findings.push({ agent, check: "Content Gap", status: competitors.length ? "warning" : "info", detail: competitors.length ? `Competitors have 30% more content` : "No competitors provided", recommendation: "Expand content to match competitors" });
  } else if (agent === "Backlink") {
    findings.push({ agent, check: "Referring Domains", status: "info", detail: "Connect Ahrefs API for data", recommendation: "Integrate backlink API" });
  } else if (agent === "AI Search") {
    findings.push({ agent, check: "Question Coverage", status: "warning", detail: "Few question patterns found", recommendation: "Add FAQ section" });
    findings.push({ agent, check: "Entity Coverage", status: "passed", detail: "Good entity density", recommendation: "No action needed" });
  } else if (agent === "Claude AI Deep Analysis") {
    findings.push({ agent, check: "AI Content Quality", status: "info", detail: "Simulator active — connect backend for Claude analysis", recommendation: "Start the FastAPI backend with ANTHROPIC_API_KEY" });
  }

  return findings;
}

function computeScore(findings: Finding[]): number {
  const weights: Record<Severity, number> = { passed: 100, info: 80, warning: 55, critical: 25 };
  if (findings.length === 0) return 70;
  const total = findings.reduce((sum, f) => sum + weights[f.status], 0);
  return Math.round(total / findings.length);
}