import { useState, useEffect } from "react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import {
  Link2,
  TrendingUp,
  TrendingDown,
  Globe,
  ShieldAlert,
  Sparkles,
  Loader2,
  Mail,
  Trash2,
  Search,
  Download,
  Plus,
  AlertCircle,
  CreditCard,
} from "lucide-react";
import { useClaude } from "@/components/ClaudeProvider";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";

interface Backlink {
  id: string;
  source_url: string;
  target_url: string;
  anchor_text: string;
  link_type: string;
  domain_authority: number;
  spam_score: number;
  status: string;
  ai_analysis: string;
  detected_at: string;
}

interface Opportunity {
  id: string;
  domain: string;
  opportunity_type: string;
  domain_authority: number;
  relevance: string;
  status: string;
}

interface OutreachEmail {
  id: string;
  opportunity_id: string;
  subject: string;
  body: string;
  status: string;
}

interface Statistics {
  total: number;
  referring_domains: number;
  domain_authority: number;
  toxic_links: number;
  new_this_month: number;
  new_domains: number;
  da_change: number;
  toxic_fixed: number;
  growth_history: { month: string; new: number; lost: number }[];
  link_types: { [key: string]: number };
}

const COLORS = ["#10b981", "#6366f1", "#f59e0b", "#8b5cf6"];

