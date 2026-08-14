import { useState } from "react";
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

type ViewKey = 
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
  | "settings"
  | "admin";

function MainApp() {
  const { user, logout } = useAuth();
  const [dark, setDark] = useState(false);
  const [activeView, setActiveView] = useState<ViewKey>("dashboard");

  // Super Admin sees the admin panel by default
  if (user && user.role === "super_admin" && activeView === "dashboard") {
    setActiveView("admin");
  }

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
      case "settings":
        return <Settings />;
      case "admin":
        return <AdminDashboard />;
      default:
        return <div className="p-8">Page not found</div>;
    }
  };

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