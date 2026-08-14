import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
    TrendingUp,
    TrendingDown,
    Activity,
    FileText,
    Zap,
    Database,
    ShieldCheck,
    Bot,
    Server,
    CheckCircle2,
} from "lucide-react";

import {
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
} from "recharts";

const accentMap: Record<string, string> = {
  emerald: "bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  indigo: "bg-indigo-50 dark:bg-indigo-500/10 text-indigo-600 dark:text-indigo-400",
  amber: "bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400",
  rose: "bg-rose-50 dark:bg-rose-500/10 text-rose-600 dark:text-rose-400",
};

interface DashboardProps {
  onRunAudit: () => void;
}

interface DashboardOverview {
  total_clients: number;
  total_audits: number;
  completed_audits: number;
  pending_audits: number;
  failed_audits: number;

  running_audits: number;
  queued_audits: number;

  critical_issues: number;
  warnings: number;
  passed_checks: number;

  overall_score: number;
  technical_score: number;
  content_score: number;
  eeat_score: number;
  local_seo_score: number;
  schema_score: number;
  ai_search_score: number;
  backlink_score: number;
  internal_link_score: number;
  core_web_vitals_score: number;
  performance_score: number;
  security_score: number;
}

interface DashboardChartPoint {
  date: string;
  overall: number;
  technical: number;
  content: number;
}

interface DashboardChartsResponse {
  trend: DashboardChartPoint[];
}

interface RecentAudit {
  id: number;
  url: string;
  keyword: string;
  score: number;
  status: string;
  created_at: string;
}

interface DashboardSystem {
  database: string;
  api_latency: number;
  claude_status: string;
  crawler_status: string;
  queue_size: number;
}

interface DashboardTask {
  id: number;
  title: string;
  priority: string;
  status: string;
}

interface DashboardNotification {
  id: number;
  title: string;
  type: string;
  created_at: string;
}

interface DashboardRecommendation {
  title: string;
  impact: string;
  priority: string;
}

interface DashboardClient {
  id: number;
  name: string;
  website: string;
  score: number;
}

