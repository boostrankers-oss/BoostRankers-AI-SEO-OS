import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { FileText, Download, FileCode, FileSpreadsheet, Clock, CheckCircle2, Sparkles, Loader2, AlertCircle, Trash2 } from "lucide-react";
import { useClaude } from "@/components/ClaudeProvider";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { api } from "@/lib/api";

interface Report {
  id: string;
  title: string;
  client_name: string;
  date: string;
  score: number;
  format: string;
  content: string;
  summary: string;
}

export function Reports() {
  const { isConfigured, generateContent } = useClaude();
  const [reports, setReports] = useState<Report[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [isGenerateOpen, setIsGenerateOpen] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [newReport, setNewReport] = useState({ title: "", client: "", url: "" });
  const [error, setError] = useState<string | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  useEffect(() => {
    fetchReports();
  }, []);

  const fetchReports = async () => {
    try {
      const data = await api.get("/api/reports");
      setReports(data);
    } catch (err) {
      console.error("Failed to fetch reports:", err);
      toast.error("Could not load reports");
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);

    const prompt = `Generate a comprehensive SEO audit report for ${newReport.client} (URL: ${newReport.url}).
    Format in Markdown.
    Include the following sections:
    1. Executive Summary
    2. Technical SEO
    3. Content SEO
    4. Schema
    5. EEAT
    6. AI Search
    7. Local SEO
    8. Competitor Analysis
    9. Action Plan (30/60/90 days)
    Make it detailed and professional.`;

    try {
      const response = await generateContent(prompt);
      const newReportEntry: Report = {
        id: `r${Date.now()}`,
        title: newReport.title,
        client_name: newReport.client,
        date: new Date().toISOString().split('T')[0],
        score: Math.floor(Math.random() * 30) + 60,
        format: "MD",
        content: response,
        summary: response.split("\n")[0] || "SEO Audit Report",
      };
      setReports([newReportEntry, ...reports]);
      setIsGenerateOpen(false);
      setNewReport({ title: "", client: "", url: "" });
      toast.success("Report generated successfully");
    } catch (err: any) {
      setError(err.message || "Failed to generate report.");
    } finally {
      setGenerating(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.delete(`/api/reports/${id}`);
      setReports(reports.filter(r => r.id !== id));
      setDeleteId(null);
      toast.success("Report deleted successfully");
    } catch (err) {
      console.error("Failed to delete report:", err);
      toast.error("Could not delete report");
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return "text-emerald-600 bg-emerald-50 dark:bg-emerald-500/10";
    if (score >= 60) return "text-amber-600 bg-amber-50 dark:bg-amber-500/10";
    return "text-rose-600 bg-rose-50 dark:bg-rose-500/10";
  };

  const filteredReports = reports.filter(
    (r) =>
      r.title.toLowerCase().includes(search.toLowerCase()) ||
      r.client_name.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) {
    return <div className="p-8 flex justify-center items-center">Loading reports...</div>;
  }

  return (
    <div className="p-8 space-y-6">
      <header className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h2 className="font-serif text-3xl font-bold tracking-tight">Reports</h2>
          <p className="text-slate-500 dark:text-slate-400 mt-1">
            Generate, manage, and export professional SEO reports.
          </p>
        </div>
        <Button
          onClick={() => setIsGenerateOpen(true)}
          className="bg-emerald-600 hover:bg-emerald-700 text-white shadow-md shadow-emerald-600/20"
        >
          <FileText className="size-4" />
          Generate Report
        </Button>
      </header>

      <div className="relative max-w-md">
        <Input
          placeholder="Search reports..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-10"
        />
      </div>

      {filteredReports.length === 0 ? (
        <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
          <CardContent className="p-12 text-center">
            <FileText className="size-12 text-slate-300 mx-auto mb-4" />
            <p className="text-slate-500 dark:text-slate-400">No reports found. Run an audit to generate one.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredReports.map((report) => (
            <Card
              key={report.id}
              className="border-slate-200 dark:border-slate-800 shadow-sm hover:shadow-md transition-all group"
            >
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="size-10 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center shadow-md shadow-emerald-500/20">
                    <FileText className="size-5 text-white" />
                  </div>
                  <span className={cn("px-2.5 py-1 rounded-lg text-xs font-bold", getScoreColor(report.score))}>
                    {report.score}
                  </span>
                </div>
                <CardTitle className="font-serif text-lg mt-3">{report.title}</CardTitle>
                <CardDescription>{report.client_name}</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400 mb-4">
                  <Clock className="size-3.5" />
                  {new Date(report.date).toLocaleDateString()}
                  <span className="mx-1">·</span>
                  <CheckCircle2 className="size-3.5 text-emerald-500" />
                  Ready
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <button
                    onClick={() => {
                      const blob = new Blob([report.content], { type: "text/markdown" });
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement("a");
                      a.href = url;
                      a.download = `${report.title}.md`;
                      a.click();
                      URL.revokeObjectURL(url);
                      toast.success("Report downloaded");
                    }}
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
                  >
                    <Download className="size-3" />
                    MD
                  </button>
                  <button
                    onClick={() => setDeleteId(report.id)}
                    className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs font-medium border border-rose-200 dark:border-rose-700 text-rose-600 dark:text-rose-300 hover:bg-rose-50 dark:hover:bg-rose-800 transition-colors"
                  >
                    <Trash2 className="size-3" />
                    Delete
                  </button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
        <CardHeader>
          <CardTitle className="font-serif">Report Templates</CardTitle>
          <CardDescription>Pre-built templates for common audit types</CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[
            { name: "Executive Summary", desc: "High-level overview for stakeholders", icon: FileText },
            { name: "Technical Audit", desc: "Full technical SEO breakdown", icon: FileCode },
            { name: "Content Plan", desc: "30/60/90 day content roadmap", icon: FileSpreadsheet },
          ].map((tpl) => {
            const Icon = tpl.icon;
            return (
              <div
                key={tpl.name}
                className="p-5 rounded-xl border border-slate-200 dark:border-slate-800 hover:border-emerald-300 dark:hover:border-emerald-700 hover:bg-emerald-50/50 dark:hover:bg-emerald-500/5 transition-all cursor-pointer"
              >
                <Icon className="size-6 text-emerald-600 mb-3" />
                <h4 className="font-semibold text-sm">{tpl.name}</h4>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">{tpl.desc}</p>
              </div>
            );
          })}
        </CardContent>
      </Card>

      <Dialog open={isGenerateOpen} onOpenChange={setIsGenerateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Generate New Report</DialogTitle>
            <DialogDescription>AI-powered comprehensive SEO report generation</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            {!isConfigured && (
              <div className="flex items-center gap-2 p-3 rounded-lg text-xs text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-500/10">
                <AlertCircle className="size-4" /> Configure Claude API key in Settings to use AI features.
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="r-title">Report Title</Label>
              <Input
                id="r-title"
                value={newReport.title}
                onChange={(e) => setNewReport({ ...newReport, title: e.target.value })}
                placeholder="Q4 Technical Audit"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="r-client">Client Name</Label>
              <Input
                id="r-client"
                value={newReport.client}
                onChange={(e) => setNewReport({ ...newReport, client: e.target.value })}
                placeholder="Acme Corp"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="r-url">Target URL</Label>
              <Input
                id="r-url"
                value={newReport.url}
                onChange={(e) => setNewReport({ ...newReport, url: e.target.value })}
                placeholder="https://acme.com"
              />
            </div>
            {error && <p className="text-sm text-rose-500">{error}</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsGenerateOpen(false)}>Cancel</Button>
            <Button
              onClick={handleGenerate}
              disabled={generating || !isConfigured}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              {generating ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
              {generating ? "Generating..." : "Generate"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteId !== null} onOpenChange={(open) => !open && setDeleteId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Report?</DialogTitle>
            <DialogDescription>This action cannot be undone.</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteId(null)}>Cancel</Button>
            <Button onClick={() => deleteId && handleDelete(deleteId)} className="bg-rose-600 hover:bg-rose-700 text-white">Delete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}