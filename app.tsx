import { useState } from "react";
import { AuthScreen } from "@/components/AuthScreen";
import { Sidebar } from "@/components/Sidebar";
import { Dashboard } from "@/components/Dashboard";
import { Backlinks } from "@/components/Backlinks";
import { Settings } from "@/components/Settings";
import { ClaudeProvider } from "@/components/ClaudeProvider";

type Role = "super_admin" | "agency_admin" | "client";

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [role, setRole] = useState<Role>("agency_admin");
  const [activeView, setActiveView] = useState("dashboard");

  const handleLogin = (userRole: Role) => {
    setRole(userRole);
    setIsAuthenticated(true);
  };

  const handleLogout = () => {
    setIsAuthenticated(false);
    setActiveView("dashboard");
  };

  if (!isAuthenticated) {
    return (
      <ClaudeProvider>
        <AuthScreen onLogin={handleLogin} />
      </ClaudeProvider>
    );
  }

  const renderContent = () => {
    if (activeView === "dashboard") return <Dashboard role={role} />;
    if (activeView === "backlinks") return <Backlinks />;
    if (activeView === "settings") return <Settings />;
    if (activeView === "logout") {
      handleLogout();
      return null;
    }
    
    return (
      <div className="p-8">
        <h2 className="font-serif text-3xl font-bold tracking-tight capitalize">
          {activeView.replace("_", " ")}
        </h2>
        <p className="text-slate-500 dark:text-slate-400 mt-1">
          This module is under development. Explore the Backlinks module for a full feature demonstration.
        </p>
      </div>
    );
  };

  return (
    <ClaudeProvider>
      <div className="flex h-screen bg-slate-50 dark:bg-slate-950">
        <Sidebar activeView={activeView} setActiveView={setActiveView} role={role} />
        <main className="flex-1 overflow-y-auto">
          {renderContent()}
        </main>
      </div>
    </ClaudeProvider>
  );
}