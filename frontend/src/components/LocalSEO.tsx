import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { MapPin, CheckCircle2, XCircle, Star, Phone, Clock } from "lucide-react";

const audits = [
  { name: "Google Business Profile", status: true, detail: "Claimed and verified" },
  { name: "NAP Consistency", status: true, detail: "Name, Address, Phone consistent across 45 citations" },
  { name: "Local Citations", status: false, detail: "Missing from 12 local directories" },
  { name: "Review Velocity", status: true, detail: "4.8 average from 210 reviews" },
  { name: "Local Schema Markup", status: false, detail: "LocalBusiness schema not detected" },
  { name: "Geo-targeted Pages", status: true, detail: "12 city pages found" },
];

export function LocalSEO() {
  return (
    <div className="p-8 space-y-6">
      <header>
        <h2 className="font-serif text-3xl font-bold tracking-tight">Local SEO</h2>
        <p className="text-slate-500 dark:text-slate-400 mt-1">
          Monitor local search presence, citations, and Google Business Profile.
        </p>
      </header>

      <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
        <CardHeader>
          <CardTitle className="font-serif">Business Profile</CardTitle>
          <CardDescription>Enter your business details to audit local presence</CardDescription>
        </CardHeader>
        <CardContent className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2"><Label htmlFor="bName">Business Name</Label><Input id="bName" defaultValue="Acme Corp" /></div>
          <div className="space-y-2"><Label htmlFor="bPhone">Phone Number</Label><Input id="bPhone" defaultValue="+1 555 0100" /></div>
          <div className="space-y-2"><Label htmlFor="bAddress">Address</Label><Input id="bAddress" defaultValue="123 Main St, San Francisco" /></div>
          <div className="space-y-2"><Label htmlFor="bCategory">Category</Label><Input id="bCategory" defaultValue="Software Company" /></div>
          <Button className="md:col-span-2 bg-emerald-600 hover:bg-emerald-700 text-white shadow-md shadow-emerald-600/20">Run Local Audit</Button>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
          <CardHeader><CardTitle className="font-serif flex items-center gap-2"><Star className="size-5 text-amber-500" /> Reviews</CardTitle></CardHeader>
          <CardContent>
            <p className="font-serif text-4xl font-bold text-amber-500">4.8</p>
            <p className="text-sm text-slate-500 mt-1">210 total reviews</p>
            <div className="mt-4 space-y-1">
              <div className="flex items-center gap-2 text-sm"><Star className="size-3 text-amber-400 fill-amber-400" /> 180</div>
              <div className="flex items-center gap-2 text-sm"><Star className="size-3 text-amber-400 fill-amber-400" /> 20</div>
              <div className="flex items-center gap-2 text-sm"><Star className="size-3 text-amber-400 fill-amber-400" /> 5</div>
            </div>
          </CardContent>
        </Card>
        <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
          <CardHeader><CardTitle className="font-serif flex items-center gap-2"><MapPin className="size-5 text-emerald-600" /> Citations</CardTitle></CardHeader>
          <CardContent>
            <p className="font-serif text-4xl font-bold text-emerald-600">45</p>
            <p className="text-sm text-slate-500 mt-1">Live local citations</p>
            <div className="mt-4 text-xs text-slate-500">12 missing directories identified</div>
          </CardContent>
        </Card>
        <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
          <CardHeader><CardTitle className="font-serif flex items-center gap-2"><Clock className="size-5 text-indigo-600" /> Response Rate</CardTitle></CardHeader>
          <CardContent>
            <p className="font-serif text-4xl font-bold text-indigo-600">92%</p>
            <p className="text-sm text-slate-500 mt-1">Review response rate</p>
            <div className="mt-4 text-xs text-slate-500">Avg response time: 4 hours</div>
          </CardContent>
        </Card>
      </div>

      <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
        <CardHeader>
          <CardTitle className="font-serif">Audit Checklist</CardTitle>
          <CardDescription>Local SEO completeness evaluation</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {audits.map((item) => (
            <div key={item.name} className="flex items-center gap-3 p-3 rounded-lg border border-slate-200 dark:border-slate-800">
              {item.status ? <CheckCircle2 className="size-5 text-emerald-500" /> : <XCircle className="size-5 text-rose-500" />}
              <div>
                <p className="text-sm font-medium">{item.name}</p>
                <p className="text-xs text-slate-500 dark:text-slate-400">{item.detail}</p>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}