export function Dashboard({ onRunAudit }: DashboardProps) {
  const [loading, setLoading] = useState(true);

const [error, setError] = useState("");

const [overview, setOverview] =
  useState<DashboardOverview | null>(null);

const [charts, setCharts] =
  useState<DashboardChartPoint[]>([]);

const [recentAudits, setRecentAudits] =
  useState<RecentAudit[]>([]);

const [systemStatus, setSystemStatus] =
  useState<DashboardSystem | null>(null);

const [tasks, setTasks] =
  useState<DashboardTask[]>([]);

const [notifications, setNotifications] =
  useState<DashboardNotification[]>([]);

const [recommendations, setRecommendations] =
  useState<DashboardRecommendation[]>([]);

const [clients, setClients] =
  useState<DashboardClient[]>([]);

const loadDashboard = useCallback(async () => {
  setLoading(true);
  setError("");

  try {
    const [
		overviewData,
		chartsData,
		auditsData,
		systemData,
		tasksData,
		notificationsData,
		clientsData,
		 aiData,
	] = await Promise.all([
		api.get("/api/dashboard/overview"),
		api.get("/api/dashboard/charts"),
		api.get("/api/dashboard/recent-audits"),
		api.get("/api/dashboard/system"),
		api.get("/api/dashboard/tasks"),
		api.get("/api/dashboard/notifications"),
		api.get("/api/dashboard/clients"),
		api.get("/api/dashboard/ai"),
]);

console.log("Charts API:", chartsData);
console.log("Is Array:", Array.isArray(chartsData));


    setOverview(overviewData);

    setCharts(chartsData.items ?? []);

    setRecentAudits(auditsData.items ?? []);

    setSystemStatus(systemData);

    setTasks(tasksData.items ?? []);

    setNotifications(notificationsData.items ?? []);

    setRecommendations(aiData ?? []);

    setClients(clientsData.clients ?? []);
  } catch (err) {
    console.error(err);

    setError("Unable to load dashboard.");
  } finally {
    setLoading(false);
  }
}, []);

useEffect(() => {
  loadDashboard();
}, [loadDashboard]);

const stats = overview
  ? [
      {
        label: "Overall",
        value: overview.overall_score,
        icon: Activity,
        accent: "emerald",
      },
      {
        label: "Technical",
        value: overview.technical_score,
        icon: Database,
        accent: "indigo",
      },
      {
        label: "Content",
        value: overview.content_score,
        icon: FileText,
        accent: "amber",
      },
      {
        label: "EEAT",
        value: overview.eeat_score,
        icon: ShieldCheck,
        accent: "emerald",
      },
      {
        label: "Local SEO",
        value: overview.local_seo_score,
        icon: CheckCircle2,
        accent: "indigo",
      },
      {
        label: "Schema",
        value: overview.schema_score,
        icon: Bot,
        accent: "amber",
      },
      {
        label: "AI Search",
        value: overview.ai_search_score,
        icon: Zap,
        accent: "emerald",
      },
      {
        label: "CWV",
        value: overview.core_web_vitals_score,
        icon: Activity,
        accent: "rose",
      },
      {
        label: "Backlinks",
        value: overview.backlink_score,
        icon: TrendingUp,
        accent: "indigo",
      },
      {
        label: "Internal Links",
        value: overview.internal_link_score,
        icon: TrendingUp,
        accent: "amber",
      },
      {
        label: "Performance",
        value: overview.performance_score,
        icon: Server,
        accent: "emerald",
      },
      {
        label: "Security",
        value: overview.security_score,
        icon: ShieldCheck,
        accent: "rose",
      },
    ]
  : [];
  
 if (loading) {
  return (
    <div className="p-8">
      Loading dashboard...
    </div>
  );
}

if (error) {
  return (
    <div className="p-8 space-y-4">
      <p className="text-red-500">
        {error}
      </p>

      <Button onClick={loadDashboard}>
        Retry
      </Button>
    </div>
  );
}

  return (
    <div className="p-8 space-y-6">
      <header className="flex flex-col xl:flex-row xl:items-center xl:justify-between gap-6">

  <div>
    <h2 className="font-serif text-3xl font-bold tracking-tight">
      Agency Dashboard
    </h2>

    <p className="text-slate-500 dark:text-slate-400 mt-2">
      Monitor clients, audits, SEO performance and AI recommendations in one place.
    </p>

    <div className="flex flex-wrap gap-3 mt-4">

      <div className="px-3 py-1 rounded-full bg-emerald-100 text-emerald-700 text-xs font-medium">
        {overview?.running_audits ?? 0} Running
      </div>

      <div className="px-3 py-1 rounded-full bg-amber-100 text-amber-700 text-xs font-medium">
        {overview?.queued_audits ?? 0} Queued
      </div>

      <div className="px-3 py-1 rounded-full bg-rose-100 text-rose-700 text-xs font-medium">
        {overview?.critical_issues ?? 0} Critical
      </div>

    </div>

  </div>

  <div className="flex gap-3">

    <Button
      variant="outline"
      onClick={loadDashboard}
    >
      Refresh
    </Button>

    <Button
      onClick={onRunAudit}
      className="bg-emerald-600 hover:bg-emerald-700 text-white"
    >
      <Zap className="mr-2 h-4 w-4"/>
      Run New Audit
    </Button>

  </div>

</header>

      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
       {stats.map((stat) => (

		<Card key={stat.label} className="border-slate-200 dark:border-slate-800 shadow-sm hover:shadow-md transition-all" >

		<CardContent className="p-5">

		<div className="flex items-center justify-between">

		<div>

		<p className="text-sm text-slate-500">

		{stat.label}

		</p>

		<p className="text-3xl font-bold mt-2">

		{stat.value}

		</p>

		</div>

		<div className={`size-11 rounded-xl flex items-center justify-center ${accentMap[stat.accent]}`} >

		<stat.icon className="size-5"/>

		</div>

		</div>

		<div className="mt-5">

		<div className="h-2 rounded-full bg-slate-200 dark:bg-slate-700 overflow-hidden">

		<div className="h-full bg-emerald-500" style={{width:`${Math.min(100,Number(stat.value))}%`}} />

		</div>

		</div>

		</CardContent>

		</Card>

		))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2 border-slate-200 dark:border-slate-800 shadow-sm">
          <CardHeader>
            <CardTitle className="font-serif">Performance Trends</CardTitle>
          </CardHeader>
     
		  <CardContent>
			<div className="h-[340px]">
				<ResponsiveContainer width="100%" height="100%">
				<LineChart data={charts} margin={{top:20,right:20,left:0,bottom:0}}>

				<CartesianGrid strokeDasharray="3 3" opacity={0.15} />

			<XAxis dataKey="date" />
			<YAxis domain={[0,100]} />

			<Tooltip/>

			<Legend/>

			<Line
				type="monotone"
				dataKey="overall"
				name="Overall Score"
				strokeWidth={3}
				dot={{r:4}}
			/>

			<Line
				type="monotone"
				dataKey="technical"
				name="Technical"
				strokeWidth={3}
				dot={{r:4}}
			/>

			<Line
				type="monotone"
				dataKey="content"
				name="Content"
				strokeWidth={3}
				dot={{r:4}}
			/>

			</LineChart>

		</ResponsiveContainer>

		</div>

		</CardContent>
        </Card>
        <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
          <CardHeader>
            <CardTitle className="font-serif">System Status</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
             <div className="space-y-4">

				<div className="flex justify-between">
				<span>Database</span>
				<span>{systemStatus?.database}</span>
				</div>

				<div className="flex justify-between">
				<span>API</span>
				<span>{systemStatus?.api}</span>
				</div>

				<div className="flex justify-between">
				<span>Audit Engine</span>
				<span>{systemStatus?.audit_engine}</span>
				</div>

				<div className="flex justify-between">
				<span>Claude AI</span>
				<span>{systemStatus?.claude_ai}</span>
				</div>

				<div className="flex justify-between">
				<span>Queue</span>
				<span>{systemStatus?.queue.running}</span>
				</div>

				<div className="flex justify-between">
				<span>Success Rate</span>
				<span>{systemStatus?.success_rate}%</span>
				</div>

				</div>
          </CardContent>
        </Card>
		<Card>

			<CardHeader>

				<CardTitle>

					Recent Audits

				</CardTitle>

			</CardHeader>

				<CardContent>

					{recentAudits.map(audit=>(

						<div
						key={audit.id}
						className="flex justify-between py-2 border-b"
						>

						<div>

						<div className="font-medium">

						{audit.website}

						</div>

						<div className="text-xs text-slate-500">

						{audit.primary_keyword}

						</div>

					</div>

						<div>

						{audit.overall_score}

						</div>

					</div>

					))}

				</CardContent>

		</Card>
		<Card>

			<CardHeader>

				<CardTitle>

				AI Recommendations

				</CardTitle>

			</CardHeader>

			<CardContent>

				{recommendations.map((item,index)=>(

				<div
				key={index}
				className="border-b py-3"
				>

				<div className="font-medium">

				{item.title}

				</div>

				<div className="text-xs">

				{item.priority}

				</div>

				</div>

				))}

			</CardContent>

	</Card>
      </div>
    </div>
  );
}