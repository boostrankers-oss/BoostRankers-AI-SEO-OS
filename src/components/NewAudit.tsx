import { useState } from "react";
import { useStore, AUDIT_AGENTS, generateAudit, type AuditResult } from "@/lib/store";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { AlertTriangle, CheckCircle2, Info, Loader2, Search, XCircle } from "lucide-react";
import { motion } from "framer-motion";

export function NewAudit() {
  const { addAudit, apiKey } = useStore();
  const [url, setUrl] = useState("");
  const [keyword, setKeyword] = useState("");
  const [location, setLocation] = useState("");
  const [competitors, setCompetitors] = useState("");
  const [running, setRunning] = useState(false);
  const [currentAgent, setCurrentAgent] = useState(-1);
  const [result, setResult] = useState<AuditResult | null>(null);

  const handleAudit = async () => {
    if (!url || !keyword) return;
    setRunning(true);
    setResult(null);
    setCurrentAgent(0);

    // Simulate agent execution
    for (let i = 0; i < AUDIT_AGENTS.length; i++) {
      setCurrentAgent(i);
      await new Promise((resolve) => setTimeout(resolve, 600));
    }

    const compArray = competitors.split("\n").map((c) => c.trim()).filter(Boolean);
    const audit = generateAudit(url, keyword, location, compArray);
    
    addAudit(audit);
    setResult(audit);
    setRunning(false);
    setCurrentAgent(-1);
  };

  const statusConfig = {
    critical: { icon: XCircle, color: "text-rose-600", bg: "bg-rose-50" },
    warning: { icon: AlertTriangle, color: "text-amber-600", bg: "bg-amber-50" },
    passed: { icon: CheckCircle2, color: "text-emerald-600", bg: "bg-emerald-50" },
    info: { icon: Info, color: "text-blue-600", bg: "bg-blue-50" },
  };

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="font-serif text-3xl font-bold text-slate-900">New SEO Audit</h1>
        <p className="mt-1 text-sm text-slate-500">Run a comprehensive multi-agent SEO analysis</p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card className="border-slate-200 shadow-sm">
          <CardHeader>
            <CardTitle className="font-serif text-xl">Audit Configuration</CardTitle>
            <CardDescription>Enter the details below to start the audit</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="url">Website URL</Label>
              <Input id="url" placeholder="https://example.com" value={url} onChange={(e) => setUrl(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="keyword">Primary Keyword</Label>
              <Input id="keyword" placeholder="roof repair denver" value={keyword} onChange={(e) => setKeyword(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="location">Business Location</Label>
              <Input id="location" placeholder="Denver, CO" value={location} onChange={(e) => setLocation(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="competitors">Competitor URLs (one per line)</Label>
              <Textarea id="competitors" placeholder="https://competitor1.com" value={competitors} onChange={(e) => setCompetitors(e.target.value)} rows={4} />
            </div>
            <Button onClick={handleAudit} disabled={running || !url || !keyword} className="w-full bg-emerald-600 hover:bg-emerald-700">
              {running ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Search className="mr-2 h-4 w-4" />}
              {running ? "Running Audit..." : "Start Audit"}
            </Button>
          </CardContent>
        </Card>

        <Card className="border-slate-200 shadow-sm">
          <CardHeader>
            <CardTitle className="font-serif text-xl">Agent Execution</CardTitle>
            <CardDescription>
              {apiKey ? "Live AI agents analyzing your site" : "Simulated agents (add API key in Settings for live AI)"}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {AUDIT_AGENTS.map((agent, i) => {
              const isDone = currentAgent > i || (currentAgent === -1 && !running);
              const isActive = currentAgent === i && running;
              return (
                <motion.div
                  key={agent}
                  initial={{ opacity: 0.5 }}
                  animate={{ opacity: isDone || isActive ? 1 : 0.5 }}
                  className={`flex items-center gap-3 rounded-lg p-3 ${isActive ? "bg-emerald-50" : "bg-slate-50"}`}
                >
                  {isActive ? (
                    <Loader2 className="h-4 w-4 animate-spin text-emerald-600" />
                  ) : isDone ? (
                    <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                  ) : (
                    <div className="h-4 w-4 rounded-full border-2 border-slate-300" />
                  )}
                  <span className={`text-sm font-medium ${isDone || isActive ? "text-slate-800" : "text-slate-400"}`}>
                    {agent}
                  </span>
                </motion.div>
              );
            })}
          </CardContent>
        </Card>
      </div>

      {result && (
        <Card className="border-slate-200 shadow-sm">
          <CardHeader>
            <CardTitle className="font-serif text-xl">Audit Results for {result.url}</CardTitle>
            <CardDescription>{result.findings.length} findings across {AUDIT_AGENTS.length} agents</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
              {Object.entries(result.scores).map(([key, value]) => (
                <div key={key} className="rounded-lg border border-slate-200 p-3 text-center">
                  <p className="text-2xl font-bold text-slate-900">{value}</p>
                  <p className="mt-1 text-xs text-slate-500">{key}</p>
                </div>
              ))}
            </div>
            <div className="space-y-2">
              {result.findings.map((finding, i) => {
                const config = statusConfig[finding.status];
                const Icon = config.icon;
                return (
                  <div key={i} className="flex items-start gap-3 rounded-lg border border-slate-200 p-4">
                    <div className={`rounded-lg p-2 ${config.bg}`}>
                      <Icon className={`h-4 w-4 ${config.color}`} />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-slate-900">{finding.check}</span>
                        <Badge variant="outline" className="text-xs">{finding.agent}</Badge>
                      </div>
                      <p className="mt-1 text-sm text-slate-600">{finding.detail}</p>
                      <p className="mt-1 text-xs text-slate-500">
                        <span className="font-medium">Recommendation:</span> {finding.recommendation}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}