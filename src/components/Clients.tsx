import { useState } from "react";
import { useStore, type Client } from "@/lib/store";
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
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Plus, Building2, Globe, MapPin, Target, Calendar } from "lucide-react";

export function Clients() {
  const { clients, addClient } = useStore();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    businessName: "",
    website: "",
    industry: "",
    country: "",
    city: "",
    primaryKeywords: "",
    secondaryKeywords: "",
    competitors: "",
    monthlyGoals: "",
  });

  const handleSubmit = () => {
    if (!form.businessName || !form.website) return;
    addClient({
      businessName: form.businessName,
      website: form.website,
      industry: form.industry,
      country: form.country,
      city: form.city,
      primaryKeywords: form.primaryKeywords.split(",").map((k) => k.trim()).filter(Boolean),
      secondaryKeywords: form.secondaryKeywords.split(",").map((k) => k.trim()).filter(Boolean),
      competitors: form.competitors.split("\n").map((c) => c.trim()).filter(Boolean),
      monthlyGoals: form.monthlyGoals,
    });
    setForm({
      businessName: "",
      website: "",
      industry: "",
      country: "",
      city: "",
      primaryKeywords: "",
      secondaryKeywords: "",
      competitors: "",
      monthlyGoals: "",
    });
    setShowForm(false);
  };

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-serif text-3xl font-bold text-slate-900">Clients</h1>
          <p className="mt-1 text-sm text-slate-500">Manage your SEO client profiles</p>
        </div>
        <Button onClick={() => setShowForm(!showForm)} className="bg-emerald-600 hover:bg-emerald-700">
          <Plus className="mr-2 h-4 w-4" />
          {showForm ? "Cancel" : "Add Client"}
        </Button>
      </div>

      {showForm && (
        <Card className="border-slate-200 shadow-sm">
          <CardHeader>
            <CardTitle className="font-serif text-xl">New Client Profile</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <Label>Business Name</Label>
              <Input value={form.businessName} onChange={(e) => setForm({ ...form, businessName: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Website</Label>
              <Input value={form.website} onChange={(e) => setForm({ ...form, website: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Industry</Label>
              <Input value={form.industry} onChange={(e) => setForm({ ...form, industry: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Country</Label>
              <Input value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>City</Label>
              <Input value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Primary Keywords (comma separated)</Label>
              <Input value={form.primaryKeywords} onChange={(e) => setForm({ ...form, primaryKeywords: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Secondary Keywords (comma separated)</Label>
              <Input value={form.secondaryKeywords} onChange={(e) => setForm({ ...form, secondaryKeywords: e.target.value })} />
            </div>
            <div className="space-y-2">
              <Label>Competitors (one per line)</Label>
              <Textarea rows={2} value={form.competitors} onChange={(e) => setForm({ ...form, competitors: e.target.value })} />
            </div>
            <div className="space-y-2 md:col-span-2">
              <Label>Monthly Goals</Label>
              <Textarea value={form.monthlyGoals} onChange={(e) => setForm({ ...form, monthlyGoals: e.target.value })} />
            </div>
            <div className="md:col-span-2">
              <Button onClick={handleSubmit} className="bg-emerald-600 hover:bg-emerald-700">Save Client</Button>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {clients.map((client) => (
          <ClientCard key={client.id} client={client} />
        ))}
      </div>
    </div>
  );
}

function ClientCard({ client }: { client: Client }) {
  return (
    <Card className="overflow-hidden border-slate-200 shadow-sm transition-shadow hover:shadow-md">
      <CardHeader className="bg-slate-50">
        <div className="flex items-center gap-3">
          <Avatar>
            <AvatarFallback className="bg-emerald-100 text-emerald-700">
              {client.businessName.substring(0, 2).toUpperCase()}
            </AvatarFallback>
          </Avatar>
          <div>
            <CardTitle className="font-serif text-lg">{client.businessName}</CardTitle>
            <CardDescription className="flex items-center gap-1">
              <Globe className="h-3 w-3" /> {client.website}
            </CardDescription>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 p-4">
        <div className="flex items-center gap-2 text-sm text-slate-600">
          <Building2 className="h-4 w-4 text-slate-400" />
          {client.industry}
        </div>
        <div className="flex items-center gap-2 text-sm text-slate-600">
          <MapPin className="h-4 w-4 text-slate-400" />
          {client.city}, {client.country}
        </div>
        <div>
          <p className="mb-1 text-xs font-medium text-slate-500">Primary Keywords</p>
          <div className="flex flex-wrap gap-1">
            {client.primaryKeywords.map((k) => (
              <Badge key={k} variant="secondary" className="bg-emerald-50 text-emerald-700">{k}</Badge>
            ))}
          </div>
        </div>
        <div>
          <p className="mb-1 text-xs font-medium text-slate-500">Monthly Goals</p>
          <p className="text-sm text-slate-600">{client.monthlyGoals}</p>
        </div>
      </CardContent>
    </Card>
  );
}