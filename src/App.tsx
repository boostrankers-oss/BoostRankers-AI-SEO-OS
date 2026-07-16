import { useState } from "react";
import { useStore, type View } from "@/lib/store";
import { Dashboard } from "@/components/Dashboard";
import { NewAudit } from "@/components/NewAudit";
import { Clients } from "@/components/Clients";
import { Settings } from "@/components/Settings";
import { Placeholder } from "@/components/Placeholder";
import {
  LayoutDashboard,
  Users,
  FileSearch,
  FileText,
  CalendarDays,
  Search,
  Network,
  Target,
  Link2,
  Link as LinkIcon,
  MapPin,
  Code2,
  ShieldCheck,
  Bot,
  BarChart3,
  Settings as SettingsIcon,
  HelpCircle,
  Menu,
  X,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS: { id: View; label: string; icon: typeof LayoutDashboard }[] = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "clients", label: "Clients", icon: Users },
  { id: "new-audit", label: "New Audit", icon: FileSearch },
  { id: "reports", label: "Reports", icon: FileText },
  { id: "content-planner", label: "Content Planner", icon: CalendarDays },
  { id: "keyword-research", label: "Keyword Research", icon: Search },
  { id: "keyword-clusters", label: "Keyword Clusters", icon: Network },
  { id: "competitors", label: "Competitors", icon: Target },
  { id: "internal-linking", label: "Internal Linking", icon: Link2 },
  { id: "backlinks", label: "Backlinks", icon: LinkIcon },
  { id: "local-seo", label: "Local SEO", icon: MapPin },
  { id: "schema", label: "Schema", icon: Code2 },
  { id: "eeat", label: "EEAT", icon: ShieldCheck },
  { id: "ai-search", label: "AI Search", icon: Bot },
  { id: "search-console", label: "Search Console", icon: BarChart3 },
  { id: "analytics", label: "Google Analytics", icon: BarChart3 },
  { id: "settings", label: "Settings", icon: SettingsIcon },
  { id: "documentation", label: "Documentation", icon: HelpCircle },
];

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { view, setView } = useStore();

  return (
    <div className="flex h-full flex-col bg-slate-900 text-slate-300">
      <div className="flex h-16 items-center gap-2 border-b border-slate-800 px-6">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500 text-slate-900">
          <Sparkles className="h-5 w-5" />
        </div>
        <span className="font-serif text-lg font-bold text-white">Boost Rankers</span>
      </div>
      <nav className="flex-1 overflow-y-auto px-3 py-4">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = view === item.id;
          return (
            <button
              key={item.id}
              onClick={() => {
                setView(item.id);
                onNavigate?.();
              }}
              className={cn(
                "mb-1 flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-emerald-500 text-slate-900"
                  : "text-slate-400 hover:bg-slate-800 hover:text-white"
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </button>
          );
        })}
      </nav>
      <div className="border-t border-slate-800 p-4">
        <div className="rounded-lg bg-slate-800 p-3 text-xs text-slate-400">
          <p className="font-semibold text-slate-200">AI SEO OS v1.0</p>
          <p className="mt-1">Powered by Claude 3.5 Sonnet</p>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const { view } = useStore();
  const [mobileOpen, setMobileOpen] = useState(false);

  const renderView = () => {
    switch (view) {
      case "dashboard":
        return <Dashboard />;
      case "new-audit":
        return <NewAudit />;
      case "clients":
        return <Clients />;
      case "settings":
        return <Settings />;
      case "reports":
        return <Placeholder title="Reports" description="Automatically generate executive summaries, technical SEO reports, and action plans. Export as HTML, Markdown, or PDF." />;
      case "content-planner":
        return <Placeholder title="Content Planner" description="Generate 100 topics, build a monthly calendar, and manage internal links and target keywords." />;
      case "keyword-research":
        return <Placeholder title="Keyword Research" description="Generate seed, commercial, informational, question, and buying keywords with priority scores." />;
      case "keyword-clusters":
        return <Placeholder title="Keyword Clusters" description="Automatically group keywords into pillar pages and supporting pages with internal linking strategies." />;
      case "competitors":
        return <Placeholder title="Competitors" description="Compare keywords, content, schema, backlinks, EEAT, entities, and topic gaps against competitors." />;
      case "internal-linking":
        return <Placeholder title="Internal Linking" description="Automatically build hub pages, clusters, anchor text, silos, and identify orphan pages." />;
      case "backlinks":
        return <Placeholder title="Backlinks" description="Plan guest posts, digital PR, broken link building, citation sites, and directory submissions." />;
      case "local-seo":
        return <Placeholder title="Local SEO" description="Analyze Google Business Profile, NAP, reviews, citations, local schema, service areas, and local content." />;
      case "schema":
        return <Placeholder title="Schema" description="Automatically generate and validate Organization, LocalBusiness, Service, FAQ, Breadcrumb, Article, Review, and Product schema." />;
      case "eeat":
        return <Placeholder title="EEAT" description="Evaluate Experience, Expertise, Authority, Trust, author pages, contact info, privacy, about, and trust signals." />;
      case "ai-search":
        return <Placeholder title="AI Search" description="Optimize for ChatGPT, Claude, Gemini, Perplexity, Google AI Overviews, and Copilot. Evaluate entities, knowledge graph, question coverage, and brand mentions." />;
      case "search-console":
        return <Placeholder title="Google Search Console" description="Upload CSV exports to analyze CTR, impressions, clicks, lost rankings, cannibalization, and quick wins." />;
      case "analytics":
        return <Placeholder title="Google Analytics" description="Upload CSV exports to analyze traffic, conversions, bounce rate, landing pages, revenue, and channels." />;
      case "documentation":
        return <Placeholder title="Documentation" description="Learn how to use Boost Rankers AI SEO OS, configure API keys, and run audits." />;
      default:
        return <Dashboard />;
    }
  };

  return (
    <div className="flex h-screen bg-slate-50 text-slate-900">
      {/* Desktop Sidebar */}
      <aside className="hidden w-64 flex-shrink-0 md:block">
        <SidebarContent />
      </aside>

      {/* Mobile Drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 flex md:hidden">
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setMobileOpen(false)}
          />
          <div className="relative w-64 flex-shrink-0">
            <button
              onClick={() => setMobileOpen(false)}
              className="absolute right-2 top-3 z-10 rounded-md bg-slate-800 p-1.5 text-slate-300 hover:bg-slate-700"
            >
              <X className="h-5 w-5" />
            </button>
            <SidebarContent onNavigate={() => setMobileOpen(false)} />
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Mobile Header */}
        <header className="flex h-16 items-center justify-between border-b border-slate-200 bg-white px-4 md:hidden">
          <button
            onClick={() => setMobileOpen(true)}
            className="rounded-md p-2 text-slate-600 hover:bg-slate-100"
          >
            <Menu className="h-6 w-6" />
          </button>
          <span className="font-serif text-lg font-bold">Boost Rankers</span>
          <div className="w-10" />
        </header>

        <main className="flex-1 overflow-y-auto">
          {renderView()}
        </main>
      </div>
    </div>
  );
}