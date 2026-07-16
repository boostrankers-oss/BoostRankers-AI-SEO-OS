import { useStore } from "@/lib/store";
import {
  Card, CardContent, CardHeader, CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
} from "recharts";
import {
  Users, FileSearch, AlertTriangle, CheckCircle2, TrendingUp, CalendarDays,
  ShieldCheck, MapPin, Bot, Code2, Gauge, FileText, Server,
} from "lucide-react";
import { useState, useEffect } from "react";
import { motion } from "framer-motion";

const trendData = [
  { month: "Jan", traffic: 1200, conversions: 45 },
  { month: "Feb", traffic: 1500, conversions: 52 },
  { month: "Mar", traffic: 1800, conversions: 61 },
  { month: "Apr", traffic: 2200, conversions: 75 },
  { month: "May", traffic: 2500, conversions: 82 },
  { month: "Jun", traffic: 3100, conversions: 95 },
];

export function Dashboard() {
  const { clients, audits, loading } = useStore();
  const [scores, setScores] = useState<any>({});

  useEffect(() => {
    if (audits.length > 0 && audits[0].scores) {
      try {
        setScores(JSON.parse(audits[0].scores));
      } catch (e) {
        console.error("Failed to parse scores", e);
      }
    }
  }, [audits]);

  if (loading) return <div className="p-6">Loading...</div>;

  const criticalIssues = audits.reduce((sum, a) => {
    try {
      const findings = a.findings ? JSON.parse(a.findings) : [];
      return sum + findings.filter((f: any) => f.status === "critical").length;
    } catch {
      return sum;
    }
  }, 0);

  const stats = [
    { label: "Total Clients", value: clients.length, icon: Users, color: "text-emerald-600 bg-emerald-50" },
    { label: "Total Audits", value: audits.length, icon: FileSearch, color: "text-blue-600 bg-blue-50" },
    { label: "Critical Issues", value: criticalIssues, icon: AlertTriangle, color: "text-rose-600 bg-rose-50" },
    { label: "System Status", value: "Operational", icon: Server, color: "text-amber-600 bg-amber-50" },
  ];

  const scoreCards = [
    { label: "Technical Score", value: scores.Technical || 0, icon: Gauge, color: "bg-blue-500" },
    { label: "Content Score", value: scores.Content || 0, icon: FileText, color: "bg-emerald-500" },
    { label: "Local SEO Score", value: scores.Local || 0, icon: MapPin, color: "bg-amber-500" },
    { label: "Schema Score", value: scores.Schema || 0, icon: Code2, color: "bg-purple-500" },
    { label: "EEAT Score", value: scores.EEAT || 0, icon: ShieldCheck, color: "bg-rose-500" },
    { label: "AI Search Score", value: scores["AI Search"] || 0, icon: Bot, color: "bg-indigo-500" },
  ];

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="font-serif text-3xl font-bold text-slate-900">SEO Dashboard</h1>
        <p className="mt-1 text-sm text-slate-500">Overview of your clients and SEO performance</p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat, i) => {
          const Icon = stat.icon;
          return (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }}
            >
              <Card className="overflow-hidden border-slate-200 shadow-sm">
                <CardContent className="flex items-center justify-between p-6">
                  <div>
                    <p className="text-sm font-medium text-slate-500">{stat.label}</p>
                    <p className="mt-2 text-3xl font-bold text-slate-900">{stat.value}</p>
                  </div>
                  <div className={`rounded-xl p-3 ${stat.color}`}>
                    <Icon className="h-6 w-6" />
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {scoreCards.map((card, i) => {
          const Icon = card.icon;
          return (
            <motion.div
              key={card.label}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }}
            >
              <Card className="border-slate-200 shadow-sm">
                <CardContent className="p-6">
                  <div className="mb-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className={`rounded-lg p-2 ${card.color} text-white`}>
                        <Icon className="h-4 w-4" />
                      </div>
                      <span className="text-sm font-medium text-slate-600">{card.label}</span>
                    </div>
                    <span className="text-2xl font-bold text-slate-900">{card.value}</span>
                  </div>
                  <Progress value={card.value} className="h-2" />
                </CardContent>
              </Card>
            </motion.div>
          );
        })}
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="border-slate-200 shadow-sm lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 font-serif text-xl">
              <TrendingUp className="h-5 w-5 text-emerald-600" />
              Traffic & Conversions
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={trendData}>
                <defs>
                  <linearGradient id="colorTraffic" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="colorConv" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="month" stroke="#64748b" fontSize={12} />
                <YAxis stroke="#64748b" fontSize={12} />
                <Tooltip />
                <Area type="monotone" dataKey="traffic" stroke="#10b981" fillOpacity={1} fill="url(#colorTraffic)" />
                <Area type="monotone" dataKey="conversions" stroke="#6366f1" fillOpacity={1} fill="url(#colorConv)" />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card className="border-slate-200 shadow-sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 font-serif text-xl">
              <CalendarDays className="h-5 w-5 text-emerald-600" />
              Recent Audits
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {audits.slice(0, 5).map((audit) => (
              <div key={audit.id} className="flex items-start gap-3 rounded-lg border border-slate-100 p-3">
                <div className="flex-1">
                  <p className="text-sm font-medium text-slate-800">{audit.url}</p>
                  <Badge variant="outline" className="mt-1 text-xs">{audit.status}</Badge>
                </div>
              </div>
            ))}
            {audits.length === 0 && (
              <p className="text-sm text-slate-500">No audits run yet.</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}