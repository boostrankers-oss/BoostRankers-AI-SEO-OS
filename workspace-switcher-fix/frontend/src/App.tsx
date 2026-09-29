import { useEffect, useState } from "react";

import { AuthScreen } from "@/components/AuthScreen";
import { ClientInvitation } from "@/components/ClientInvitation";
import { Sidebar } from "@/components/Sidebar";
import { Dashboard } from "@/components/Dashboard";
import { Backlinks } from "@/components/Backlinks";
import { Settings } from "@/components/Settings";
import { Clients } from "@/components/Clients";
import { Reports } from "@/components/Reports";
import { AuditEngine } from "@/components/AuditEngine";
import { ContentPlanner } from "@/components/ContentPlanner";
import { KeywordResearch } from "@/components/KeywordResearch";
import { KeywordClusters } from "@/components/KeywordClusters";
import { BlogOptimizer } from "@/components/BlogOptimizer";
import { Competitors } from "@/components/Competitors";
import { InternalLinking } from "@/components/InternalLinking";
import { LocalSEO } from "@/components/LocalSEO";
import { SchemaGenerator } from "@/components/SchemaGenerator";
import { EEAT } from "@/components/EEAT";
import { AISearch } from "@/components/AISearch";
import { GoogleIntegration } from "@/components/GoogleIntegration";
import { AuthProvider, useAuth } from "@/components/AuthProvider";
import { ClaudeProvider } from "@/components/ClaudeProvider";
import { AuditProvider } from "@/context/AuditContext";
import AdminDashboard from "@/components/AdminDashboard";
import { RankTracker } from "./components/RankTracker";
import { KeywordConflicts } from "./components/KeywordConflicts";
import { PagePostIndexing } from "./components/PagePostIndexing";
import { api } from "@/lib/api";
import { Building2, Check, ChevronDown } from "lucide-react";

export type ViewKey =
  | "dashboard"
  | "clients"
  | "audit"
  | "reports"
  | "content"
  | "keywords"
  | "clusters"
  | "blog"
  | "competitors"
  | "linking"
  | "backlinks"
  | "local"
  | "schema"
  | "eeat"
  | "aisearch"
  | "google"
  | "ranktracker"
  | "keywordconflicts"
  | "pagepostindexing"
  | "settings"
  | "admin";

interface WorkspaceOption {
  id: string;
  name: string;
  companyId: string;
  isAgency: boolean;
}

