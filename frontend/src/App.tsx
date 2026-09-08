import { useEffect, useState } from "react";

import { AuthScreen } from "@/components/AuthScreen";
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
        {renderContent()}
      </main>
    </div>
  );
}

function App() {
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