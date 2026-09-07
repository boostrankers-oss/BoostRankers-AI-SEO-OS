import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { LayoutDashboard, Users, FolderKanban, FileSearch, FileText, CalendarRange, Search, Network, PenLine, Target, Link2, MapPin, Code2, Award, Bot, BarChart3, Settings, Bell, User, ArrowRight } from "lucide-react";
import type { ViewKey } from "@/App";
import { cn } from "@/lib/utils";

interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  setView: (view: ViewKey) => void;
}

export function CommandPalette({ open, onOpenChange, setView }: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);

  const commands = [
    { id: "dashboard", label: "Go to Dashboard", icon: LayoutDashboard },
    { id: "clients", label: "Go to Clients", icon: Users },
    { id: "projects", label: "Go to Projects", icon: FolderKanban },
    { id: "audit", label: "Start New Audit", icon: FileSearch },
    { id: "reports", label: "View Reports", icon: FileText },
    { id: "content", label: "Open Content Planner", icon: CalendarRange },
    { id: "keywords", label: "Keyword Research", icon: Search },
    { id: "clusters", label: "Keyword Clusters", icon: Network },
    { id: "blog", label: "Blog Optimizer", icon: PenLine },
    { id: "competitors", label: "Competitors Analysis", icon: Target },
    { id: "linking", label: "Internal Linking", icon: Link2 },
    { id: "backlinks", label: "Backlink Intelligence", icon: Link2 },
    { id: "local", label: "Local SEO", icon: MapPin },
    { id: "schema", label: "Schema Generator", icon: Code2 },
    { id: "eeat", label: "EEAT Optimization", icon: Award },
    { id: "aisearch", label: "AI Search Optimization", icon: Bot },
    { id: "google", label: "Google Integration", icon: BarChart3 },
    { id: "settings", label: "Open Settings", icon: Settings },
    { id: "notifications", label: "View Notifications", icon: Bell },
    { id: "profile", label: "View Profile", icon: User },
  ] as const;

  const filteredCommands = commands.filter((cmd) =>
    cmd.label.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveIndex((prev) => (prev + 1) % filteredCommands.length);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIndex((prev) => (prev - 1 + filteredCommands.length) % filteredCommands.length);
      } else if (e.key === "Enter" && filteredCommands[activeIndex]) {
        e.preventDefault();
        setView(filteredCommands[activeIndex].id as ViewKey);
        onOpenChange(false);
      }
    };

    if (open) {
      window.addEventListener("keydown", handleKeyDown);
      return () => window.removeEventListener("keydown", handleKeyDown);
    }
  }, [open, filteredCommands, activeIndex, setView, onOpenChange]);

  useEffect(() => {
    setActiveIndex(0);
    setQuery("");
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="p-0 gap-0 max-w-xl">
        <DialogHeader className="sr-only">
          <DialogTitle>Command Palette</DialogTitle>
          <DialogDescription>Search for pages and actions</DialogDescription>
        </DialogHeader>
        <Input
          autoFocus
          placeholder="Type a command or search..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="border-0 border-b border-slate-200 dark:border-slate-800 rounded-none focus-visible:ring-0 focus-visible:ring-offset-0 text-base h-12"
        />
        <div className="p-2 max-h-[400px] overflow-y-auto">
          {filteredCommands.length === 0 ? (
            <div className="p-6 text-center text-sm text-slate-500">No results found.</div>
          ) : (
            filteredCommands.map((cmd, index) => (
              <button
                key={cmd.id}
                onClick={() => {
                  setView(cmd.id as ViewKey);
                  onOpenChange(false);
                }}
                className={cn(
                  "w-full flex items-center justify-between px-3 py-2.5 rounded-md text-sm transition-colors",
                  activeIndex === index
                    ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400"
                    : "text-slate-700 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800"
                )}
              >
                <div className="flex items-center gap-3">
                  <cmd.icon className="size-4" />
                  {cmd.label}
                </div>
                {activeIndex === index && <ArrowRight className="size-4" />}
              </button>
            ))
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}