function WorkspaceSwitcher({ user }: { user: NonNullable<ReturnType<typeof useAuth>["user"]> }) {
  const isAgency = ["agency_admin", "manager", "super_admin"].includes(user.role);
  const [options, setOptions] = useState<WorkspaceOption[]>([]);
  const [selectedId, setSelectedId] = useState<string>(
    () => localStorage.getItem("boost_workspace_client_id") || "__agency__"
  );
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(isAgency);

  useEffect(() => {
    if (!isAgency) {
      setOptions([]);
      setLoading(false);
      return;
    }

    let mounted = true;
    const load = async () => {
      try {
        const clients = await api.get<Array<{ id: string; company_id: string; business_name: string }>>(
          "/api/clients/"
        );
        if (!mounted) return;
        setOptions([
          {
            id: "__agency__",
            name: "Boost Rankers Agency",
            companyId: user.company_id || "",
            isAgency: true,
          },
          ...clients.map((client) => ({
            id: client.id,
            name: client.business_name,
            companyId: client.company_id,
            isAgency: client.company_id === user.company_id,
          })),
        ].filter((item, index, all) => all.findIndex((x) => x.id === item.id) === index));

        const stored = localStorage.getItem("boost_workspace_client_id");
        if (stored && !clients.some((client) => client.id === stored)) {
          localStorage.removeItem("boost_workspace_client_id");
          setSelectedId("__agency__");
        }
      } catch (error) {
        console.warn("Workspace list unavailable:", error);
      } finally {
        if (mounted) setLoading(false);
      }
    };

    load();
    return () => { mounted = false; };
  }, [isAgency, user.company_id]);

  if (!isAgency) return null;

  const selected = options.find((option) => option.id === selectedId) || options[0];

  const selectWorkspace = (option: WorkspaceOption) => {
    if (option.isAgency) {
      localStorage.removeItem("boost_workspace_client_id");
      setSelectedId("__agency__");
    } else {
      localStorage.setItem("boost_workspace_client_id", option.id);
      setSelectedId(option.id);
    }
    setOpen(false);
    window.dispatchEvent(new CustomEvent("workspace:changed"));
    window.location.reload();
  };

  return (
    <div className="relative z-40 flex items-center gap-2 px-4 py-3 border-b border-slate-200 bg-white/95 dark:border-slate-800 dark:bg-slate-900/95 backdrop-blur">
      <Building2 className="size-4 text-emerald-600 shrink-0" />
      <span className="text-xs font-medium text-slate-500 dark:text-slate-400 shrink-0">Workspace</span>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        disabled={loading || options.length === 0}
        className="min-w-0 flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-800 shadow-sm hover:border-emerald-300 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
      >
        <span className="truncate max-w-[280px]">{loading ? "Loading workspaces..." : selected?.name || "Boost Rankers Agency"}</span>
        <ChevronDown className="size-4 shrink-0" />
      </button>

      {open && (
        <div className="absolute left-20 top-12 w-[320px] rounded-xl border border-slate-200 bg-white p-2 shadow-xl dark:border-slate-700 dark:bg-slate-900">
          {options.map((option) => (
            <button
              key={option.id}
              type="button"
              onClick={() => selectWorkspace(option)}
              className="flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-left text-sm hover:bg-slate-50 dark:hover:bg-slate-800"
            >
              <span className="min-w-0">
                <span className="block truncate font-medium text-slate-800 dark:text-slate-100">{option.name}</span>
                <span className="block text-xs text-slate-500 dark:text-slate-400">
                  {option.isAgency ? "Agency workspace" : "Managed client workspace"}
                </span>
              </span>
              {selectedId === option.id && <Check className="size-4 text-emerald-600 shrink-0" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function MainApp() {
  const { user, logout, loading } = useAuth();
  const [dark, setDark] = useState(false);
  const [activeView, setActiveView] = useState<ViewKey>("dashboard");

  /*
   * Keep the existing Super Admin behavior:
   * Super Admin opens the Admin panel by default.
   *
   * This is implemented with useEffect instead of changing state
   * directly during render.
   */
  useEffect(() => {
    if (user && user.role === "super_admin" && activeView === "dashboard") {
      setActiveView("admin");
    }
  }, [user, activeView]);

  const renderContent = () => {
    switch (activeView) {
      case "dashboard":
        return <Dashboard onRunAudit={() => setActiveView("audit")} />;

      case "clients":
        return <Clients />;

      case "audit":
        return <AuditEngine />;

      case "reports":
        return <Reports />;

      case "content":
        return <ContentPlanner />;

      case "keywords":
        return <KeywordResearch />;

      case "clusters":
        return <KeywordClusters />;

      case "blog":
        return <BlogOptimizer />;

      case "competitors":
        return <Competitors />;

      case "linking":
        return <InternalLinking />;

      case "backlinks":
        return <Backlinks />;

      case "local":
        return <LocalSEO />;

      case "schema":
        return <SchemaGenerator />;

      case "eeat":
        return <EEAT />;

      case "aisearch":
        return <AISearch />;

      case "google":
        return <GoogleIntegration />;

      case "ranktracker":
        return <RankTracker />;

      case "keywordconflicts":
        return <KeywordConflicts />;

      case "pagepostindexing":
        return <PagePostIndexing />;

      case "settings":
        return <Settings />;

      case "admin":
        return <AdminDashboard />;

      default:
        return <div className="p-8">Page not found</div>;
    }
  };
  
  if (loading) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950">
      <div className="text-sm text-slate-500 dark:text-slate-400">
        Restoring session...
      </div>
    </div>
  );
}

  if (!user) {
    return <AuthScreen />;
  }

  return (
    <div className={`flex h-screen ${dark ? "dark" : ""}`}>
      <Sidebar
        view={activeView}
        setView={setActiveView}
        dark={dark}
        setDark={setDark}
        onLogout={logout}
        role={user.role}
      />

      <main className="flex-1 overflow-y-auto bg-slate-50 dark:bg-slate-950">
        <WorkspaceSwitcher user={user} />
        {renderContent()}
      </main>
    </div>
  );
}

function App() {
  const pathname = window.location.pathname;

  if (/^\/invite\/[^/]+\/?$/.test(pathname)) {
    return <ClientInvitation />;
  }

  return (
    <AuthProvider>
      <ClaudeProvider>
        <AuditProvider>
          <MainApp />
        </AuditProvider>
      </ClaudeProvider>
    </AuthProvider>
  );
}

export default App;