export function Backlinks() {
  const { isConfigured, isReady, status } = useClaude();
  const [stats, setStats] = useState<Statistics | null>(null);
  const [backlinks, setBacklinks] = useState<Backlink[]>([]);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [outreachEmails, setOutreachEmails] = useState<OutreachEmail[]>([]);
  const [loading, setLoading] = useState(true);

  // UI state
  const [activeTab, setActiveTab] = useState<
    "dashboard" | "analysis" | "opportunities" | "outreach"
  >("dashboard");
  const [searchQuery, setSearchQuery] = useState("");
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [newBacklink, setNewBacklink] = useState({
    source_url: "",
    target_url: "",
    anchor_text: "",
    link_type: "Dofollow",
  });
  const [isDeleteOpen, setIsDeleteOpen] = useState<string | null>(null);
  const [analyzingId, setAnalyzingId] = useState<string | null>(null);
  const [showBudgetDialog, setShowBudgetDialog] = useState(false);
  const [budgetAmount, setBudgetAmount] = useState(10);
  const [isAddingBudget, setIsAddingBudget] = useState(false);

  const requireAiReady = (): boolean => {
    if (!isConfigured) {
      toast.error("Claude API key not configured. Please add it in Settings.");
      return false;
    }

    if (!isReady) {
      toast.error(
        status === "billing_required"
          ? "Anthropic billing is required. Add credits or upgrade your plan, then try again."
          : status === "invalid_api_key"
            ? "Anthropic API key is invalid. Please update it in Settings."
            : "Claude AI is currently unavailable. Please check Settings."
      );
      return false;
    }

    return true;
  };
  const [generatingEmail, setGeneratingEmail] = useState<{
    id: string;
    loading: boolean;
  } | null>(null);
  const [generatedEmail, setGeneratedEmail] = useState<string | null>(null);
  useEffect(() => {
    fetchAllData();
  }, []);

  const fetchAllData = async () => {
    setLoading(true);
    try {
      // Use Promise.allSettled to avoid one failure breaking everything
      const [statsData, backlinksData, oppsData, emailsData] = await Promise.all([
        api.get<Statistics>("/api/backlinks/statistics"),
        api.get<Backlink[]>("/api/backlinks"),
        api.get<Opportunity[]>("/api/backlinks/opportunities"),
        api.get<OutreachEmail[]>("/api/backlinks/outreach"),
      ]);

      setStats(statsData);
      setBacklinks(backlinksData);
      setOpportunities(oppsData);
      setOutreachEmails(emailsData);
    } catch (err) {
      console.error("Failed to fetch backlink data:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleAddBacklink = async () => {
    try {
      const data = await api.post<Backlink>("/api/backlinks", newBacklink);
      setBacklinks([data, ...backlinks]);
      setIsAddOpen(false);
      setNewBacklink({ source_url: "", target_url: "", anchor_text: "", link_type: "Dofollow" });
      toast.success("Backlink added");
      fetchAllData();
    } catch (err) {
      console.error(err);
      toast.error("Failed to add backlink");
    }
  };

  const handleDeleteBacklink = async (id: string) => {
    try {
      await api.delete(`/api/backlinks/${id}`);
      setBacklinks(backlinks.filter((b) => b.id !== id));
      setIsDeleteOpen(null);
      toast.success("Backlink deleted");
      fetchAllData();
    } catch (err) {
      console.error(err);
      toast.error("Could not delete");
    }
  };

  const handleAnalyze = async (id: string) => {
    if (!requireAiReady()) return;

    setAnalyzingId(id);
    try {
      const data = await api.post<{ analysis: string }>(`/api/backlinks/${id}/analyze`);
      setBacklinks(
        backlinks.map((b) =>
          b.id === id ? { ...b, ai_analysis: data.analysis } : b
        )
      );
      toast.success("Analysis complete");
    } catch (err: any) {
      let msg = err?.data?.detail || "Analysis failed";
      if (msg.includes("credits") || msg.includes("402")) {
        setShowBudgetDialog(true);
        msg = "Insufficient AI credits. Please add budget.";
      }
      toast.error(msg);
    } finally {
      setAnalyzingId(null);
    }
  };

  const handleGenerateOpportunities = async () => {
    if (!requireAiReady()) return;

    try {
      const data = await api.post<Opportunity[]>("/api/backlinks/opportunities/generate");
      setOpportunities([...data, ...opportunities]);
      toast.success("Opportunities generated");
      fetchAllData();
    } catch (err: any) {
      let msg = err?.data?.detail || "Failed to generate opportunities";
      if (msg.includes("credits") || msg.includes("402")) {
        setShowBudgetDialog(true);
        msg = "Insufficient AI credits. Please add budget.";
      }
      toast.error(msg);
    }
  };

  const handleGenerateEmail = async (oppId: string) => {
    setGeneratingEmail({ id: oppId, loading: true });
    try {
      const data = await api.post<{ email: string }>(`/api/backlinks/opportunities/${oppId}/outreach`);
      setGeneratedEmail(data.email);
      setActiveTab("outreach");
      toast.success("Email generated");
      fetchAllData();
    } catch (err: any) {
      let msg = err?.data?.detail || "Email generation failed";
      if (msg.includes("credits") || msg.includes("402")) {
        setShowBudgetDialog(true);
        msg = "Insufficient AI credits. Please add budget.";
      }
      toast.error(msg);
    } finally {
      setGeneratingEmail(null);
    }
  };

  const addBudget = async () => {
    setIsAddingBudget(true);
    try {
      await api.post(`/api/company/add-credits?amount=${budgetAmount}`, {});
      toast.success(`Added ${budgetAmount} credits.`);
      setShowBudgetDialog(false);
      } catch (error) {
      console.error("Failed to add credits:", error);
      toast.error("Could not add credits.");
    } finally {
      setIsAddingBudget(false);
    }
  };

  const handleExport = () => {
    // CSV export
    const headers = ["Source URL", "Target URL", "Anchor Text", "Type", "DA", "Spam Score", "Status"];
    const csvRows = [
      headers.join(","),
      ...backlinks.map((row) =>
        [row.source_url, row.target_url, `"${row.anchor_text}"`, row.link_type, row.domain_authority, row.spam_score, row.status].join(",")
      ),
    ].join("\n");
    const blob = new Blob([csvRows], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "backlinks_export.csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast.success("Backlinks exported");
  };

  if (loading) {
    return <div className="p-8 flex justify-center items-center">Loading backlink data...</div>;
  }

  return (
    <div className="p-8 space-y-6">
      <header className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h2 className="font-serif text-3xl font-bold tracking-tight">Backlink Intelligence</h2>
          <p className="text-slate-500 dark:text-slate-400 mt-1">
            AI-powered link building, toxic detection, and outreach CRM.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" className="border-slate-200 dark:border-slate-800" onClick={handleExport}>
            <Download className="size-4" /> Export
          </Button>
          <Button className="bg-emerald-600 hover:bg-emerald-700 text-white shadow-md shadow-emerald-600/20" onClick={() => setIsAddOpen(true)}>
            <Plus className="size-4" /> Add Backlink
          </Button>
        </div>
      </header>

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-slate-200 dark:border-slate-800 overflow-x-auto">
        {[
          { key: "dashboard", label: "Dashboard" },
          { key: "analysis", label: "Backlink Analysis" },
          { key: "opportunities", label: "AI Opportunities" },
          { key: "outreach", label: "Outreach CRM" },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key as typeof activeTab)}
            className={cn(
              "px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap",
              activeTab === tab.key
                ? "border-emerald-600 text-emerald-700 dark:text-emerald-400"
                : "border-transparent text-slate-500 hover:text-slate-900 dark:hover:text-slate-100"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {!isConfigured ? (
        <Card className="border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-900/10">
          <CardContent className="p-4 flex items-center gap-3">
            <AlertCircle className="size-5 text-amber-600" />
            <p className="text-sm text-amber-700 dark:text-amber-400">
              Claude API Key required. Please configure it in Settings to enable AI features.
            </p>
          </CardContent>
        </Card>
      ) : !isReady && (
        <Card className="border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-900/10">
          <CardContent className="p-4 flex items-center gap-3">
            {status === "billing_required" ? <CreditCard className="size-5 text-amber-600" /> : <AlertCircle className="size-5 text-amber-600" />}
            <p className="text-sm text-amber-700 dark:text-amber-400">
              {status === "billing_required"
                ? "Anthropic billing is required. Add credits or upgrade your plan, then try again."
                : "Claude AI is currently unavailable. Please check Settings."}
            </p>
          </CardContent>
        </Card>
      )}

      {/* Dashboard Tab */}
      {activeTab === "dashboard" && stats && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
              <CardContent className="p-5">
                <div className="flex items-center justify-between">
                  <p className="text-sm text-slate-500 dark:text-slate-400">Total Backlinks</p>
                  <Link2 className="size-4 text-slate-400" />
                </div>
                <p className="font-serif text-2xl font-bold mt-2">{stats.total}</p>
                <div className="flex items-center gap-1 mt-2 text-xs text-emerald-600 dark:text-emerald-400">
                  <TrendingUp className="size-3.5" /> +{stats.new_this_month} this month
                </div>
              </CardContent>
            </Card>
            <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
              <CardContent className="p-5">
                <div className="flex items-center justify-between">
                  <p className="text-sm text-slate-500 dark:text-slate-400">Referring Domains</p>
                  <Globe className="size-4 text-slate-400" />
                </div>
                <p className="font-serif text-2xl font-bold mt-2">{stats.referring_domains}</p>
                <div className="flex items-center gap-1 mt-2 text-xs text-emerald-600 dark:text-emerald-400">
                  <TrendingUp className="size-3.5" /> +{stats.new_domains} new
                </div>
              </CardContent>
            </Card>
            <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
              <CardContent className="p-5">
                <div className="flex items-center justify-between">
                  <p className="text-sm text-slate-500 dark:text-slate-400">Domain Authority</p>
                  <TrendingUp className="size-4 text-slate-400" />
                </div>
                <p className="font-serif text-2xl font-bold mt-2">{stats.domain_authority}</p>
                <div className="flex items-center gap-1 mt-2 text-xs text-emerald-600 dark:text-emerald-400">
                  <TrendingUp className="size-3.5" /> +{stats.da_change} pts
                </div>
              </CardContent>
            </Card>
            <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
              <CardContent className="p-5">
                <div className="flex items-center justify-between">
                  <p className="text-sm text-slate-500 dark:text-slate-400">Toxic Links</p>
                  <ShieldAlert className="size-4 text-rose-500" />
                </div>
                <p className="font-serif text-2xl font-bold mt-2 text-rose-600 dark:text-rose-400">{stats.toxic_links}</p>
                <div className="flex items-center gap-1 mt-2 text-xs text-rose-500">
                  <TrendingDown className="size-3.5" /> -{stats.toxic_fixed} fixed
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <Card className="lg:col-span-2 border-slate-200 dark:border-slate-800 shadow-sm">
              <CardHeader>
                <CardTitle className="font-serif">Link Growth History</CardTitle>
                <CardDescription>New vs. lost backlinks over time</CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <AreaChart data={stats.growth_history}>
                    <defs>
                      <linearGradient id="newLinks" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="lostLinks" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#f43f5e" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" strokeOpacity={0.2} />
                    <XAxis dataKey="month" stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                    <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                    <Tooltip contentStyle={{ backgroundColor: "rgba(15, 23, 42, 0.9)", border: "none", borderRadius: "0.75rem", color: "#fff" }} />
                    <Area type="monotone" dataKey="new" stroke="#10b981" strokeWidth={2} fill="url(#newLinks)" />
                    <Area type="monotone" dataKey="lost" stroke="#f43f5e" strokeWidth={2} fill="url(#lostLinks)" />
                  </AreaChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
              <CardHeader>
                <CardTitle className="font-serif">Link Types</CardTitle>
                <CardDescription>Distribution of attributes</CardDescription>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie data={Object.entries(stats.link_types).map(([name, value]) => ({ name, value }))} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={60} outerRadius={90} paddingAngle={5}>
                      {Object.entries(stats.link_types).map(([,], index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ backgroundColor: "rgba(15, 23, 42, 0.9)", border: "none", borderRadius: "0.75rem", color: "#fff" }} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="flex flex-wrap gap-3 justify-center mt-4">
                  {Object.entries(stats.link_types).map(([name, value], idx) => (
                    <div key={name} className="flex items-center gap-1.5 text-xs">
                      <span className="size-2.5 rounded-full" style={{ backgroundColor: COLORS[idx % COLORS.length] }} />
                      <span className="text-slate-600 dark:text-slate-400">{name} ({value})</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {/* Analysis Tab */}
      {activeTab === "analysis" && (
        <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
          <CardHeader>
            <div className="flex items-center justify-between flex-wrap gap-4">
              <div>
                <CardTitle className="font-serif">Backlink Analysis</CardTitle>
                <CardDescription>Review and analyze your link profile</CardDescription>
              </div>
              <div className="flex items-center gap-2">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-slate-400" />
                  <Input
                    placeholder="Search..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-9 w-48"
                  />
                </div>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 dark:border-slate-800 text-left text-slate-500 dark:text-slate-400">
                    <th className="pb-3 pr-4 font-medium">Source Domain</th>
                    <th className="pb-3 pr-4 font-medium">Anchor Text</th>
                    <th className="pb-3 pr-4 font-medium">Type</th>
                    <th className="pb-3 pr-4 font-medium">DA</th>
                    <th className="pb-3 pr-4 font-medium">Spam</th>
                    <th className="pb-3 pr-4 font-medium">Status</th>
                    <th className="pb-3 pr-4 font-medium">AI Analysis</th>
                    <th className="pb-3 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {backlinks.filter(b => (b.source_url ?? "").toLowerCase().includes(searchQuery.toLowerCase()) || (b.anchor_text ?? "").toLowerCase().includes(searchQuery.toLowerCase())).map((row) => (
                    <tr key={row.id} className="border-b border-slate-100 dark:border-slate-800/50 hover:bg-slate-50 dark:hover:bg-slate-800/30">
                      <td className="py-3 pr-4">
                        <div className="font-medium">{row.source_url}</div>
                        <div className="text-xs text-slate-500 dark:text-slate-400 truncate max-w-[150px]">{row.target_url}</div>
                      </td>
                      <td className="py-3 pr-4 text-slate-600 dark:text-slate-300">{row.anchor_text}</td>
                      <td className="py-3 pr-4">
                        <Badge variant="outline" className={row.link_type === "Dofollow" ? "border-emerald-200 text-emerald-700 dark:border-emerald-800 dark:text-emerald-400" : "border-slate-200 text-slate-600 dark:border-slate-700 dark:text-slate-400"}>
                          {row.link_type}
                        </Badge>
                      </td>
                      <td className="py-3 pr-4 font-serif font-bold">{row.domain_authority}</td>
                      <td className="py-3 pr-4">
                        <span className={row.spam_score > 50 ? "text-rose-600 font-bold" : row.spam_score > 10 ? "text-amber-600" : "text-slate-600 dark:text-slate-400"}>
                          {row.spam_score}
                        </span>
                      </td>
                      <td className="py-3 pr-4">
                        <span className={`px-2 py-1 rounded-md text-xs font-medium ${row.status === "toxic" ? "bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:text-rose-400" : "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400"}`}>
                          {row.status}
                        </span>
                      </td>
                      <td className="py-3 pr-4 max-w-[200px]">
                        {analyzingId === row.id ? (
                          <div className="flex items-center gap-2 text-xs text-emerald-600">
                            <Loader2 className="size-3 animate-spin" /> Analyzing...
                          </div>
                        ) : row.ai_analysis ? (
                          <p className="text-xs text-slate-600 dark:text-slate-300 line-clamp-2">{row.ai_analysis}</p>
                        ) : (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleAnalyze(row.id)}
                            disabled={!isReady || analyzingId !== null}
                            className="text-xs h-7"
                          >
                            <Sparkles className="size-3" /> Analyze
                          </Button>
                        )}
                      </td>
                      <td className="py-3">
                        <Button variant="ghost" size="icon" className="h-8 w-8 text-slate-400 hover:text-rose-500" onClick={() => setIsDeleteOpen(row.id)}>
                          <Trash2 className="size-4" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Opportunities Tab */}
      {activeTab === "opportunities" && (
        <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
          <CardHeader>
            <CardTitle className="font-serif flex items-center gap-2">
              <Sparkles className="size-5 text-emerald-600" /> AI Link Opportunities
            </CardTitle>
            <CardDescription>Discover high-quality link building prospects</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Button onClick={handleGenerateOpportunities} disabled={!isReady} className="bg-emerald-600 hover:bg-emerald-700 text-white">
              <Sparkles className="size-4" /> Generate New Opportunities
            </Button>
            {opportunities.length === 0 ? (
              <p className="text-slate-500">No opportunities yet. Click "Generate" to find prospects.</p>
            ) : (
              opportunities.map((opp) => (
                <div key={opp.id} className="flex items-center justify-between p-4 rounded-lg border border-slate-200 dark:border-slate-800 hover:border-emerald-300 dark:hover:border-emerald-700 transition-colors">
                  <div className="flex items-center gap-3">
                    <div className="size-10 rounded-lg bg-emerald-50 dark:bg-emerald-500/10 flex items-center justify-center">
                      <Globe className="size-5 text-emerald-600" />
                    </div>
                    <div>
                      <p className="font-medium">{opp.domain}</p>
                      <p className="text-xs text-slate-500 dark:text-slate-400">{opp.opportunity_type} · DA {opp.domain_authority}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge variant="outline" className={opp.relevance?.toLowerCase() === "high" ? "border-emerald-200 text-emerald-700 dark:border-emerald-800 dark:text-emerald-400" : "border-amber-200 text-amber-700 dark:border-amber-800 dark:text-amber-400"}>
                      {opp.relevance} Relevance
                    </Badge>
                    <Button size="sm" variant="outline" onClick={() => handleGenerateEmail(opp.id)} disabled={generatingEmail?.id === opp.id}>
                      {generatingEmail?.id === opp.id ? <Loader2 className="size-3 animate-spin" /> : <Mail className="size-3" />}
                      {generatingEmail?.id === opp.id ? "Generating..." : "Outreach"}
                    </Button>
                    <Button variant="ghost" size="icon" onClick={() => api.delete(`/api/backlinks/opportunities/${opp.id}`).then(() => fetchAllData())}>
                      <Trash2 className="size-4" />
                    </Button>
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      )}

      {/* Outreach Tab */}
      {activeTab === "outreach" && (
        <div className="space-y-6">
          {generatedEmail && (
            <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
              <CardHeader>
                <CardTitle className="font-serif flex items-center gap-2">
                  <Mail className="size-5 text-indigo-600" /> Generated Email
                </CardTitle>
                <CardDescription>Review and copy your email</CardDescription>
              </CardHeader>
              <CardContent>
                <Textarea value={generatedEmail} readOnly className="h-[300px] font-mono text-xs" />
              </CardContent>
            </Card>
          )}
          <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
            <CardHeader>
              <CardTitle className="font-serif">Outreach History</CardTitle>
            </CardHeader>
            <CardContent>
              {outreachEmails.length === 0 ? (
                <p className="text-slate-500">No outreach emails yet.</p>
              ) : (
                outreachEmails.map((email) => (
                  <div key={email.id} className="border-b py-3">
                    <p className="font-medium">{email.subject}</p>
                    <p className="text-xs text-slate-500">Status: {email.status}</p>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Add Backlink Dialog */}
      <Dialog open={isAddOpen} onOpenChange={setIsAddOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add New Backlink</DialogTitle>
            <DialogDescription>Manually add a backlink to your profile.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Source Domain</Label>
              <Input value={newBacklink.source_url} onChange={(e) => setNewBacklink({ ...newBacklink, source_url: e.target.value })} placeholder="example.com" />
            </div>
            <div className="space-y-2">
              <Label>Target URL</Label>
              <Input value={newBacklink.target_url} onChange={(e) => setNewBacklink({ ...newBacklink, target_url: e.target.value })} placeholder="/blog/post" />
            </div>
            <div className="space-y-2">
              <Label>Anchor Text</Label>
              <Input value={newBacklink.anchor_text} onChange={(e) => setNewBacklink({ ...newBacklink, anchor_text: e.target.value })} placeholder="Click here" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsAddOpen(false)}>Cancel</Button>
            <Button onClick={handleAddBacklink} className="bg-emerald-600 hover:bg-emerald-700 text-white">Add</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Dialog */}
      <Dialog open={isDeleteOpen !== null} onOpenChange={(open) => !open && setIsDeleteOpen(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Backlink?</DialogTitle>
            <DialogDescription>This action cannot be undone.</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDeleteOpen(null)}>Cancel</Button>
            <Button onClick={() => isDeleteOpen && handleDeleteBacklink(isDeleteOpen)} className="bg-rose-600 hover:bg-rose-700 text-white">Delete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Budget Dialog */}
      <Dialog open={showBudgetDialog} onOpenChange={setShowBudgetDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="font-serif flex items-center gap-2">
              <CreditCard className="size-5 text-amber-600" />
              Insufficient AI Credits
            </DialogTitle>
            <DialogDescription>
              You need to add budget to use AI features. Each analysis/email generation consumes 1 credit.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="budget-amount">Credits to Add</Label>
              <Input
                id="budget-amount"
                type="number"
                min={1}
                value={budgetAmount}
                onChange={(e) => setBudgetAmount(parseInt(e.target.value) || 1)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowBudgetDialog(false)}>Cancel</Button>
            <Button onClick={addBudget} disabled={isAddingBudget} className="bg-emerald-600 hover:bg-emerald-700 text-white">
              {isAddingBudget ? <Loader2 className="size-4 animate-spin" /> : "Add Credits"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}