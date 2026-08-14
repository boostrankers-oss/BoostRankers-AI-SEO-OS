import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { BarChart3, Upload, FileText, CheckCircle2 } from "lucide-react";
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";

const gscData = [
  { date: "Oct 1", clicks: 1200, impressions: 24000 },
  { date: "Oct 5", clicks: 1800, impressions: 31000 },
  { date: "Oct 10", clicks: 1500, impressions: 28000 },
  { date: "Oct 15", clicks: 2200, impressions: 38000 },
  { date: "Oct 20", clicks: 2600, impressions: 42000 },
  { date: "Oct 25", clicks: 3100, impressions: 51000 },
];

export function GoogleIntegration() {
  return (
    <div className="p-8 space-y-6">
      <header>
        <h2 className="font-serif text-3xl font-bold tracking-tight">Google Integration</h2>
        <p className="text-slate-500 dark:text-slate-400 mt-1">
          Upload and analyze Search Console and GA4 data.
        </p>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
          <CardHeader>
            <CardTitle className="font-serif flex items-center gap-2"><FileText className="size-5 text-emerald-600" /> Search Console CSV</CardTitle>
            <CardDescription>Upload performance report</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="border-2 border-dashed border-slate-200 dark:border-slate-800 rounded-xl p-8 text-center hover:border-emerald-400 transition-colors cursor-pointer">
              <Upload className="size-8 text-slate-400 mx-auto mb-3" />
              <p className="text-sm font-medium">Drop CSV here or click to upload</p>
              <p className="text-xs text-slate-500 mt-1">Max 10MB</p>
            </div>
            <div className="mt-3 flex items-center gap-2 text-xs text-emerald-600"><CheckCircle2 className="size-4" /> Last upload: Oct 25, 2024</div>
          </CardContent>
        </Card>

        <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
          <CardHeader>
            <CardTitle className="font-serif flex items-center gap-2"><BarChart3 className="size-5 text-indigo-600" /> GA4 Data</CardTitle>
            <CardDescription>Upload analytics export</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="border-2 border-dashed border-slate-200 dark:border-slate-800 rounded-xl p-8 text-center hover:border-indigo-400 transition-colors cursor-pointer">
              <Upload className="size-8 text-slate-400 mx-auto mb-3" />
              <p className="text-sm font-medium">Drop CSV here or click to upload</p>
              <p className="text-xs text-slate-500 mt-1">Max 10MB</p>
            </div>
            <div className="mt-3 flex items-center gap-2 text-xs text-emerald-600"><CheckCircle2 className="size-4" /> Last upload: Oct 24, 2024</div>
          </CardContent>
        </Card>
      </div>

      <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
        <CardHeader>
          <CardTitle className="font-serif">Search Console Performance</CardTitle>
          <CardDescription>Clicks and impressions over time</CardDescription>
        </CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={gscData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" strokeOpacity={0.3} />
              <XAxis dataKey="date" stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
              <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
              <Tooltip contentStyle={{ backgroundColor: "rgba(15, 23, 42, 0.9)", border: "none", borderRadius: "0.75rem", color: "#fff" }} />
              <Line type="monotone" dataKey="clicks" stroke="#10b981" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="impressions" stroke="#6366f1" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  );
}