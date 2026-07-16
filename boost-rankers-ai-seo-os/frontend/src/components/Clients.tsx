import { useState } from "react";
import { useStore } from "@/lib/store";
import {
  Card, CardContent, CardHeader, CardTitle, CardDescription,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Plus, Trash2, Globe, MapPin } from "lucide-react";

export function Clients() {
  const { clients, addClient, deleteClient, loading } = useStore();
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    business_name: "",
    website: "",
    industry: "",
    country: "",
    city: "",
    primary_keywords: "",
    secondary_keywords: "",
    competitors: "",
    monthly_goals: "",
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await addClient(formData);
    setFormData({
      business_name: "", website: "", industry: "", country: "", city: "",
      primary_keywords: "", secondary_keywords: "", competitors: "", monthly_goals: ""
    });
    setShowForm(false);
  };

  if (loading) return <div className="p-6">Loading...</div>;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-serif text-3xl font-bold text-slate-900">Clients</h1>
          <p className="mt-1 text-sm text-slate-500">Manage your SEO client profiles.</p>
        </div>
        <Button onClick={() => setShowForm(!showForm)} className="bg-emerald-600 hover:bg-emerald-700">
          <Plus className="mr-2 h-4 w-4" />
          Add Client
        </Button>
      </div>

      {showForm && (
        <Card className="border-slate-200 shadow-sm">
          <CardHeader>
            <CardTitle className="font-serif text-xl">New Client Profile</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="business_name">Business Name</Label>
                  <Input id="business_name" name="business_name" value={formData.business_name} onChange={handleChange} required />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="website">Website</Label>
                  <Input id="website" name="website" placeholder="https://" value={formData.website} onChange={handleChange} required />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="industry">Industry</Label>
                  <Input id="industry" name="industry" value={formData.industry} onChange={handleChange} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="country">Country</Label>
                  <Input id="country" name="country" value={formData.country} onChange={handleChange} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="city">City</Label>
                  <Input id="city" name="city" value={formData.city} onChange={handleChange} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="primary_keywords">Primary Keywords (comma separated)</Label>
                  <Input id="primary_keywords" name="primary_keywords" value={formData.primary_keywords} onChange={handleChange} />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="competitors">Competitors (comma separated URLs)</Label>
                <Textarea id="competitors" name="competitors" value={formData.competitors} onChange={handleChange} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="monthly_goals">Monthly Goals</Label>
                <Textarea id="monthly_goals" name="monthly_goals" value={formData.monthly_goals} onChange={handleChange} />
              </div>
              <Button type="submit" className="bg-emerald-600 hover:bg-emerald-700">Save Client</Button>
            </form>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {clients.map((client) => (
          <Card key={client.id} className="border-slate-200 shadow-sm">
            <CardContent className="p-6">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-serif text-lg font-bold text-slate-900">{client.business_name}</h3>
                  <a href={client.website} target="_blank" rel="noopener noreferrer" className="mt-1 flex items-center gap-1 text-sm text-emerald-600 hover:underline">
                    <Globe className="h-3 w-3" /> {client.website}
                  </a>
                </div>
                <button onClick={() => deleteClient(client.id)} className="text-slate-400 hover:text-rose-500">
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
              <div className="mt-4 space-y-2 text-sm text-slate-600">
                {client.industry && <p><span className="font-medium text-slate-800">Industry:</span> {client.industry}</p>}
                {client.city && <p className="flex items-center gap-1"><MapPin className="h-3 w-3" /> {client.city}, {client.country}</p>}
                {client.primary_keywords && (
                  <div className="flex flex-wrap gap-1 pt-2">
                    {client.primary_keywords.split(",").map((kw, i) => (
                      <Badge key={i} variant="secondary" className="bg-slate-100 text-slate-700">{kw.trim()}</Badge>
                    ))}
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
        {clients.length === 0 && !showForm && (
          <div className="col-span-full text-center py-12 text-slate-500">
            No clients yet. Click "Add Client" to create one.
          </div>
        )}
      </div>
    </div>
  );
}