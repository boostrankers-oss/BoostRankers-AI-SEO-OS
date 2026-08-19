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
  Filter,
  Download,
  Plus,
  AlertCircle,
  Wand2,
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
  domain_authority: number | null;
  spam_score: number;
  status: string;
  ai_analysis: string;
  detected_at: string;
  target_url?: string;
}

interface Opportunity {
  id: string;
  domain: string;
  opportunity_type: string;
  domain_authority: number | null;
  relevance: string;
  status: string;
  sent_at?: string | null;
}

interface OutreachEmail {
  id: string;
  opportunity_id: string;
  subject: string;
  body: string;
  status: string;
  sent_at?: string | null;
}

interface Statistics {
  total: number;
  referring_domains: number;
  domain_authority: number | null;
  toxic_links: number;
  new_this_month: number;
  new_domains: number | null;
  da_change: number | null;
  toxic_fixed: number | null;
  growth_history: { month: string; new: number; lost: number }[];
  link_types: { [key: string]: number };
}

const COLORS = ["#10b981", "#6366f1", "#f59e0b", "#8b5cf6"];

export function Backlinks() {
  const { isConfigured } = useClaude();
  const [stats, setStats] = useState<Statistics | null>(null);
  const [backlinks, setBacklinks] = useState<Backlink[]>([]);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [outreachEmails, setOutreachEmails] = useState<OutreachEmail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // UI state
  const [activeTab, setActiveTab] = useState<
    "dashboard" | "analysis" | "opportunities" | "outreach"
  >("dashboard");
  const [searchQuery, setSearchQuery] = useState("");
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [creatingBacklink, setCreatingBacklink] = useState(false);
  const [createResult, setCreateResult] = useState<string | null>(null);
  const [wordpressBacklink, setWordpressBacklink] = useState({
    wordpress_site: "",
    wordpress_username: "",
    wordpress_application_password: "",
    title: "",
    content: "",
    target_url: "",
    anchor_text: "",
    status: "publish",
  });
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
  const [generatingEmail, setGeneratingEmail] = useState<{
    id: string;
    loading: boolean;
  } | null>(null);
  const [generatedEmail, setGeneratedEmail] = useState<OutreachEmail | null>(null);
  const [recipientEmail, setRecipientEmail] = useState("");
  const [sendingOutreach, setSendingOutreach] = useState(false);
  const [sendEmailId, setSendEmailId] = useState<string | null>(null);
  useEffect(() => {
    fetchAllData();
  }, []);

  const fetchAllData = async () => {
    setLoading(true);
    setError(null);
    try {
      // Use Promise.allSettled to avoid one failure breaking everything
      const results = await Promise.allSettled([
        api.get("/api/backlinks/statistics"),
        api.get("/api/backlinks"),
        api.get("/api/backlinks/opportunities"),
        api.get("/api/backlinks/outreach"),
      ]);

      // Extract data or fallback to empty/default
      const [statsData, backlinksData, oppsData, emailsData] = results.map(r =>
        r.status === "fulfilled" ? r.value : null
      );

      setStats(statsData || { total: 0, referring_domains: 0, domain_authority: 0, toxic_links: 0, new_this_month: 0, new_domains: 0, da_change: 0, toxic_fixed: 0, growth_history: [], link_types: {} });
      setBacklinks(Array.isArray(backlinksData) ? backlinksData : []);
      setOpportunities(Array.isArray(oppsData) ? oppsData : []);
      setOutreachEmails(Array.isArray(emailsData) ? emailsData : []);
    } catch (err) {
      console.error("Failed to fetch backlink data:", err);
       setError("Could not load backlink data. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateWordPressBacklink = async () => {
    setCreatingBacklink(true);
    setCreateResult(null);
    try {
      const data = await api.post(
        "/api/backlinks/publish/wordpress",
        wordpressBacklink,
      );

      if (data.verified && data.backlink) {
        toast.success("Backlink published and verified.");
        setCreateResult(data.message);
        setBacklinks((current) => [data.backlink, ...current]);
      } else {
        toast.success("WordPress content published; verification is still pending.");
        setCreateResult(data.message || "Published, but not yet verified.");
      }

      setWordpressBacklink({
        wordpress_site: "",
        wordpress_username: "",
        wordpress_application_password: "",
        title: "",
        content: "",
        target_url: "",
        anchor_text: "",
        status: "publish",
      });
      fetchAllData();
    } catch (err: any) {
      const message = err?.data?.detail || err?.message || "Backlink publication failed.";
      toast.error(message);
      setCreateResult(message);
    } finally {
      setCreatingBacklink(false);
    }
  };

  const handleAddBacklink = async () => {
    try {
      const data = await api.post("/api/backlinks", newBacklink);
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
    setAnalyzingId(id);
    try {
      const data = await api.post(`/api/backlinks/${id}/analyze`);
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
    try {
      const data = await api.post("/api/backlinks/opportunities/generate");
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
      const data = await api.post(`/api/backlinks/opportunities/${oppId}/outreach`);
      const generated = data?.email;
      if (!generated?.id) {
        throw new Error("The outreach email was generated but no email record was returned.");
      }
      setGeneratedEmail(generated);
      setActiveTab("outreach");
      toast.success("AI outreach email generated. Enter the recipient and send it.");
      await fetchAllData();
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

  const handleSendOutreach = async (emailId: string) => {
    if (!recipientEmail.trim()) {
      toast.error("Enter the recipient email address first.");
      return;
    }
    setSendingOutreach(true);
    setSendEmailId(emailId);
    try {
      const draft = generatedEmail?.id === emailId ? generatedEmail : outreachEmails.find((item) => item.id === emailId);
      if (!draft) {
        throw new Error("Outreach email not found.");
      }
      if (draft.status !== "sent") {
        const updated = await api.put(`/api/backlinks/outreach/${emailId}`, {
          subject: draft.subject,
          body: draft.body,
        });
        setGeneratedEmail(updated);
      }
      const data = await api.post(`/api/backlinks/outreach/${emailId}/send`, {
        recipient_email: recipientEmail.trim(),
      });
      toast.success(data?.message || "Outreach email sent successfully.");
      setRecipientEmail("");
      if (generatedEmail?.id === emailId) {
        setGeneratedEmail((current) => current ? { ...current, status: "sent" } : current);
      }
      await fetchAllData();
    } catch (err: any) {
      toast.error(err?.data?.detail || err?.message || "Failed to send outreach email.");
    } finally {
      setSendingOutreach(false);
      setSendEmailId(null);
    }
  };

  const openSendDialog = (email: OutreachEmail) => {
    setGeneratedEmail(email);
    setSendEmailId(email.id);
  };

  const addBudget = async () => {
    setIsAddingBudget(true);
    try {
      await api.post(`/api/company/add-credits?amount=${budgetAmount}`, {});
      toast.success(`Added ${budgetAmount} credits.`);
      setShowBudgetDialog(false);
      setError(null);
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
          <Button variant="outline" onClick={() => setIsAddOpen(true)}>
            <Plus className="size-4" /> Track Backlink
          </Button>
          <Button className="bg-emerald-600 hover:bg-emerald-700 text-white shadow-md shadow-emerald-600/20" onClick={() => setIsCreateOpen(true)}>
            <Wand2 className="size-4" /> Create Backlink
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

      {!isConfigured && (
        <Card className="border-amber-200 dark:border-amber-900/50 bg-amber-50 dark:bg-amber-900/10">
          <CardContent className="p-4 flex items-center gap-3">
            <AlertCircle className="size-5 text-amber-600" />
            <p className="text-sm text-amber-700 dark:text-amber-400">
              Claude API Key required. Please configure it in Settings to enable AI features.
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
                      {Object.entries(stats.link_types).map((entry, index) => (
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
                            disabled={!isConfigured || analyzingId !== null}
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
            <Button onClick={handleGenerateOpportunities} disabled={!isConfigured} className="bg-emerald-600 hover:bg-emerald-700 text-white">
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
                  <Mail className="size-5 text-indigo-600" /> AI Outreach Email
                </CardTitle>
                <CardDescription>Review the AI draft, enter the prospect's email address, and send through your configured SMTP account.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Subject</Label>
                    <Input value={generatedEmail.subject} onChange={(e) => setGeneratedEmail({ ...generatedEmail, subject: e.target.value })} disabled={generatedEmail.status === "sent"} />
                  </div>
                  <div className="space-y-2">
                    <Label>Recipient Email</Label>
                    <Input type="email" value={recipientEmail} onChange={(e) => setRecipientEmail(e.target.value)} placeholder="editor@example.com" disabled={generatedEmail.status === "sent"} />
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Email Body</Label>
                  <Textarea value={generatedEmail.body} onChange={(e) => setGeneratedEmail({ ...generatedEmail, body: e.target.value })} className="min-h-[260px]" disabled={generatedEmail.status === "sent"} />
                </div>
                <div className="flex items-center justify-between gap-3 flex-wrap">
                  <div className="text-xs text-slate-500">
                    Status: <span className="font-medium">{generatedEmail.status}</span>
                    {generatedEmail.sent_at ? ` · Sent ${new Date(generatedEmail.sent_at).toLocaleString()}` : ""}
                  </div>
                  <Button
                    onClick={() => handleSendOutreach(generatedEmail.id)}
                    disabled={generatedEmail.status === "sent" || sendingOutreach}
                    className="bg-emerald-600 hover:bg-emerald-700 text-white"
                  >
                    {sendingOutreach && sendEmailId === generatedEmail.id ? <Loader2 className="size-4 animate-spin" /> : <Mail className="size-4" />}
                    {generatedEmail.status === "sent" ? "Already Sent" : "Send Email"}
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
            <CardHeader>
              <CardTitle className="font-serif">Outreach History</CardTitle>
              <CardDescription>AI-generated drafts and emails actually sent through SMTP.</CardDescription>
            </CardHeader>
            <CardContent>
              {outreachEmails.length === 0 ? (
                <p className="text-slate-500">No outreach emails yet. Generate one from AI Opportunities.</p>
              ) : (
                <div className="space-y-3">
                  {outreachEmails.map((email) => (
                    <div key={email.id} className="rounded-lg border border-slate-200 dark:border-slate-800 p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0">
                          <p className="font-medium truncate">{email.subject}</p>
                          <p className="text-xs text-slate-500 mt-1">Status: {email.status}{email.sent_at ? ` · ${new Date(email.sent_at).toLocaleString()}` : ""}</p>
                        </div>
                        <Button size="sm" variant="outline" onClick={() => openSendDialog(email)} disabled={email.status === "sent"}>
                          <Mail className="size-3" /> {email.status === "sent" ? "Sent" : "Review / Send"}
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Create Real WordPress Backlink Dialog */}
      <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="font-serif">Create Real Backlink</DialogTitle>
            <DialogDescription>
              Publish a WordPress post on a site you control or are explicitly authorized to publish on.
              The backlink is counted only after the public page is independently verified.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800 dark:border-amber-900/50 dark:bg-amber-900/10 dark:text-amber-300">
              Use a WordPress Application Password, not your normal WordPress password. Credentials are used only for this publication request and are not saved.
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>WordPress Site</Label>
                <Input value={wordpressBacklink.wordpress_site} onChange={(e) => setWordpressBacklink({ ...wordpressBacklink, wordpress_site: e.target.value })} placeholder="https://example.com" />
              </div>
              <div className="space-y-2">
                <Label>WordPress Username</Label>
                <Input value={wordpressBacklink.wordpress_username} onChange={(e) => setWordpressBacklink({ ...wordpressBacklink, wordpress_username: e.target.value })} placeholder="publisher" />
              </div>
            </div>

            <div className="space-y-2">
              <Label>Application Password</Label>
              <Input type="password" value={wordpressBacklink.wordpress_application_password} onChange={(e) => setWordpressBacklink({ ...wordpressBacklink, wordpress_application_password: e.target.value })} placeholder="xxxx xxxx xxxx xxxx" />
            </div>

            <div className="space-y-2">
              <Label>Post Title</Label>
              <Input value={wordpressBacklink.title} onChange={(e) => setWordpressBacklink({ ...wordpressBacklink, title: e.target.value })} placeholder="Useful industry resource" />
            </div>

            <div className="space-y-2">
              <Label>Post Content</Label>
              <Textarea className="min-h-[220px]" value={wordpressBacklink.content} onChange={(e) => setWordpressBacklink({ ...wordpressBacklink, content: e.target.value })} placeholder="Write the article/resource content here. Minimum 300 characters." />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Target URL</Label>
                <Input value={wordpressBacklink.target_url} onChange={(e) => setWordpressBacklink({ ...wordpressBacklink, target_url: e.target.value })} placeholder="https://your-site.com/page/" />
              </div>
              <div className="space-y-2">
                <Label>Anchor Text</Label>
                <Input value={wordpressBacklink.anchor_text} onChange={(e) => setWordpressBacklink({ ...wordpressBacklink, anchor_text: e.target.value })} placeholder="commercial cleaning Perth" />
              </div>
            </div>

            {createResult && (
              <div className="rounded-lg border border-slate-200 dark:border-slate-800 p-3 text-sm">
                {createResult}
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsCreateOpen(false)} disabled={creatingBacklink}>Cancel</Button>
            <Button onClick={handleCreateWordPressBacklink} disabled={creatingBacklink} className="bg-emerald-600 hover:bg-emerald-700 text-white">
              {creatingBacklink ? <><Loader2 className="size-4 animate-spin" /> Publishing & Verifying...</> : <><Wand2 className="size-4" /> Publish Real Backlink</>}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Add Backlink Dialog */}
      <Dialog open={isAddOpen} onOpenChange={setIsAddOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Track Existing Backlink</DialogTitle>
            <DialogDescription>The source page is checked live first. It will only be added if the target link is actually found.</DialogDescription>
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
            <Button onClick={handleAddBacklink} className="bg-emerald-600 hover:bg-emerald-700 text-white">Verify & Track</Button>
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