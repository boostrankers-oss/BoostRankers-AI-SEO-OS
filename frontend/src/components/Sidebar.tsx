import { cn } from "@/lib/utils";
import { useAuth, UserRole } from "@/components/AuthProvider";
import { 
  LayoutDashboard, 
  Users, 
  FolderKanban, 
  FileSearch, 
  FileText, 
  CalendarRange, 
  Search, 
  Network, 
  PenLine, 
  Target, 
  Link2, 
  MapPin, 
  Code2, 
  Award, 
  Bot, 
  BarChart3, 
  Settings as SettingsIcon, 
  Bell, 
  User as UserIcon, 
  LogOut,
  ShieldCheck,
  Moon,
  Sun,
} from "lucide-react";
import type { ViewKey } from "@/App";

interface SidebarProps {
  view: ViewKey;
  setView: (view: ViewKey) => void;
  dark: boolean;
  setDark: (dark: boolean) => void;
  onLogout: () => void;
  role: UserRole;
}

export function Sidebar({ view, setView, dark, setDark, onLogout, role }: SidebarProps) {
  const navItems = [
    { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
    { id: "clients", label: "Clients", icon: Users },
    { id: "audit", label: "New Audit", icon: FileSearch },
    { id: "reports", label: "Reports", icon: FileText },
    { id: "content", label: "Content Planner", icon: CalendarRange },
    { id: "keywords", label: "Keyword Research", icon: Search },
    { id: "clusters", label: "Keyword Clusters", icon: Network },
    { id: "blog", label: "Blog Optimizer", icon: PenLine },
    { id: "competitors", label: "Competitors", icon: Target },
    { id: "linking", label: "Internal Linking", icon: Link2 },
    { id: "backlinks", label: "Backlinks", icon: Link2 },
    { id: "local", label: "Local SEO", icon: MapPin },
    { id: "schema", label: "Schema", icon: Code2 },
    { id: "eeat", label: "EEAT", icon: Award },
    { id: "aisearch", label: "AI Search", icon: Bot },
    { id: "google", label: "Google Integration", icon: BarChart3 },
  ] as const;

  const bottomItems = [
    { id: "settings", label: "Settings", icon: SettingsIcon },
  ] as const;

  return (
    <aside className="w-64 h-screen bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 flex flex-col">
      <div className="p-6 border-b border-slate-200 dark:border-slate-800">
        <div className="flex items-center gap-2">
          <div className="size-8 rounded-lg bg-emerald-600 flex items-center justify-center">
            <ShieldCheck className="size-5 text-white" />
          </div>
          <div>
            <h1 className="font-serif text-lg font-bold leading-none">Boost Rankers</h1>
            <p className="text-xs text-slate-500 mt-1">AI SEO OS</p>
          </div>
        </div>
      </div>

      <div className="px-4 py-3 border-b border-slate-200 dark:border-slate-800">
        <div className="flex items-center gap-2">
          <span className={cn(
            "px-2 py-0.5 rounded-md text-xs font-medium",
            role === "Super Admin" ? "bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:text-rose-400" :
            role === "Agency Admin" ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400" :
            role === "Team Member" ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-400" :
            "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400"
          )}>
            {role}
          </span>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
        {navItems.map((item) => (
          <button
            key={item.id}
            onClick={() => setView(item.id as ViewKey)}
            className={cn(
              "w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
              view === item.id
                ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400"
                : "text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
            )}
          >
            <item.icon className="size-4" />
            {item.label}
          </button>
        ))}
      </nav>

      <div className="p-3 border-t border-slate-200 dark:border-slate-800 space-y-1">
        <button
          onClick={() => setDark(!dark)}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
        >
          {dark ? <Moon className="size-4" /> : <Sun className="size-4" />}
          {dark ? "Dark Mode" : "Light Mode"}
        </button>
        {bottomItems.map((item) => (
          <button
            key={item.id}
            onClick={() => setView(item.id as ViewKey)}
            className={cn(
              "w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors",
              view === item.id
                ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400"
                : "text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
            )}
          >
            <item.icon className="size-4" />
            {item.label}
          </button>
        ))}
        <button
          onClick={onLogout}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
        >
          <LogOut className="size-4" />
          Logout
        </button>
      </div>
    </aside>
  );
}