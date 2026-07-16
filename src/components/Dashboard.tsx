import { useStore } from "@/lib/store";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import {
  Users,
  FileSearch,
  AlertTriangle,
  CheckCircle2,
  TrendingUp,
  CalendarDays,
  ShieldCheck,
  MapPin,
  Bot,
  Code2,
  Gauge,
  FileText,
  Check,
} from "lucide-react";

const trendData = [
  { month: "Jan", traffic: 1200, conversions: 45 },
  { month: "Feb", traffic: 1500, conversions: 52 },
  { month: "Mar", traffic: 1800, conversions: 61 },
  { month: "Apr", traffic: 2200, conversions: 75 },
  { month: "May", traffic: 2500, conversions: 82 },
  { month: "Jun", traffic: 3100, conversions: 95 },
];

export function Dashboard() {
  const { clients, audits, tasks, toggleTask } = useStore();

  const latestAudit = audits[0];
  const scores = latestAudit?.scores || {};
  const criticalIssues = audits.reduce((sum, a) => sum + a.findings.filter((f) => f.status === "critical").length, 0);
  const completedTasks = tasks.filter((t) => t.done).length;

  const stats = [
    { label: "Total Clients", value: clients.length, icon: Users, color: "text-emerald-600 bg-emerald-50" },
    { label: "Total Audits", value: audits.length, icon: FileSearch, color: "text-blue-600 bg-blue-50" },
    { label: "Critical Issues", value: criticalIssues, icon: AlertTriangle, color: "text-rose-600 bg-rose-50" },
    { label: "Completed Tasks", value: `${completedTasks}/${tasks.length}`, icon: CheckCircle2, color: "text-amber-600 bg-amber-50" },
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

      {/* Top Stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <Card key={stat.label} className="overflow-hidden border-slate-200 shadow-sm">
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
          );
        })}
      </div>

      {/* Score Cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {scoreCards.map((card) => {
          const Icon = card.icon;
          return (
            <Card key={card.label} className="border-slate-200 shadow-sm">
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
          );
        })}
      </div>

      {/* Charts and Tasks */}
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
              Monthly Tasks
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {tasks.slice(0, 5).map((task) => (
              <div key={task.id} className="flex items-start gap-3 rounded-lg border border-slate-100 p-3">
                <Button
                  variant="ghost"
                  size="icon"
                  className="mt-0 h-5 w-5 rounded-full p-0"
                  onClick={() => toggleTask(task.id)}
                >
                  {task.done ? (
                    <Check className="h-4 w-4 text-emerald-600" />
                  ) : (
                    <div className="h-4 w-4 rounded-full border-2 border-slate-300" />
                  )}
                </Button>
                <div className="flex-1">
                  <p className={`text-sm font-medium ${task.done ? "text-slate-400 line-through" : "text-slate-800"}`}>
                    {task.title}
                  </p>
                  <Badge variant="outline" className="mt-1 text-xs">{task.category}</Badge>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}