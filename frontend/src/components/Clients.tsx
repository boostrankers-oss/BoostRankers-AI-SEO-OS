import { useEffect, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { toast } from "sonner";
import {
  Search,
  Plus,
  Globe,
  MapPin,
  TrendingUp,
  Trash2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";

const colorOptions = [
  "bg-gradient-to-br from-emerald-500 to-teal-600",
  "bg-gradient-to-br from-indigo-500 to-purple-600",
  "bg-gradient-to-br from-rose-500 to-orange-600",
  "bg-gradient-to-br from-blue-500 to-cyan-600",
  "bg-gradient-to-br from-amber-500 to-yellow-600",
  "bg-gradient-to-br from-pink-500 to-rose-600",
];

export interface Client {
  id: string;
  company_id: string;
  business_name: string;
  legal_name?: string;
  website?: string;
  industry?: string;
  business_type?: string;
  company_size?: string;
  contact_name?: string;
  email?: string;
  phone?: string;
  city?: string;
  country?: string;
  primary_keyword?: string;
  target_location?: string;
  overall_score: number;
  technical_score: number;
  content_score: number;
  eeat_score: number;
  local_seo_score: number;
  backlinks_score: number;
  schema_score: number;
  ai_search_score: number;
  total_keywords: number;
  total_backlinks: number;
  total_audits: number;
  critical_issues: number;
  status: string;
  priority: string;
  is_active: boolean;
  is_archived: boolean;
  created_at: string;
  updated_at: string;
}

const emptyClient = {
  business_name: "",
  website: "",
  industry: "",
  city: "",
  country: "",
};

export function Clients() {
  const [loading, setLoading] = useState(true);
  const [clients, setClients] = useState<Client[]>([]);
  const [search, setSearch] = useState("");
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [newClient, setNewClient] = useState(emptyClient);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    const fetchClients = async () => {
      try {
        const data = await api.get<Client[]>("/api/clients");
        setClients(data);
      } catch (error) {
        console.error("Failed to fetch clients:", error);
        toast.error("Could not load clients");
      } finally {
        setLoading(false);
      }
    };
    fetchClients();
  }, []);

  const filtered = clients.filter(
    (c) =>
      c.business_name?.toLowerCase().includes(search.toLowerCase()) ||
      c.website?.toLowerCase().includes(search.toLowerCase()) ||
      c.industry?.toLowerCase().includes(search.toLowerCase())
  );

  const getScoreColor = (score: number) => {
    if (score >= 80) return "text-emerald-600 dark:text-emerald-400";
    if (score >= 60) return "text-amber-600 dark:text-amber-400";
    return "text-rose-600 dark:text-rose-400";
  };

  const handleAddClient = async () => {
    if (!newClient.business_name || !newClient.website || !newClient.industry) {
      toast.error("Please fill in all required fields");
      return;
    }

    setIsSubmitting(true);
    try {
      const payload = {
        business_name: newClient.business_name,
        website: newClient.website,
        industry: newClient.industry,
        city: newClient.city || undefined,
        country: newClient.country || undefined,
      };
      const data = await api.post<Client>("/api/clients", payload);
      setClients([data, ...clients]);
      setNewClient(emptyClient);
      setIsAddOpen(false);
      toast.success("Client added successfully");
    } catch (error: any) {
      console.error("Failed to add client:", error);
      let message = "Could not add client. Please try again.";
      if (error?.data?.detail) {
        message = error.data.detail;
      } else if (error?.message) {
        message = error.message;
      }
      toast.error(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.delete(`/api/clients/${id}`);
      setClients(clients.filter((c) => c.id !== id));
      setDeleteId(null);
      toast.success("Client deleted successfully");
    } catch (error: any) {
      console.error("Failed to delete client:", error);
      toast.error("Could not delete client");
    }
  };

  if (loading) {
    return (
      <div className="p-8 flex justify-center items-center">
        <p>Loading clients...</p>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-6">
      <header className="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h2 className="font-serif text-3xl font-bold tracking-tight">Clients</h2>
          <p className="text-slate-500 dark:text-slate-400 mt-1">
            Manage your agency's client portfolio.
          </p>
        </div>
        <Button
          onClick={() => setIsAddOpen(true)}
          className="bg-emerald-600 hover:bg-emerald-700 text-white shadow-md shadow-emerald-600/20"
        >
          <Plus className="size-4" />
          Add Client
        </Button>
      </header>

      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-slate-400" />
        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search clients, websites, or industries..."
          className="pl-10"
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map((client) => {
          const initials = client.business_name
            .split(" ")
            .map((n) => n[0])
            .join("")
            .substring(0, 2)
            .toUpperCase();
          const randomColor = colorOptions[Math.floor(Math.random() * colorOptions.length)];
          const location = [client.city, client.country].filter(Boolean).join(", ") || "N/A";

          return (
            <Card
              key={client.id}
              className="border-slate-200 dark:border-slate-800 shadow-sm hover:shadow-md transition-all group"
            >
              <CardContent className="p-6">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <Avatar className="size-12 rounded-xl">
                      <AvatarFallback className={cn("rounded-xl bg-gradient-to-br text-white font-bold", randomColor)}>
                        {initials}
                      </AvatarFallback>
                    </Avatar>
                    <div>
                      <h3 className="font-semibold text-base group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors">
                        {client.business_name}
                      </h3>
                      <p className="text-xs text-slate-500 dark:text-slate-400">
                        {client.industry || "N/A"}
                      </p>
                    </div>
                  </div>
                  <button
                    onClick={() => setDeleteId(client.id)}
                    className="p-1.5 rounded-md text-slate-400 hover:bg-rose-50 hover:text-rose-500 dark:hover:bg-rose-500/10 transition-colors"
                  >
                    <Trash2 className="size-4" />
                  </button>
                </div>

                <div className="mt-4 space-y-2 text-sm">
                  <div className="flex items-center gap-2 text-slate-600 dark:text-slate-300">
                    <Globe className="size-3.5 text-slate-400" />
                    {client.website || "No website"}
                  </div>
                  <div className="flex items-center gap-2 text-slate-600 dark:text-slate-300">
                    <MapPin className="size-3.5 text-slate-400" />
                    {location}
                  </div>
                </div>

                <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between">
                  <div>
                    <p className="text-xs text-slate-500 dark:text-slate-400">SEO Score</p>
                    <p className={cn("font-serif text-xl font-bold", getScoreColor(client.overall_score))}>
                      {client.overall_score}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-slate-500 dark:text-slate-400">Audits</p>
                    <p className="font-serif text-xl font-bold flex items-center gap-1">
                      <TrendingUp className="size-4 text-emerald-500" />
                      {client.total_audits}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {filtered.length === 0 && (
        <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
          <CardContent className="p-12 text-center">
            <p className="text-slate-500 dark:text-slate-400">No clients found matching your search.</p>
          </CardContent>
        </Card>
      )}

      <Dialog open={isAddOpen} onOpenChange={setIsAddOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add New Client</DialogTitle>
            <DialogDescription>Register a new client to your agency portfolio.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="client-name">Business Name *</Label>
              <Input
                id="client-name"
                value={newClient.business_name}
                onChange={(e) =>
                  setNewClient({ ...newClient, business_name: e.target.value })
                }
                placeholder="Acme Corp"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="client-website">Website *</Label>
              <Input
                id="client-website"
                value={newClient.website}
                onChange={(e) =>
                  setNewClient({ ...newClient, website: e.target.value })
                }
                placeholder="https://acme.com"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="client-industry">Industry *</Label>
              <Input
                id="client-industry"
                value={newClient.industry}
                onChange={(e) =>
                  setNewClient({ ...newClient, industry: e.target.value })
                }
                placeholder="SaaS"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="client-city">City</Label>
              <Input
                id="client-city"
                value={newClient.city}
                onChange={(e) =>
                  setNewClient({ ...newClient, city: e.target.value })
                }
                placeholder="San Francisco"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="client-country">Country</Label>
              <Input
                id="client-country"
                value={newClient.country}
                onChange={(e) =>
                  setNewClient({ ...newClient, country: e.target.value })
                }
                placeholder="USA"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsAddOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleAddClient}
              disabled={isSubmitting}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              {isSubmitting ? "Adding..." : "Add Client"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteId !== null} onOpenChange={(open) => !open && setDeleteId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Client?</DialogTitle>
            <DialogDescription>
              This action cannot be undone. The client and all associated data will be permanently removed.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteId(null)}>
              Cancel
            </Button>
            <Button
              onClick={() => deleteId && handleDelete(deleteId)}
              className="bg-rose-600 hover:bg-rose-700 text-white"
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}